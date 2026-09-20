"""Pure rules of the /teach integration: no database, no model, no network.

Same idea as memory_model.py: everything here is deterministic and unit-testable. Frame events,
manifests and agent output are untrusted input; these validators are the boundary."""
import json
import re
from hashlib import sha256

INTENTS = ("understand", "apply", "build", "explore")
FAMILIARITY = ("new", "basics", "using")            # self-report, never evidence
APPROACHES = ("concepts", "examples", "hands_on", "mix")
TIME_BUDGETS = (5, 10, 20)
DEPTHS = ("overview", "working", "deep")
JOB_STAGES = ("queued", "preparing", "generating", "validating", "ready", "failed", "cancelled")
JOB_TERMINAL = ("ready", "failed", "cancelled")
RUN_STATUS = ("active", "paused", "completed", "abandoned", "needs_attention")
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def key(*parts) -> str:
    return sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]


def _text(value, limit, name, required=True):
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()) or len(value) > limit:
        raise ValueError(f"{name}: text of 1-{limit} characters expected")
    return value.strip()


def _lines(value, limit, each, name):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError(f"{name}: at most {limit} items")
    return list(dict.fromkeys(_text(v, each, name) for v in value))


# ---- Objectives -------------------------------------------------------------

def onboarding(data: dict) -> dict:
    """The 2-4 pills. Every answer is optional: 'skip' is a valid answer."""
    def choice(field, allowed):
        value = data.get(field)
        if value is None:
            return None
        if value not in allowed:
            raise ValueError(f"{field}: one of {', '.join(map(str, allowed))}")
        return value
    return {"intent": choice("intent", INTENTS), "familiarity": choice("familiarity", FAMILIARITY),
            "approach": choice("approach", APPROACHES), "time_budget_min": choice("time_budget_min", TIME_BUDGETS),
            "free_text": _text(data.get("free_text"), 600, "free_text", required=False)}


def objective(data: dict) -> dict:
    if data.get("intent") not in INTENTS:
        raise ValueError("intent: understand, apply, build or explore")
    depth = data.get("preferred_depth") or "working"
    if depth not in DEPTHS:
        raise ValueError("preferred_depth: overview, working or deep")
    outcomes = _lines(data.get("observable_outcomes"), 6, 240, "observable_outcomes")
    if not outcomes:
        raise ValueError("observable_outcomes: at least one observable outcome")
    return {"intent": data["intent"], "preferred_depth": depth,
            "objective_markdown": _text(data.get("objective_markdown"), 1200, "objective_markdown"),
            "observable_outcomes": outcomes,
            "constraints": _lines(data.get("constraints"), 6, 240, "constraints"),
            "out_of_scope": _lines(data.get("out_of_scope"), 6, 240, "out_of_scope")}


def fallback_objective(topic_title: str, answers: dict, language: str) -> dict:
    """Deterministic draft when the model is unavailable. The learner still edits and confirms it."""
    intent = answers.get("intent") or "understand"
    nl = language == "nl"
    why = {"understand": (f"I want to understand how {topic_title} works and where its limits are.",
                          f"Ik wil begrijpen hoe {topic_title} werkt en waar de grenzen liggen."),
           "apply": (f"I want to apply {topic_title} to my own problems.",
                     f"Ik wil {topic_title} kunnen toepassen op mijn eigen vraagstukken."),
           "build": (f"I want to build something small that uses {topic_title}.",
                     f"Ik wil iets kleins bouwen dat {topic_title} gebruikt."),
           "explore": (f"I want to explore what {topic_title} makes possible and decide what to study next.",
                       f"Ik wil verkennen wat {topic_title} mogelijk maakt en kiezen wat ik verder uitzoek.")}[intent][nl]
    outcome = {"understand": ("Explain the core mechanism in my own words", "Het kernmechanisme in eigen woorden uitleggen"),
               "apply": ("Work a new example without help", "Een nieuw voorbeeld zonder hulp uitwerken"),
               "build": ("Build and inspect a small working example", "Een klein werkend voorbeeld bouwen en bekijken"),
               "explore": ("Compare two applications and choose one to study", "Twee toepassingen vergelijken en er één kiezen")}[intent][nl]
    text = why + ((" " + answers["free_text"]) if answers.get("free_text") else "")
    return objective({"intent": intent, "objective_markdown": text, "observable_outcomes": [outcome],
                      "constraints": [], "out_of_scope": [], "preferred_depth": "working"})


# ---- Manifest ---------------------------------------------------------------

CHECKERS = ("numeric_close", "choice", "set_equals", "ordering", "matrix_close", "rubric", "none")
ACTIVITY_TYPES = ("predict", "manipulate", "quiz", "explain", "steps", "custom")
EVENTS = ("activity.state_changed", "activity.answer_submitted", "activity.hint_requested", "mentor.question_requested")


