"""Mentor: vragen beantwoorden op instelbaar niveau, gegrond in de graph."""
from . import llm, graph

LEVELS = {
    1: "een nieuwsgierige 10-jarige: korte zinnen, concrete voorbeelden uit het dagelijks leven, geen jargon",
    2: "een middelbare scholier: eenvoudige analogieën, jargon alleen met uitleg",
    3: "een geïnteresseerde professional zonder technische achtergrond",
    4: "een developer of engineer met basiskennis van het domein",
    5: "een ervaren engineer: precies, technisch, geen versimpeling, benoem nuances en randgevallen",
}


def ask(question: str, concept: str | None, level: int) -> str:
    ctx = graph.concept_context(concept) if concept else None
    system = f"""Je bent een persoonlijke technische mentor. Leg uit op het niveau van {LEVELS[level]}.
Gebruik de kennisgraph-context als die er is; benoem prerequisites die de gebruiker mogelijk mist.
Antwoord in het Nederlands, bondig."""
    user = question if not ctx else f"CONTEXT UIT KENNISGRAPH:\n{ctx}\n\nVRAAG: {question}"
    return llm.complete(system, user, llm.MENTOR_MODEL)
