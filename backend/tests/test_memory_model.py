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
