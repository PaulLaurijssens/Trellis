"""Model-agnostic layer. Changing models = changing the settings, not the code."""
import asyncio, json, os, random, re, time
import litellm

from .provider_errors import ProviderError, classify

# Provider presets include reasoning models that reject optional sampling parameters.
litellm.drop_params = True

# Two jobs, two models: extraction is volume work (fast and cheap), mentor answers
# need reasoning power.
EXTRACT_MODEL = os.getenv("EXTRACT_MODEL", "gemini/gemini-3.7-flash")
MENTOR_MODEL = os.getenv("MENTOR_MODEL", "gemini/gemini-3.1-pro-preview")
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini/gemini-embedding-2-preview")
EMBED_DIM = int(os.getenv("EMBED_DIM", "3072"))
# Gemini Embedding 2: Google recommends a task instruction as a prefix for text tasks.
EMBED_PREFIX = os.getenv("EMBED_PREFIX", "task: search result | query: ")

# Provider "custom" (Other): its own endpoint and key variable, set by settings.apply(). Passed per call,
# and only for the custom models, so a model set in .env for another provider never gets this endpoint.
API_BASE: str | None = None
API_VERSION: str | None = None
API_KEY_ENV: str | None = None
CUSTOM_MODELS: set[str] = set()

# Retries on busy (503) and rate limits (429): exponential backoff with jitter, honour retry_after.
LLM_RETRIES = int(os.getenv("LLM_RETRIES", "3"))
BACKOFF_BASE = 2.0
BACKOFF_CAP = 30.0
_sleep = time.sleep
_asleep = asyncio.sleep


def endpoint(model: str) -> dict:
    """Extra LiteLLM arguments for this model: api_base/api_version/api_key of the custom provider."""
    if model not in CUSTOM_MODELS:
        return {}
    out = {}
    if API_BASE:
        out["api_base"] = API_BASE
    if API_VERSION:
        out["api_version"] = API_VERSION
    if API_KEY_ENV and os.getenv(API_KEY_ENV):
        out["api_key"] = os.getenv(API_KEY_ENV)
    return out


def _stage(stage: str | None, model: str, phase: str = "") -> str | None:
    if stage:
        return stage
    if phase in ("plan", "author", "agent", "rubric"):
        return "lesson"
    if phase in ("extract", "segment", "resolve", "relations") or model == EXTRACT_MODEL:
        return "extract"
    if model == MENTOR_MODEL:
        return "mentor"
    return None


def backoff(attempt: int, err: ProviderError) -> float:
    """Seconds before retry number `attempt` (0-based)."""
    if err.retry_after:
        return min(BACKOFF_CAP, float(err.retry_after) + random.uniform(0, 1))
    return min(BACKOFF_CAP, BACKOFF_BASE * 2 ** attempt * random.uniform(0.75, 1.25))


def call_model(fn, model: str, stage: str | None, retries: int | None = None):
    """Run one model call; failures become ProviderError, busy/quota are retried."""
    retries = LLM_RETRIES if retries is None else retries
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as exc:
            err = classify(exc, model=model, stage=stage)
            if not err.retryable or attempt >= retries:
                raise err from exc
            _sleep(backoff(attempt, err))


async def acall_model(fn, model: str, stage: str | None, retries: int | None = None):
    """Async variant of call_model(): `fn` returns an awaitable."""
    retries = LLM_RETRIES if retries is None else retries
    for attempt in range(retries + 1):
        try:
            return await fn()
        except Exception as exc:
            err = classify(exc, model=model, stage=stage)
            if not err.retryable or attempt >= retries:
                raise err from exc
            await _asleep(backoff(attempt, err))


def _check_dim(vector, model: str):
    if EMBED_DIM and len(vector) != EMBED_DIM:
        raise ProviderError("provider.embedDim", model=model, stage="embed", expected=EMBED_DIM, got=len(vector),
                            provider=model.split("/", 1)[0] if "/" in model else None)
    return vector