def manifest(data) -> dict:
    """What a lesson declares about itself. The answer key (check) stays on the server: see public_manifest."""
    if not isinstance(data, dict):
        raise ValueError("manifest: object expected")
    activities, seen = [], set()
    raw = data.get("activities")
    if not isinstance(raw, list) or not 1 <= len(raw) <= 8:
        raise ValueError("manifest.activities: 1-8 activities")
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not ID.match(item["id"]) or item["id"] in seen:
            raise ValueError("manifest.activities: unique ids of letters, digits, - and _")
        seen.add(item["id"])
        if item.get("type") not in ACTIVITY_TYPES:
            raise ValueError(f"activity {item['id']}: type must be one of {', '.join(ACTIVITY_TYPES)}")
        check = item.get("check") or {"kind": "none"}
        if not isinstance(check, dict) or check.get("kind") not in CHECKERS:
            raise ValueError(f"activity {item['id']}: check.kind must be one of {', '.join(CHECKERS)}")
        if check["kind"] == "rubric":
            _text(check.get("rubric"), 1200, f"activity {item['id']}: check.rubric")
        elif check["kind"] != "none" and "expected" not in check:
            raise ValueError(f"activity {item['id']}: check.expected is required for {check['kind']}")
        events = item.get("events") or []
        if not isinstance(events, list) or any(e not in EVENTS for e in events):
            raise ValueError(f"activity {item['id']}: events must be from {', '.join(EVENTS)}")
        state = item.get("state_fields") or []
        if not isinstance(state, list) or len(state) > 24 or any(not isinstance(f, str) or not ID.match(f) for f in state):
            raise ValueError(f"activity {item['id']}: state_fields is a list of at most 24 field names")
        activities.append({"id": item["id"], "type": item["type"], "title": _text(item.get("title"), 160, "activity title"),
                           "prompt": _text(item.get("prompt"), 1200, "activity prompt", required=False),
                           "check": check, "events": events, "state_fields": state,
                           "concept_ids": _lines(item.get("concept_ids"), 8, 80, "concept_ids")})
    sources = []
    for ref in data.get("sources") or []:
        if not isinstance(ref, dict) or not isinstance(ref.get("source_id"), str):
            raise ValueError("manifest.sources: objects with source_id")
        sources.append({"source_id": ref["source_id"][:80], "primary": ref.get("primary") is True,
                        "start_sec": ref["start_sec"] if isinstance(ref.get("start_sec"), (int, float)) else None})
    if data.get("language") not in ("en", "nl"):
        raise ValueError("manifest.language: en or nl")
    return {"entrypoint": "index.html", "title": _text(data.get("title"), 160, "manifest.title"),
            "outcome": _text(data.get("outcome"), 400, "manifest.outcome"), "language": data["language"],
            "duration_min": int(data.get("duration_min") or 10), "activities": activities, "sources": sources,
            "assets": _lines(data.get("assets"), 24, 120, "manifest.assets"),
            "illustrative_values": data.get("illustrative_values") is True}


def public_manifest(full: dict) -> dict:
    """What the browser may see: everything except the answer keys."""
    out = {k: v for k, v in full.items() if k != "activities"}
    out["activities"] = [{**{k: v for k, v in a.items() if k != "check"}, "check_kind": a["check"]["kind"]}
                         for a in full["activities"]]
    return out


# ---- Frame events (untrusted) ----------------------------------------------

MAX_EVENT_BYTES = 16 * 1024
MAX_STATE_BYTES = 32 * 1024
_SCALAR = (str, int, float, bool, type(None))


def _flat(value, depth=0):
    """Numbers, short strings, booleans, and small lists/objects of them. Never DOM dumps or code."""
    if isinstance(value, _SCALAR):
        return not isinstance(value, str) or len(value) <= 2000
    if depth >= 3:
        return False
    if isinstance(value, list):
        return len(value) <= 64 and all(_flat(v, depth + 1) for v in value)
    if isinstance(value, dict):
        return len(value) <= 32 and all(isinstance(k, str) and len(k) <= 64 and _flat(v, depth + 1) for k, v in value.items())
    return False


def widget_state(full_manifest: dict, activity_id: str, params) -> dict:
    """Keeps only the fields the activity declared. Everything else the frame sends is dropped."""
    activity = next((a for a in full_manifest["activities"] if a["id"] == activity_id), None)
    if activity is None:
        raise ValueError("Unknown activity")
    if not isinstance(params, dict):
        raise ValueError("params: object expected")
    kept = {k: v for k, v in params.items() if k in activity["state_fields"] and _flat(v)}
    if len(json.dumps(kept, ensure_ascii=False).encode()) > MAX_STATE_BYTES:
        raise ValueError("Activity state is too large")
    return kept


# ---- Deterministic checkers (no generated code runs on the server) ---------

def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("number expected")
    return float(value)


def check_answer(check: dict, response) -> dict | None:
    """Returns {'outcome', 'assessed_by': 'deterministic'} or None when the mentor must assess (rubric)
    or when the activity has no check. A malformed response is 'needs_practice', never an exception that
    a frame could use to probe the key."""
    kind = check.get("kind")
    if kind in ("none", "rubric", None):
        return None
    expected = check.get("expected")
    try:
        if kind == "numeric_close":
            ok = abs(_number(response) - _number(expected)) <= float(check.get("tolerance", 1e-6))
        elif kind == "choice":
            ok = isinstance(response, str) and response == expected
        elif kind == "set_equals":
            ok = isinstance(response, list) and sorted(map(str, response)) == sorted(map(str, expected))
        elif kind == "ordering":
            ok = isinstance(response, list) and list(map(str, response)) == list(map(str, expected))
        else:  # matrix_close
            tol = float(check.get("tolerance", 1e-6))
            ok = (isinstance(response, list) and len(response) == len(expected) and
                  all(isinstance(r, list) and len(r) == len(e) and all(abs(_number(a) - _number(b)) <= tol for a, b in zip(r, e))
                      for r, e in zip(response, expected)))
    except (ValueError, TypeError):
        ok = False
    return {"outcome": "demonstrated" if ok else "needs_practice", "assessed_by": "deterministic", "uncertainty": "low"}


def assistance_level(hint_usage) -> str:
    """Assisted success stays distinguishable from unassisted success (plan §4)."""
    if not isinstance(hint_usage, dict):
        return "none"
    if hint_usage.get("worked_example"):
        return "worked_example"
    return "hint" if int(hint_usage.get("hints") or 0) > 0 else "none"
