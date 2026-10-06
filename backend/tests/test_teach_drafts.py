"""Failed lessons are kept as drafts on the artifact volume, addressed by job id only."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def load_artifacts(root):
    with patch.dict(os.environ, {"TEACH_ARTIFACT_DIR": root}):
        spec = importlib.util.spec_from_file_location("teach_artifacts_draft", Path(__file__).resolve().parents[1] / "app/teach/artifacts.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.artifacts = load_artifacts(self.root)
        self.job = "0f8fad5b-d9cb-469f-a165-70867728950e"

    def test_store_and_read_back(self):
        self.artifacts.store_draft(self.job, {"files": {"index.html": "<p>hi</p>"}, "errors": ["x"]})
        self.assertEqual(self.artifacts.read_draft(self.job)["files"]["index.html"], "<p>hi</p>")

    def test_missing_draft_is_none(self):
        self.assertIsNone(self.artifacts.read_draft(self.job))

    def test_ids_are_never_paths(self):
        with self.assertRaises(ValueError):
            self.artifacts.store_draft("../../etc/passwd", {})
        self.assertIsNone(self.artifacts.read_draft("../x"))


if __name__ == "__main__":
    unittest.main()
