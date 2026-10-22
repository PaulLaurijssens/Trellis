"""One error type for every failed model call, with a stable code the frontend can translate.

classify() maps LiteLLM (and plain httpx/socket) exceptions to the codes of the API contract. It only
looks at class names, status codes and message text, so it does not import litellm itself: tests can
stub litellm and still use this module."""
import re

from . import providers

STATUS = {
    "provider.auth": 502,           # never 401: the frontend logs the user out on 401
    "provider.quota": 429,
    "provider.quotaZero": 402,
    "provider.busy": 503,
    "provider.notFound": 502,
    "provider.network": 502,
    "provider.timeout": 504,
    "provider.badRequest": 502,
    "provider.embedDim": 502,
    "provider.unknown": 502,
}
RETRYABLE = ("provider.busy", "provider.quota")
STAGES = ("fetch", "extract", "embed", "mentor", "lesson", "setup")

_MESSAGES = {
    "provider.auth": "{label} rejected the API key. Check the key and the provider.",
    "provider.quota": "{label} says the rate limit is reached. Wait a moment and try again.",
    "provider.quotaZero": "Your {label} plan does not include {model}. Add billing on the provider site, or choose another model.",
    "provider.busy": "The model {model} is overloaded at the moment. Try again in a few minutes.",
    "provider.notFound": "{label} does not know the model, deployment or endpoint {model}. Check the model name and the endpoint.",
    "provider.network": "Trellis could not reach {label}. Check the endpoint address and the network.",
    "provider.timeout": "{label} did not answer in time. Try again.",
    "provider.badRequest": "{label} refused the request.",
    "provider.embedDim": "The embedding model gives vectors of size {got}. Trellis expects size {expected}.",
    "provider.unknown": "The call to {label} failed.",
}


class ProviderError(Exception):
    """A failed model call. `code` is one of STATUS; `detail` is the provider's own text, redacted."""

    def __init__(self, code: str, provider: str | None = None, model: str | None = None, stage: str | None = None,
                 retry_after: int | None = None, detail: str = "", **extra):
        self.code = code if code in STATUS else "provider.unknown"
        self.provider = provider
        self.model = model
        self.stage = stage if stage in STAGES else None
        self.retry_after = retry_after
        self.detail = redact(detail)[:400]
        self.extra = extra
        super().__init__(self.message)

    @property
    def status(self) -> int:
        return STATUS[self.code]

    @property
    def retryable(self) -> bool:
        return self.code in RETRYABLE

    @property
    def message(self) -> str:
        label = _label(self.provider)
        text = _MESSAGES[self.code].format(label=label, model=self.model or "this model",
                                           got=self.extra.get("got", "?"), expected=self.extra.get("expected", "?"))
        text = text[0].upper() + text[1:]
        if self.code == "provider.quota" and self.retry_after:
            text = text.replace("Wait a moment", f"Wait {self.retry_after} seconds")
        return text

    def params(self) -> dict:
        return {"provider": self.provider, "model": self.model, "retry_after": self.retry_after,
                "stage": self.stage, **self.extra}

    def to_dict(self) -> dict:
        out = {"code": self.code, "params": self.params(), "message": self.message}
        if self.detail:
            out["params"]["detail"] = self.detail
        return out

    def __str__(self):
        return f"{self.code}: {self.message}" + (f" ({self.detail})" if self.detail else "")


def _label(provider: str | None) -> str:
    preset = providers.PROVIDERS.get(provider or "")
    if preset:
        return preset["label"].split(" (")[0]
    return provider or "the model provider"


def provider_of(model: str | None) -> str | None:
    """'gemini/gemini-3.7-flash' -> 'gemini'. LiteLLM routes on this prefix."""
    if not model or "/" not in model:
        return None
    return model.split("/", 1)[0].lower()


# ---- redaction ---------------------------------------------------------------

