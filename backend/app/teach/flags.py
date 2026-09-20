"""Feature flag for interactive lessons. Set by the Ansible role in the API's environment, so a flip
is a sudo-free app-layer deploy. off = the routes answer 404 and the UI shows nothing new."""
import os

MODES = ("off", "pilot", "on")


def mode() -> str:
    value = os.getenv("TEACH_MODE", "off").strip().lower()
    return value if value in MODES else "off"


def persons() -> list[str]:
    return [p.strip() for p in os.getenv("TEACH_PERSONS", "paul").split(",") if p.strip()]


def enabled_for(person_id: str) -> bool:
    return mode() == "on" or (mode() == "pilot" and person_id in persons())


def public(person_id: str) -> dict:
    return {"mode": mode(), "enabled": enabled_for(person_id)}