class Usage:
    """Token counter per phase, so an analysis can report what it cost."""

    def __init__(self):
        self.phases: dict[str, dict] = {}

    def add(self, phase: str, resp, fallback_chars: int = 0):
        u = getattr(resp, "usage", None)
        prompt = getattr(u, "prompt_tokens", None) if u else None
        completion = getattr(u, "completion_tokens", None) if u else None
        if prompt is None:
            prompt = fallback_chars // 4          # no usage returned: estimate
        cached = 0
        details = getattr(u, "prompt_tokens_details", None) if u else None
        if details is not None:
            cached = getattr(details, "cached_tokens", None) or (details.get("cached_tokens") if isinstance(details, dict) else 0) or 0
        cached = cached or (getattr(u, "cache_read_input_tokens", None) or 0 if u else 0)
        p = self.phases.setdefault(phase, {"calls": 0, "prompt": 0, "completion": 0, "cached": 0})
        p["calls"] += 1
        p["prompt"] += int(prompt or 0)
        p["completion"] += int(completion or 0)
        p["cached"] = p.get("cached", 0) + int(cached or 0)

    def total(self) -> int:
        return sum(v["prompt"] + v["completion"] for v in self.phases.values())

    def report(self) -> dict:
        out = {k: {**v, "total": v["prompt"] + v["completion"]} for k, v in self.phases.items()}
        out["total"] = sum(v["total"] for v in out.values())
        return out


def _strip_fences(text: str) -> str:
    return text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()


def parse_json(text: str):
    """JSON from a model answer, tolerant of code fences and chatty introductions."""
    text = _strip_fences(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"[\[{]", text)
        if not m:
            raise
        start = m.start()
        end = max(text.rfind("}"), text.rfind("]"))
        return json.loads(text[start:end + 1])


def complete(system: str, user: str, model: str, json_mode: bool = False,
             usage: Usage | None = None, phase: str = "", timeout: float = 180.0, stage: str | None = None) -> str:
    resp = call_model(lambda: litellm.completion(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
        timeout=timeout,
        **endpoint(model),
    ), model, _stage(stage, model, phase))
    if usage is not None:
        usage.add(phase, resp, len(system) + len(user))
    text = resp.choices[0].message.content
    return _strip_fences(text) if json_mode else text


def complete_json(system: str, user: str, model: str, usage: Usage | None = None,
                  phase: str = "", timeout: float = 180.0, stage: str | None = None) -> dict | list:
    return parse_json(complete(system, user, model, json_mode=True, usage=usage, phase=phase, timeout=timeout, stage=stage))


async def acomplete_json(system: str, user: str, model: str, usage: Usage | None = None,
                         phase: str = "", timeout: float = 180.0, stage: str | None = None) -> dict | list:
    """Async variant for the parallel extraction."""
    resp = await acall_model(lambda: litellm.acompletion(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
        timeout=timeout,
        **endpoint(model),
    ), model, _stage(stage, model, phase))
    if usage is not None:
        usage.add(phase, resp, len(system) + len(user))
    return parse_json(resp.choices[0].message.content)


def embed(texts: list[str], usage: Usage | None = None, phase: str = "embed") -> list[list[float]]:
    """One call per text: Gemini Embedding 2 aggregates several inputs in one call
    into one vector, so batching would merge concepts."""
    out = []
    model = EMBED_MODEL
    for t in texts:
        resp = call_model(lambda: litellm.embedding(model=model, input=[EMBED_PREFIX + t], dimensions=EMBED_DIM, **endpoint(model)),
                    model, "embed")
        if usage is not None:
            usage.add(phase, resp, len(t))
        out.append(_check_dim(resp.data[0]["embedding"], model))
    return out


async def aembed(texts: list[str], usage: Usage | None = None, phase: str = "embed",
                 concurrency: int = 6) -> list[list[float]]:
    """Same as embed(), but in parallel with a semaphore."""
    sem = asyncio.Semaphore(concurrency)
    model = EMBED_MODEL

    async def one(t: str):
        async with sem:
            resp = await acall_model(lambda: litellm.aembedding(model=model, input=[EMBED_PREFIX + t],
                                                          dimensions=EMBED_DIM, **endpoint(model)), model, "embed")
            if usage is not None:
                usage.add(phase, resp, len(t))
            return _check_dim(resp.data[0]["embedding"], model)

    return list(await asyncio.gather(*(one(t) for t in texts)))


