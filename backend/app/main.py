from typing import Literal
import asyncio
import logging
import os

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from . import graph, extract, mentor, chat, memory, jobs, transcript, journey, learn as learning, auth, settings, llm, backup
from .teach import api as teach_api

# Identity comes from the session cookie (auth.py). `Me` replaces every person_id default; a route
# with {person_id} in its path uses `Own`, which refuses any other id.
Me = Depends(auth.current_person)
Own = Depends(auth.own_person)

log = logging.getLogger("uvicorn.error")
PENDING_TTL_DAYS = 7
STALE_MINUTES = 30          # sessie stil -> consolideren
CONSOLIDATE_EVERY = 600     # seconden tussen twee dream-rondes

app = FastAPI(title="Mentor")
# Production is same-origin (nginx serves the frontend and /api), so it needs no CORS at all. The
# list is for local dev only. It was "*": with that, a sandboxed lesson frame (opaque origin) could
# have READ any /api response if its CSP ever failed. Now the browser refuses that by itself.
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.middleware("http")(auth.middleware)
app.include_router(auth.router)
app.include_router(teach_api.public)
app.include_router(teach_api.router)


async def _consolidation_loop():
    """Dream-fase: bij startup en daarna elke 10 minuten stille sessies
    destilleren naar laag 2 en 3."""
    while True:
        try:
            done = await asyncio.to_thread(memory.consolidate_stale, STALE_MINUTES)
            if done:
                log.info("Geconsolideerd: %d sessie(s)", done)
        except Exception as e:
            log.warning("Consolidatieronde mislukt: %s", e)
        await asyncio.sleep(CONSOLIDATE_EVERY)


@app.on_event("startup")
async def startup():
    graph.init_schema()
    settings.load()                       # models + keys from the setup screen (or .env), session secret
    if settings.configured():
        try:
            graph.ensure_vector_index(llm.EMBED_DIM)
        except ValueError as exc:
            log.warning("vector index: %s", exc)
    graph.migrate_memory()
    teach_api.startup()
    asyncio.create_task(backup.nightly_loop())
    # The retained initial dataset includes pending drafts; cleanup is explicit.
    asyncio.create_task(_consolidation_loop())


class IngestText(BaseModel):
    text: str
    title: str
    source_type: str = "text"
    url: str | None = None
    job_id: str | None = None


class IngestYoutube(BaseModel):
    url: str
    languages: list[str] = ["en", "nl"]
    ui_language: Literal["en", "nl"] = "en"
    job_id: str | None = None


class IngestTopic(BaseModel):
    topic: str
    depth: int = 3


class Learn(BaseModel):
    concept: str
    context: str = ""
    level: int = 3
    person_id: str | None = None      # ignored: the session decides
    source_id: str | None = None
    # Uit de analyse: citaten met tijdcode voor deze kandidaat, en de relaties
    # tussen alle kandidaten van dezelfde bron (alleen toegepast tussen
    # kandidaten die daadwerkelijk geleerd zijn).
    mentions: list[dict] | None = None
    candidate_relations: list[dict] | None = None


class CommitCandidates(BaseModel):
    source_id: str
    selected: list[dict] = []
    link_existing: list = []          # namen of {name, mentions, context}
    relations: list[dict] = []
    person_id: str | None = None


class Chat(BaseModel):
    concept: str
    message: str
    person_id: str | None = None
    level: int | None = None


class ProfilePatch(BaseModel):
    teaching_preferences: list[str] | None = None
    ambient_motion: bool | None = None
    works_well: list[str] | None = None
    works_poorly: list[str] | None = None
    preferences: list[str] | None = None
    notes: str | None = None
    ui_language: str | None = None      # "nl" | "en": taal van UI, uitleg en geheugen


class StatePatch(BaseModel):
    covered: list[str] | None = None
    struggles: list[str] | None = None
    misconceptions: list[str] | None = None
    summary: str | None = None


class Ask(BaseModel):
    question: str
    concept: str | None = None
    level: int = 5


