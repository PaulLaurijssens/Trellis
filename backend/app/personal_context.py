"""Shared learner memory for initial explanations and conversations."""
from . import graph, journey


def _bullet(items, empty=None):
    items = [str(i).strip() for i in (items or []) if str(i).strip()]
    return "\n".join("- " + i for i in items) if items else (empty or "")


def personal_context(person_id: str, concept_id: str | None = None) -> str:
    parts = []
    state = graph.understands_state(person_id, concept_id) if concept_id else None
    if state:
        block = ["\n## Wat deze lerende al met jou besprak (begripstoestand)"]
        if state.get("summary") and not state.get("summary_stale"):
            block.append(f"Waar jullie gebleven waren: {state['summary']}")
        if state.get("covered"):
            block.append("Al besproken (geen bewijs van beheersing; bouw voort, herhaal op verzoek):\n" + _bullet(state["covered"]))
        if state.get("struggles"):
            block.append("Waar hij moeite mee had:\n" + _bullet(state["struggles"]))
        if state.get("misconceptions"):
            block.append("Eerdere misvattingen (check of ze weg zijn):\n" + _bullet(state["misconceptions"]))
        assessment=state.get("self_assessment")
        if assessment:block.append("Zelfbeoordeling, geen toetsbewijs: " + str(assessment.get("value")))
        demonstrated=[e for e in state.get("evidence",[]) if e.get("outcome")=="demonstrated"]
        if demonstrated:block.append("Eerder gedemonstreerd (specifiek voorbeeld, geen algemene beheersing):\n"+_bullet([e.get("kind","")+": "+e.get("assessment","") for e in demonstrated[-5:]]))
        if state.get("quiz_correct") or state.get("quiz_wrong"):
            block.append(f"Controlevragen: {state.get('quiz_correct', 0)} goed, {state.get('quiz_wrong', 0)} fout.")
        parts.append("\n".join(block))

    profile = graph.learning_profile(person_id)
    if profile.get("teaching_preferences"):
        parts.append("\n## Explicit teaching preferences selected by the learner\n" + _bullet(profile["teaching_preferences"]) + "\nUse these as the default; a current request takes priority. Older inferred observations may be contextual or contradictory: do not treat them as fixed restrictions.")
    if any(profile.get(f) for f in graph.PROFILE_LISTS) or profile.get("notes"):
        block = ["\n## Leerprofiel van deze persoon (geldt voor alle onderwerpen)"]
        if profile.get("works_well"):
            block.append("Werkt goed bij hem:\n" + _bullet(profile["works_well"]))
        if profile.get("works_poorly"):
            block.append("Werkt niet:\n" + _bullet(profile["works_poorly"]))
        if profile.get("preferences"):
            block.append("Uitgesproken voorkeuren:\n" + _bullet(profile["preferences"]))
        if profile.get("notes"):
            block.append("Notities: " + profile["notes"])
        parts.append("\n".join(block))

    parts.append(journey.prompt_context(person_id, concept_id))
    return "\n".join(parts)
