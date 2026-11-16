"""Lessons use the AI provider chosen in Settings. The lesson models were read once at import, before the
stored provider was applied, so an OpenAI (or any non-Gemini) setup still sent lessons to Gemini without a key."""
import os
import unittest
from unittest.mock import patch

try:
    from app import llm
    from app.teach import orchestrator
except ImportError:      # the "pure" CI job runs test_teach_*.py without the backend's packages; the "backend" job runs this
    raise unittest.SkipTest("needs the backend packages (pip install -r backend/requirements.lock.txt)")


class ProviderModelTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for key in ("TEACH_AUTHOR_MODEL", "TEACH_PLAN_MODEL"):
            os.environ.pop(key, None)
        for name in ("MENTOR_MODEL", "EXTRACT_MODEL"):
            p = patch.object(llm, name, getattr(llm, name))
            p.start()
            self.addCleanup(p.stop)

    def test_follow_the_provider_set_after_import(self):
        llm.MENTOR_MODEL, llm.EXTRACT_MODEL = "openai/gpt-5.5", "openai/gpt-5.4-mini"     # what settings.apply() does
        self.assertEqual(orchestrator.author_model(), "openai/gpt-5.5")
        self.assertEqual(orchestrator.plan_model(), "openai/gpt-5.4-mini")

    def test_env_still_wins(self):
        llm.MENTOR_MODEL = "openai/gpt-5.5"
        os.environ["TEACH_AUTHOR_MODEL"] = "anthropic/claude-sonnet-5-5"
        os.environ["TEACH_PLAN_MODEL"] = "anthropic/claude-haiku-5-5"
        self.assertEqual(orchestrator.author_model(), "anthropic/claude-sonnet-5-5")
        self.assertEqual(orchestrator.plan_model(), "anthropic/claude-haiku-5-5")

    def test_cost_card_names_the_model_in_use(self):
        llm.MENTOR_MODEL = "openai/gpt-5.5"
        self.assertEqual(orchestrator.prices(), (2.5, 10.0))      # the "gpt" row, not Gemini's


if __name__ == "__main__":
    unittest.main()
