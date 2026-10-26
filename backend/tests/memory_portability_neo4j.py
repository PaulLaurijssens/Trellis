"""Integration check for memory export and import on a real database; no LLM calls.

Run against a throwaway database only (it wipes it):
    TRELLIS_TEST_WIPE=yes python tests/memory_portability_neo4j.py
Seeds a learner through the normal code paths (concepts, sources, a consolidated conversation, an
exercise, a correction, a goal, an example, a profile), then checks:
  1. export -> wipe -> import: same personal context, same due reviews, and rebuild() succeeds;
  2. importing the same file again changes nothing;
  3. importing into a second learner on the same install gives new ids, and the first learner is untouched;
  4. the export matches docs/memory-format.schema.json (when jsonschema is installed).
"""
import json
import os
import sys
from unittest.mock import patch

from app import graph, memory, journey, memory_export, memory_import, personal_context

assert os.getenv("TRELLIS_TEST_WIPE") == "yes", "This test wipes the database. Set TRELLIS_TEST_WIPE=yes on a test database."
DIM = 8


def wipe():
    graph.run("MATCH (n) DETACH DELETE n")


def vec(i):
    return [float((i * 7 + k) % 5) + 0.1 for k in range(DIM)]


def seed(pid="paul"):
    graph.run("MERGE (p:Person {id:$pid}) SET p.name='Paul', p.ui_language='en', p.level=3", pid=pid)
    names = ["Attention mechanism", "Softmax", "Backpropagation", "Transformer architecture"]
    ids = {}
    for i, n in enumerate(names):
        ids[n] = graph.upsert_concept(n, f"Definition of {n}.", [n.split()[0] + " alias"] if i == 0 else [], "ml", vec(i), "learning")
    graph.link_concepts(ids["Softmax"], ids["Attention mechanism"], "PREREQUISITE_OF", 1.0, "weights")
    graph.link_concepts(ids["Attention mechanism"], ids["Transformer architecture"], "PREREQUISITE_OF", 1.0, "core block")
    graph.link_concepts(ids["Backpropagation"], ids["Softmax"], "RELATED_TO", 0.5)
    sid_src = graph.create_pending_source("youtube", "Attention explained", "https://example.com/v")
    graph.promote_source(sid_src)
    graph.link_mention(ids["Attention mechanism"], sid_src, "Explains attention", 3, [{"start_sec": 12, "quote": "attention is all"}])
    graph.ensure_understands(pid, ids["Attention mechanism"], 3)
    sid = graph.create_session(pid, ids["Attention mechanism"], 3)
    graph.add_message(sid, "assistant", "What does attention do?")
    graph.add_message(sid, "user", "Each token weighs all other tokens.")
    graph.add_message(sid, "assistant", "Right. And the weights?")
    graph.add_message(sid, "user", "I think the weights are learned parameters.")
    payload = {"covered": ["Query, key, value"], "summary": "Good start on attention.",
               "evidence": [{"key": "e1", "seq": 1, "quote": "Each token weighs all other tokens.", "kind": "explain",
                             "outcome": "demonstrated", "assessment": "Explained the idea", "check": False},
                            {"key": "e2", "seq": 3, "quote": "the weights are learned parameters", "kind": "apply",
                             "outcome": "needs_practice", "assessment": "Confuses weights", "check": True}],
               "observations": [{"kind": "misconceptions", "text": "Thinks attention weights are learned parameters", "evidence_keys": ["e2"]},
                                {"kind": "struggles", "text": "Mixes up keys and values", "evidence_keys": ["e2"]}],
               "changes": [], "learning_style": {"works_well": ["Concrete numbers"], "works_poorly": [], "preferences": ["Python"]}}
    with patch.object(memory, "_distil", return_value=payload):
        assert memory.consolidate_session(sid)
    state = graph.understands_state(pid, ids["Attention mechanism"])
    struggle = next(o for o in state["observations"] if o["kind"] == "struggles")
    memory.correct_observation(pid, "Attention mechanism", struggle["id"], "resolved")
    # An exercise attempt (layer 1) and its evidence (layer 2), as teach/lessons.py writes them.
    graph.run("""CREATE (:ExerciseAttempt {id:'att-1', run_id:'run-1', person_id:$pid, activity_id:'a1', concept_ids:[$cid],
                 prompt_snapshot:'Predict the top weight', response_json:'"token 3"', response_mode:'text', assistance_level:'none',
                 outcome:'demonstrated', assessed_by:'deterministic', uncertainty:'low', rationale:'', occurred_at:$now})""",
              pid=pid, cid=ids["Attention mechanism"], now=graph._now())
    attempt = graph.run("MATCH (a:ExerciseAttempt {id:'att-1'}) RETURN properties(a) AS a")[0]["a"]
    assert memory.record_exercise(pid, "run-1", attempt, "predict") == 1
    memory.set_learning_position(pid, "Attention mechanism", assessment="partial")
    memory.patch_profile(pid, {"notes": "Podcast learner", "teaching_preferences": ["Concrete examples"]})
    memory.set_learning_position(pid, "Softmax", intent="queued")
    journey.create_goal(pid, "Understand transformers", [ids["Transformer architecture"]])
    journey.save_example(pid, sid, 2)
    graph.link_asked_about(pid, ids["Softmax"])
    return ids, sid


