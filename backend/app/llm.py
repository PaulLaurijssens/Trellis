"""LLM-agnostische laag. Model wisselen = .env aanpassen."""
import asyncio, json, os, re
import litellm

# Twee taken, twee modellen: extractie is volume-werk (snel/goedkoop),
# mentor-antwoorden vragen om redeneerkracht.
EXTRACT_MODEL = os.getenv("EXTRACT_MODEL", "gemini/gemini-3.7-flash")
MENTOR_MODEL = os.getenv("MENTOR_MODEL", "gemini/gemini-3.1-pro-preview")
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini/gemini-embedding-2-preview")
EMBED_DIM = int(os.getenv("EMBED_DIM", "3072"))
# Gemini Embedding 2: Google raadt voor tekst-taken een task-instructie als prefix aan.
EMBED_PREFIX = os.getenv("EMBED_PREFIX", "task: search result | query: ")


class Usage:
    """Tokenteller per fase, zodat een analyse kan rapporteren wat hij kostte."""

    def __init__(self):
        self.phases: dict[str, dict] = {}

    def add(self, phase: str, resp, fallback_chars: int = 0):
        u = getattr(resp, "usage", None)
        prompt = getattr(u, "prompt_tokens", None) if u else None
        completion = getattr(u, "completion_tokens", None) if u else None
        if prompt is None:
            prompt = fallback_chars // 4          # geen usage teruggekregen: schatting
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
    """JSON uit een modelantwoord, tolerant voor fences en pratende inleidingen."""
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
             usage: Usage | None = None, phase: str = "", timeout: float = 180.0) -> str:
    resp = litellm.completion(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
        timeout=timeout,
    )
    if usage is not None:
        usage.add(phase, resp, len(system) + len(user))
    text = resp.choices[0].message.content
    return _strip_fences(text) if json_mode else text


def complete_json(system: str, user: str, model: str, usage: Usage | None = None,
                  phase: str = "", timeout: float = 180.0) -> dict | list:
    return parse_json(complete(system, user, model, json_mode=True, usage=usage, phase=phase, timeout=timeout))


async def acomplete_json(system: str, user: str, model: str, usage: Usage | None = None,
                         phase: str = "", timeout: float = 180.0) -> dict | list:
    """Asynchrone variant voor de parallelle extractie."""
    resp = await litellm.acompletion(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
        timeout=timeout,
    )
    if usage is not None:
        usage.add(phase, resp, len(system) + len(user))
    return parse_json(resp.choices[0].message.content)


def embed(texts: list[str], usage: Usage | None = None, phase: str = "embed") -> list[list[float]]:
    """Eén call per tekst: Gemini Embedding 2 aggregeert meerdere inputs
    in één call tot één vector, dus batchen zou concepten samensmelten."""
    out = []
    for t in texts:
        resp = litellm.embedding(model=EMBED_MODEL, input=[EMBED_PREFIX + t], dimensions=EMBED_DIM)
        if usage is not None:
            usage.add(phase, resp, len(t))
        out.append(resp.data[0]["embedding"])
    return out


async def aembed(texts: list[str], usage: Usage | None = None, phase: str = "embed",
                 concurrency: int = 6) -> list[list[float]]:
    """Zelfde als embed(), maar parallel met een semaphore."""
    sem = asyncio.Semaphore(concurrency)

    async def one(t: str):
        async with sem:
            resp = await litellm.aembedding(model=EMBED_MODEL, input=[EMBED_PREFIX + t],
                                            dimensions=EMBED_DIM)
            if usage is not None:
                usage.add(phase, resp, len(t))
            return resp.data[0]["embedding"]

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
              should_stop=None, timeout: float = 180.0, max_tokens: int | None = None, keep_images: int = 1) -> str:
    """Bounded agent loop over function calling. `handler(name, args)` returns (result_dict, extra_messages);
    extra messages (e.g. a screenshot for the model to look at) are appended after the tool results.
    The assistant message is passed back unmodified, so provider fields (Gemini thought signatures) survive.
    Cost controls: the system prompt and task are cache breakpoints (Anthropic); only the newest
    `keep_images` image messages stay in the context; `max_tokens` stops the loop over the whole job."""
    import time
    caching = _caches(model)
    messages = [{"role": "system", "content": _cached(system) if caching else system},
                {"role": "user", "content": _cached(task) if caching else task}]
    for _ in range(max_steps):
        if should_stop and should_stop():
            raise ToolLoopStopped("cancelled")
        if deadline and time.monotonic() > deadline:
            raise ToolLoopStopped("time budget used up")
        if max_tokens and usage is not None and usage.total() > max_tokens:
            raise ToolLoopStopped("token budget used up")
        resp = litellm.completion(model=model, messages=messages, tools=tools, tool_choice="auto",
                                  temperature=0.3, timeout=timeout)
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