# ---- Suggesties: extractie levert kandidaten, slaat niets op ----

@app.post("/ingest/text")
def ingest_text(body: IngestText, me: str = Me):
    return extract.suggest(body.text, body.source_type, body.title, body.url, body.job_id, language=graph.ui_language(me))


@app.post("/ingest/raw")
def ingest_raw(
    text: str = Body(..., media_type="text/plain"),
    title: str = Query(..., description="Titel van de bron"),
    source_type: str = Query("text"),
    url: str | None = Query(None),
    job_id: str | None = Query(None, description="Door de client gekozen id om voortgang te pollen"),
    me: str = Me,
):
    """Rauwe tekst als request body: plakken zonder JSON-escaping.
    Timestamps worden bewaard als tijdcodes; hoofdstuktitels worden chunk-grenzen."""
    return extract.suggest(text, source_type, title, url, job_id, language=graph.ui_language(me))


@app.post("/ingest/youtube")
def ingest_youtube(body: IngestYoutube, me: str = Me):
    from youtube_transcript_api import YouTubeTranscriptApi
    try:
        vid = transcript.youtube_id(body.url)
    except ValueError as e:
        raise HTTPException(422, str(e))
    jobs.update(body.job_id, "fetch", 0, 0, "Transcript ophalen…")
    try:
        fetched = YouTubeTranscriptApi().fetch(vid, languages=body.languages)
    except Exception as e:
        from . import video
        try:
            result = video.analyze(f"https://www.youtube.com/watch?v={vid}", body.ui_language, body.job_id)
            staged = extract.stage_result(result, "youtube", result["title"], f"https://www.youtube.com/watch?v={vid}")
            jobs.update(body.job_id, "done", 1, 1, "Video analysis ready")
            return staged
        except Exception:
            log.warning("Direct YouTube video analysis unavailable")
            message = ("Captions and direct video analysis are unavailable. " if body.ui_language == "en" else "Ondertiteling en directe videoanalyse zijn niet beschikbaar. ") + transcript.fetch_error(e, body.ui_language)
            jobs.update(body.job_id, "error", 0, 0, message)
            raise HTTPException(503, message)
    segments = transcript.from_youtube(fetched)
    meta = transcript.youtube_meta(vid)
    title = meta["title"] or f"YouTube {vid}"
    return extract.suggest_segments(segments, meta["chapters"], True, "youtube", title,
                                    body.url, body.job_id, meta["duration_sec"], language=body.ui_language)


@app.get("/ingest/status/{job_id}")
def ingest_status(job_id: str):
    """Voortgang van een lopende analyse: {phase, done, total, message}."""
    st = jobs.get(job_id)
    if st is None:
        raise HTTPException(404, "Onbekende job")
    return st


@app.post("/ingest/topic")
def ingest_topic(body: IngestTopic, me: str = Me):
    """Generates source material about a topic and extracts candidates from it."""
    if body.depth not in mentor.LEVELS:
        raise HTTPException(400, "depth 1..5")
    language = graph.ui_language(me)
    text = extract.generate(body.topic, body.depth, language)
    return {**extract.suggest(text, "generated", body.topic, language=language), "text": text}


# ---- Leren: hier wordt pas naar de graph geschreven ----

@app.post("/learn")
def learn(body: Learn, me: str = Me):
    if body.level not in mentor.LEVELS:
        raise HTTPException(400, "level 1..5")
    try:
        return learning.learn(body.concept, body.context, body.level,
                              me, body.source_id,
                              body.mentions, body.candidate_relations)
    except KeyError:
        raise HTTPException(404, "Onbekende source_id; draai de ingest opnieuw")


@app.post("/candidates/commit")
def commit_candidates(body: CommitCandidates, me: str = Me):
    """Review-paneel: kandidaten opnemen als 'queued', bestaande koppelen,
    relaties leggen. Alleen entity resolution kan een LLM-call doen."""
    try:
        return learning.commit_candidates(body.source_id, body.selected, body.link_existing,
                                          body.relations, me)
    except KeyError:
        raise HTTPException(404, "Onbekende source_id; draai de ingest opnieuw")


