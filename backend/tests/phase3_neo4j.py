"""Opt-in integration: UUID fixtures only, no model calls, cleanup in finally."""
import json
import uuid
from app import graph, journey

prefix='phase3-'+str(uuid.uuid4())
pid=prefix+'-person'
cids=[prefix+'-'+n for n in ['A','B','C']]
sid=prefix+'-source'
try:
    graph.run('CREATE (:Person {id:$pid})',pid=pid)
    for cid in cids:
        graph.run('CREATE (:Concept {id:$cid,name:$cid,status:"queued"})',cid=cid)
    graph.run('MATCH (a:Concept {id:$a}),(b:Concept {id:$b}) CREATE (a)-[:PREREQUISITE_OF {reason:"Basis for the application"}]->(b)',a=cids[0],b=cids[1])
    graph.run('MATCH (b:Concept {id:$b}) CREATE (s:Source {id:$sid,title:"Fixture paper"}) CREATE (b)-[:MENTIONED_IN {context:"Stored summary",mentions:$quotes}]->(s)',b=cids[1],sid=sid,quotes=json.dumps([{'quote':'Exact source words','start_sec':12}]))
    goal=journey.create_goal(pid,'Understand the fixture paper',[],sid)
    assert [s['concept_id'] for s in goal['steps']]==cids[:2]
    assert goal['steps'][0]['reason']=='Basis for the application'
    assert 'Exact source words' in journey.prompt_context(pid,cids[1])
    session=graph.create_session(pid,cids[1],3)
    seq=graph.add_message(session,'assistant','Imagine a water pipe.')
    assert graph.run('MATCH (:LearningGoal {id:$gid})-[:HAS_SESSION]->(s:ChatSession {id:$sid}) RETURN s.id',gid=goal['id'],sid=session)
    example=journey.save_example(pid,session,seq)
    assert journey.save_example(pid,session,seq)['id']==example['id']
    assert len(journey.examples(pid))==1
    journey.change_example(pid,example['id'],'Imagine two water pipes.')
    prompt=journey.prompt_context(pid,cids[1])
    assert 'Imagine two water pipes.' in prompt and 'Imagine a water pipe.' not in prompt
    assert journey.examples(pid)[0]['example']['original']=='Imagine a water pipe.'
    for operation in [lambda:journey.save_example('not-owner',session,seq),lambda:journey.change_example('not-owner',example['id'],'x'),lambda:journey.patch_goal('not-owner',goal['id'],'active')]:
        try:operation();raise AssertionError('Ownership check missing')
        except KeyError:pass
    updated=journey.patch_goal(pid,goal['id'],concept_id=cids[0],done=True)
    assert updated['steps'][0]['done']
    assert graph.find_concept(cids[0])['status']=='queued'
    journey.patch_goal(pid,goal['id'],status='paused')
    assert journey.active_goal(pid) is None
    other=journey.create_goal(pid,'A second goal',[cids[2]])
    journey.patch_goal(pid,goal['id'],status='active')
    assert journey.active_goal(pid)['id']==goal['id']
    assert next(g for g in journey.goals(pid) if g['id']==other['id'])['status']=='paused'
    before=journey.goals(pid)
    try:journey.create_goal(pid,'Invalid',['missing']);raise AssertionError('Missing concept accepted')
    except ValueError:pass
    assert journey.goals(pid)==before
    recent=journey.overview(pid)['recent']
    assert recent['session_id']==session and not recent['consolidated']
    journey.change_example(pid,example['id'],delete=True)
    assert journey.examples(pid)==[]
    assert 'Imagine two water pipes.' not in journey.prompt_context(pid,cids[1])
    assert graph.session_messages(session)[0]['content']=='Imagine a water pipe.'
    print('PASS: source/prerequisite goal, resumptions, one active goal, ownership, session links, idempotent examples, corrections, deletion, original messages and invalid-create rollback.')
finally:
    graph.run('MATCH (s:ChatSession {person_id:$pid}) OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m) DETACH DELETE m,s',pid=pid)
    graph.run('MATCH (n) WHERE n.person_id=$pid OR n.id IN $ids DETACH DELETE n',pid=pid,ids=[pid,sid,*cids])
