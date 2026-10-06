"""Check failures in plain words, and which failed lessons may be opened anyway."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("teach_issues", Path(__file__).resolve().parents[1] / "app/teach/issues.py")
issues = importlib.util.module_from_spec(spec)
spec.loader.exec_module(issues)


class IssueTests(unittest.TestCase):
    def test_validator_messages_get_a_kind(self):
        cases = {
            "step 3: unreadable text 'Loss' (contrast 2.1:1, need 3:1) - use var(--text-1)": "contrast",
            "step 2: touch target too small (28x28 px): button 'Next'; use .dl-btn": "small_button",
            "step 4: scrolls horizontally by 40 px on a phone": "sideways",
            "browser error: Cannot read properties of undefined (reading 'x')": "script_error",
            "lesson.ready was not received within 10 s: load the SDK": "slow_start",
            "unknown asset: assets/trellis-lesson/1.1.0/fonts.css (read assets/README.md for what exists)": "unknown_block",
            "fetch() is not allowed: lessons have no network": "unsafe_code",
            'activity "a2" is in the manifest but has no <section data-dl-activity="a2">': "missing_part",
            "manifest.json is not valid JSON": "description",
            "something new": "other",
        }
        for message, kind in cases.items():
            self.assertEqual(issues.kind_of(message), kind, message)

    def test_summary_groups_kinds_and_steps(self):
        out = issues.summarize(["step 3: unreadable text 'a'", "step 1: unreadable text 'b'", "step 3: unreadable text 'c'",
                                "browser error: x"])
        self.assertEqual(out, [{"kind": "contrast", "steps": [1, 3]}, {"kind": "script_error", "steps": []}])

    def test_only_quality_problems_may_be_opened(self):
        self.assertTrue(issues.can_open(["step 3: unreadable text 'a'", "browser error: x", "lesson.ready was not received within 10 s"]))
        self.assertFalse(issues.can_open(["eval() is not allowed"]))
        self.assertFalse(issues.can_open(["phone: the lesson did not load"]))
        self.assertFalse(issues.can_open(["manifest.json is missing: write it next to index.html"]))


if __name__ == "__main__":
    unittest.main()
