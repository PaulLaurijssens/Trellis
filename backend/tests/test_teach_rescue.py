"""A lesson that did not pass is never thrown away: a free final check may still publish it; otherwise it is
kept as a draft that can be opened anyway (quality problems only) or fixed from where it stopped."""
import unittest
from unittest.mock import MagicMock, patch

from app.teach import orchestrator, worker

JOB = "0f8fad5b-d9cb-469f-a165-70867728950e"
MANIFEST = {"title": "T", "sources": [], "activities": []}


class RescueTests(unittest.TestCase):
    def setUp(self):
        self.job = orchestrator.Job("p1", JOB, {"concept_id": "c1", "language": "en", "device": "desktop"})
        self.job.topic, self.job.objective, self.job.dirty = {"id": "t1"}, None, False
        self.store = MagicMock()
        for target, value in ((worker, "list_files"), (worker, "read_file"), (worker, "bundle"), (worker, "validate"),
                              (orchestrator.artifacts, "store_draft")):
            p = patch.object(target, value)
            self.addCleanup(p.stop)
            setattr(self, value, p.start())
        self.list_files.return_value = ["index.html", "lesson.js", "manifest.json"]
        self.read_file.return_value = "content"
        self.bundle.return_value = {"errors": [], "html": "<html></html>", "sha256": "abc"}
        p = patch.object(orchestrator.Job, "_manifest", return_value=MANIFEST)
        self.addCleanup(p.stop)
        self.manifest = p.start()

    def kept(self):
        return self.store_draft.call_args[0][1]

    def test_quality_problems_are_kept_and_can_be_opened(self):
        self.job.report = {"ok": False, "errors": ["step 2: unreadable text 'x' (contrast 2:1, need 3:1)"]}
        self.job._rescue()
        self.validate.assert_not_called()                     # nothing changed since the last check: no re-run
        self.assertEqual(self.job.draft, {"issues": [{"kind": "contrast", "steps": [2]}], "can_open": True})
        self.assertEqual(self.kept()["html"], "<html></html>")
        self.assertEqual(set(self.kept()["files"]), {"index.html", "lesson.js", "manifest.json"})

    def test_a_final_check_that_passes_publishes_without_the_model(self):
        self.job.dirty = True
        self.validate.return_value = {"ok": True, "errors": [], "bundle": {"sha256": "abc"}}
        with patch.object(orchestrator.Job, "_publish_ok_bundle") as publish:
            self.job._rescue()
        publish.assert_called_once()
        self.store_draft.assert_not_called()
        self.assertIsNone(self.job.draft)

    def test_a_slow_start_is_checked_again(self):
        self.job.report = {"ok": False, "errors": ["lesson.ready was not received within 10 s: load the SDK"]}
        self.validate.return_value = {"ok": False, "errors": ["lesson.ready was not received within 10 s: load the SDK"]}
        self.job._rescue()
        self.validate.assert_called_once()
        self.assertTrue(self.job.draft["can_open"])

    def test_unsafe_code_is_kept_for_fixing_but_never_opened(self):
        self.job.report = {"ok": False, "errors": ["eval() is not allowed"]}
        self.job._rescue()
        self.bundle.assert_not_called()
        self.assertFalse(self.job.draft["can_open"])
        self.assertIsNone(self.kept()["html"])

    def test_a_broken_description_file_cannot_be_opened(self):
        self.manifest.side_effect = ValueError("manifest.json is not valid JSON")
        self.job._rescue()
        self.assertEqual(self.job.draft["issues"][0]["kind"], "description")
        self.assertFalse(self.job.draft["can_open"])

    def test_nothing_written_means_nothing_kept(self):
        self.list_files.return_value = []
        self.job._rescue()
        self.store_draft.assert_not_called()
        self.assertIsNone(self.job.draft)


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.job = orchestrator.Job("p1", "job-2", {"repair_of": JOB})
        p = patch.object(worker, "write_file")
        self.addCleanup(p.stop)
        self.write = p.start()

    def test_the_draft_files_return_and_the_author_gets_the_failures(self):
        draft = {"person_id": "p1", "files": {"index.html": "a", "lesson.js": "b"}, "errors": ["step 1: unreadable text 'x'"]}
        with patch.object(orchestrator.artifacts, "read_draft", return_value=draft):
            block = self.job._load_repair()
        self.assertEqual(self.write.call_count, 2)
        self.assertIn("REPAIR", block)
        self.assertIn("step 1: unreadable text 'x'", block)

    def test_someone_elses_draft_is_ignored(self):
        with patch.object(orchestrator.artifacts, "read_draft", return_value={"person_id": "p2", "files": {"index.html": "a"}}):
            self.assertEqual(self.job._load_repair(), "")
        self.write.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class VersionNotesTests(unittest.TestCase):
    """The lesson screen shows "opened without passing every check" and "may not work well on a phone":
    both fields must survive the API's field list (they did not, the first time)."""

    def test_notes_reach_the_lesson_screen(self):
        from app.teach import api, lessons
        version = {"id": "v", "lesson_id": "l", "phone_issues": 2, "open_issues": [{"kind": "contrast", "steps": [1]}]}
        with patch.object(lessons, "get_version", return_value=version):
            out = api.get_version("p1", "l", "v")
        self.assertEqual(out["phone_issues"], 2)
        self.assertEqual(out["open_issues"], [{"kind": "contrast", "steps": [1]}])
