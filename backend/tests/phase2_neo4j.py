"""Explicit integration check; temporary UUID fixtures only, no LLM calls."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from app import graph, memory

pid="__phase2_check_"+uuid.uuid4().hex
cid=pid+"_concept";name=cid
sids=[]
def session():
    sid=graph.create_session(pid,cid,3);sids.append(sid)
    graph.add_message(sid,"assistant","Explain the two directions.")
    graph.add_message(sid,"user","Two directions can align.")
    return sid
def payload(*args,**kwargs):
    return {"covered":["Directions"],"summary":"A useful example.","evidence":[{"key":"e","seq":1,"quote":"Two directions can align.","kind":"explain","outcome":"demonstrated","assessment":"Explained alignment","check":True}],"observations":[],"changes":[{"observation_id":oid,"state":"resolved","evidence_keys":["e"]}],"learning_style":{}}
try:
    graph.run("CREATE (p:Person {id:$pid}) CREATE (c:Concept {id:$cid,name:$name,status:'learned'}) CREATE (p)-[:UNDERSTANDS {struggles:['Sign confusion'],quiz_correct:2}]->(c)",pid=pid,cid=cid,name=name)
    initial=graph.understands_state(pid,cid);oid=initial["observations"][0]["id"]
    assert initial["self_assessment"]["origin"]=="legacy" and initial["evidence"]==[]
    sid=session()
    with patch.object(memory,"_distil",side_effect=payload):
        assert memory.consolidate_session(sid)
        assert not memory.consolidate_session(sid)
    state=graph.understands_state(pid,cid)
    assert state["quiz_correct"]==3 and state["struggles"]==[] and len(state["evidence"])==1
    memory.correct_observation(pid,name,oid,"active")
    memory.rebuild(pid)
    assert graph.understands_state(pid,cid)["struggles"]==["Sign confusion"]
    memory.correct_observation(pid,name,oid,"resolved")
    sid2=session()
    before=graph.understands_state(pid,cid)
    with patch.object(memory,"_distil",side_effect=payload),patch.object(memory,"_profile_commit",side_effect=RuntimeError("simulated write failure")):
        try:memory.consolidate_session(sid2);assert False,"expected rollback"
        except memory.ConsolidationError:pass
    assert graph.understands_state(pid,cid)==before and not graph.session_info(sid2)["consolidated"]
    with patch.object(memory,"_distil",side_effect=payload):assert memory.consolidate_session(sid2)
    assert graph.understands_state(pid,cid)["quiz_correct"]==4
    sid3=session();barrier=Barrier(2)
    def concurrent_payload(*a,**kw):barrier.wait(timeout=15);return payload()
    def consolidate():
        try:return memory.consolidate_session(sid3)
        except memory.ConsolidationError:return False
    with patch.object(memory,"_distil",side_effect=concurrent_payload),ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:consolidate(),range(2)))
    assert sum(results)==1,results
    assert graph.understands_state(pid,cid)["quiz_correct"]==5
    sid4=session()
    def changed(*a,**kw):graph.add_message(sid4,"user","One more thought.");return payload()
    with patch.object(memory,"_distil",side_effect=changed):
        try:memory.consolidate_session(sid4);assert False,"expected conflict"
        except memory.ConsolidationError:pass
    assert not graph.session_info(sid4)["consolidated"]
    assert graph.understands_state(pid,cid)["quiz_correct"]==5
    memory.set_learning_position(pid,name,intent="queued",assessment="partial")
    assert graph.find_concept(name)["status"]=="queued"
    assert graph.understands_state(pid,cid)["self_assessment"]["origin"]=="learner"
    memory.patch_understands(pid,name,{"summary":"My own summary","struggles":["My own difficulty"]})
    before=graph.understands_state(pid,cid)
    memory.rebuild(pid);memory.rebuild(pid)
    assert graph.understands_state(pid,cid)==before
    # A bad source aborts replay rather than partially clearing memory.
    graph.run("MATCH (:ChatSession {id:$sid})-[:HAS_MESSAGE]->(m:ChatMessage {seq:1}) SET m.content='changed fixture'",sid=sid)
    try:memory.rebuild(pid);assert False,"expected source check"
    except memory.ConsolidationError:pass
    assert graph.understands_state(pid,cid)==before
    print("PASS: legacy migration, quoted evidence, lifecycle, correction preservation, idempotence, atomic rollback/retry, concurrent commits, message conflict, replay and source-integrity rollback.")
finally:
    graph.run("MATCH (s:ChatSession {person_id:$pid}) OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m) DETACH DELETE m,s",pid=pid)
    graph.run("MATCH (n) WHERE n.id IN [$pid,$cid] DETACH DELETE n",pid=pid,cid=cid)
    graph.driver.close()
