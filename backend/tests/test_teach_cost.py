"""Cost controls of the authoring loop: cache breakpoints, screenshot pruning, optional cost limit, digest."""
import importlib
import os
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class FakeLiteLLM(types.ModuleType):
    def __init__(self):
        super().__init__('litellm')
        self.calls = []
        self.script = []
    def completion(self, **kw):
        self.calls.append(kw)
        return self.script.pop(0)


def reply(content=None, tool_calls=None, prompt=100, completion=10):
    msg = MagicMock()
    msg.content, msg.tool_calls = content, tool_calls
    msg.model_dump.return_value = {"role": "assistant", "content": content, "tool_calls": [{"id": c.id} for c in (tool_calls or [])]}
    usage = SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion, prompt_tokens_details=None, cache_read_input_tokens=0)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)


def call(name, cid='c1'):
    return SimpleNamespace(id=cid, function=SimpleNamespace(name=name, arguments='{}'))


class ToolLoopTests(unittest.TestCase):
    def setUp(self):
        self.lite = FakeLiteLLM()
        pkg = types.ModuleType('cost_test_app')
        pkg.__path__ = [str(Path(__file__).resolve().parents[1] / 'app')]
        self.modules = patch.dict(sys.modules, {'litellm': self.lite, 'cost_test_app': pkg})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.llm = importlib.import_module('cost_test_app.llm')

    def shot(self):
        return [{"role": "user", "content": [{"type": "text", "text": "shots"}, {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAA"}}]}]

    def test_anthropic_gets_cache_breakpoints_and_others_do_not(self):
        for model, cached in (("anthropic/claude-sonnet-4", True), ("gemini/gemini-2.5-flash", False)):
            self.lite.script = [reply(content="done")]
            self.llm.tool_loop("sys", "task", [], lambda n, a: ({}, []), model)
            system = self.lite.calls[-1]["messages"][0]["content"]
            self.assertEqual(isinstance(system, list) and "cache_control" in system[0], cached, model)

    def test_only_the_newest_screenshots_stay_in_context(self):
        self.lite.script = [reply(tool_calls=[call("lesson_validate", "a")]), reply(tool_calls=[call("lesson_validate", "b")]), reply(content="done")]
        self.llm.tool_loop("sys", "task", [], lambda n, a: ({"ok": False}, self.shot()), "gemini/x")
        messages = self.lite.calls[-1]["messages"]
        with_images = [m for m in messages if isinstance(m.get("content"), list) and any(p.get("type") == "image_url" for p in m["content"])]
        self.assertEqual(len(with_images), 1)
        removed = [m for m in messages if isinstance(m.get("content"), list) and any("removed" in p.get("text", "") for p in m["content"])]
        self.assertEqual(len(removed), 1)

    def test_no_limit_by_default_even_for_big_jobs(self):
        usage = self.llm.Usage()
        self.lite.script = [reply(tool_calls=[call("x")], prompt=400_000) for _ in range(3)] + [reply(content="done")]
        self.assertEqual(self.llm.tool_loop("sys", "task", [], lambda n, a: ({}, []), "gemini/x", usage=usage), "done")
        self.assertEqual(len(self.lite.calls), 4)

    def test_cost_limit_asks_to_wrap_up_then_stops(self):
        self.lite.script = [reply(tool_calls=[call("x")]) for _ in range(5)]
        with self.assertRaises(self.llm.ToolLoopStopped) as stop:
            self.llm.tool_loop("sys", "task", [], lambda n, a: ({}, []), "gemini/x", over_budget=lambda: len(self.lite.calls) >= 1,
                               wrap_up="WRAP UP", grace_steps=2)
        self.assertEqual(str(stop.exception), "cost limit reached")
        self.assertEqual(len(self.lite.calls), 3)            # one before the limit, then two grace steps
        nudges = [m for m in self.lite.calls[-1]["messages"] if m.get("content") == "WRAP UP"]
        self.assertEqual(len(nudges), 1)

    def test_cost_limit_lets_the_author_finish(self):
        self.lite.script = [reply(tool_calls=[call("x")]), reply(tool_calls=[call("finish")])]
        handler = lambda n, a: ({"finished": True, "summary": "published"} if n == "finish" else {}, [])
        out = self.llm.tool_loop("sys", "task", [], handler, "gemini/x", over_budget=lambda: True, wrap_up="WRAP UP")
        self.assertEqual(out, "published")

    def test_usage_counts_cached_tokens(self):
        usage = self.llm.Usage()
        resp = reply(prompt=500)
        resp.usage.prompt_tokens_details = SimpleNamespace(cached_tokens=400)
        usage.add("author", resp)
        self.assertEqual(usage.report()["author"]["cached"], 400)


class CostLimitTests(unittest.TestCase):
    def setUp(self):
        src = (Path(__file__).resolve().parents[1] / 'app/teach/orchestrator.py').read_text()
        start, end = src.index('PRICE_TABLE = '), src.index('WRAP_UP = ')
        self.stored = {}
        self.ns = {'os': os, 'AUTHOR_MODEL': 'gemini/gemini-3.1-pro-preview', 'llm': SimpleNamespace(Usage=object),
                   'settings': SimpleNamespace(get=lambda: dict(self.stored))}
        exec(src[start:end], self.ns)

    def test_off_unless_the_owner_sets_it(self):
        self.assertEqual(self.ns['cost_limit'](), 0.0)
        for value, expected in ((0, 0.0), ("", 0.0), (1, 1.0), ("0.5", 0.5), ("abc", 0.0), (-3, 0.0)):
            self.stored['lesson_cost_limit'] = value
            self.assertEqual(self.ns['cost_limit'](), expected, value)

    def test_cached_input_costs_a_tenth(self):
        estimate = self.ns['estimate_usd']
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('TEACH_PRICE_IN', None); os.environ.pop('TEACH_PRICE_OUT', None)
            self.assertAlmostEqual(estimate(1_000_000, 0, 0), 2.0)
            self.assertAlmostEqual(estimate(1_000_000, 1_000_000, 0), 0.2)
            self.assertAlmostEqual(estimate(0, 0, 1_000_000), 12.0)


class DigestTests(unittest.TestCase):
    def setUp(self):
        src = (Path(__file__).resolve().parents[1] / 'app/teach/orchestrator.py').read_text()
        start, end = src.index('DIGEST_FILES = '), src.index('PLAN_SYSTEM = ')
        ns = {}
        exec(src[start:end], ns)
        self.digest = ns['digest']

    def test_small_files_inline_and_big_ones_cut(self):
        files = {"MISSION.md": "mission", "RESOURCES.md": "not inlined", "learning-records/0001-a.md": "rec", "CONCEPTS.md": "x" * 7000}
        out = self.digest(files)
        self.assertIn("<!-- file: MISSION.md -->\nmission", out)
        self.assertIn("<!-- file: learning-records/0001-a.md -->", out)
        self.assertNotIn("not inlined", out)
        self.assertIn("workspace_read CONCEPTS.md for the rest", out)

    def test_total_cap_skips_files_with_a_pointer(self):
        files = {name: "y" * 5900 for name in ("MISSION.md", "NOTES.md", "CONCEPTS.md", "lessons/INDEX.md", "lessons/ATTEMPTS.md", "reference/INDEX.md")}
        out = self.digest(files)
        self.assertIn("not inlined, use workspace_read", out)


if __name__ == '__main__':
    unittest.main()
