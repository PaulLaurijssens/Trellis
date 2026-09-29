import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location("memory_model",Path(__file__).resolve().parents[1]/"app/memory_model.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class MemoryModelTests(unittest.TestCase):
    def payload(self):
        return {"covered":["Vectors"],"summary":"Next: an example.","evidence":[{"key":"e1","seq":1,"quote":"Two directions","kind":"explain","outcome":"demonstrated","assessment":"Explained the directions","check":True}],"observations":[],"changes":[]}
    def messages(self):return [{"seq":0,"role":"assistant","content":"Explain two directions"},{"seq":1,"role":"user","content":"Two directions can align."}]
    def test_legacy_understanding_never_fabricates_evidence(self):
        doc=m.initialize({"struggles":["Signs"],"quiz_correct":3},"c","learned")
        state=m.project(doc)
        self.assertEqual(state["self_assessment"],{"value":"understood","date":None,"origin":"legacy"})
        self.assertEqual(state["evidence"],[]);self.assertEqual(state["observations"][0]["origin"],"legacy")
    def test_rejects_mentor_quotes_and_fabricated_quotes(self):
        for seq,quote in [(0,"Explain two directions"),(1,"I mastered everything")]:
            payload=self.payload();payload["evidence"][0].update(seq=seq,quote=quote)
            self.assertEqual(m.validate(payload,self.messages(),"s","today")["evidence"],[])
    def test_replay_deduplicates_and_resolutions_keep_proof(self):
        doc=m.initialize({"struggles":["Signs"],"quiz_correct":2},"c")
        payload=self.payload();payload["changes"]=[{"observation_id":doc["legacy"][0]["id"],"state":"resolved","evidence_keys":["e1"]}]
        entry=m.validate(payload,self.messages(),"s","today")
        doc["sessions"]["s"]=entry;first=m.project(doc);doc["sessions"]["s"]=entry
        self.assertEqual(first,m.project(doc));self.assertEqual(first["quiz_correct"],3)
        self.assertEqual(first["struggles"],[]);self.assertEqual(first["observations"][0]["state"],"resolved")
        self.assertTrue(first["observations"][0]["resolution_evidence_ids"])
    def test_corrections_survive_replay_and_recurrence_is_a_new_record(self):
        doc=m.initialize({"struggles":["Signs"]},"c");oid=doc["legacy"][0]["id"]
        doc["corrections"][oid]={"state":"resolved"}
        payload=self.payload();payload["observations"]=[{"kind":"struggles","text":"Signs","evidence_keys":["e1"]}]
        doc["sessions"]["later"]=m.validate(payload,self.messages(),"later","today")
        state=m.project(doc)
        self.assertEqual(state["struggles"],["Signs"]);self.assertEqual(len(state["observations"]),2)
        self.assertEqual(state["observations"][0]["state"],"resolved")
    def test_resolution_requires_demonstrated_evidence(self):
        payload=self.payload();payload["evidence"][0]["outcome"]="needs_practice"
        payload["changes"]=[{"observation_id":"legacy","state":"resolved","evidence_keys":["e1"]}]
        self.assertEqual(m.validate(payload,self.messages(),"s","today")["changes"],[])
    def test_invalid_schema_is_retryable_not_a_successful_empty_checkpoint(self):
        with self.assertRaises(ValueError):m.validate({"covered":[]},self.messages(),"s","today")

    def test_summary_is_withheld_after_a_correction_until_refreshed(self):
        doc=m.initialize({"struggles":["Signs"],"summary":"Still struggles with signs."},"c")
        oid=doc["legacy"][0]["id"];doc["corrections"][oid]={"state":"resolved"}
        self.assertTrue(m.project(doc)["summary_stale"])
        entry=m.validate(self.payload(),self.messages(),"new","today");entry["summary_inactive_ids"]=[oid]
        doc["sessions"]["new"]=entry
        self.assertFalse(m.project(doc)["summary_stale"])


class ExerciseEvidenceTests(unittest.TestCase):
    """M2: exercise evidence lives in memory_v2.runs, next to the chat sessions."""
    def attempt(self,**over):
        base={"id":"a1","person_id":"p","run_id":"r1","outcome":"demonstrated","assessed_by":"deterministic","assistance_level":"none",
              "uncertainty":"low","prompt_snapshot":"Which weight grows?","occurred_at":"2026-09-28T10:00:00+00:00"}
        base.update(over);return base
    def test_only_owned_assessed_attempts_become_evidence(self):
        attempts={"a1":self.attempt(),"a2":self.attempt(id="a2",person_id="someone"),"a3":self.attempt(id="a3",run_id="other"),
                  "a4":self.attempt(id="a4",assessed_by=None,outcome="pending"),"a5":self.attempt(id="a5",assessed_by="frame")}
        items=[{"attempt_id":k,"activity_type":"quiz"} for k in ["a1","a2","a3","a4","a5","nope"]]
        got=m.validate_run(items,attempts,"r1","p","today")
        self.assertEqual([e["attempt_id"] for e in got],["a1"])
        self.assertEqual(got[0]["origin"],"exercise");self.assertEqual(got[0]["kind"],"recall");self.assertNotIn("quote",got[0])
    def test_assisted_success_is_never_demonstrated(self):
        got=m.validate_run([{"attempt_id":"a1","activity_type":"predict"}],{"a1":self.attempt(assistance_level="hint")},"r1","p","today")
        self.assertEqual(got[0]["outcome"],"assisted")
    def test_projection_counts_unassisted_checks_and_ignores_runs_on_old_docs(self):
        doc=m.initialize({"quiz_correct":1},"c")
        items=m.validate_run([{"attempt_id":"a1","activity_type":"quiz"},{"attempt_id":"a2","activity_type":"quiz"},{"attempt_id":"a3","activity_type":"explain"}],
                             {"a1":self.attempt(),"a2":self.attempt(id="a2",outcome="needs_practice",assessed_by="mentor"),"a3":self.attempt(id="a3",assistance_level="worked_example")},"r1","p","today")
        doc["runs"]["r1"]={"evidence":items,"observations":[],"changes":[],"date":"2026-09-28"}
        state=m.project(doc)
        self.assertEqual(state["quiz_correct"],2);self.assertEqual(state["quiz_wrong"],1)
        self.assertEqual(sorted(e["outcome"] for e in state["evidence"]),["assisted","demonstrated","needs_practice"])
        self.assertEqual(m.project(doc),state)          # replay is deterministic
        del doc["runs"]                                  # a document from before M2 still projects
        self.assertEqual(m.project(doc)["quiz_correct"],1)