def snapshot(pid):
    """What the mentor and the review queue see, without ids that may change."""
    out = {}
    for s in graph.all_understands(pid):
        ctx = personal_context.personal_context(pid, s["concept_id"])
        out[s["concept"]] = {"context": ctx, "summary": s.get("summary"), "struggles": s["struggles"],
                             "misconceptions": s["misconceptions"], "covered": s["covered"],
                             "evidence": sorted((e["kind"], e["outcome"], e.get("quote") or e.get("prompt")) for e in s["evidence"]),
                             "quiz": (s["quiz_correct"], s["quiz_wrong"]), "intent": s["intent"],
                             "self": (s.get("self_assessment") or {}).get("value")}
    out["_review"] = [(r["concept"], r["kind"]) for r in journey.due_reviews(graph.all_understands(pid))]
    out["_profile"] = {k: v for k, v in graph.learning_profile(pid).items() if k != "updated_at"}
    out["_goals"] = [(g["title"], g["status"], [s["name"] for s in g["steps"]]) for g in journey.goals(pid)]
    out["_examples"] = sorted(e["example"]["text"] for e in journey.examples(pid))
    return out


def check_schema(doc):
    """The published JSON Schema (docs/memory-format.schema.json) accepts a real export."""
    try:
        import jsonschema
    except ImportError:
        print("note: jsonschema not installed, schema check skipped (pip install jsonschema)")
        return
    with open(os.path.join(os.path.dirname(__file__), "..", "..", "docs", "memory-format.schema.json")) as f:
        jsonschema.validate(json.loads(json.dumps(doc)), json.load(f))


