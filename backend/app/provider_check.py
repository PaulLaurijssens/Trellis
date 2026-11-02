"""The setup screen's "Test the key": three tiny model calls before anything is stored.

Keys are passed to LiteLLM per call (api_key=...), never put into os.environ. No retries and a short
timeout: the person waits for this answer."""
from concurrent.futures import ThreadPoolExecutor

import litellm

from . import providers
from .provider_errors import ProviderError, classify, redact

TIMEOUT = 20
MAX_TOKENS = 8
PROMPT = [{"role": "user", "content": "Reply with the word OK."}]


def _args(key, endpoint) -> dict:
    out = {k: v for k, v in (endpoint or {}).items() if v}
    if key:
        out["api_key"] = key
    return out


def probe_chat(model: str, key, endpoint=None):
    litellm.completion(model=model, messages=PROMPT, max_tokens=MAX_TOKENS, timeout=TIMEOUT, num_retries=0,
                       **_args(key, endpoint))


def probe_embed(model: str, key, dim: int, endpoint=None):
    resp = litellm.embedding(model=model, input=["Trellis setup check"], dimensions=dim, timeout=TIMEOUT,
                             max_retries=0, **_args(key, endpoint))
    got = len(resp.data[0]["embedding"])
    if got != dim:
        raise ProviderError("provider.embedDim", model=model, stage="setup", expected=dim, got=got)


def _result(name: str, model: str, error: ProviderError | None, secrets) -> dict:
    if error is None:
        return {"name": name, "model": model, "ok": True, "code": None, "params": {}, "message": ""}
    params = {"retry_after": error.retry_after, **error.extra}
    if error.detail:
        params["detail"] = redact(error.detail, secrets)
    return {"name": name, "model": model, "ok": False, "code": error.code, "params": params,
            "message": redact(error.message, secrets)}


def run(plan: dict) -> dict:
    """plan: provider, mentor_model, extract_model, mentor_key, endpoint, embed_provider, embed_model,
    embed_dim, embed_key, embed_endpoint. Returns the contract's response body."""
    secrets = [k for k in (plan.get("mentor_key"), plan.get("embed_key")) if k]

    def attempt(fn, *args, model=None):
        try:
            fn(*args)
            return None
        except Exception as exc:                  # every failure becomes a code; never raise from here
            return classify(exc, model=model, stage="setup")

    jobs = {"extract": (probe_chat, plan["extract_model"], plan.get("mentor_key"), plan.get("endpoint")),
            "mentor": (probe_chat, plan["mentor_model"], plan.get("mentor_key"), plan.get("endpoint")),
            "embed": (probe_embed, plan["embed_model"], plan.get("embed_key"), plan["embed_dim"], plan.get("embed_endpoint"))}
    if plan["mentor_model"] == plan["extract_model"]:
        jobs.pop("mentor")                        # the same model twice: one call answers both
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {name: pool.submit(attempt, *job, model=job[1]) for name, job in jobs.items()}
        errors = {name: f.result() for name, f in futures.items()}
    errors.setdefault("mentor", errors["extract"])

    checks = [_result(name, plan[name + "_model"], errors[name], secrets) for name in ("extract", "mentor", "embed")]
    hint = providers.key_hint(plan["provider"], plan.get("mentor_key"))
    if hint is None and plan.get("embed_provider") != plan["provider"]:
        hint = providers.key_hint(plan.get("embed_provider"), plan.get("embed_key"))
        if hint:
            hint["params"]["field"] = "embed_key"
    suggest = None
    mentor, extract = errors["mentor"], errors["extract"]
    if mentor is not None and mentor.code == "provider.quotaZero" and extract is None and plan["mentor_model"] != plan["extract_model"]:
        suggest = {"mentor_model": plan["extract_model"], "reason": "provider.quotaZero"}
    return {"ok": all(c["ok"] for c in checks), "checks": checks, "key_hint": hint, "suggest": suggest}