@app.post("/concept/{name}/learned")
def mark_learned(name: str, person_id: str = Me):
    result = graph.mark_learned(name, person_id)
    if not result:
        raise HTTPException(404, "Onbekend concept")
    return result


# ---- Mentor-chat ----

@app.post("/chat")
def post_chat(body: Chat, me: str = Me):
    if body.level is not None and body.level not in mentor.LEVELS:
        raise HTTPException(400, "level 1..5")
    return chat.send(body.concept, body.message, me, body.level)


@app.get("/chat/{concept}")
def get_chat(concept: str, person_id: str = Me):
    h = chat.history(concept, person_id)
    if h is None:
        raise HTTPException(404, "Onbekend concept")
    return h


@app.post("/chat/{concept}/new")
def new_chat(concept: str, person_id: str = Me, level: int | None = Query(None)):
    """Forceert een nieuwe sessie; de oude wordt meteen geconsolideerd."""
    c = graph.find_concept(concept)
    if c:
        old = graph.active_session(person_id, c["id"])
        if old:
            try:
                memory.consolidate_session(old["id"])
            except memory.ConsolidationError as exc:
                raise HTTPException(503, str(exc))
    opened = chat.open_session(concept, person_id, level, force_new=True)
    return {"concept": opened["concept"]["name"], "session_id": opened["session_id"],
            "level": opened["level"], "messages": []}


@app.post("/chat/{concept}/end")
def end_chat(concept: str, person_id: str = Me):
    c = graph.find_concept(concept)
    if not c:
        raise HTTPException(404, "Onbekend concept")
    session = graph.active_session(person_id, c["id"])
    if not session:
        return {"consolidated": False, "reden": "geen actieve sessie"}
    try:
        done = memory.consolidate_session(session["id"])
    except memory.ConsolidationError as exc:
        raise HTTPException(503, str(exc))
    return {"consolidated": done, "session_id": session["id"],
            "state": graph.understands_state(person_id, c["id"])}


# ---- Geheugen: inspecteren, corrigeren, herbouwen ----

@app.get("/memory/{person_id}")
def get_memory(person_id: str = Own):
    return {"person_id": person_id,
            **graph.display_preferences(person_id),
            "ui_language": graph.ui_language(person_id),
            "learning_profile": graph.learning_profile(person_id),
            "concepts": graph.all_understands(person_id)}


