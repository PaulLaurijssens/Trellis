"""HTTP routes of the /teach integration. Convention of this API: person_id in the path.

There is no login in this deployment (access control is the tailnet), so a route never trusts an ID by
itself: every lookup also matches person_id on the node. With TEACH_MODE=off every route here is 404."""
import asyncio
import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import auth, chat, graph
from . import artifacts, flags, lessons, model, objectives, orchestrator, skill

log = logging.getLogger("uvicorn.error")
public = APIRouter(prefix="/teach")


def _enabled(person_id: str, request: Request):
    auth.own_person(person_id, request)
    if not flags.enabled_for(person_id):
        raise HTTPException(404, "Not found")
    if not graph.run("MATCH (p:Person {id:$pid}) RETURN p.id AS id", pid=person_id):
        raise HTTPException(404, "Unknown learner")


router = APIRouter(prefix="/teach/{person_id}", dependencies=[Depends(_enabled)])


def guarded(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except KeyError as exc:
        raise HTTPException(404, str(exc).strip("'"))
    except ValueError as exc:
        if str(exc) == "stale":
            raise HTTPException(409, "stale")
        raise HTTPException(400, str(exc))


@public.get("/flags/{person_id}")
def get_flags(person_id: str, request: Request):
    auth.own_person(person_id, request)
    return {**flags.public(person_id), **skill.provenance()}


# ---- Topics and objectives --------------------------------------------------

class TopicCreate(BaseModel):
    title: str
    concept_ids: list[str]
    language: Literal["en", "nl"] = "en"
    origin: Literal["curriculum_group", "learner"] = "curriculum_group"
    plan_key: str | None = None


class TopicLookup(BaseModel):
    group_ids: list[str] = []


class Onboarding(BaseModel):
    intent: str | None = None
    familiarity: str | None = None
    approach: str | None = None
    time_budget_min: int | None = None
    free_text: str | None = None


class ObjectiveSave(BaseModel):
    objective: dict
    expected_revision: int | None = None
    answers: Onboarding | None = None
    serves_goal_id: str | None = None


@router.post("/topics")
def create_topic(person_id: str, body: TopicCreate):
    return guarded(objectives.create_topic, person_id, body.title, body.concept_ids, body.language, body.origin, body.plan_key)


@router.post("/concepts/{concept_id}/context")
def concept_context(person_id: str, concept_id: str, body: TopicLookup):
    """Everything the lesson entry needs for one concept: its topic(s) with objective, an open run to
    continue, the lessons made so far, references and pending recommendations."""
    topics = objectives.topics_for_concept(person_id, concept_id, body.group_ids[:400])
    made = lessons.lessons_for(person_id, concept_id=concept_id)
    topic_id = topics[0]["id"] if topics else None
    job = graph.run('''MATCH (j:LessonJob {person_id:$pid}) WHERE j.stage IN $active
        RETURN j.id AS id, j.stage AS stage, j.request_json AS request LIMIT 1''', pid=person_id, active=lessons.ACTIVE_JOB_STAGES)
    return {"topics": topics, "lessons": made, "resume": next((l for l in made if l["open_run_id"]), None),
            "references": lessons.references_for(person_id, topic_id=topic_id, concept_id=concept_id),
            "recommendations": lessons.recommendations(person_id, topic_id), "defaults": objectives.defaults(person_id),
            "active_job": ({"id": job[0]["id"], "stage": job[0]["stage"], "concept_id": json.loads(job[0]["request"]).get("concept_id")} if job else None)}


@router.get("/topics/{topic_id}/objective")
def get_objective(person_id: str, topic_id: str):
    found = objectives.overview(person_id, topic_id)
    if not found:
        raise HTTPException(404, "Topic not found")
    return found


@router.post("/topics/{topic_id}/objective/preview")
def preview_objective(person_id: str, topic_id: str, body: Onboarding):
    return guarded(objectives.draft, person_id, topic_id, body.model_dump())


@router.put("/topics/{topic_id}/objective")
def save_objective(person_id: str, topic_id: str, body: ObjectiveSave):
    return guarded(objectives.save, person_id, topic_id, body.objective, body.expected_revision,
                   body.answers.model_dump() if body.answers else None, "learner", body.serves_goal_id)


@router.delete("/topics/{topic_id}/objective/proposal")
def dismiss_objective_proposal(person_id: str, topic_id: str):
    return {"dismissed": objectives.dismiss_proposal(person_id, topic_id)}


# ---- Lesson jobs ------------------------------------------------------------

class JobCreate(BaseModel):
    topic_id: str
    concept_id: str
    objective_id: str | None = None
    language: Literal["en", "nl"] = "en"
    time_budget_min: Literal[5, 10, 20] = 10
    intent: str | None = None
    note: str | None = Field(None, max_length=400)
    idempotency_key: str = Field(min_length=8, max_length=80)


def _public_job(job):
    out = {k: job.get(k) for k in ("id", "stage", "error", "detail", "repairs", "lesson_id", "lesson_version_id", "created_at", "updated_at")}
    out["concept_id"] = job["request"].get("concept_id")
    return out


@router.post("/lesson-jobs")
async def create_lesson_job(person_id: str, body: JobCreate):
    if not objectives.get_topic(body.topic_id):
        raise HTTPException(404, "Topic not found")
    if body.intent is not None and body.intent not in model.INTENTS:
        raise HTTPException(400, "intent")
    job, created = guarded(lessons.create_job, person_id, body.model_dump(exclude={"idempotency_key"}), body.idempotency_key)
    if created:
        asyncio.create_task(asyncio.to_thread(orchestrator.run_job, person_id, job["id"]))
    return _public_job(job)


@router.get("/lesson-jobs/summary")
def lesson_usage_summary(person_id: str, days: int = 30):
    """Token use of the last `days` days plus a rough cost estimate from the price table in settings."""
    summary = lessons.usage_summary(person_id, max(1, min(days, 365)))
    price_in, price_out = orchestrator.prices()
    summary["model"] = orchestrator.AUTHOR_MODEL
    summary["price_per_mtok"] = {"input": price_in, "output": price_out}
    summary["estimated_usd"] = round(orchestrator.estimate_usd(summary["prompt"], summary["cached"], summary["completion"]), 2)
    summary["cost_limit"] = orchestrator.cost_limit()
    return summary


@router.get("/lesson-jobs/{job_id}")
def get_lesson_job(person_id: str, job_id: str, trace: bool = False):
    job = lessons.get_job(person_id, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {**_public_job(job), **({"trace": job["trace"], "usage": job["usage"]} if trace else {})}


@router.post("/lesson-jobs/{job_id}/cancel")
def cancel_lesson_job(person_id: str, job_id: str):
    job = lessons.cancel_job(person_id, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _public_job(job)


# ---- Versions and the artifact ---------------------------------------------

@router.get("/lessons/{lesson_id}/versions/{version_id}")
def get_version(person_id: str, lesson_id: str, version_id: str):
    version = lessons.get_version(person_id, version_id)
    if not version or version["lesson_id"] != lesson_id:
        raise HTTPException(404, "Lesson not found")
    return {k: version[k] for k in ("id", "lesson_id", "manifest", "sources", "language", "outcome", "created_at",
                                    "skill_upstream_commit", "skill_adaptation_revision", "content_hash")}


@router.get("/lessons/{lesson_id}/versions/{version_id}/artifact")
def get_artifact(person_id: str, lesson_id: str, version_id: str):
    """The generated page. It is served with `sandbox` in the CSP, so even opened directly in a tab it
    has an opaque origin: no cookies, no storage, no service worker, no readable /api response."""
    version = lessons.get_version(person_id, version_id)
    if not version or version["lesson_id"] != lesson_id or version["status"] != "published":
        raise HTTPException(404, "Lesson not found")
    try:
        html = artifacts.read_lesson(lesson_id, version["content_hash"])
    except (FileNotFoundError, OSError):
        raise HTTPException(404, "Lesson file not found")
    return Response(html, media_type="text/html; charset=utf-8", headers={
        "Content-Security-Policy": artifacts.csp(version["script_hashes"]), "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store", "Cross-Origin-Resource-Policy": "same-origin", "Referrer-Policy": "no-referrer"})


# ---- Runs -------------------------------------------------------------------

class RunCreate(BaseModel):
    lesson_version_id: str
    time_budget_min: int | None = None


class Checkpoint(BaseModel):
    expected_revision: int
    activity_id: str | None = Field(None, max_length=64)
    params: dict | None = None
    step: int | None = None
    status: str | None = None


class Attempt(BaseModel):
    activity_id: str = Field(max_length=64)
    response: bool | int | float | str | list | dict | None = None
    params: dict | None = None
    hint_usage: dict | None = None
    client_op_id: str = Field(min_length=4, max_length=80)


class Question(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    concept: str | None = Field(None, max_length=300)      # the panel the learner is in
    activity_id: str | None = Field(None, max_length=64)
    params: dict | None = None
    level: int | None = None


def _public_run(run):
    return {k: run.get(k) for k in ("id", "lesson_id", "lesson_version_id", "channel", "current_activity", "step",
                                    "state_revision", "state", "status", "started_at", "updated_at")}


@router.post("/runs")
def create_run(person_id: str, body: RunCreate):
    return _public_run(guarded(lessons.create_run, person_id, body.lesson_version_id, body.time_budget_min))


@router.get("/runs/{run_id}")
def get_run(person_id: str, run_id: str):
    run = lessons.get_run(person_id, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return _public_run(run)


@router.patch("/runs/{run_id}")
def checkpoint_run(person_id: str, run_id: str, body: Checkpoint):
    return _public_run(guarded(lessons.checkpoint, person_id, run_id, body.expected_revision, body.activity_id,
                               body.params, body.step, body.status))


@router.post("/runs/{run_id}/attempts")
def submit_attempt(person_id: str, run_id: str, body: Attempt):
    return guarded(lessons.record_attempt, person_id, run_id, body.activity_id, body.response, body.params,
                   body.hint_usage, body.client_op_id)


@router.post("/runs/{run_id}/questions")
def ask_in_lesson(person_id: str, run_id: str, body: Question):
    """The existing mentor pipeline plus bounded lesson context. The learner's message is stored
    literally in layer 1, so conversation evidence keeps quoting real words."""
    from . import lesson_chat
    run = lessons.get_run(person_id, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    concept, context = guarded(lesson_chat.context, person_id, run, body.activity_id, body.params, body.concept)
    reply = chat.send(concept, body.message, person_id, body.level, extra_context=context)
    graph.run("MATCH (r:LessonRun {id:$rid}) SET r.session_id=$sid", rid=run_id, sid=reply["session_id"])
    return reply


# ---- References and recommendations ----------------------------------------

class ReferenceSave(BaseModel):
    topic_id: str
    kind: str
    title: str
    markdown: str
    concept_ids: list[str] = []
    source_ids: list[str] = []


class RecommendationAct(BaseModel):
    state: Literal["accepted", "dismissed"]


@router.get("/topics/{topic_id}/references")
def topic_references(person_id: str, topic_id: str):
    return lessons.references_for(person_id, topic_id=topic_id)


@router.get("/concepts/{concept_id}/references")
def concept_references(person_id: str, concept_id: str):
    return lessons.references_for(person_id, concept_id=concept_id)


@router.get("/references/{reference_id}")
def get_reference(person_id: str, reference_id: str):
    found = lessons.get_reference(person_id, reference_id)
    if not found:
        raise HTTPException(404, "Reference not found")
    return found


@router.post("/references")
def save_reference(person_id: str, body: ReferenceSave):
    return guarded(lessons.save_reference, person_id, body.topic_id, body.kind, body.title, body.markdown,
                   body.concept_ids, body.source_ids, "learner", None, graph.ui_language(person_id))


@router.post("/recommendations/{rec_id}")
def act_on_recommendation(person_id: str, rec_id: str, body: RecommendationAct):
    if not guarded(lessons.act_on_recommendation, person_id, rec_id, body.state):
        raise HTTPException(404, "Recommendation not found")
    return {"id": rec_id, "state": body.state}


def startup():
    """Called from main.startup(): safe with the flag off, and never blocks the API from starting."""
    try:
        interrupted = lessons.fail_interrupted()
        seeded = artifacts.seed_assets() if flags.mode() != "off" else []
        log.info("teach: mode=%s skill=%s seeded=%s interrupted_jobs=%d artifacts=%s", flags.mode(),
                 skill.adaptation_revision(), seeded, interrupted, artifacts.available())
    except Exception as exc:
        log.warning("teach startup skipped: %s", exc)
