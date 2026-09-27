"""Runtime settings, stored in Neo4j on one (:Settings {id:'app'}) node and applied to the process.

Why in the database and not only in .env: the setup screen at http://localhost:8080 must be able to
finish the install without anyone editing a file. .env still wins when it is set (the VPS path).
The API key is stored on the same node; the API is the only process with database access, and the
node never leaves the server (the settings route returns masked values)."""
import json
import os
import secrets

from . import graph, llm, providers

_cache: dict = {}
SECRET_FIELDS = ("mentor_key", "embed_key")


def _row() -> dict:
    rows = graph.run("MATCH (s:Settings {id:'app'}) RETURN s.data AS data")
    return json.loads(rows[0]["data"]) if rows and rows[0]["data"] else {}


def _save(data: dict):
    graph.run("MERGE (s:Settings {id:'app'}) SET s.data=$data, s.updated_at=$now", data=json.dumps(data), now=graph._now())


def load() -> dict:
    """Read once at startup, generate the session secret on first use, and apply."""
    global _cache
    data = _row()
    if not data.get("session_secret"):
        data["session_secret"] = secrets.token_hex(32)
        _save(data)
    _cache = data
    apply()
    return data


def get() -> dict:
    return dict(_cache)


def configured() -> bool:
    """Models are usable: either the setup screen stored a provider, or .env brought the models along."""
    return bool(_cache.get("provider")) or bool(os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("MISTRAL_API_KEY"))


def apply():
    """Environment first (explicit operator choice), then the stored settings. LiteLLM reads keys from
    the environment, so a stored key is exported into this process only."""
    data = _cache
    provider = providers.spec(data.get("provider"), data)
    if provider:
        llm.MENTOR_MODEL = os.getenv("MENTOR_MODEL") or data.get("mentor_model") or provider["mentor"]
        llm.EXTRACT_MODEL = os.getenv("EXTRACT_MODEL") or data.get("extract_model") or provider["extract"]
        if provider["key_env"] and data.get("mentor_key") and not os.getenv(provider["key_env"]):
            os.environ[provider["key_env"]] = data["mentor_key"]
        if provider.get("api_base"):
            os.environ.setdefault("OLLAMA_API_BASE", provider["api_base"])
    embed = providers.spec(data.get("embed_provider") or data.get("provider"), data)
    if embed and embed["embed"]:
        llm.EMBED_MODEL = os.getenv("EMBED_MODEL") or embed["embed"]
        llm.EMBED_DIM = int(os.getenv("EMBED_DIM") or embed["embed_dim"])
        if embed["key_env"] and data.get("embed_key") and not os.getenv(embed["key_env"]):
            os.environ[embed["key_env"]] = data["embed_key"]
        if embed.get("api_base"):
            os.environ.setdefault("OLLAMA_API_BASE", embed["api_base"])


def update(changes: dict) -> dict:
    global _cache
    data = _row()
    for key, value in changes.items():
        if value is None or value == "":
            continue
        data[key] = value
    _save(data)
    _cache = data
    apply()
    return public()


def public() -> dict:
    """Never the key itself: only whether one is stored and its last 4 characters."""
    data = get()
    out = {k: v for k, v in data.items() if k not in SECRET_FIELDS and k != "session_secret"}
    for field in SECRET_FIELDS:
        value = data.get(field) or ""
        out[field + "_set"] = bool(value)
        out[field + "_tail"] = value[-4:] if value else ""
    out["models"] = {"mentor": llm.MENTOR_MODEL, "extract": llm.EXTRACT_MODEL, "embed": llm.EMBED_MODEL, "embed_dim": llm.EMBED_DIM}
    prov = providers.spec(data.get("provider"), data) or {}
    out["features"] = {"voice": bool(prov.get("voice")), "video": bool(prov.get("video"))}
    out["configured"] = configured()
    return out


def session_secret() -> bytes:
    return (_cache.get("session_secret") or "").encode()
