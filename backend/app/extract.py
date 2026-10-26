"""Concept extraction from text + entity resolution against the existing graph.

Extraction only returns suggestions; writing happens via /learn. The extraction
itself is chunked and parallel (pipeline.py); this file holds the normalisation,
the source registration and the resolution against the graph."""
import asyncio

from . import llm, graph, transcript, pipeline
from .mentor import LEVELS

RESOLVE_SYSTEM = """Decide whether the new concept is the same as one of the candidates from the existing knowledge graph.
Answer with JSON only: {"same_as": "<candidate name>"} or {"same_as": null}."""


def normalize(text: str) -> dict:
    """Raw transcripts to timestamped segments plus chapter markers. Timestamps are
    kept as start_sec; without timestamps, paragraphs become segments without
    start_sec. See transcript.parse()."""
    return transcript.parse(text)


def normalized_text(text: str) -> str:
    """Plain text without timestamps and chapter titles (for callers that only
    need the content)."""
    return "\n\n".join(s["text"] for s in transcript.parse(text)["segments"])


GENERATE_SYSTEM = """You write a thorough, factual explanation of a topic, meant as source material for a knowledge graph.
Write for {audience}.
Rules:
- 600 to 1000 words, running paragraphs, no headings, lists or bullets.
- Introduce the underlying concepts explicitly and say how they relate: what is a prerequisite for what, what is part of what.
- Use the common English technical term when you introduce a concept.
- No introductory or closing meta sentences; start with the content.
- Write in {language}."""


def generate(topic: str, depth: int, language: str = "en") -> str:
    """Let the extract model write source material about a topic.
    depth 1-5 sets the technical level on the same scale as the mentor."""
    from . import languages
    return llm.complete(GENERATE_SYSTEM.format(audience=LEVELS[depth], language=languages.name(language)),
                        f"Topic: {topic}", llm.EXTRACT_MODEL)


def resolve(name: str, definition: str, embedding: list[float]) -> str | None:
    """Returns the existing concept name when this is a duplicate, otherwise None."""
    cands = graph.find_similar(embedding, k=3)
    cands = [c for c in cands if c["score"] > 0.80]
    if not cands:
        return None
    if cands[0]["score"] > 0.95:
        return cands[0]["name"]
    user = f"NEW: {name}: {definition}\nCANDIDATES:\n" + "\n".join(
        f"- {c['name']}: {c['definition']}" for c in cands)
    return llm.complete_json(RESOLVE_SYSTEM, user, llm.EXTRACT_MODEL).get("same_as")


def suggest_segments(segments: list[dict], chapters: list[dict], timed: bool,
                     source_type: str, title: str, url: str | None = None,
                     job_id: str | None = None, duration_sec: float | None = None, language: str = "en") -> dict:
    """Candidate concepts from segments, without storing anything. The source is
    parked as a PendingSource; only /learn promotes it."""
    result = asyncio.run(pipeline.run(segments, chapters, timed, job_id, duration_sec))
    return stage_result(result, source_type, title, url)


def stage_result(result, source_type, title, url):
    # Mark candidates that already exist as a Concept (name/alias) for the review.
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
            job_id: str | None = None, language: str = "en") -> dict:
    """Gets candidate concepts from raw text without storing anything."""
    parsed = normalize(text)
    return suggest_segments(parsed["segments"], parsed["chapters"], parsed["timed"],
                            source_type, title, url, job_id)