_KEY_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9_\-*]{12,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"(?i)\b(bearer|api[-_ ]?key|x-goog-api-key|key)([\"':= ]+)[A-Za-z0-9_\-.*]{12,}"),
    re.compile(r"\b[0-9a-fA-F]{32}\b"),
    # Long opaque tokens with letters and digits (Azure 84-char keys, JWTs, provider tokens).
    re.compile(r"\b(?=[A-Za-z0-9_\-]*\d)(?=[A-Za-z0-9_\-]*[A-Za-z])[A-Za-z0-9_\-]{40,}\b"),
]


def redact(text, secrets=()) -> str:
    """Remove anything key-shaped, plus the given secret values, from a text we pass on."""
    out = str(text or "")
    for secret in secrets:
        if secret and len(secret) >= 6:
            out = out.replace(secret, "[key]")
    for pattern in _KEY_PATTERNS:
        out = pattern.sub(lambda m: (m.group(1) + m.group(2) + "[key]") if pattern.groups == 2 else "[key]", out)
    return out


# ---- classification ----------------------------------------------------------

_QUOTA_ZERO = re.compile(
    r"limit:\s*0\b|\"quotaValue\"\s*:\s*\"0\"|insufficient_quota|billing_hard_limit|billing_not_active|enable billing|"
    r"credit balance is too low|purchase credits|payment required|requires a paid|paid tier|not available on the free tier",
    re.I)
_BUSY = re.compile(r"overloaded|high demand|\bUNAVAILABLE\b|service unavailable|temporarily unavailable|try again later|capacity", re.I)
_NOT_FOUND = re.compile(r"not[ _]?found|does not exist|DeploymentNotFound|no such model|unknown model|"
                        r"LLM Provider NOT provided|is not supported for|model_not_found|not a valid model", re.I)
_AUTH = re.compile(r"api[ _]?key not valid|API_KEY_INVALID|invalid[ _]api[ _]key|incorrect api key|invalid x-api-key|"
                   r"authentication|unauthori[sz]ed|permission[ _]denied|missing .*api[ _]?key|api[ _]?key.* (missing|not set|required)|"
                   r"access denied|invalid subscription key", re.I)
_NETWORK = re.compile(r"connection (refused|reset|error|aborted)|name or service not known|nodename nor servname|"
                      r"getaddrinfo|temporary failure in name resolution|certificate|ssl|tls|no route to host|"
                      r"network is unreachable|failed to establish|cannot connect|could not connect|connecterror", re.I)
_TIMEOUT = re.compile(r"timed? ?out|timeout|deadline exceeded|DEADLINE_EXCEEDED", re.I)


def _status(exc) -> int | None:
    for attr in ("status_code", "http_status", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int) and 100 <= value < 600:
            return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def _names(exc) -> set[str]:
    return {cls.__name__ for cls in type(exc).__mro__}


def _headers(exc) -> dict:
    out = {}
    for source in (getattr(getattr(exc, "response", None), "headers", None), getattr(exc, "headers", None)):
        try:
            out.update({str(k).lower(): str(v) for k, v in (source or {}).items()})
        except (AttributeError, TypeError):
            continue
    return out


def retry_after(exc=None, text: str = "", headers: dict | None = None) -> int | None:
    """Seconds to wait, from a Retry-After header, Gemini's retryDelay, or 'retry after/in N seconds'."""
    headers = headers if headers is not None else (_headers(exc) if exc is not None else {})
    for name in ("retry-after", "x-ratelimit-reset-requests", "retry-after-ms"):
        value = headers.get(name)
        if not value:
            continue
        m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(ms|s)?\s*$", value)
        if m:
            seconds = float(m.group(1)) / (1000 if name == "retry-after-ms" or m.group(2) == "ms" else 1)
            return max(1, int(round(seconds)))
    text = text or (str(exc) if exc is not None else "")
    for pattern in (r"\"?retryDelay\"?\s*[:=]\s*\"?(\d+(?:\.\d+)?)s", r"retry (?:in|after) (\d+(?:\.\d+)?)\s*(?:s\b|sec|second)"):
        m = re.search(pattern, text, re.I)
        if m:
            return max(1, int(round(float(m.group(1)))))
    return None


