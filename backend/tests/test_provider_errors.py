"""Provider errors: classification of real LiteLLM exceptions, redaction, retries and the API shape. No network."""
import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import litellm

from app import llm, pipeline
from app.provider_errors import ProviderError, classify, redact, retry_after

GEMINI_LIMIT_ZERO = '''GeminiException - {
  "error": {
    "code": 429,
    "message": "You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits.\\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0, model: gemini-3.1-pro\\nPlease retry in 28.418s.",
    "status": "RESOURCE_EXHAUSTED",
    "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "28s"}]
  }
}'''
GEMINI_RATE = GEMINI_LIMIT_ZERO.replace("limit: 0", "limit: 15")
GEMINI_BUSY = ('GeminiException - {"error": {"code": 503, "message": "This model is currently experiencing high demand. '
               'Spikes in demand are usually temporary. Please try again later.", "status": "UNAVAILABLE"}}')
OPENAI_KEY = "sk-proj-AbCdEf1234567890abcdefghijklmnopQRST"


def response(status, headers=None):
    return httpx.Response(status, headers=headers or {}, request=httpx.Request("POST", "https://api.example.com"))


class ClassifyTests(unittest.TestCase):
    def test_gemini_busy(self):
        err = classify(litellm.ServiceUnavailableError(GEMINI_BUSY, "gemini", "gemini-3.1-pro-preview"),
                       model="gemini/gemini-3.1-pro-preview", stage="mentor")
        self.assertEqual((err.code, err.status, err.provider, err.stage), ("provider.busy", 503, "gemini", "mentor"))
        self.assertTrue(err.retryable)

    def test_gemini_limit_zero_is_quota_zero_not_a_retry(self):
        err = classify(litellm.RateLimitError(GEMINI_LIMIT_ZERO, "gemini", "gemini-3.1-pro-preview"), model="gemini/gemini-3.1-pro-preview")
        self.assertEqual((err.code, err.status), ("provider.quotaZero", 402))
        self.assertFalse(err.retryable)

    def test_gemini_normal_rate_limit_keeps_retry_delay(self):
        err = classify(litellm.RateLimitError(GEMINI_RATE, "gemini", "gemini-3.7-flash"), model="gemini/gemini-3.7-flash")
        self.assertEqual((err.code, err.status, err.retry_after), ("provider.quota", 429, 28))
        self.assertIn("28 seconds", err.message)
        self.assertTrue(err.retryable)

    def test_retry_after_header_and_text(self):
        self.assertEqual(retry_after(headers={"retry-after": "12"}), 12)
        self.assertEqual(retry_after(headers={"retry-after-ms": "2500"}), 2)
        self.assertEqual(retry_after(text="Please retry after 20 seconds."), 20)
        self.assertIsNone(retry_after(text="nothing here", headers={}))
        err = classify(litellm.RateLimitError("Rate limit reached for requests", "openai", "gpt-5.5-mini",
                                              response=response(429, {"retry-after": "7"})), model="openai/gpt-5.5-mini")
        self.assertEqual((err.code, err.retry_after), ("provider.quota", 7))

    def test_wrapped_connection_error_and_proxy_block_are_network(self):
        # Seen end to end behind a filtering proxy: LiteLLM reports both as an InternalServerError.
        exc = litellm.InternalServerError("InternalServerError: OpenAIException - Connection error.", "openai", "gpt-5.5-mini")
        self.assertEqual(classify(exc, model="openai/gpt-5.5-mini").code, "provider.network")
        exc = litellm.InternalServerError("InternalServerError: Azure_aiException - 403 Forbidden", "azure_ai", "gpt-4o")
        self.assertEqual(classify(exc, model="azure_ai/gpt-4o").code, "provider.network")

    def test_openai_invalid_key(self):
        exc = litellm.AuthenticationError("OpenAIException - Error code: 401 - {'error': {'message': 'Incorrect API key provided: "
                                          + OPENAI_KEY + ".', 'type': 'invalid_request_error', 'code': 'invalid_api_key'}}", "openai", "gpt-5.5")
        err = classify(exc, model="openai/gpt-5.5", stage="setup")
        self.assertEqual((err.code, err.status, err.provider), ("provider.auth", 502, "openai"))
        body = json.dumps(err.to_dict())
        self.assertNotIn(OPENAI_KEY, body)
        self.assertNotIn("AbCdEf1234567890", body)

    def test_openai_insufficient_quota(self):
        exc = litellm.RateLimitError("OpenAIException - You exceeded your current quota, please check your plan and billing details. "
                                     "{'type': 'insufficient_quota', 'code': 'insufficient_quota'}", "openai", "gpt-5.5")
        self.assertEqual(classify(exc).code, "provider.quotaZero")

    def test_azure_deployment_not_found(self):
        exc = litellm.NotFoundError("AzureException - Error code: 404 - {'error': {'code': 'DeploymentNotFound', 'message': "
                                    "'The API deployment for this resource does not exist.'}}", "azure/gpt-4o", "azure")
        err = classify(exc, model="azure/gpt-4o", stage="extract")
        self.assertEqual((err.code, err.status, err.provider, err.stage), ("provider.notFound", 502, "azure", "extract"))

    def test_other_kinds(self):
        cases = [
            (litellm.Timeout("Request timed out", "openai/gpt-5.5", "openai"), "provider.timeout", 504),
            (litellm.APIConnectionError("OllamaException - [Errno 111] Connection refused", "ollama", "qwen3:8b"), "provider.network", 502),
            (httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED]"), "provider.network", 502),
            (litellm.BadRequestError("GeminiException - API key not valid. Please pass a valid API key. API_KEY_INVALID", "gemini/x", "gemini"), "provider.auth", 502),
            (litellm.BadRequestError("AnthropicException - Your credit balance is too low to access the Anthropic API.", "anthropic/x", "anthropic"), "provider.quotaZero", 402),
            (litellm.BadRequestError("LLM Provider NOT provided. You passed model=gpt5", "gpt5", None), "provider.notFound", 502),
            (litellm.BadRequestError("Invalid value for 'temperature'", "openai/x", "openai"), "provider.badRequest", 502),
            (litellm.InternalServerError("AnthropicException - Overloaded", "anthropic", "claude-sonnet-5"), "provider.busy", 503),
            (litellm.InternalServerError("Something broke", "openai", "x"), "provider.unknown", 502),
            (litellm.PermissionDeniedError("Forbidden", "openai", "x", response=response(403)), "provider.auth", 502),
            (RuntimeError("weird"), "provider.unknown", 502),
        ]
        for exc, code, status in cases:
            with self.subTest(exc=type(exc).__name__, code=code):
                err = classify(exc)
                self.assertEqual((err.code, err.status), (code, status))
                self.assertNotEqual(err.status, 401)

    def test_classify_keeps_a_provider_error(self):
        first = ProviderError("provider.auth", model="openai/gpt-5.5")
        again = classify(first, stage="extract")
        self.assertIs(again, first)
        self.assertEqual((again.stage, again.provider), ("extract", "openai"))

    def test_redact(self):
        text = ("keys: AIzaSyD-abcdefghijklmnopqrstuvwxyz12345 sk-ant-api03-abcdefghijklmnop "
                "0123456789abcdef0123456789abcdef Bearer abcdefghijklmnop1234 key=zzzzzzzzzzzzzzzzzz12")
        out = redact(text, secrets=["my-secret-value"])
        for secret in ("AIzaSyD", "sk-ant-api03", "0123456789abcdef", "abcdefghijklmnop1234", "zzzzzzzz"):
            self.assertNotIn(secret, out)
        self.assertEqual(redact("plain my-secret-value", secrets=["my-secret-value"]), "plain [key]")
        self.assertIn("gemini-3.7-flash", redact("model gemini/gemini-3.7-flash failed"))


