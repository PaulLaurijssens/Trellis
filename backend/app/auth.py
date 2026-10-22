"""Login for a self-hosted Trellis: password + signed session cookie. No third party, no new dependency.

Rules that the rest of the API relies on:
- every request carries a session, except /auth/*, /levels and the OpenAPI document;
- the person comes from the session, never from the URL or body. A route that has {person_id} in
  its path gets `own_person`, which refuses any other id (403), so the ownership checks in the
  data layer keep working unchanged;
- the first run has no persons with a password: /auth/setup creates the first one (or adds the
  password to an existing profile from before the login existed) and is closed after that.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import unicodedata
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from . import graph, providers, settings

router = APIRouter(prefix="/auth")
COOKIE = "trellis_session"
SESSION_DAYS = int(os.getenv("SESSION_DAYS", "30"))
OPEN_PATHS = ("/auth/", "/health", "/levels", "/openapi.json", "/docs", "/redoc")
_attempts: dict[str, list[float]] = {}          # login rate limit: ip -> timestamps


# ---- passwords (scrypt, stdlib) --------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32, maxmem=128 * 1024 * 1024)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str | None) -> bool:
    try:
        kind, salt, digest = (stored or "").split("$")
        if kind != "scrypt":
            return False
        candidate = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=2 ** 14, r=8, p=1, dklen=32, maxmem=128 * 1024 * 1024)
        return hmac.compare_digest(candidate, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


# ---- sessions (HMAC-signed token in an HttpOnly cookie) --------------------

def _sign(payload: bytes) -> str:
    return base64.urlsafe_b64encode(hmac.new(settings.session_secret(), payload, hashlib.sha256).digest()).decode().rstrip("=")


def issue_token(person_id: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"p": person_id, "e": int(time.time()) + SESSION_DAYS * 86400, "n": secrets.token_hex(8)}).encode()).decode().rstrip("=")
    return payload + "." + _sign(payload.encode())


def read_token(token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    payload, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(_sign(payload.encode()), signature):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, TypeError):
        return None
    if not isinstance(data.get("p"), str) or int(data.get("e", 0)) < time.time():
        return None
    return data["p"]


def set_cookie(response: Response, request: Request, token: str | None):
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    if token:
        response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax", secure=secure, path="/")
    else:
        response.delete_cookie(COOKIE, path="/")


# ---- persons ----------------------------------------------------------------

def slug(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:40] or "learner"


def persons_with_password() -> int:
    return graph.run("MATCH (p:Person) WHERE p.password_hash IS NOT NULL RETURN count(p) AS n")[0]["n"]


def setup_needed() -> bool:
    return persons_with_password() == 0


def person_public(person_id: str) -> dict | None:
    rows = graph.run("MATCH (p:Person {id:$pid}) RETURN p.id AS id, p.name AS name, coalesce(p.ui_language,'en') AS language, coalesce(p.is_admin,false) AS is_admin", pid=person_id)
    return rows[0] if rows else None


# ---- dependencies used by the other routers ---------------------------------

def current_person(request: Request) -> str:
    person = getattr(request.state, "person_id", None)
    if not person:
        raise HTTPException(401, "Please log in")
    return person


def own_person(person_id: str, request: Request) -> str:
    """For routes with {person_id} in the path: it must be the logged-in person."""
    if person_id != current_person(request):
        raise HTTPException(403, "Not your profile")
    return person_id


async def middleware(request: Request, call_next):
    """Resolve the session for every request; refuse everything that is not public without one."""
    request.state.person_id = read_token(request.cookies.get(COOKIE))
    path = request.url.path
    if request.method == "OPTIONS" or any(path == p.rstrip("/") or path.startswith(p) for p in OPEN_PATHS):
        return await call_next(request)
    if not request.state.person_id:
        return Response(json.dumps({"detail": "Please log in"}), status_code=401, media_type="application/json")
    return await call_next(request)


# ---- routes -------------------------------------------------------------------

class Setup(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    language: Literal["en", "nl"] = "en"
    password: str = Field(min_length=8, max_length=200)
    provider: str | None = None
    mentor_key: str | None = Field(None, max_length=400)
    embed_provider: str | None = None
    embed_key: str | None = Field(None, max_length=400)
    # Only for provider "custom" (Other): LiteLLM model ids, embedding size, and the key's variable name.
    mentor_model: str | None = Field(None, max_length=120)
    extract_model: str | None = Field(None, max_length=120)
    embed_model: str | None = Field(None, max_length=120)
    embed_dim: int | None = None
    key_env: str | None = Field(None, max_length=64)
    # Only for "custom": an endpoint (Azure, a proxy, a local server) and its API version.
    api_base: str | None = Field(None, max_length=300)
    api_version: str | None = Field(None, max_length=40)


class Login(BaseModel):
    person_id: str | None = None
    password: str = Field(max_length=200)


class SettingsPatch(BaseModel):
    provider: str | None = None
    mentor_key: str | None = Field(None, max_length=400)
    embed_provider: str | None = None
    embed_key: str | None = Field(None, max_length=400)
    mentor_model: str | None = Field(None, max_length=120)
    extract_model: str | None = Field(None, max_length=120)
    embed_model: str | None = Field(None, max_length=120)
    embed_dim: int | None = None
    key_env: str | None = Field(None, max_length=64)
    api_base: str | None = Field(None, max_length=300)
    api_version: str | None = Field(None, max_length=40)
    lesson_cost_limit: float | None = Field(None, ge=0, le=100)     # USD per lesson; 0 = off


CUSTOM_FIELDS = ("mentor_model", "extract_model", "embed_model", "embed_dim", "key_env", "api_base", "api_version")
CUSTOM_ONLY = ("embed_model", "embed_dim", "key_env", "api_base", "api_version")


def _rate_limited(request: Request, attempts: dict | None = None) -> bool:
    attempts = _attempts if attempts is None else attempts
    ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "?")
    now = time.time()
    recent = [t for t in attempts.get(ip, []) if now - t < 600]
    attempts[ip] = recent
    return len(recent) >= 10


def _note_attempt(request: Request, attempts: dict | None = None):
    attempts = _attempts if attempts is None else attempts
    ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "?")
    attempts.setdefault(ip, []).append(time.time())


def _preset_models(values: dict) -> dict:
    """A preset may override its mentor (and extract) model, e.g. Flash as mentor on a free Gemini key."""
    out = {}
    for field in ("mentor_model", "extract_model"):
        value = values.get(field)
        if value:
            if not providers.valid_model_id(value):
                raise HTTPException(400, f"{field}: type a LiteLLM model id, for example gemini/gemini-3.7-flash")
            out[field] = value
    return out


@router.get("/status")
def status(request: Request):
    person = read_token(request.cookies.get(COOKIE))
    profiles = graph.run("MATCH (p:Person) WHERE p.password_hash IS NOT NULL RETURN p.id AS id, p.name AS name ORDER BY p.name")
    return {"setup_needed": setup_needed(), "authenticated": bool(person), "person": person_public(person) if person else None,
            "profiles": profiles if len(profiles) > 1 else [], "providers": providers.public(),
            "embedding_providers": providers.EMBEDDING_PROVIDERS, "configured": settings.configured()}


def _validate_provider_choice(provider, embed_provider, mentor_key, embed_key, custom=None):
    """(provider, embed_provider, embedding size), or (None, None, None) when the .env models stay.
    "custom" embeds with its own model and one key, so it never takes a second embedding provider."""
    if provider is None:
        return None, None, None
    if provider == providers.CUSTOM:
        reason = providers.validate_custom(custom or {})
        if reason:
            raise HTTPException(400, reason)
        key_env = (custom or {}).get("key_env")
        if key_env and not (mentor_key or os.getenv(key_env)):
            raise HTTPException(400, f"Type the API key for {key_env}")
        return provider, provider, custom["embed_dim"]
    if provider not in providers.PROVIDERS:
        raise HTTPException(400, "Unknown provider")
    spec = providers.PROVIDERS[provider]
    if spec["key_env"] and not (mentor_key or os.getenv(spec["key_env"])):
        raise HTTPException(400, f"{spec['label']} needs an API key")
    if embed_provider == providers.CUSTOM:      # left over from an earlier "Other" choice
        embed_provider = None
    embed_provider = embed_provider or (provider if spec["embed"] else None)
    if not embed_provider or embed_provider not in providers.EMBEDDING_PROVIDERS:
        raise HTTPException(400, "Choose an embedding provider")
    espec = providers.PROVIDERS[embed_provider]
    if espec["key_env"] and embed_provider != provider and not (embed_key or os.getenv(espec["key_env"])):
        raise HTTPException(400, f"{espec['label']} needs an API key for embeddings")
    return provider, embed_provider, espec["embed_dim"]


def _index_dim(dim):
    """.env wins for the embedding model (settings.apply), so it must win for the index size too."""
    return int(os.getenv("EMBED_DIM") or dim)


@router.post("/setup")
def setup(body: Setup, request: Request, response: Response):
    if not setup_needed():
        raise HTTPException(409, "Setup is already done. Log in instead.")
    custom = {k: getattr(body, k) for k in CUSTOM_FIELDS}
    provider, embed_provider, dim = _validate_provider_choice(body.provider, body.embed_provider, body.mentor_key, body.embed_key, custom)
    if provider:
        models = custom if provider == providers.CUSTOM else _preset_models(custom)
        # The vector size is decided here, once. Refuse a change when embeddings already exist.
        try:
            graph.ensure_vector_index(_index_dim(dim))
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        settings.update({"provider": provider, "embed_provider": embed_provider, "mentor_key": body.mentor_key,
                         "embed_key": body.embed_key if embed_provider != provider else body.mentor_key,
                         **models})
    elif not settings.configured():
        raise HTTPException(400, "Choose a model provider")
    # An install from before the login has a profile without password: it becomes the owner.
    existing = graph.run("MATCH (p:Person) WHERE p.password_hash IS NULL RETURN p.id AS id ORDER BY p.id LIMIT 1")
    person_id = existing[0]["id"] if existing else slug(body.name)
    graph.run('''MERGE (p:Person {id:$pid}) SET p.name=$name, p.ui_language=$lang, p.password_hash=$hash, p.is_admin=true,
        p.level=coalesce(p.level, 3), p.created_at=coalesce(p.created_at, $now)''',
              pid=person_id, name=body.name.strip(), lang=body.language, hash=hash_password(body.password), now=graph._now())
    set_cookie(response, request, issue_token(person_id))
    return {"person": person_public(person_id), "settings": settings.public()}


@router.post("/login")
def login(body: Login, request: Request, response: Response):
    if _rate_limited(request):
        raise HTTPException(429, "Too many attempts. Wait ten minutes.")
    if body.person_id:
        rows = graph.run("MATCH (p:Person {id:$pid}) RETURN p.id AS id, p.password_hash AS hash", pid=body.person_id)
    else:
        rows = graph.run("MATCH (p:Person) WHERE p.password_hash IS NOT NULL RETURN p.id AS id, p.password_hash AS hash ORDER BY p.created_at LIMIT 1")
    if not rows or not verify_password(body.password, rows[0]["hash"]):
        _note_attempt(request)
        raise HTTPException(401, "Wrong password")
    set_cookie(response, request, issue_token(rows[0]["id"]))
    return {"person": person_public(rows[0]["id"])}


@router.post("/logout")
def logout(request: Request, response: Response):
    set_cookie(response, request, None)
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    person = current_person(request)
    return {"person": person_public(person), "settings": settings.public()}


@router.get("/settings")
def get_settings(request: Request):
    current_person(request)
    return settings.public()


@router.put("/settings")
def put_settings(body: SettingsPatch, request: Request):
    person = person_public(current_person(request))
    if not person or not person["is_admin"]:
        raise HTTPException(403, "Only the owner can change model settings")
    changes = body.model_dump(exclude_unset=True)
    current = settings.get()
    if (changes.get("provider") or current.get("provider")) != providers.CUSTOM:
        for field in CUSTOM_ONLY:                                  # only "custom" reads these
            changes.pop(field, None)
        changes.update(_preset_models(changes))
    if "provider" in changes or "embed_provider" in changes or (current.get("provider") == providers.CUSTOM and changes.keys() & set(CUSTOM_FIELDS)):
        provider, embed_provider, dim = _validate_provider_choice(changes.get("provider") or current.get("provider"),
                                                                  changes.get("embed_provider") or current.get("embed_provider"),
                                                                  changes.get("mentor_key") or current.get("mentor_key"),
                                                                  changes.get("embed_key") or current.get("embed_key"),
                                                                  {k: changes.get(k, current.get(k)) for k in CUSTOM_FIELDS})
        try:
            graph.ensure_vector_index(_index_dim(dim))
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        changes.update(provider=provider, embed_provider=embed_provider)
        if provider != providers.CUSTOM and current.get("provider") != provider:
            # The stored model ids belong to the old choice: fall back to the preset's models.
            spec = providers.PROVIDERS[provider]
            changes.setdefault("mentor_model", spec["mentor"]); changes.setdefault("extract_model", spec["extract"])
    return settings.update(changes)


# ---- "Test the key" on the setup screen and in Settings ----------------------

class ProviderCheck(BaseModel):
    provider: str = Field(max_length=40)
    mentor_key: str | None = Field(None, max_length=400)
    embed_provider: str | None = Field(None, max_length=40)
    embed_key: str | None = Field(None, max_length=400)
    mentor_model: str | None = Field(None, max_length=120)
    extract_model: str | None = Field(None, max_length=120)
    embed_model: str | None = Field(None, max_length=120)
    embed_dim: int | None = None
    key_env: str | None = Field(None, max_length=64)
    api_base: str | None = Field(None, max_length=300)
    api_version: str | None = Field(None, max_length=40)
    use_stored_keys: bool = False


_check_attempts: dict[str, list[float]] = {}     # separate from login: testing keys must not lock anyone out


def _check_plan(body: ProviderCheck, stored: dict | None) -> dict:
    """What to call, with which key. `stored` (owner after setup, use_stored_keys) fills empty key fields
    with the stored key, but only for the provider that key belongs to. Raises 400 on unusable input."""
    stored = stored or {}

    def stored_key(provider):
        if stored.get("provider") == provider and stored.get("mentor_key"):
            return stored["mentor_key"]
        if stored.get("embed_provider") == provider and stored.get("embed_key"):
            return stored["embed_key"]
        return None

    if body.provider == providers.CUSTOM:
        custom = {k: getattr(body, k) for k in CUSTOM_FIELDS}
        reason = providers.validate_custom(custom)
        if reason:
            raise HTTPException(400, reason)
        # key_env only says that a key is expected; the value comes from the form (or what is stored).
        key = body.mentor_key or stored_key(providers.CUSTOM) or (os.getenv(body.key_env) if body.key_env else None)
        if body.key_env and not key:
            raise HTTPException(400, f"Type the API key for {body.key_env}")
        endpoint = {"api_base": body.api_base, "api_version": body.api_version}
        return {"provider": body.provider, "mentor_model": body.mentor_model, "extract_model": body.extract_model,
                "mentor_key": key, "endpoint": endpoint, "embed_provider": body.provider, "embed_model": body.embed_model,
                "embed_dim": body.embed_dim, "embed_key": key, "embed_endpoint": endpoint}
    spec = providers.PROVIDERS.get(body.provider)
    if not spec:
        raise HTTPException(400, "Unknown provider")
    models = _preset_models({"mentor_model": body.mentor_model, "extract_model": body.extract_model})
    key = body.mentor_key or stored_key(body.provider) or (os.getenv(spec["key_env"]) if spec["key_env"] else None)
    if spec["key_env"] and not key:
        raise HTTPException(400, f"{spec['label']} needs an API key")
    embed_provider = body.embed_provider if body.embed_provider and body.embed_provider != providers.CUSTOM else None
    embed_provider = embed_provider or (body.provider if spec["embed"] else None)
    if not embed_provider or embed_provider not in providers.EMBEDDING_PROVIDERS:
        raise HTTPException(400, "Choose an embedding provider")
    espec = providers.PROVIDERS[embed_provider]
    if embed_provider == body.provider:
        embed_key = body.embed_key or key
    else:
        embed_key = body.embed_key or stored_key(embed_provider) or (os.getenv(espec["key_env"]) if espec["key_env"] else None)
    if espec["key_env"] and not embed_key:
        raise HTTPException(400, f"{espec['label']} needs an API key for embeddings")
    return {"provider": body.provider, "mentor_model": models.get("mentor_model") or spec["mentor"],
            "extract_model": models.get("extract_model") or spec["extract"], "mentor_key": key,
            "endpoint": {"api_base": spec.get("api_base")}, "embed_provider": embed_provider,
            "embed_model": espec["embed"], "embed_dim": espec["embed_dim"], "embed_key": embed_key,
            "embed_endpoint": {"api_base": espec.get("api_base")}}


@router.post("/check-provider")
def check_provider(body: ProviderCheck, request: Request):
    """Three tiny calls (extract, mentor, one embedding) with the typed key. Open while setup is needed;
    afterwards only the owner may use it. Always 200 with the result per check."""
    from . import provider_check
    stored = None
    if not setup_needed():
        person = person_public(request.state.person_id) if getattr(request.state, "person_id", None) else None
        if not person or not person["is_admin"]:
            raise HTTPException(403, "Only the owner can test model settings")
        stored = settings.get() if body.use_stored_keys else None
    if _rate_limited(request, _check_attempts):
        raise HTTPException(429, {"code": "check.tooMany", "params": {}, "message": "Too many tests. Wait ten minutes."})
    _note_attempt(request, _check_attempts)
    return provider_check.run(_check_plan(body, stored))
