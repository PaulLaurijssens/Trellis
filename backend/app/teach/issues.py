"""Check failures in plain words. The validator speaks to the lesson author ("touch target too small
(28x28 px)"); the learner sees one short line per kind ("A button is too small to tap on a phone"),
with the steps it concerns. The frontend owns the wording (teach.issue.<kind> in lib/en.js / nl.js)."""
import re

# First match wins, so the specific patterns come before the general ones.
KINDS = (
    ("unknown_block", ("unknown asset",)),
    ("unsafe_code", ("is not allowed", "are blocked", "are not allowed", "external URLs", "external CSS", "larger than",
                     "allowed file types", "directory is full", "invalid job id")),
    ("slow_start", ("lesson.ready was not received",)),
    ("did_not_load", ("did not load", "navigated or reloaded", "index.html is missing", "file not found")),
    ("script_error", ("browser error", "malformed message")),
    ("contrast", ("unreadable text",)),
    ("small_button", ("touch target",)),
    ("sideways", ("scrolls horizontally",)),
    ("several_at_once", ("more than one activity",)),
    ("network", ("load from the network",)),
    ("missing_part", ("has no <section", "lesson.ready announced activities")),
    ("incomplete", ("data-dl-objective", "data-dl-ask-mentor")),
    ("sources", ("primary source", "cites source", "RESOURCES.md")),
    ("language", ("lang=", "manifest.language")),
    ("too_little_text", ("almost no text",)),
    ("description", ("manifest", "CONCEPTS.md")),
)
STEP = re.compile(r"\bstep (\d+)")


def kind_of(error: str) -> str:
    text = error or ""
    return next((kind for kind, keys in KINDS if any(k in text for k in keys)), "other")


def summarize(errors: list[str]) -> list[dict]:
    """[{kind, steps}] in the order the kinds first appear; steps sorted, without duplicates."""
    out: dict[str, set] = {}
    for error in errors or []:
        steps = out.setdefault(kind_of(error), set())
        steps.update(int(n) for n in STEP.findall(error or ""))
    return [{"kind": kind, "steps": sorted(steps)} for kind, steps in out.items()]


def can_open(errors: list[str]) -> bool:
    """A lesson with only quality problems may be opened anyway, in the same sandbox. Never one that broke a
    safety rule (it was never bundled), never one that does not load, never one that links a building block that does not exist."""
    return not any(kind_of(e) in ("unsafe_code", "did_not_load", "unknown_block", "description") for e in errors or [])
