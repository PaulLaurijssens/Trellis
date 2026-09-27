"""Shared learner memory for initial explanations and conversations."""
from . import graph, journey


def _bullet(items, empty=None):
    items = [str(i).strip() for i in (items or []) if str(i).strip()]
    return "\n".join("- " + i for i in items) if items else (empty or "")


def personal_context(person_id: str, concept_id: str | None = None) -> str:
    parts = []
    state = graph.understands_state(person_id, concept_id) if concept_id else None
    if state:
        block = ["\n## What this learner already discussed with you (understanding state)"]
        if state.get("summary") and not state.get("summary_stale"):
            block.append(f"Where you left off: {state['summary']}")
        if state.get("covered"):
            block.append("Already discussed (no proof of mastery; build on it, repeat on request):\n" + _bullet(state["covered"]))
        if state.get("struggles"):
            block.append("What they struggled with:\n" + _bullet(state["struggles"]))
        if state.get("misconceptions"):
            block.append("Earlier misconceptions (check whether they are gone):\n" + _bullet(state["misconceptions"]))
        assessment=state.get("self_assessment")
        if assessment:block.append("Self-assessment, not test evidence: " + str(assessment.get("value")))
        demonstrated=[e for e in state.get("evidence",[]) if e.get("outcome")=="demonstrated"]
        if demonstrated:block.append("Demonstrated earlier (specific example, not general mastery):\n"+_bullet([e.get("kind","")+": "+e.get("assessment","") for e in demonstrated[-5:]]))
        if state.get("quiz_correct") or state.get("quiz_wrong"):
            block.append(f"Check questions: {state.get('quiz_correct', 0)} right, {state.get('quiz_wrong', 0)} wrong.")
        parts.append("\n".join(block))

    profile = graph.learning_profile(person_id)
    if profile.get("teaching_preferences"):
        parts.append("\n## Explicit teaching preferences selected by the learner\n" + _bullet(profile["teaching_preferences"]) + "\nUse these as the default; a current request takes priority. Older inferred observations may be contextual or contradictory: do not treat them as fixed restrictions.")
    if any(profile.get(f) for f in graph.PROFILE_LISTS) or profile.get("notes"):
        block = ["\n## This person's learning profile (applies to all topics)"]
        if profile.get("works_well"):
            block.append("Works well for them:\n" + _bullet(profile["works_well"]))
        if profile.get("works_poorly"):
            block.append("Does not work:\n" + _bullet(profile["works_poorly"]))
        if profile.get("preferences"):
            block.append("Stated preferences:\n" + _bullet(profile["preferences"]))
        if profile.get("notes"):
            block.append("Notes: " + profile["notes"])
        parts.append("\n".join(block))

    parts.append(journey.prompt_context(person_id, concept_id))
    return "\n".join(parts)