@app.patch("/memory/{person_id}/profile")
def patch_profile(body: ProfilePatch, person_id: str = Own):
    patch = body.model_dump(exclude_unset=True)
    motion = patch.pop("ambient_motion", None)
    if motion is not None:
        graph.set_ambient_motion(person_id, motion)
    lang = patch.pop("ui_language", None)
    if lang is not None:
        try:
            graph.set_ui_language(person_id, lang)
        except ValueError:
            raise HTTPException(400, "ui_language: nl of en")
    try:
        profile = memory.patch_profile(person_id, patch) if patch else graph.learning_profile(person_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {**profile, "ui_language": graph.ui_language(person_id), **graph.display_preferences(person_id)}


@app.patch("/memory/{person_id}/concept/{name}")
def patch_concept_memory(name: str, body: StatePatch, person_id: str = Own):
    state = memory.patch_understands(person_id, name, body.model_dump(exclude_unset=True))
    if state is None:
        raise HTTPException(404, "Geen begripstoestand voor dit concept")
    return state


@app.post("/memory/rebuild/{person_id}")
def rebuild_memory(person_id: str = Own):
    try:
        return memory.rebuild(person_id)
    except memory.ConsolidationError as exc:
        raise HTTPException(409, str(exc))


@app.get("/health")
def health():
    """Public, no personal data: for the deploy asserts, uptime checks and the setup screen."""
    from .teach import flags
    return {"ok": True, "setup_needed": auth.setup_needed(), "configured": settings.configured(), "teach_mode": flags.mode()}


# ---- Backups (owner only). Online: the app keeps running. ----
def _owner(request: Request) -> str:
    person = auth.person_public(auth.current_person(request))
    if not person or not person["is_admin"]:
        raise HTTPException(403, "Only the owner can do this")
    return person["id"]


@app.get("/admin/backups")
def list_backups(owner: str = Depends(_owner)):
    return {"available": backup.available(), "keep": backup.KEEP, "nightly_hour_utc": backup.NIGHTLY_HOUR_UTC, "backups": backup.listing()}


@app.post("/admin/backups")
async def create_backup(owner: str = Depends(_owner)):
    if not backup.available():
        raise HTTPException(503, "The backup folder is not writable. Mount ./backups into the API container.")
    async with backup._lock:
        try:
            return await asyncio.to_thread(backup.create)
        except Exception as exc:
            log.warning("backup failed: %s", exc)
            raise HTTPException(500, f"Backup failed: {exc}")


@app.post("/admin/backups/{stamp}/verify")
def verify_backup(stamp: str, owner: str = Depends(_owner)):
    if not stamp.replace("T", "").replace("Z", "").isdigit():
        raise HTTPException(400, "stamp")
    try:
        return backup.verify(stamp)
    except FileNotFoundError as exc:
        raise HTTPException(404, f"No backup {exc}")


@app.get("/levels")
def get_levels():
    """Niveau-omschrijvingen, zodat de frontend dezelfde labels toont."""
    return mentor.LEVELS


@app.get("/graph")
def get_graph(limit: int = 500):
    return graph.get_graph(limit)


@app.get("/concept/{name}")
def get_concept(name: str):
    c = graph.concept_context(name)
    if not c:
        raise HTTPException(404, "Onbekend concept")
    return c


@app.post("/ask")
def ask(body: Ask, me: str = Me):
    if body.level not in mentor.LEVELS:
        raise HTTPException(400, "level 1..5")
    return {"answer": mentor.ask(body.question, body.concept, body.level, graph.ui_language(me))}


class SuggestionAccept(BaseModel):
    person_id: str | None = None
    action: Literal["explore", "save"]


class SuggestionDismiss(BaseModel):
    person_id: str | None = None


def _suggestion_action(suggestion_id, person_id, action):
    try:
        return graph.act_on_suggestion(suggestion_id, person_id, action)
    except KeyError:
        raise HTTPException(404, "Suggestion not found")
    except ValueError as error:
        raise HTTPException(409, str(error))


@app.post("/suggestions/{suggestion_id}/accept")
def accept_suggestion(suggestion_id: str, body: SuggestionAccept, me: str = Me):
    return _suggestion_action(suggestion_id, me, body.action)


@app.post("/suggestions/{suggestion_id}/dismiss")
def dismiss_suggestion(suggestion_id: str, body: SuggestionDismiss, me: str = Me):
    return _suggestion_action(suggestion_id, me, "dismiss")


class ObservationPatch(BaseModel):
    state: str

@app.patch("/memory/{person_id}/concept/{name}/observations/{observation_id}")
def correct_observation(name: str, observation_id: str, body: ObservationPatch, person_id: str = Own):
    try:
        result=memory.correct_observation(person_id,name,observation_id,body.state)
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    if result is None:raise HTTPException(404,"Observation not found for this learner and topic")
    return result


class LearningPositionPatch(BaseModel):
    intent: str | None = None
    assessment: str | None = None

@app.patch("/memory/{person_id}/concept/{name}/position")
def set_learning_position(name: str, body: LearningPositionPatch, person_id: str = Own):
    try:
        result=memory.set_learning_position(person_id,name,body.intent,body.assessment)
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    if result is None:raise HTTPException(404,"Concept not found")
    return result


# Phase 3: saved learning direction and learner-confirmed examples.
class GoalCreate(BaseModel):
    title: str
    concept_ids: list[str] = []
    source_id: str | None = None

class GoalPatch(BaseModel):
    status: str | None = None
    concept_id: str | None = None
    done: bool | None = None

class ExampleCreate(BaseModel):
    session_id: str
    seq: int

class ExamplePatch(BaseModel):
    text: str


def journey_action(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@app.get("/journey/{person_id}")
def get_journey(person_id: str = Own):
    return journey.overview(person_id)

@app.post("/journey/{person_id}/goals")
def create_learning_goal(body: GoalCreate, person_id: str = Own):
    return journey_action(journey.create_goal,person_id,body.title,body.concept_ids,body.source_id)

@app.patch("/journey/{person_id}/goals/{goal_id}")
def update_learning_goal(goal_id: str, body: GoalPatch, person_id: str = Own):
    return journey_action(journey.patch_goal,person_id,goal_id,**body.model_dump(exclude_unset=True))

@app.get("/journey/{person_id}/examples")
def get_helpful_examples(person_id: str = Own, concept_id: str | None = None):
    return [r['example'] for r in journey.examples(person_id,concept_id)]

@app.post("/journey/{person_id}/examples")
def save_helpful_example(body: ExampleCreate, person_id: str = Own):
    return journey_action(journey.save_example,person_id,body.session_id,body.seq)

@app.patch("/journey/{person_id}/examples/{example_id}")
def edit_helpful_example(example_id: str, body: ExamplePatch, person_id: str = Own):
    return journey_action(journey.change_example,person_id,example_id,text=body.text)

@app.delete("/journey/{person_id}/examples/{example_id}")
def delete_helpful_example(example_id: str, person_id: str = Own):
    return journey_action(journey.change_example,person_id,example_id,delete=True)


class TranslationRequest(BaseModel):
    language: Literal['en', 'nl']
    texts: list[str]


@app.post('/translations')
def translate_content(body: TranslationRequest):
    from . import translations
    if not body.texts or len(body.texts) > 30 or sum(map(len, body.texts)) > 24000 or any(not t.strip() for t in body.texts):
        raise HTTPException(422, 'Provide 1–30 nonempty texts, at most 24000 characters in total.')
    try:
        return {'texts': translations.translate(body.texts, body.language)}
    except Exception:
        log.warning('Display translation failed')
        raise HTTPException(503, 'Translation unavailable. Original content is preserved; please retry.')


@app.post('/voice/transcribe')
async def transcribe_voice(request: Request, language: Literal['en', 'nl'] = 'en'):
    from . import voice
    if request.headers.get('content-type', '').split(';')[0] != 'audio/wav':
        raise HTTPException(415, 'Expected WAV audio')
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > voice.MAX_BYTES:
            raise HTTPException(413, 'Recording too large')
    try:
        voice.validate_audio(bytes(data))
    except ValueError as e:
        raise HTTPException(422, str(e))
    try:
        return {'text': await voice.transcribe(bytes(data), language)}
    except Exception:
        log.warning('Voice transcription failed')
        raise HTTPException(503, 'Transcription unavailable. Please retry.')


class CurriculumRequest(BaseModel):
    nodes: list[dict]
    links: list[dict]
    language: Literal['en', 'nl'] = 'en'


@app.post('/curriculum')
async def curriculum_proposal(body: CurriculumRequest):
    from . import curriculum
    if len(body.nodes)>1500 or len(body.links)>10000:
        raise HTTPException(422, 'Graph is too large for this curriculum view')
    nodes=[{'id':str(n.get('id',''))[:200],'name':str(n.get('name',''))[:300], 'definition':str(n.get('definition',''))[:800], 'domain':str(n.get('domain',''))[:200]} for n in body.nodes]
    ids={n['id'] for n in nodes}
    links=[{'source':str(e.get('source','')),'target':str(e.get('target','')),'type':str(e.get('type',''))} for e in body.links if e.get('source') in ids and e.get('target') in ids]
    if not nodes:return {'groups':[],'conflicts':[],'coverage':0}
    try:return await curriculum.propose(nodes,links,body.language)
    except Exception:
        raise HTTPException(503,'Could not organize the learning roadmap. Please retry.')
