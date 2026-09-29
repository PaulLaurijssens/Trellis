import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

class JourneyTests(unittest.TestCase):
    def setUp(self):
        pkg=types.ModuleType('journey_test_app')
        pkg.__path__=[str(Path(__file__).resolve().parents[1]/'app')]
        self.graph=MagicMock()
        self.modules=patch.dict(sys.modules,{'journey_test_app':pkg,'journey_test_app.graph':self.graph})
        self.modules.start()
        self.journey=importlib.import_module('journey_test_app.journey')
        self.journey.graph=self.graph
        self.graph.memory_transaction.side_effect=lambda pid, fn:fn()
        self.addCleanup(self.modules.stop)

    def test_prerequisites_only_deduplicated_with_real_reasons(self):
        nodes=[{'id':n,'name':n} for n in ['A','B','C','D']]
        edges=[{'source':'A','target':'B','type':'PREREQUISITE_OF','reason':'A explains B'},
          {'source':'B','target':'C','type':'PREREQUISITE_OF'},
          {'source':'D','target':'C','type':'RELATED_TO'}]
        steps,cycle=self.journey.learning_steps(['C','B'],nodes,edges)
        self.assertEqual([s['name'] for s in steps],['A','B','C'])
        self.assertEqual(steps[0]['reason'],'A explains B')
        self.assertFalse(cycle)
        self.assertTrue(all(not s['done'] for s in steps))

    def test_cycles_flagged_and_invalid_targets_rejected(self):
        nodes=[{'id':n,'name':n} for n in ['A','B']]
        edges=[{'source':a,'target':b,'type':'PREREQUISITE_OF'} for a,b in [('A','B'),('B','A')]]
        self.assertTrue(self.journey.learning_steps(['A'],nodes,edges)[1])
        with self.assertRaises(ValueError):self.journey.learning_steps(['Unknown'],nodes,edges)
        with self.assertRaises(ValueError):self.journey.learning_steps([],nodes,edges)

    def test_examples_require_owned_assistant_message(self):
        self.graph.session_info.return_value={'person_id':'someone_else'}
        with self.assertRaises(KeyError):self.journey.save_example('learner','s',0)
        self.graph.run.assert_not_called()
        self.graph.session_info.return_value={'person_id':'learner'}
        self.graph.session_messages.return_value=[{'seq':0,'role':'user','content':'Hi'}]
        with self.assertRaises(ValueError):self.journey.save_example('learner','s',0)
        self.graph.run.assert_not_called()

    def test_source_quotes_remain_distinct_from_summaries(self):
        data=self.journey.source_material([{'source':'Paper','context':'Summary','quotes':'[{"quote":"Exact words","start_sec":12}]'}, {'source':'Other','quotes':'invalid'}])
        self.assertEqual(data[0]['stored_summary'],'Summary')
        self.assertEqual(data[0]['stored_quotes'],[{'quote':'Exact words','start_sec':12}])
        self.assertEqual(data[1]['stored_quotes'],[])

    def test_review_uses_latest_positive_evidence_not_old_failure(self):
        self.graph.run.return_value=[]
        self.graph.all_understands.return_value=[{'concept':'A','evidence':[
          {'outcome':'demonstrated','date':'2000-01-01T00:00:00+00:00','quote':'Old'},
          {'outcome':'demonstrated','date':'2999-01-01T00:00:00+00:00','quote':'New'}]},
          {'concept':'B','evidence':[{'outcome':'needs_practice','date':'2000-01-01','quote':'Wrong'}]}]
        review=self.journey.overview('learner')['review']
        # A: the latest evidence is a fresh success, so nothing is due. B: needs_practice is due after a day.
        self.assertEqual([r['concept'] for r in review],['B']);self.assertEqual(review[0]['kind'],'practice')

    def test_goal_context_and_helpful_examples_are_data_not_mastery(self):
        goal={'title':'Read this paper','source_title':None,'steps':[]}
        with patch.object(self.journey,'active_goal',return_value=goal),patch.object(self.journey,'examples',return_value=[{'example':{'text':'A water analogy','concept':'A','date':'2026-01-01'}}]):
            result=self.journey.prompt_context('learner','A')
        self.assertIn('Read this paper',result)
        self.assertIn('A water analogy',result)
        self.assertIn('not proof of mastery',result)


