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
        self.assertEqual(self.journey.overview('learner')['review'],[])

    def test_goal_context_and_helpful_examples_are_data_not_mastery(self):
        goal={'title':'Read this paper','source_title':None,'steps':[]}
        with patch.object(self.journey,'active_goal',return_value=goal),patch.object(self.journey,'examples',return_value=[{'example':{'text':'A water analogy','concept':'A','date':'2026-01-01'}}]):
            result=self.journey.prompt_context('learner','A')
        self.assertIn('Read this paper',result)
        self.assertIn('A water analogy',result)
        self.assertIn('not proof of mastery',result)
