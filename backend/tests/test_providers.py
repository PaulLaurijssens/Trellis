import importlib.util, unittest
from pathlib import Path

# providers.py has no dependencies: load it by path so the test runs on the host and in the container.
_spec = importlib.util.spec_from_file_location("providers_under_test", Path(__file__).resolve().parents[1] / "app/providers.py")
providers = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(providers)

GOOD = {"mentor_model": "openrouter/deepseek/deepseek-chat", "extract_model": "openrouter/qwen/qwen3-8b",
        "embed_model": "openai/text-embedding-3-small", "embed_dim": 1536, "key_env": "OPENROUTER_API_KEY"}


class CustomProviderTests(unittest.TestCase):
    def test_good_values_pass(self):
        self.assertIsNone(providers.validate_custom(GOOD))
        self.assertIsNone(providers.validate_custom({**GOOD, "key_env": None}))       # local model, no key

    def test_bad_values_fail(self):
        for field, value in (("mentor_model", ""), ("extract_model", "has space"), ("embed_model", "x;rm -rf"),
                             ("embed_dim", 0), ("embed_dim", "1536"), ("embed_dim", 100000),
                             ("key_env", "PATH"), ("key_env", "LD_PRELOAD"), ("key_env", "lower_api_key"),
                             ("key_env", "NEO4J_API_KEY"), ("key_env", "TRELLIS_KEY")):
            with self.subTest(field=field, value=value):
                self.assertIsNotNone(providers.validate_custom({**GOOD, field: value}))

    def test_spec_builds_a_preset_shaped_dict(self):
        spec = providers.spec(providers.CUSTOM, GOOD)
        self.assertEqual((spec["mentor"], spec["extract"], spec["embed"], spec["embed_dim"], spec["key_env"]),
                         (GOOD["mentor_model"], GOOD["extract_model"], GOOD["embed_model"], 1536, "OPENROUTER_API_KEY"))
        self.assertFalse(spec["voice"] or spec["video"])
        self.assertIs(providers.spec("gemini"), providers.PROVIDERS["gemini"])
        self.assertIsNone(providers.spec(None)); self.assertIsNone(providers.spec("nope"))


if __name__ == "__main__":
    unittest.main()
