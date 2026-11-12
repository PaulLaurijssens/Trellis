"""Model providers a person can pick at setup. One place for names, defaults, key hints and limits.

Everything goes through LiteLLM, so a provider is three model names plus one key. Embeddings are the
exception: their vector size is fixed in the database at first run and cannot change later."""
import re

PROVIDERS = {
    "gemini": {
        "label": "Google Gemini",
        "key_env": "GEMINI_API_KEY",
        "key_url": "https://aistudio.google.com/apikey",
        "key_hint": "Sign in with a Google account, click 'Create API key', copy it. The free tier is enough to import sources. The mentor model (Gemini Pro) and lessons need a paid key: turn on billing for the key in Google AI Studio.",
        "mentor": "gemini/gemini-3.1-pro-preview", "extract": "gemini/gemini-3.7-flash",
        "embed": "gemini/gemini-embedding-2-preview", "embed_dim": 3072,
        "voice": True, "video": True,
    },
    "openai": {
        "label": "OpenAI",
        "key_env": "OPENAI_API_KEY",
        "key_url": "https://platform.openai.com/api-keys",
        "key_hint": "Create an account, add a payment method, then 'Create new secret key'.",
        "mentor": "openai/gpt-5.5", "extract": "openai/gpt-5.4-mini",
        "embed": "openai/text-embedding-3-large", "embed_dim": 3072,
        "voice": False, "video": False,
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "key_env": "ANTHROPIC_API_KEY",
        "key_url": "https://console.anthropic.com/settings/keys",
        "key_hint": "Claude needs a second key for embeddings, from Gemini or OpenAI: pick that provider below. For Claude itself: create an account, add credit, then 'Create Key'.",
        "mentor": "anthropic/claude-sonnet-5", "extract": "anthropic/claude-haiku-4-5-20251001",
        "embed": None, "embed_dim": None,
        "voice": False, "video": False,
    },
    "mistral": {
        "label": "Mistral",
        "key_env": "MISTRAL_API_KEY",
        "key_url": "https://console.mistral.ai/api-keys",
        "key_hint": "Create an account, then 'Create new key'.",
        "mentor": "mistral/mistral-large-latest", "extract": "mistral/mistral-small-latest",
        "embed": "mistral/mistral-embed", "embed_dim": 1024,
        "voice": False, "video": False,
    },
    "ollama": {
        "label": "Ollama (local, free)",
        "key_env": None,
        "key_url": "https://ollama.com/download",
        "key_hint": "Install Ollama on this machine and pull the models: ollama pull qwen3:32b nomic-embed-text. Slow without a strong GPU; interactive lessons may fail.",
        "mentor": "ollama/qwen3:32b", "extract": "ollama/qwen3:8b",
        "embed": "ollama/nomic-embed-text", "embed_dim": 768,
        "voice": False, "video": False,
        "api_base": "http://host.docker.internal:11434",
    },
}
EMBEDDING_PROVIDERS = [name for name, p in PROVIDERS.items() if p["embed"]]

# "Other": the person types the LiteLLM model ids, the embedding size and the name of the key variable.
CUSTOM = "custom"
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/@+-]{1,119}$")
# Only key-shaped names, and never one of our own variables: the value is exported into the process.
_KEY_ENV = re.compile(r"^[A-Z][A-Z0-9_]{0,60}_(API_KEY|KEY|TOKEN)$")
_RESERVED_ENV = ("NEO4J_", "TRELLIS_", "SESSION_")


def custom_spec(data: dict) -> dict:
    """A preset-shaped dict from the stored (or submitted) custom values."""
    return {"label": "Other", "key_env": data.get("key_env") or None,
            "mentor": data.get("mentor_model"), "extract": data.get("extract_model"),
            "embed": data.get("embed_model"), "embed_dim": data.get("embed_dim"), "voice": False, "video": False,
            "endpoint": {"api_base": data.get("api_base") or None, "api_version": data.get("api_version") or None}}


def spec(name, data: dict | None = None) -> dict | None:
    """The preset, or the custom spec built from `data` for "custom"."""
    if name == CUSTOM:
        return custom_spec(data or {})
    return PROVIDERS.get(name or "")


def valid_model_id(value) -> bool:
    return bool(_MODEL_ID.match(str(value or "")))


# An endpoint for "custom": https anywhere, plain http only to this machine (a local model server).
_API_BASE = re.compile(r"^(https://[A-Za-z0-9.-]+(:\d{1,5})?(/[^\s]*)?|http://(host\.docker\.internal|localhost|127\.0\.0\.1)(:\d{1,5})?(/[^\s]*)?)$")
_API_VERSION = re.compile(r"^[A-Za-z0-9._-]{1,40}$")


def validate_endpoint(api_base, api_version) -> str | None:
    """None when the optional endpoint values are usable, else a short reason for the person."""
    if api_base and (len(api_base) > 300 or not _API_BASE.match(api_base)):
        return "Endpoint: an https:// address (or http://localhost / http://host.docker.internal for a local server)"
    if api_version and not _API_VERSION.match(api_version):
        return "API version: letters, digits, dots and dashes, for example 2024-10-21"
    return None


def validate_custom(data: dict) -> str | None:
    """None when the custom values are usable, else a short reason for the person."""
    for field, label in (("mentor_model", "Mentor model"), ("extract_model", "Extract model"), ("embed_model", "Embedding model")):
        if not valid_model_id(data.get(field)):
            return f"{label}: type a LiteLLM model id, for example openrouter/some-model"
    dim = data.get("embed_dim")
    if not isinstance(dim, int) or not 64 <= dim <= 8192:
        return "Embedding size: a whole number between 64 and 8192"
    key_env = data.get("key_env")
    if key_env and (not _KEY_ENV.match(key_env) or key_env.startswith(_RESERVED_ENV)):
        return "Key variable: a name like OPENROUTER_API_KEY"
    return validate_endpoint(data.get("api_base"), data.get("api_version"))


# Key prefixes that give away the provider. Order matters: "sk-ant-" before "sk-".
_KEY_PREFIXES = (("sk-ant-", "anthropic"), ("AIza", "gemini"), ("sk-", "openai"))


def key_hint(provider, key) -> dict | None:
    """A shape check before any call: {"code", "params"} when the key looks wrong for this provider, else None.
    Azure (Microsoft Foundry) keys are 32 hex characters or 84 characters without a known prefix."""
    if not key:
        return None
    if re.search(r"\s", key):
        return {"code": "key.hasSpaces", "params": {}}
    if provider not in ("openai", "anthropic", "gemini", "mistral"):
        return None
    looks_like = next((name for prefix, name in _KEY_PREFIXES if key.startswith(prefix)), None)
    if looks_like and looks_like != provider:
        return {"code": "key.wrongProvider", "params": {"looks_like": looks_like}}
    if looks_like is None and (re.fullmatch(r"[0-9a-fA-F]{32}", key) or len(key) == 84):
        return {"code": "key.looksAzure", "params": {}}
    return None


def public() -> dict:
    """What the setup screen may see: no key values, ever."""
    return {name: {k: v for k, v in p.items() if k in ("label", "key_env", "key_url", "key_hint", "mentor", "extract", "embed", "embed_dim", "voice", "video")}
            for name, p in PROVIDERS.items()}
