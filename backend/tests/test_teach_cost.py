"""Cost controls of the authoring loop: cache breakpoints, screenshot pruning, token budget, digest."""
import importlib
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

    def test_token_budget_stops_the_loop(self):
        usage = self.llm.Usage()
        self.lite.script = [reply(tool_calls=[call("x")], prompt=900, completion=200), reply(content="never")]
        with self.assertRaises(self.llm.ToolLoopStopped) as stop:
            self.llm.tool_loop("sys", "task", [], lambda n, a: ({}, []), "gemini/x", usage=usage, max_tokens=1000)
        self.assertIn("token budget", str(stop.exception))
        self.assertEqual(usage.total(), 1100)

    def test_usage_counts_cached_tokens(self):
        usage = self.llm.Usage()
        resp = reply(prompt=500)
        resp.usage.prompt_tokens_details = SimpleNamespace(cached_tokens=400)
        usage.add("author", resp)
        self.assertEqual(usage.report()["author"]["cached"], 400)


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