class RoadmapGoalTests(JourneyTests):
    def test_roadmap_order_kept_and_prerequisites_inserted(self):
        nodes=[{'id':n,'name':n} for n in ['A','B','C','D']]
        edges=[{'source':'A','target':'C','type':'PREREQUISITE_OF'}]
        steps,_=self.journey.learning_steps(['D','C','B'],nodes,edges,160)
        self.assertEqual([s['name'] for s in steps],['D','A','C','B'])

    def test_roadmap_goal_allows_more_steps_than_manual(self):
        nodes=[{'id':f'c{i}','name':f'c{i}'} for i in range(80)]
        ids=[n['id'] for n in nodes]
        with self.assertRaises(ValueError):self.journey.learning_steps(ids,nodes,[],self.journey.MAX_STEPS['manual'])
        self.assertEqual(len(self.journey.learning_steps(ids,nodes,[],self.journey.MAX_STEPS['roadmap'])[0]),80)

    def test_unknown_origin_refused(self):
        with self.assertRaises(ValueError):self.journey.create_goal('p','Course',['A'],None,'weird')


class DueReviewTests(unittest.TestCase):
    def setUp(self):
        import datetime as dt
        self.dt=dt
        self.now=dt.datetime(2026,9,29,tzinfo=dt.timezone.utc)
        pkg=types.ModuleType('journey_due_app');pkg.__path__=[str(Path(__file__).resolve().parents[1]/'app')]
        self.modules=patch.dict(sys.modules,{'journey_due_app':pkg,'journey_due_app.graph':MagicMock()});self.modules.start();self.addCleanup(self.modules.stop)
        self.journey=importlib.import_module('journey_due_app.journey')
    def ev(self,days_ago,outcome,**more):
        return {'outcome':outcome,'date':(self.now-self.dt.timedelta(days=days_ago)).isoformat(),'quote':'said so',**more}
    def state(self,name,evidence):return {'concept':name,'concept_id':name.lower(),'evidence':evidence}
    def test_streak_lengthens_the_gap_and_needs_practice_shortens_it(self):
        states=[self.state('One',[self.ev(2,'demonstrated')]),                                   # streak 1: due after 1 day
                self.state('Two',[self.ev(20,'demonstrated'),self.ev(10,'demonstrated'),self.ev(5,'demonstrated')]),  # streak 3: 7 days, not yet
                self.state('Three',[self.ev(30,'demonstrated'),self.ev(2,'needs_practice')]),   # practice: due after 1 day
                self.state('Four',[self.ev(0,'demonstrated')]),                                  # today: not due
                self.state('Five',[self.ev(3,'demonstrated',outcome_x=1)])]
        due=self.journey.due_reviews(states,self.now)
        names={d['concept']:d for d in due}
        self.assertIn('One',names);self.assertIn('Three',names);self.assertNotIn('Two',names);self.assertNotIn('Four',names)
        self.assertEqual(names['Three']['kind'],'practice');self.assertEqual(names['One']['kind'],'strengthen')
    def test_assisted_success_resets_the_streak_and_exercise_prompt_is_shown(self):
        states=[self.state('A',[self.ev(40,'demonstrated'),self.ev(9,'assisted',origin='exercise',prompt='Which one?',quote=None)])]
        due=self.journey.due_reviews(states,self.now)
        self.assertEqual(due[0]['streak'],0);self.assertEqual(due[0]['quote'],'Which one?');self.assertEqual(due[0]['origin'],'exercise')
    def test_most_overdue_first_and_capped(self):
        states=[self.state(f'C{i}',[self.ev(i+2,'demonstrated')]) for i in range(8)]
        due=self.journey.due_reviews(states,self.now)
        self.assertEqual(len(due),5);self.assertEqual(due[0]['concept'],'C7')
