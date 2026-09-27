"""Feature flag for interactive lessons. Default on. TEACH_MODE=off makes the routes answer 404 and
hides the UI; pilot limits it to TEACH_PERSONS (comma-separated person ids)."""
import os

MODES = ("off", "pilot", "on")


def mode() -> str:
    value = os.getenv("TEACH_MODE", "on").strip().lower()
    return value if value in MODES else "on"


def persons() -> list[str]:
    return [p.strip() for p in os.getenv("TEACH_PERSONS", "").split(",") if p.strip()]


def enabled_for(person_id: str) -> bool:
    return mode() == "on" or (mode() == "pilot" and person_id in persons())


def public(person_id: str) -> dict:
    return {"mode": mode(), "enabled": enabled_for(person_id)}