class HandlerTests(unittest.TestCase):
    def test_exception_handler_returns_contract_json(self):
        from app import main
        err = ProviderError("provider.quota", provider="gemini", model="gemini/gemini-3.7-flash", stage="extract", retry_after=28)
        resp = asyncio.run(main.provider_error(None, err))
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.headers["retry-after"], "28")
        body = json.loads(resp.body)
        self.assertEqual(body["detail"]["code"], "provider.quota")
        self.assertEqual(body["detail"]["params"], {"provider": "gemini", "model": "gemini/gemini-3.7-flash",
                                                    "retry_after": 28, "stage": "extract"})
        self.assertIn("28 seconds", body["detail"]["message"])

    def test_auth_is_never_401(self):
        from app import main
        resp = asyncio.run(main.provider_error(None, ProviderError("provider.auth", provider="openai")))
        self.assertEqual(resp.status_code, 502)
        self.assertIsNone(resp.headers.get("retry-after"))

    def test_health_has_version_and_commit(self):
        from app import main
        with patch.object(main.auth, "setup_needed", return_value=False), patch.object(main.settings, "configured", return_value=True), \
                patch.dict("os.environ", {"TRELLIS_VERSION": "0.4.0", "TRELLIS_COMMIT": "abc1234"}):
            out = main.health()
        self.assertEqual((out["version"], out["commit"]), ("0.4.0", "abc1234"))
        with patch.object(main.auth, "setup_needed", return_value=False), patch.object(main.settings, "configured", return_value=True), \
                patch.dict("os.environ", {}, clear=True):
            out = main.health()
        self.assertEqual((out["version"], out["commit"]), ("dev", ""))


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.sleeps = []
        patcher = patch.object(llm, "_sleep", self.sleeps.append)
        patcher.start()
        self.addCleanup(patcher.stop)

    def busy(self):
        return litellm.ServiceUnavailableError(GEMINI_BUSY, "gemini", "gemini-3.1-pro-preview")

    def test_busy_is_retried_with_growing_capped_waits(self):
        calls = []

        def fn():
            calls.append(1)
            if len(calls) < 3:
                raise self.busy()
            return "ok"
        self.assertEqual(llm.call_model(fn, "gemini/gemini-3.1-pro-preview", "mentor", retries=3), "ok")
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(self.sleeps), 2)
        self.assertTrue(1.5 <= self.sleeps[0] <= 2.5 and 3 <= self.sleeps[1] <= 5, self.sleeps)

    def test_gives_up_after_retries_and_raises_provider_error(self):
        def fn():
            raise self.busy()
        with self.assertRaises(ProviderError) as ctx:
            llm.call_model(fn, "gemini/gemini-3.1-pro-preview", "mentor", retries=2)
        self.assertEqual((ctx.exception.code, ctx.exception.stage), ("provider.busy", "mentor"))
        self.assertEqual(len(self.sleeps), 2)

    def test_auth_and_quota_zero_are_not_retried(self):
        for exc in (litellm.AuthenticationError("bad key", "openai", "gpt-5.5"),
                    litellm.RateLimitError(GEMINI_LIMIT_ZERO, "gemini", "gemini-3.1-pro")):
            calls = []

            def fn():
                calls.append(1)
                raise exc
            with self.assertRaises(ProviderError):
                llm.call_model(fn, "x/y", None, retries=3)
            self.assertEqual(len(calls), 1)
        self.assertEqual(self.sleeps, [])

    def test_retry_after_is_honoured_up_to_the_cap(self):
        self.assertTrue(28 <= llm.backoff(0, ProviderError("provider.quota", retry_after=28)) <= 29)
        self.assertLessEqual(llm.backoff(0, ProviderError("provider.quota", retry_after=600)), llm.BACKOFF_CAP)
        self.assertLessEqual(llm.backoff(10, ProviderError("provider.busy")), llm.BACKOFF_CAP)

    def test_async_retry(self):
        waits, calls = [], []

        async def fake_sleep(seconds):
            waits.append(seconds)

        async def fn():
            calls.append(1)
            if len(calls) == 1:
                raise litellm.RateLimitError(GEMINI_RATE, "gemini", "gemini-3.7-flash")
            return "ok"
        with patch.object(llm, "_asleep", fake_sleep):
            self.assertEqual(asyncio.run(llm.acall_model(fn, "gemini/gemini-3.7-flash", "extract")), "ok")
        self.assertEqual(len(waits), 1)
        self.assertTrue(28 <= waits[0] <= 29)

    def test_complete_passes_endpoint_for_custom_models_only(self):
        seen = []

        def fake_completion(**kw):
            seen.append(kw)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))], usage=None)
        with patch.object(llm, "API_BASE", "https://x.services.ai.azure.com/models"), patch.object(llm, "API_VERSION", "2024-10-21"), \
                patch.object(llm, "CUSTOM_MODELS", {"azure_ai/gpt-4o"}), patch.object(llm.litellm, "completion", fake_completion):
            llm.complete("s", "u", "azure_ai/gpt-4o")
            llm.complete("s", "u", "gemini/gemini-3.7-flash")
        self.assertEqual((seen[0]["api_base"], seen[0]["api_version"]), ("https://x.services.ai.azure.com/models", "2024-10-21"))
        self.assertNotIn("api_base", seen[1])

    def test_embed_checks_the_vector_size(self):
        resp = SimpleNamespace(data=[{"embedding": [0.0] * 768}], usage=None)
        with patch.object(llm, "EMBED_DIM", 3072), patch.object(llm.litellm, "embedding", return_value=resp):
            with self.assertRaises(ProviderError) as ctx:
                llm.embed(["x"])
        self.assertEqual((ctx.exception.code, ctx.exception.stage), ("provider.embedDim", "embed"))
        self.assertEqual((ctx.exception.extra["expected"], ctx.exception.extra["got"]), (3072, 768))


class PipelineWarningTests(unittest.TestCase):
    def test_skipped_parts_warning_is_a_code_with_the_reason(self):
        async def fail(*args, **kwargs):
            raise ProviderError("provider.auth", provider="openai", model="openai/gpt-5.5-mini", stage="extract")
        segments = [{"text": "Attention lets a model weigh the words of a sentence. " * 5, "start_sec": None}]
        with patch.object(pipeline.llm, "acomplete_json", fail):
            out = asyncio.run(pipeline.run(segments, [], False))
        self.assertEqual(out["meta"]["warnings"], [{"code": "extract.partsSkipped",
                                                    "params": {"skipped": 1, "total": 1, "parts": "1", "reason": "provider.auth"}}])

    def test_empty_text_warning_is_a_code(self):
        out = asyncio.run(pipeline.run([], [], False))
        self.assertEqual(out["meta"]["warnings"], [{"code": "extract.noText", "params": {}}])


if __name__ == "__main__":
    unittest.main()
