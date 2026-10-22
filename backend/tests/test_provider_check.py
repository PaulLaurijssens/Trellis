"""Setup check (POST /auth/check-provider), key shape hints and the endpoint settings. LiteLLM is mocked."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import litellm
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app import auth, llm, provider_check, providers, settings

GEMINI_KEY = "AIzaSyD-abcdefghijklmnopqrstuvwxyz12345"
LIMIT_ZERO = ('GeminiException - {"error": {"code": 429, "message": "Quota exceeded for metric: '
              'generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0, model: gemini-3.1-pro", '
              '"status": "RESOURCE_EXHAUSTED", "details": [{"retryDelay": "28s"}]}}')


def vector(n):
    return SimpleNamespace(data=[{"embedding": [0.0] * n}])


class KeyHintTests(unittest.TestCase):
    def test_hints(self):
        hint = providers.key_hint
        self.assertIsNone(hint("openai", None))
        self.assertIsNone(hint("openai", "sk-proj-abcdefghijklmnopqrstuvwxyz"))
        self.assertIsNone(hint("gemini", GEMINI_KEY))
        self.assertIsNone(hint("anthropic", "sk-ant-api03-abcdefghijklmnop"))
        self.assertEqual(hint("openai", "sk-ant-api03-abcdefghijklmnop"), {"code": "key.wrongProvider", "params": {"looks_like": "anthropic"}})
        self.assertEqual(hint("openai", GEMINI_KEY), {"code": "key.wrongProvider", "params": {"looks_like": "gemini"}})
        self.assertEqual(hint("gemini", "sk-proj-abc123abc123"), {"code": "key.wrongProvider", "params": {"looks_like": "openai"}})
        self.assertEqual(hint("openai", "0123456789abcdef0123456789abcdef"), {"code": "key.looksAzure", "params": {}})
        self.assertEqual(hint("anthropic", "A" * 84), {"code": "key.looksAzure", "params": {}})
        self.assertEqual(hint("openai", " sk-proj-abc"), {"code": "key.hasSpaces", "params": {}})
        self.assertEqual(hint("gemini", "AIza abc"), {"code": "key.hasSpaces", "params": {}})
        self.assertIsNone(hint("ollama", "0123456789abcdef0123456789abcdef"))
        self.assertIsNone(hint("custom", "0123456789abcdef0123456789abcdef"))
        self.assertIsNone(hint("mistral", "AbCdEfGh" * 4))     # a real Mistral key shape

    def test_hints_name_the_second_key(self):
        self.assertIn("paid key", providers.PROVIDERS["gemini"]["key_hint"])
        self.assertIn("mentor", providers.PROVIDERS["gemini"]["key_hint"])
        self.assertTrue(providers.PROVIDERS["anthropic"]["key_hint"].startswith("Claude needs a second key"))


class EndpointValidationTests(unittest.TestCase):
    GOOD = {"mentor_model": "azure_ai/gpt-4o", "extract_model": "azure_ai/gpt-4o-mini", "embed_model": "azure_ai/text-embedding-3-large",
            "embed_dim": 3072, "key_env": "AZURE_AI_API_KEY"}

    def test_api_base(self):
        for good in ("https://x.services.ai.azure.com/models", "https://openrouter.ai/api/v1", "http://host.docker.internal:1234/v1",
                     "http://localhost:11434", "http://127.0.0.1:8080", None, ""):
            with self.subTest(good=good):
                self.assertIsNone(providers.validate_custom({**self.GOOD, "api_base": good}))
        for bad in ("http://example.com/v1", "ftp://x", "https://", "https://a b", "javascript:alert(1)", "https://x.com/" + "a" * 300):
            with self.subTest(bad=bad):
                self.assertIsNotNone(providers.validate_custom({**self.GOOD, "api_base": bad}))

    def test_api_version(self):
        self.assertIsNone(providers.validate_endpoint(None, "2024-10-21"))
        self.assertIsNone(providers.validate_endpoint(None, "2025-01-01-preview"))
        self.assertIsNotNone(providers.validate_endpoint(None, "2024 10"))

    def test_preset_model_override_is_validated(self):
        self.assertEqual(auth._preset_models({"mentor_model": "gemini/gemini-3.7-flash"}), {"mentor_model": "gemini/gemini-3.7-flash"})
        self.assertEqual(auth._preset_models({"mentor_model": None, "extract_model": ""}), {})
        with self.assertRaises(HTTPException):
            auth._preset_models({"mentor_model": "not a model;"})


class PutSettingsTests(unittest.TestCase):
    def put(self, current, **body):
        request = SimpleNamespace(state=SimpleNamespace(person_id="owner"))
        with patch.object(auth, "person_public", return_value={"id": "owner", "is_admin": True}), \
                patch.object(auth.settings, "get", return_value=current), \
                patch.object(auth.settings, "update", side_effect=lambda changes: changes), \
                patch.object(auth.graph, "ensure_vector_index"):
            return auth.put_settings(auth.SettingsPatch(**body), request)

    def test_preset_keeps_mentor_override_and_drops_endpoint(self):
        current = {"provider": "gemini", "embed_provider": "gemini", "mentor_key": GEMINI_KEY}
        changes = self.put(current, mentor_model="gemini/gemini-3.7-flash", api_base="https://x.example.com")
        self.assertEqual(changes, {"mentor_model": "gemini/gemini-3.7-flash"})
        with self.assertRaises(HTTPException):
            self.put(current, mentor_model="bad model id")

    def test_switching_preset_resets_an_old_override(self):
        current = {"provider": "gemini", "embed_provider": "gemini", "mentor_key": GEMINI_KEY, "mentor_model": "gemini/gemini-3.7-flash"}
        changes = self.put(current, provider="openai", embed_provider="openai", mentor_key="sk-proj-abc123abc123")
        self.assertEqual(changes["mentor_model"], providers.PROVIDERS["openai"]["mentor"])

    def test_custom_endpoint_is_validated(self):
        current = {"provider": "custom", "embed_provider": "custom", "mentor_key": "abc123secretvalue", **EndpointValidationTests.GOOD}
        changes = self.put(current, api_base="https://x.services.ai.azure.com/models", api_version="2024-10-21")
        self.assertEqual(changes["api_base"], "https://x.services.ai.azure.com/models")
        with self.assertRaises(HTTPException) as ctx:
            self.put(current, api_base="http://example.com")
        self.assertEqual(ctx.exception.status_code, 400)


class SettingsApplyTests(unittest.TestCase):
    def setUp(self):
        saved = {k: getattr(llm, k) for k in ("MENTOR_MODEL", "EXTRACT_MODEL", "EMBED_MODEL", "EMBED_DIM", "API_BASE", "API_VERSION", "API_KEY_ENV", "CUSTOM_MODELS")}
        cache = dict(settings._cache)
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        for k in ("MENTOR_MODEL", "EXTRACT_MODEL", "EMBED_MODEL", "EMBED_DIM", "GEMINI_API_KEY", "AZURE_AI_API_KEY"):
            os.environ.pop(k, None)

        def restore():
            env.stop()
            for k, v in saved.items():
                setattr(llm, k, v)
            settings._cache = cache
        self.addCleanup(restore)

    def test_preset_mentor_override_survives_apply(self):
        settings._cache = {"provider": "gemini", "embed_provider": "gemini", "mentor_key": "k" * 39, "mentor_model": "gemini/gemini-3.7-flash"}
        settings.apply()
        self.assertEqual(llm.MENTOR_MODEL, "gemini/gemini-3.7-flash")
        self.assertEqual(llm.EXTRACT_MODEL, providers.PROVIDERS["gemini"]["extract"])
        self.assertIsNone(llm.API_BASE)
        self.assertEqual(llm.endpoint(llm.MENTOR_MODEL), {})

    def test_custom_endpoint_is_applied_per_call_and_public(self):
        settings._cache = {"provider": "custom", "embed_provider": "custom", "mentor_key": "secret-azure-key-123",
                           **EndpointValidationTests.GOOD, "api_base": "https://x.services.ai.azure.com/models", "api_version": "2024-10-21"}
        settings.apply()
        self.assertEqual(llm.endpoint("azure_ai/gpt-4o"), {"api_base": "https://x.services.ai.azure.com/models",
                                                          "api_version": "2024-10-21", "api_key": "secret-azure-key-123"})
        self.assertEqual(llm.endpoint("gemini/gemini-3.7-flash"), {})
        self.assertNotEqual(os.environ.get("OLLAMA_API_BASE"), "https://x.services.ai.azure.com/models")
        public = settings.public()
        self.assertEqual(public["api_base"], "https://x.services.ai.azure.com/models")
        self.assertNotIn("secret-azure-key-123", str(public))


class CheckProviderTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(auth.router)
        self.client = TestClient(app)
        auth._check_attempts.clear()
        self.setup_needed = patch.object(auth, "setup_needed", return_value=True)
        self.setup_needed.start()
        self.addCleanup(self.setup_needed.stop)
        self.calls = []
        self.fail = {}                  # model -> exception
        self.dim = None

        def completion(**kw):
            self.calls.append(kw)
            if kw["model"] in self.fail:
                raise self.fail[kw["model"]]
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="OK"))])

        def embedding(**kw):
            self.calls.append(kw)
            if kw["model"] in self.fail:
                raise self.fail[kw["model"]]
            return vector(self.dim or kw["dimensions"])
        for name, fn in (("completion", completion), ("embedding", embedding)):
            p = patch.object(provider_check.litellm, name, fn)
            p.start()
            self.addCleanup(p.stop)

    def check(self, **body):
        resp = self.client.post("/auth/check-provider", json=body)
        return resp.status_code, resp.json()

    def test_all_ok_with_the_key_passed_explicitly(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            status, out = self.check(provider="gemini", mentor_key=GEMINI_KEY)
            self.assertNotIn("GEMINI_API_KEY", os.environ)
        self.assertEqual(status, 200)
        self.assertTrue(out["ok"])
        self.assertEqual([c["name"] for c in out["checks"]], ["extract", "mentor", "embed"])
        self.assertEqual([c["model"] for c in out["checks"]], [providers.PROVIDERS["gemini"][k] for k in ("extract", "mentor", "embed")])
        self.assertIsNone(out["key_hint"])
        self.assertIsNone(out["suggest"])
        self.assertEqual(len(self.calls), 3)
        for call in self.calls:
            self.assertEqual(call["api_key"], GEMINI_KEY)
            self.assertLessEqual(call["timeout"], 30)
        self.assertTrue(all(c.get("num_retries", c.get("max_retries")) == 0 for c in self.calls))
        self.assertLessEqual(max(c.get("max_tokens", 0) for c in self.calls), 16)

    def test_auth_failure(self):
        bad = litellm.AuthenticationError("Incorrect API key provided: sk-proj-abc...wxyz", "openai", "gpt-5.5")
        self.fail = {providers.PROVIDERS["openai"][k]: bad for k in ("extract", "mentor", "embed")}
        status, out = self.check(provider="openai", mentor_key="sk-ant-api03-abcdefghijklmnop")
        self.assertEqual(status, 200)
        self.assertFalse(out["ok"])
        self.assertEqual({c["code"] for c in out["checks"]}, {"provider.auth"})
        self.assertEqual(out["key_hint"], {"code": "key.wrongProvider", "params": {"looks_like": "anthropic"}})
        self.assertNotIn("sk-ant-api03-abcdefghijklmnop", str(out))

    def test_mentor_quota_zero_suggests_the_extract_model(self):
        spec = providers.PROVIDERS["gemini"]
        self.fail = {spec["mentor"]: litellm.RateLimitError(LIMIT_ZERO, "gemini", "gemini-3.1-pro-preview")}
        status, out = self.check(provider="gemini", mentor_key=GEMINI_KEY)
        checks = {c["name"]: c for c in out["checks"]}
        self.assertFalse(out["ok"])
        self.assertTrue(checks["extract"]["ok"] and checks["embed"]["ok"])
        self.assertEqual(checks["mentor"]["code"], "provider.quotaZero")
        self.assertEqual(out["suggest"], {"mentor_model": spec["extract"], "reason": "provider.quotaZero"})

    def test_mentor_override_is_checked_once(self):
        flash = providers.PROVIDERS["gemini"]["extract"]
        status, out = self.check(provider="gemini", mentor_key=GEMINI_KEY, mentor_model=flash)
        self.assertTrue(out["ok"])
        self.assertEqual(out["checks"][1]["model"], flash)
        self.assertEqual(len([c for c in self.calls if "messages" in c]), 1)

    def test_embedding_size_mismatch(self):
        self.dim = 768
        status, out = self.check(provider="gemini", mentor_key=GEMINI_KEY)
        embed = out["checks"][2]
        self.assertFalse(out["ok"])
        self.assertEqual(embed["code"], "provider.embedDim")
        self.assertEqual((embed["params"]["expected"], embed["params"]["got"]), (3072, 768))

    def test_anthropic_uses_the_second_key_for_embeddings(self):
        status, out = self.check(provider="anthropic", mentor_key="sk-ant-api03-abcdefghijklmnop", embed_provider="gemini", embed_key=GEMINI_KEY)
        self.assertTrue(out["ok"])
        embed_call = next(c for c in self.calls if "input" in c)
        self.assertEqual(embed_call["api_key"], GEMINI_KEY)
        status, _ = self.check(provider="anthropic", mentor_key="sk-ant-api03-abcdefghijklmnop")
        self.assertEqual(status, 400)

    def test_custom_passes_endpoint(self):
        body = {**EndpointValidationTests.GOOD, "provider": "custom", "mentor_key": "abc123secretvalue",
                "api_base": "https://x.services.ai.azure.com/models", "api_version": "2024-10-21"}
        status, out = self.check(**body)
        self.assertTrue(out["ok"])
        for call in self.calls:
            self.assertEqual((call["api_base"], call["api_version"], call["api_key"]),
                             ("https://x.services.ai.azure.com/models", "2024-10-21", "abc123secretvalue"))
        status, out = self.check(**{**body, "api_base": "http://evil.example.com"})
        self.assertEqual(status, 400)

    def test_ollama_needs_no_key(self):
        status, out = self.check(provider="ollama")
        self.assertTrue(out["ok"])
        self.assertTrue(all("api_key" not in c and c["api_base"] == "http://host.docker.internal:11434" for c in self.calls))

    def test_after_setup_only_the_owner(self):
        self.setup_needed.stop()
        with patch.object(auth, "setup_needed", return_value=False):
            status, _ = self.check(provider="gemini", mentor_key=GEMINI_KEY)
        self.setup_needed.start()
        self.assertEqual(status, 403)
        self.assertEqual(self.calls, [])

    def test_rate_limited(self):
        for _ in range(10):
            self.check(provider="gemini", mentor_key=GEMINI_KEY)
        status, out = self.check(provider="gemini", mentor_key=GEMINI_KEY)
        self.assertEqual(status, 429)
        self.assertEqual(out["detail"]["code"], "check.tooMany")

    def test_stored_key_only_for_its_own_provider(self):
        stored = {"provider": "gemini", "embed_provider": "gemini", "mentor_key": GEMINI_KEY}
        body = auth.ProviderCheck(provider="gemini", use_stored_keys=True)
        self.assertEqual(auth._check_plan(body, stored)["mentor_key"], GEMINI_KEY)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            with self.assertRaises(HTTPException):
                auth._check_plan(auth.ProviderCheck(provider="openai", use_stored_keys=True), stored)


if __name__ == "__main__":
    unittest.main()
