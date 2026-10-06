"""The workbench health check: a job may only start (and spend tokens) when the workbench can see
the shared lesson components. A wrong volume mount once passed the old check, and every lesson then
failed on "unknown asset" after three paid attempts."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("teach_worker", Path(__file__).resolve().parents[1] / "app/teach/worker.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class HealthTests(unittest.TestCase):
    def check(self, answer):
        with patch.object(worker, "_call", side_effect=answer if isinstance(answer, Exception) else None,
                          return_value=None if isinstance(answer, Exception) else answer):
            return worker.healthy()

    def test_healthy_when_components_are_visible(self):
        self.assertTrue(self.check({"ok": True, "assets": True, "components": ["trellis-lesson@1.1.0"]}))

    def test_not_healthy_when_the_workbench_sees_no_components(self):
        with self.assertLogs(worker.log, "WARNING"):
            self.assertFalse(self.check({"ok": True, "assets": False, "components": []}))

    def test_not_healthy_when_the_workbench_does_not_answer(self):
        self.assertFalse(self.check(worker.WorkerError("down")))

    def test_older_workbench_without_the_field_still_counts(self):
        self.assertTrue(self.check({"ok": True}))


class ComposeWiringTests(unittest.TestCase):
    """compose.yaml is the file a new user runs. Skipped where it is not mounted (inside the dev container)."""

    def test_workbench_reads_the_folder_the_api_seeds(self):
        compose = Path(__file__).resolve().parents[2] / "compose.yaml"
        if not compose.exists():
            self.skipTest("compose.yaml not visible here")
        text = compose.read_text()
        self.assertIn("TEACH_ARTIFACT_DIR: /artifacts", text)
        self.assertIn("AUTHOR_ASSETS_DIR: /artifacts/assets", text)
        self.assertIn("- artifacts:/artifacts:ro", text)


if __name__ == "__main__":
    unittest.main()
