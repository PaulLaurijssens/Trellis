import importlib.util, sys, types, time, unittest
from pathlib import Path

# Inside the container the real package imports (and settings.session_secret needs no database once
# patched). On a host without neo4j/fastapi, stub the package under another name so nothing pollutes
# sys.modules["app"] for the other test modules.
try:
    from app import auth, settings as _settings
    _settings._cache = {"session_secret": "unit-test-secret"}
except ImportError:
    pkg = types.ModuleType("authtest"); pkg.__path__ = []
    graph = types.ModuleType("authtest.graph"); settings = types.ModuleType("authtest.settings"); providers = types.ModuleType("authtest.providers")
    settings.session_secret = lambda: b"unit-test-secret"; providers.PROVIDERS = {}; providers.EMBEDDING_PROVIDERS = []; providers.public = lambda: {}
    sys.modules.update({"authtest": pkg, "authtest.graph": graph, "authtest.settings": settings, "authtest.providers": providers})
    spec = importlib.util.spec_from_file_location("authtest.auth", Path(__file__).resolve().parents[1] / "app/auth.py")
    auth = importlib.util.module_from_spec(spec); sys.modules["authtest.auth"] = auth; spec.loader.exec_module(auth)


class AuthTests(unittest.TestCase):
    def test_password_hash_round_trip_and_rejects_others(self):
        stored = auth.hash_password("correct horse battery")
        self.assertTrue(stored.startswith("scrypt$"))
        self.assertTrue(auth.verify_password("correct horse battery", stored))
        self.assertFalse(auth.verify_password("correct horse batterx", stored))
        self.assertFalse(auth.verify_password("x", None)); self.assertFalse(auth.verify_password("x", "garbage"))
        self.assertNotEqual(stored, auth.hash_password("correct horse battery"))     # salted

    def test_token_round_trip_tamper_and_expiry(self):
        token = auth.issue_token("paul")
        self.assertEqual(auth.read_token(token), "paul")
        payload, sig = token.rsplit(".", 1)
        self.assertIsNone(auth.read_token(payload + "." + sig[:-2] + "xx"))
        self.assertIsNone(auth.read_token(payload[:-3] + "abc." + sig))
        self.assertIsNone(auth.read_token(None)); self.assertIsNone(auth.read_token("nodot"))
        old = auth.SESSION_DAYS; auth.SESSION_DAYS = -1
        try: self.assertIsNone(auth.read_token(auth.issue_token("paul")))
        finally: auth.SESSION_DAYS = old

    def test_slug(self):
        self.assertEqual(auth.slug("Émile Zola!"), "emile-zola"); self.assertEqual(auth.slug("   "), "learner")


if __name__ == "__main__":
    unittest.main()