def classify(exc, provider: str | None = None, model: str | None = None, stage: str | None = None) -> ProviderError:
    """The ProviderError for any exception from a model call. Never raises."""
    if isinstance(exc, ProviderError):
        exc.stage = exc.stage or (stage if stage in STAGES else None)
        exc.model = exc.model or model
        exc.provider = exc.provider or provider or provider_of(exc.model)
        return exc
    model = model or getattr(exc, "model", None) or None
    provider = provider or provider_of(model) or (getattr(exc, "llm_provider", None) or None)
    if provider and not isinstance(provider, str):
        provider = None
    text = str(exc)
    message = str(getattr(exc, "message", "") or "")
    if message and message not in text:
        text = message + " " + text
    names = _names(exc)
    status = _status(exc)
    code = _code(names, status, text)
    wait = retry_after(exc, text) if code in ("provider.quota", "provider.busy") else None
    return ProviderError(code, provider=provider, model=model, stage=stage, retry_after=wait, detail=text.strip())


def _code(names: set[str], status: int | None, text: str) -> str:
    if "ContextWindowExceededError" in names or "ContentPolicyViolationError" in names:
        return "provider.badRequest"
    if names & {"Timeout", "APITimeoutError", "TimeoutException", "ReadTimeout", "ConnectTimeout", "TimeoutError"} or status in (408,):
        return "provider.timeout"
    if status == 429 or "RateLimitError" in names:
        return "provider.quotaZero" if _quota_zero(text) else "provider.quota"
    if status == 402 or (status == 403 and _quota_zero(text)):
        return "provider.quotaZero"
    if status in (401, 403) or names & {"AuthenticationError", "PermissionDeniedError"}:
        return "provider.auth"
    if status == 404 or "NotFoundError" in names:
        return "provider.notFound"
    if status in (502, 503, 529) or names & {"ServiceUnavailableError", "BadGatewayError"}:
        return "provider.busy"
    if names & {"APIConnectionError", "ConnectError", "ConnectionError", "SSLError", "gaierror", "NetworkError"}:
        # LiteLLM also wraps unexpected errors in APIConnectionError: look at the text first.
        if _AUTH.search(text):
            return "provider.auth"
        if _TIMEOUT.search(text):
            return "provider.timeout"
        if _BUSY.search(text) and not _NETWORK.search(text):
            return "provider.busy"
        return "provider.network"
    if status == 400 or names & {"BadRequestError", "UnprocessableEntityError", "UnsupportedParamsError"} or status == 422:
        if _quota_zero(text):
            return "provider.quotaZero"              # Anthropic: "credit balance is too low" is a 400
        if _AUTH.search(text):
            return "provider.auth"                   # Gemini: an invalid key is a 400 INVALID_ARGUMENT
        if _NOT_FOUND.search(text):
            return "provider.notFound"
        return "provider.badRequest"
    if status is not None and status >= 500 or names & {"InternalServerError", "APIError"}:
        if _BUSY.search(text) or status in (502, 503, 529):
            return "provider.busy"
        return "provider.unknown"
    return "provider.unknown"


def _quota_zero(text: str) -> bool:
    """Billing needed or a plan limit of 0, as opposed to a rate limit that clears by itself.
    OpenAI's insufficient_quota says "exceeded your current quota"; Gemini says that too for normal
    rate limits, but then adds "Quota exceeded for metric ... limit: N"."""
    if _QUOTA_ZERO.search(text):
        return True
    return bool(re.search(r"exceeded your current quota", text, re.I)) and not re.search(r"quota exceeded for metric|limit:\s*\d", text, re.I)
