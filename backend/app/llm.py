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
        p = self.phases.setdefault(phase, {"calls": 0, "prompt": 0, "completion": 0})
        p["calls"] += 1
        p["prompt"] += int(prompt or 0)
        p["completion"] += int(completion or 0)

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
