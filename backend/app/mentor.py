"""Mentor: vragen beantwoorden op instelbaar niveau, gegrond in de graph."""
from . import llm, graph

LEVELS = {
    1: "a curious 10-year-old: short sentences, concrete everyday examples, no jargon",
    2: "a secondary-school student: simple analogies, jargon only with an explanation",
    3: "an interested professional without a technical background",
    4: "a developer or engineer with basic knowledge of the field",
    5: "an experienced engineer: precise, technical, no simplification, name nuances and edge cases",
}


def ask(question: str, concept: str | None, level: int, language: str = "en") -> str:
    from . import languages
    ctx = graph.concept_context(concept) if concept else None
    system = f"""You are a personal technical mentor. Explain at the level of {LEVELS[level]}.
Use the knowledge-graph context when present; name prerequisites the user may be missing.
Answer in {languages.name(language)}, concisely."""
    user = question if not ctx else f"CONTEXT FROM THE KNOWLEDGE GRAPH:\n{ctx}\n\nQUESTION: {question}"
    return llm.complete(system, user, llm.MENTOR_MODEL)
