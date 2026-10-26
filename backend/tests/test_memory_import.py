import unittest

try:
    from app import memory_import, memory_model
except ImportError:
    memory_import = None


def ledger(**over):
    doc = {"version": 2, "baseline": {}, "legacy": [], "sessions": {}, "runs": {}, "corrections": {},
           "intent": "learning", "self_assessment": None}
    doc.update(over)
    return doc


def session(evidence_seq, summary="s"):
    return {"evidence": [{"id": f"e{evidence_seq}", "kind": "explain", "outcome": "demonstrated", "quote": "q",
                          "seq": evidence_seq, "session_id": "s1", "date": "2026-10-01"}],
            "observations": [], "changes": [], "covered": ["a"], "summary": summary, "date": "2026-10-01"}


@unittest.skipIf(memory_import is None, "needs the backend packages")
class ImportMergeTests(unittest.TestCase):
    def test_validate_refuses_other_files_and_newer_versions(self):
        for bad in ({}, {"format": "other"}, {"format": "trellis-learning-memory"}):
            with self.assertRaises(memory_import.ImportProblem):
                memory_import.validate(bad)
        with self.assertRaisesRegex(memory_import.ImportProblem, "version 2"):
            memory_import.validate({"format": "trellis-learning-memory", "version": 2})
        with self.assertRaisesRegex(memory_import.ImportProblem, "twice"):
            memory_import.validate({"format": "trellis-learning-memory", "version": 1,
                                    "map": {"concepts": [{"id": "a", "name": "X"}, {"id": "b", "name": "x"}]}})

    def test_read_refuses_a_zip_without_memory_json_and_non_json(self):
        import io, zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("other.txt", "x")
        with self.assertRaisesRegex(memory_import.ImportProblem, "memory.json"):
            memory_import.read(buf.getvalue())
        with self.assertRaises(memory_import.ImportProblem):
            memory_import.read(b"not json")

    def test_remap_rewrites_session_and_attempt_ids(self):
        doc = ledger(sessions={"s1": session(1)},
                     runs={"r1": {"evidence": [{"id": "x", "attempt_id": "a1", "assessment_id": "a1"}]}})
        out = memory_import.remap_ledger(doc, {"s1": "s2"}, {"a1": "a2"})
        self.assertEqual(list(out["sessions"]), ["s2"])
        self.assertEqual(out["sessions"]["s2"]["evidence"][0]["session_id"], "s2")
        self.assertEqual(out["runs"]["r1"]["evidence"][0]["attempt_id"], "a2")
        self.assertEqual(doc["sessions"]["s1"]["evidence"][0]["session_id"], "s1", "input stays untouched")

    def test_merge_keeps_current_on_conflict_and_unions_the_rest(self):
        current = ledger(sessions={"s1": session(1, "mine")}, intent="queued", baseline={"summary": "here", "quiz_correct": 2})
        incoming = ledger(sessions={"s1": session(1, "theirs"), "s2": session(3)}, intent="learning",
                          baseline={"summary": "there", "quiz_correct": 5})
        out = memory_import.merge_ledgers(current, incoming)
        self.assertEqual(out["sessions"]["s1"]["summary"], "mine")
        self.assertIn("s2", out["sessions"])
        self.assertEqual(out["intent"], "queued")
        self.assertEqual(out["baseline"]["summary"], "here")
        self.assertEqual(out["baseline"]["quiz_correct"], 5)
        grown = memory_import.merge_ledgers(current, incoming, {"s1"})
        self.assertEqual(grown["sessions"]["s1"]["summary"], "theirs")

    def test_same_legacy_observation_keeps_the_local_id_and_its_correction_follows(self):
        here = {"id": "L-here", "kind": "struggles", "text": "Sign confusion", "state": "active", "origin": "legacy", "evidence_ids": []}
        there = {**here, "id": "L-there", "text": "sign  confusion"}
        out = memory_import.merge_ledgers(ledger(legacy=[here]),
                                          ledger(legacy=[there], corrections={"L-there": {"state": "resolved"}}))
        self.assertEqual([o["id"] for o in out["legacy"]], ["L-here"])
        self.assertEqual(out["corrections"], {"L-here": {"state": "resolved"}})
        projected = memory_model.project(out)
        self.assertEqual(projected["struggles"], [])

    def test_a_tombstone_from_the_file_never_hides_what_the_learner_has_here(self):
        out = memory_import.merge_ledgers(ledger(baseline={"covered": ["Chain rule"]}),
                                          ledger(baseline={"covered": ["Other"], "removed": ["chain rule", "Gone"]}))
        self.assertEqual(out["baseline"]["removed"], ["Gone"])
        self.assertIn("Chain rule", out["baseline"]["covered"])
        profile = memory_import.merge_profile({"works_well": ["Numbers"], "removed": []},
                                              {"works_well": ["Pictures"], "removed": ["numbers"], "notes": "n"})
        self.assertEqual(profile["works_well"], ["Numbers", "Pictures"])
        self.assertEqual(profile["notes"], "n")

    def test_claims_are_merged_by_id(self):
        out = memory_import.merge_ledgers(ledger(claims=[{"id": "c1", "text": "a", "date": "1"}]),
                                          ledger(claims=[{"id": "c1", "text": "b", "date": "1"}, {"id": "c2", "text": "c", "date": "2"}]))
        self.assertEqual([(c["id"], c["text"]) for c in out["claims"]], [("c1", "a"), ("c2", "c")])

    def test_person_status_matches_the_learning_position_rule(self):
        self.assertEqual(memory_import.person_status({"self_assessment": {"value": "understood"}, "intent": "queued"}), "learned")
        self.assertEqual(memory_import.person_status({"intent": "interested"}), "suggested")
        self.assertEqual(memory_import.person_status({"intent": "queued"}), "queued")
        self.assertEqual(memory_import.person_status({}), "learning")


if __name__ == "__main__":
    unittest.main()
