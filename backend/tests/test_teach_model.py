import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "app/teach"
spec = importlib.util.spec_from_file_location("teach_model", ROOT / "model.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
bspec = importlib.util.spec_from_file_location("bundle", ROOT.parents[2] / "author/bundle.py")
b = importlib.util.module_from_spec(bspec); bspec.loader.exec_module(b)
aspec_src = (ROOT / "artifacts.py").read_text()


def manifest(**over):
    base = {"title": "T", "outcome": "O", "language": "en", "assets": ["dendrite-lesson@1.0.0"], "sources": [],
            "activities": [{"id": "a1", "type": "predict", "title": "Predict", "state_fields": ["choice", "committed"],
                            "events": ["activity.answer_submitted"], "check": {"kind": "choice", "expected": "b"}},
                           {"id": "a2", "type": "manipulate", "title": "Explore", "state_fields": ["a", "b"], "check": {"kind": "none"}}]}
    base.update(over)
    return base


class ObjectiveTests(unittest.TestCase):
    def test_skip_is_a_valid_onboarding_answer_and_bad_choices_are_refused(self):
        self.assertEqual(m.onboarding({})["intent"], None)
        with self.assertRaises(ValueError):
            m.onboarding({"familiarity": "expert"})
        with self.assertRaises(ValueError):
            m.onboarding({"time_budget_min": 45})

    def test_objective_needs_an_observable_outcome_and_allows_theory(self):
        with self.assertRaises(ValueError):
            m.objective({"intent": "understand", "objective_markdown": "x", "observable_outcomes": []})
        ok = m.objective({"intent": "understand", "objective_markdown": "Explain attention", "observable_outcomes": ["Explain it"]})
        self.assertEqual(ok["preferred_depth"], "working")

    def test_template_draft_is_valid_without_a_model(self):
        for intent in m.INTENTS:
            for lang in ("en", "nl"):
                self.assertTrue(m.fallback_objective("Attention", {"intent": intent}, lang)["observable_outcomes"])


class ManifestTests(unittest.TestCase):
    def test_answer_key_never_reaches_the_browser(self):
        public = m.public_manifest(m.manifest(manifest()))
        self.assertNotIn("expected", str(public))
        self.assertEqual(public["activities"][0]["check_kind"], "choice")

    def test_rejects_duplicate_ids_unknown_checkers_and_missing_keys(self):
        bad = manifest(); bad["activities"][1]["id"] = "a1"
        for broken in (bad, manifest(language="de"),
                       manifest(activities=[{"id": "a", "type": "quiz", "title": "Q", "check": {"kind": "python"}}]),
                       manifest(activities=[{"id": "a", "type": "quiz", "title": "Q", "check": {"kind": "choice"}}])):
            with self.assertRaises(ValueError):
                m.manifest(broken)


class FrameInputTests(unittest.TestCase):
    def test_only_declared_flat_fields_are_kept(self):
        full = m.manifest(manifest())
        kept = m.widget_state(full, "a2", {"a": 1.5, "b": "x", "score": 100, "dom": {"a": {"b": {"c": {"d": 1}}}}})
        self.assertEqual(kept, {"a": 1.5, "b": "x"})
        with self.assertRaises(ValueError):
            m.widget_state(full, "nope", {})

    def test_forged_score_cannot_demonstrate_anything(self):
        check = {"kind": "choice", "expected": "b"}
        self.assertEqual(m.check_answer(check, {"score": 100, "correct": True})["outcome"], "needs_practice")
        self.assertEqual(m.check_answer(check, "b")["outcome"], "demonstrated")
        self.assertIsNone(m.check_answer({"kind": "none"}, "anything"))          # exploration is never evidence
        self.assertIsNone(m.check_answer({"kind": "rubric", "rubric": "r"}, "text"))

    def test_deterministic_checkers(self):
        self.assertEqual(m.check_answer({"kind": "numeric_close", "expected": 2, "tolerance": 0.01}, 2.005)["outcome"], "demonstrated")
        self.assertEqual(m.check_answer({"kind": "numeric_close", "expected": 2}, True)["outcome"], "needs_practice")
        self.assertEqual(m.check_answer({"kind": "matrix_close", "expected": [[2, 0], [0, 1]]}, [[2, 0], [0, 1]])["outcome"], "demonstrated")
        self.assertEqual(m.check_answer({"kind": "matrix_close", "expected": [[2, 0], [0, 1]]}, [[2, 0]])["outcome"], "needs_practice")
        self.assertEqual(m.check_answer({"kind": "set_equals", "expected": ["a", "c"]}, ["c", "a"])["outcome"], "demonstrated")
        self.assertEqual(m.check_answer({"kind": "ordering", "expected": ["a", "c"]}, ["c", "a"])["outcome"], "needs_practice")

    def test_assisted_success_stays_distinguishable(self):
        self.assertEqual(m.assistance_level({"hints": 0}), "none")
        self.assertEqual(m.assistance_level({"hints": 2}), "hint")
        self.assertEqual(m.assistance_level({"worked_example": True}), "worked_example")


class BundleTests(unittest.TestCase):
    def test_lint_flags_network_navigation_handlers_and_light_escape_hatches(self):
        errors = b.lint('<a href="https://x.test">x</a><div onclick="x()"></div><iframe></iframe>',
                        "fetch('/api'); window.location.href='https://x'; new Function('x'); localStorage.x=1", "@import url(http://x)")
        text = " ".join(errors)
        for needle in ("fetch()", "navigation", "new Function", "storage", "inline event handlers", "<iframe>", "external URLs", "external CSS"):
            self.assertIn(needle, text)

    def test_lint_allows_ordinary_simulation_code(self):
        self.assertEqual(b.lint("<section><p>x</p></section>", "var player = {location: 3}; player.location = 4; if (a == b) {}", ""), [])

    def test_paths_cannot_leave_the_job_or_touch_assets(self):
        job = Path("/tmp/dendrite-test-job")
        for bad in ("../x.js", "/etc/passwd", "a/../../x", "assets/x.js", ""):
            with self.assertRaises(b.BundleError):
                b.safe_job_path(job, bad)

    def test_csp_is_identical_in_api_and_workbench_and_has_no_unsafe_script(self):
        namespace = {}
        exec(aspec_src[aspec_src.index("def csp("):aspec_src.index("def store_lesson(")], namespace)
        hashes = ["sha256-abc="]
        self.assertEqual(namespace["csp"](hashes), b.csp(hashes))
        policy = b.csp(hashes)
        script = policy.split("script-src")[1].split(";")[0]
        self.assertNotIn("unsafe", script)
        for needle in ("sandbox allow-scripts;", "default-src 'none'", "connect-src 'none'", "form-action 'none'", "frame-ancestors 'self'"):
            self.assertIn(needle, policy)
        self.assertNotIn("allow-same-origin", policy)

    def test_json_data_blocks_are_not_hashed_as_scripts(self):
        html = '<script type="application/json">{"a":1}</script><script>var a=1;</script>'
        self.assertEqual(len(b.script_hashes(html)), 1)


if __name__ == "__main__":
    unittest.main()