def main():
    wipe()
    graph.init_schema(os.path.join(os.path.dirname(__file__), "..", "..", "db", "schema.cypher"))
    graph.ensure_vector_index(DIM)
    ids, sid = seed()
    before = snapshot("paul")
    doc = memory_export.build("paul")
    json.dumps(doc)                                   # JSON-ready
    check_schema(doc)
    blob = memory_export.zip_bytes(doc)
    assert blob[:2] == b"PK"
    assert doc["counts"]["conversations"] == 1 and doc["counts"]["exercises"] == 1 and doc["counts"]["goals"] == 1
    assert "embedding" not in json.dumps(doc["map"])
    assert memory.rebuild("paul")["mode"] == "checkpoint_replay"

    # 1. Move to an empty install.
    wipe()
    graph.init_schema(os.path.join(os.path.dirname(__file__), "..", "..", "db", "schema.cypher"))
    graph.ensure_vector_index(DIM)
    graph.run("CREATE (:Person {id:'paul2', name:'Paul', ui_language:'en'})")
    loaded = memory_import.read(blob)
    preview = memory_import.preview(loaded, "paul2")
    assert preview["counts"]["concepts_new"] == 4 and preview["counts"]["conversations_new"] == 1, preview
    assert graph.run("MATCH (c:Concept) RETURN count(c) AS n")[0]["n"] == 0, "preview must not write"
    result = memory_import.apply(loaded, "paul2")
    after = snapshot("paul2")
    assert after == before, json.dumps({"before": before, "after": after}, indent=1, default=str)[:4000]
    assert memory.rebuild("paul2")["mode"] == "checkpoint_replay"
    assert snapshot("paul2") == before, "rebuild after import changed the memory"
    assert graph.session_info(sid)["consolidated"] is True
    assert not memory.consolidate_session(sid), "an imported consolidated session must not be consolidated again"
    assert len(result["new_concept_ids"]) == 4
    assert graph.run("MATCH (c:Concept) WHERE c.embedding IS NULL RETURN count(c) AS n")[0]["n"] == 4
    with patch("app.llm.embed", side_effect=lambda texts, *a, **k: [vec(1) for _ in texts]):
        assert memory_import.embed_missing() == 4
    assert graph.find_similar(vec(1), 2), "imported concepts must be findable by similarity after embedding"

    # 2. The same file again: nothing changes.
    counts = graph.run("MATCH (n) RETURN labels(n)[0] AS l, count(n) AS n ORDER BY l")
    seen = memory_import.preview(memory_import.read(blob), "paul2")["counts"]
    assert seen["understanding_new"] == 0 and seen["understanding_merged"] == 0, seen   # the preview says "nothing new"
    again = memory_import.apply(memory_import.read(blob), "paul2")
    assert again["counts"]["concepts_new"] == 0 and again["counts"]["conversations_new"] == 0, again
    assert graph.run("MATCH (n) RETURN labels(n)[0] AS l, count(n) AS n ORDER BY l") == counts
    assert snapshot("paul2") == before

    # 3. A second learner on the same install imports the same file: new ids, first learner untouched.
    graph.run("CREATE (:Person {id:'heena', name:'Heena', ui_language:'en'})")
    third = memory_import.apply(memory_import.read(blob), "heena")
    assert third["counts"]["conversations_new"] == 1 and third["counts"]["concepts_matched"] == 4, third
    assert snapshot("heena") == before
    assert memory.rebuild("heena")["mode"] == "checkpoint_replay"
    assert snapshot("paul2") == before
    owners = graph.run("MATCH (s:ChatSession) RETURN s.person_id AS p, count(s) AS n ORDER BY p")
    assert owners == [{"p": "heena", "n": 1}, {"p": "paul2", "n": 1}], owners
    leaked = memory_export.build("heena")
    assert all(s["id"] != sid for s in leaked["conversations"]), "heena's export must hold her own session ids"

    # A newer format version is refused with a reason.
    try:
        memory_import.validate({**doc, "version": 99})
        raise AssertionError("expected ImportProblem")
    except memory_import.ImportProblem as exc:
        assert "version 99" in str(exc)
    # Shared status is never taken from the file: only the importer's own understanding raises it.
    statuses = {r["name"]: r["status"] for r in graph.run("MATCH (c:Concept) RETURN c.name AS name, c.status AS status")}
    assert statuses["Attention mechanism"] == "learning" and statuses["Softmax"] == "queued", statuses
    assert "learned" not in statuses.values(), statuses

    grown()
    undo()
    shared_map(doc)
    print("PASS: export, import into an empty install, rebuild, re-import is a no-op, second learner gets own ids, "
          "a newer export adds later messages, Undo restores removed items, the shared map is protected.")