class ToolLoopStopped(RuntimeError):
    """Budget, wall clock or cancellation ended an agent loop before the model did."""


def _caches(model: str) -> bool:
    """Anthropic needs explicit cache breakpoints; OpenAI and Gemini cache a stable prefix by themselves."""
    return "claude" in model.lower() or model.lower().startswith("anthropic/")


def _cached(text: str) -> list[dict]:
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def _has_images(message) -> bool:
    content = message.get("content") if isinstance(message, dict) else None
    return isinstance(content, list) and any(isinstance(part, dict) and part.get("type") == "image_url" for part in content)


def _drop_images(message) -> None:
    """Old screenshots stay out of every later call: they were looked at once and cost the most."""
    kept = [part for part in message["content"] if not (isinstance(part, dict) and part.get("type") == "image_url")]
    kept.append({"type": "text", "text": "(earlier screenshots removed; a newer validation replaced them)"})
    message["content"] = kept


def tool_loop(system: str, task: str, tools: list[dict], handler, model: str, max_steps: int = 30,
              deadline: float | None = None, usage: Usage | None = None, phase: str = "agent",
              should_stop=None, timeout: float = 180.0, over_budget=None, wrap_up: str = "", grace_steps: int = 4,
              keep_images: int = 1) -> str:
    """Bounded agent loop over function calling. `handler(name, args)` returns (result_dict, extra_messages);
    extra messages (e.g. a screenshot for the model to look at) are appended after the tool results.
    The assistant message is passed back unmodified, so provider fields (Gemini thought signatures) survive.
    Cost controls: the system prompt and task are cache breakpoints (Anthropic); only the newest
    `keep_images` image messages stay in the context. Optional cost limit: when `over_budget()` turns true,
    the model gets `wrap_up` once and `grace_steps` more steps to finish; then the loop stops."""
    import time
    caching = _caches(model)
    messages = [{"role": "system", "content": _cached(system) if caching else system},
                {"role": "user", "content": _cached(task) if caching else task}]
    grace = None                              # steps left after the cost limit; None = limit not reached
    for _ in range(max_steps):
        if should_stop and should_stop():
            raise ToolLoopStopped("cancelled")
        if deadline and time.monotonic() > deadline:
            raise ToolLoopStopped("time budget used up")
        if over_budget is not None:
            if grace is None and over_budget():
                grace = grace_steps - 1            # this step and grace_steps - 1 more
                messages.append({"role": "user", "content": wrap_up or "The cost limit is reached. Finish now."})
            elif grace is not None:
                grace -= 1
                if grace < 0:
                    raise ToolLoopStopped("cost limit reached")
        resp = call_model(lambda: litellm.completion(model=model, messages=messages, tools=tools, tool_choice="auto",
                                               temperature=0.3, timeout=timeout, **endpoint(model)), model, "lesson")
        if usage is not None:
            usage.add(phase, resp)
        message = resp.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        calls = message.tool_calls or []
        if not calls:
            return message.content or ""
        extras = []
        for call in calls:
            try:
                args = json.loads(call.function.arguments or "{}")
                if not isinstance(args, dict):
                    raise ValueError
            except ValueError:
                result, extra = {"error": "arguments must be a JSON object"}, []
            else:
                result, extra = handler(call.function.name, args)
            messages.append({"role": "tool", "tool_call_id": call.id, "name": call.function.name,
                             "content": json.dumps(result, ensure_ascii=False)[:60000]})
            extras += extra or []
            if isinstance(result, dict) and result.get("finished"):
                return str(result.get("summary") or "")
        if any(_has_images(m) for m in extras):
            with_images = [m for m in messages if m.get("role") == "user" and _has_images(m)]
            for old in with_images[:max(0, len(with_images) - keep_images + 1)]:
                _drop_images(old)
        messages += extras
    raise ToolLoopStopped("step budget used up")
