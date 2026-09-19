"""Explicit integration check: temporary Person only; no model calls."""
import uuid
from app import graph,memory
pid='profile-check-'+uuid.uuid4().hex
try:
    memory.patch_profile(pid,{'teaching_preferences':['Code examples'],'preferences':['Legacy preference']})
    memory._profile_commit(pid,'fixture-session',{'works_well':['Worked example'],'preferences':['New mentor observation']})
    profile=graph.learning_profile(pid)
    assert profile['teaching_preferences']==['Code examples']
    assert 'New mentor observation' in profile['preferences']
    memory.patch_profile(pid,{'teaching_preferences':[]})
    memory.rebuild(pid)
    assert graph.learning_profile(pid)['teaching_preferences']==[]
    assert 'New mentor observation' in graph.learning_profile(pid)['preferences']
    print('PASS: chosen preferences remain separate, survive consolidation, and stay deselected after rebuild; mentor observations continue to accumulate.')
finally:
    graph.run('MATCH (p:Person {id:$pid}) DETACH DELETE p',pid=pid)