def shared_map(doc):
    """A learner's file cannot rewire concepts that are already on the shared map, cannot plant a
    javascript: link, and cannot borrow another learner's conversation as evidence."""
    graph.run("CREATE (:Person {id:'mallory', name:'M', ui_language:'en'})")
    names = [c["name"] for c in doc["map"]["concepts"]][:2]
    bad = {"format": doc["format"], "version": doc["version"],
           "map": {"concepts": [{"id": "x1", "name": names[0]}, {"id": "x2", "name": names[1]},
                                {"id": "x3", "name": "Junk concept"}],
                   "relations": [{"from": "x3", "to": "x1", "type": "PREREQUISITE_OF"},
                                 {"from": "x1", "to": "x2", "type": "RELATED_TO", "reason": "rewired"},
                                 {"from": "x2", "to": "x1", "type": "PART_OF"}],
                   "sources": [{"id": "src-js", "type": "link", "title": "click", "url": "javascript:alert(1)",
                                "mentions": [{"concept": names[0], "context": "planted"}]}]}}
    before = graph.run("MATCH (a:Concept)-[r]->(b:Concept) WHERE a.name IN $n AND b.name IN $n RETURN count(r) AS n", n=names)[0]["n"]
    seen = memory_import.preview(memory_import.validate(json.loads(json.dumps(bad))), "mallory")
    assert seen["counts"]["relations"] == 1, seen
    assert any("already on this map" in w for w in seen["warnings"]), seen["warnings"]
    memory_import.apply(memory_import.validate(json.loads(json.dumps(bad))), "mallory")
    after = graph.run("MATCH (a:Concept)-[r]->(b:Concept) WHERE a.name IN $n AND b.name IN $n RETURN count(r) AS n", n=names)[0]["n"]
    assert after == before, (before, after)
    assert graph.run("MATCH (:Concept {name:'Junk concept'})-[:PREREQUISITE_OF]->(:Concept {name:$n}) RETURN count(*) AS n", n=names[0])[0]["n"] == 1
    assert graph.run("MATCH (s:Source {id:'src-js'}) RETURN s.url AS url")[0]["url"] is None
    # The new source is this file's own, so its mention of an existing concept is allowed; a mention on
    # an existing source is not (covered by the planner rule), and nothing became clickable.
    victim = graph.run("MATCH (s:ChatSession)-[:HAS_MESSAGE]->(:ChatMessage) WHERE s.person_id <> 'mallory' "
                       "RETURN s.id AS sid, s.person_id AS pid LIMIT 1")[0]
    assert graph.session_messages(victim["sid"], "mallory") == []
    assert graph.session_messages(victim["sid"], victim["pid"])


def fresh(pid):
    wipe()
    graph.init_schema(os.path.join(os.path.dirname(__file__), "..", "..", "db", "schema.cypher"))
    graph.ensure_vector_index(DIM)
    if pid:
        graph.run("CREATE (:Person {id:$pid, name:'Paul', ui_language:'en'})", pid=pid)


def grown():
    """Old install: export, keep chatting in the same conversation, export again. New install: import both."""
    fresh(None)
    ids, sid = seed()
    first = memory_export.zip_bytes(memory_export.build("paul"))
    graph.add_message(sid, "assistant", "Try once more: are the weights learned?")
    graph.add_message(sid, "user", "No, they are computed from queries and keys each time.")
    later = {"covered": ["Weights are computed"], "summary": "Now sees that weights are computed.",
             "evidence": [{"key": "e3", "seq": 5, "quote": "they are computed from queries and keys each time", "kind": "explain",
                           "outcome": "demonstrated", "assessment": "Fixed the misconception", "check": True}],
             "observations": [], "changes": [], "learning_style": {}}
    state = graph.understands_state("paul", ids["Attention mechanism"])
    mis = next(o for o in state["observations"] if o["kind"] == "misconceptions")
    later["changes"] = [{"observation_id": mis["id"], "state": "resolved", "evidence_keys": ["e3"]}]
    with patch.object(memory, "_distil", return_value=later):
        assert memory.consolidate_session(sid)
    expected = snapshot("paul")
    second = memory_export.zip_bytes(memory_export.build("paul"))
    fresh("paul2")
    memory_import.apply(memory_import.read(first), "paul2")
    result = memory_import.apply(memory_import.read(second), "paul2")
    assert result["counts"]["conversations_updated"] == 1, result
    assert [m["seq"] for m in graph.session_messages(sid)] == [0, 1, 2, 3, 4, 5]
    assert snapshot("paul2") == expected, json.dumps({"want": expected, "got": snapshot("paul2")}, indent=1, default=str)[:3000]


def undo():
    """Removing an item and putting it back (Undo) restores it, also after a rebuild."""
    state = graph.understands_state("paul2", graph.find_concept("Attention mechanism")["id"])
    covered = list(state["covered"]); item = covered[0]
    memory.patch_understands("paul2", "Attention mechanism", {"covered": covered[1:]})
    memory.patch_understands("paul2", "Attention mechanism", {"covered": covered})
    memory.rebuild("paul2")
    assert item in graph.understands_state("paul2", state["concept_id"])["covered"]
    kept = ["Concrete numbers"]
    memory.patch_profile("paul2", {"works_well": kept})
    memory.patch_profile("paul2", {"works_well": []})
    memory.patch_profile("paul2", {"works_well": kept})
    memory.rebuild("paul2")
    assert graph.learning_profile("paul2")["works_well"] == kept


if __name__ == "__main__":
    try:
        main()
    finally:
        graph.driver.close()
    sys.exit(0)
