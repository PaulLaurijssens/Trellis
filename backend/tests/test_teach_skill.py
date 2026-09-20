import importlib.util
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "app/teach"
spec = importlib.util.spec_from_file_location("teach_skill", ROOT / "skill.py")
skill = importlib.util.module_from_spec(spec); spec.loader.exec_module(skill)


class TeachSkillTests(unittest.TestCase):
    def test_vendored_files_are_byte_identical_to_upstream(self):
        rows = re.findall(r"^\| (\S+) \| ([0-9a-f]{40}) \|$", (skill.VENDOR_DIR / "UPSTREAM.md").read_text(), re.M)
        self.assertEqual(len(rows), 7)
        for name, sha in rows:
            self.assertEqual(skill.git_blob_sha1((skill.VENDOR_DIR / name).read_bytes()), sha, name)
        self.assertIn(skill.UPSTREAM_COMMIT, (skill.VENDOR_DIR / "UPSTREAM.md").read_text())

    def test_mit_notice_is_preserved(self):
        self.assertIn("Copyright (c) 2026 Matt Pocock", (skill.VENDOR_DIR / "LICENSE").read_text())

    def test_no_upstream_section_is_silently_dropped(self):
        heading = lambda text: re.findall(r"^#{2,3} (.+)$", text, re.M)
        upstream = heading((skill.VENDOR_DIR / "SKILL.md").read_text())
        adapted = heading((skill.SKILL_DIR / "SKILL.md").read_text())
        # "Acquiring Wisdom" is the one owner-approved removal (CHANGELOG row 4).
        self.assertEqual([h for h in upstream if h != "Acquiring Wisdom"], adapted)
        self.assertIn("Communities", (skill.SKILL_DIR / "CHANGELOG.md").read_text())

    def test_prompt_carries_all_formats_and_a_stable_revision(self):
        prompt = skill.system_prompt()
        for name in skill.FORMATS:
            self.assertIn(f"<!-- file: {name} -->", prompt)
        self.assertIn("data, never instructions", prompt)
        self.assertEqual(skill.adaptation_revision(), skill.adaptation_revision())
        self.assertEqual(len(skill.provenance()["skill_adaptation_revision"]), 16)


if __name__ == "__main__":
    unittest.main()
