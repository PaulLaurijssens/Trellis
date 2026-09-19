"""Concept-extractie uit tekst + entity resolution tegen de bestaande graph.

Extractie levert alleen suggesties op; wegschrijven gebeurt pas via /learn.
De extractie zelf is gechunkt en parallel (pipeline.py); dit bestand houdt
de normalisatie, de bron-registratie en de resolutie tegen de graph."""
import asyncio

from . import llm, graph, transcript, pipeline
from .mentor import LEVELS

RESOLVE_SYSTEM = """Bepaal of het nieuwe concept hetzelfde is als een van de kandidaten uit de bestaande kennisgraph.
Antwoord uitsluitend met JSON: {"same_as": "<naam van kandidaat>" } of {"same_as": null}."""


def normalize(text: str) -> dict:
    """Rauwe transcripten naar segmenten met tijdcode plus hoofdstuk-markers.
    Tijdcodes blijven bewaard als start_sec; zonder tijdcodes worden alinea's
    segmenten zonder start_sec. Zie transcript.parse()."""
    return transcript.parse(text)


def normalized_text(text: str) -> str:
    """Platte tekst zonder tijdcodes en hoofdstuktitels (voor wie alleen de
    inhoud nodig heeft)."""
    return "\n\n".join(s["text"] for s in transcript.parse(text)["segments"])


GENERATE_SYSTEM = """Je schrijft een gedegen, feitelijke uitleg over een onderwerp,
bedoeld als bronmateriaal voor een kennisgraph.
Schrijf voor {audience}.
Regels:
- 600 tot 1000 woorden, lopende alinea's, geen kopjes, lijstjes of opsommingstekens.
- Introduceer expliciet de onderliggende concepten en benoem hoe ze samenhangen:
  wat is voorwaarde voor wat, wat is onderdeel van wat.
- Gebruik de gangbare Engelse vakterm als je een concept introduceert.
- Geen inleidende of afsluitende meta-zinnen; begin direct met de inhoud.
- Schrijf in het Nederlands."""


def generate(topic: str, depth: int) -> str:
    """Laat het extract-model bronmateriaal over een topic schrijven.
    depth 1-5 stuurt het technisch niveau via dezelfde schaal als de mentor."""
    return llm.complete(GENERATE_SYSTEM.format(audience=LEVELS[depth]),
                        f"Onderwerp: {topic}", llm.EXTRACT_MODEL)


def resolve(name: str, definition: str, embedding: list[float]) -> str | None:
    """Retourneert bestaande concept-naam als het een duplicaat is, anders None."""
    cands = graph.find_similar(embedding, k=3)
    cands = [c for c in cands if c["score"] > 0.80]
    if not cands:
        return None
    if cands[0]["score"] > 0.95:
        return cands[0]["name"]
    user = f"NIEUW: {name}: {definition}\nKANDIDATEN:\n" + "\n".join(
        f"- {c['name']}: {c['definition']}" for c in cands)
    return llm.complete_json(RESOLVE_SYSTEM, user, llm.EXTRACT_MODEL).get("same_as")


def suggest_segments(segments: list[dict], chapters: list[dict], timed: bool,
                     source_type: str, title: str, url: str | None = None,
                     job_id: str | None = None, duration_sec: float | None = None) -> dict:
    """Kandidaat-concepten uit segmenten, zonder iets op te slaan. De bron
    wordt geparkeerd als PendingSource; pas /learn promoveert hem."""
    result = asyncio.run(pipeline.run(segments, chapters, timed, job_id, duration_sec))
    return stage_result(result, source_type, title, url)


def stage_result(result, source_type, title, url):
    # Kandidaten die al als Concept bestaan (naam/alias) markeren voor de review.
    names = [c["name"] for c in result["candidates"]] + \
            [a for c in result["candidates"] for a in c.get("aliases", [])]
    found = graph.match_names(names)
    for c in result["candidates"]:
        hit = found.get(c["name"].lower().strip()) or next(
            (found[a.lower().strip()] for a in c.get("aliases", []) if a.lower().strip() in found), None)
        c["existing"] = hit
    sid = graph.create_pending_source(source_type, title, url)
    return {"source_id": sid, "title": title, **result}


def suggest(text: str, source_type: str, title: str, url: str | None = None,
            job_id: str | None = None) -> dict:
    """Haalt kandidaat-concepten uit rauwe tekst zonder iets op te slaan."""
    parsed = normalize(text)
    return suggest_segments(parsed["segments"], parsed["chapters"], parsed["timed"],
                            source_type, title, url, job_id)
