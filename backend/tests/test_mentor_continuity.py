"""Run with python3 -m unittest discover -s backend/tests; no services required."""
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


class MentorContinuityTests(unittest.TestCase):
    def setUp(self):
        # Load production modules under an isolated package with mocked IO.
        package = types.ModuleType('continuity_test_app')
        package.__path__ = [str(Path(__file__).resolve().parents[1] / 'app')]
        self.graph = MagicMock()
        self.graph.LANGUAGES = {'en': 'English'}
        self.graph.PROFILE_LISTS = ('works_well', 'works_poorly', 'preferences')
        self.graph.STATE_LISTS = ('covered', 'struggles', 'misconceptions')
        self.graph.ui_language.return_value = 'en'
        self.graph.learning_profile.return_value = {'works_well': ['Visual examples']}
        self.graph.understands_state.return_value = {'struggles': ['Confuses weights']}
        self.revision=0
        def transaction(pid,callback):
            self.revision+=1
            return callback()
        self.graph.memory_transaction.side_effect=transaction
        self.graph.run.side_effect=lambda query,**kw: [{"revision":self.revision}] if "AS revision" in query else [{"doc":None}] if "AS doc" in query else []
        self.llm = MagicMock()
        mentor = types.ModuleType('continuity_test_app.mentor')
        mentor.LEVELS = {3: 'technical adult'}
        self.modules = patch.dict(sys.modules, {
            'continuity_test_app': package,
            'continuity_test_app.graph': self.graph,
            'continuity_test_app.llm': self.llm,
            'continuity_test_app.extract': MagicMock(),
            'continuity_test_app.mentor': mentor,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.learn = importlib.import_module('continuity_test_app.learn')
        self.memory = importlib.import_module('continuity_test_app.memory')
        self.llm.complete_json.return_value = {
            'definition': 'Definition', 'explanation': 'Explanation', 'prerequisites': []}
        self.graph.active_session.return_value = {'id': 'session'}
        self.graph.concept_prompt_context.return_value = {
            'definition': 'Stored definition',
            'prerequisites': [{'name': 'Vectors', 'status': 'learned', 'reason': 'Compare vectors'}],
            'mentions': [{'source': 'Paper', 'context': 'Weighted combinations of values'}]}
        self.graph.session_messages.return_value = [
            {'role': 'user', 'content': 'Please continue from weighted averages'}]

    def test_existing_explanation_uses_profile_state_and_recent_conversation(self):
        self.graph.find_concept.return_value = {'id': 'concept'}
        with patch.object(self.learn, '_upsert', return_value=('concept', 'Attention')):
            result = self.learn.learn('Attention')
        system, prompt, _ = self.llm.complete_json.call_args.args
        self.assertIn('Visual examples', prompt)
        self.assertIn('Confuses weights', prompt)
        self.assertIn('weighted averages', prompt)
        self.assertIn('Weighted combinations of values', prompt)
        self.assertIn('Vectors', prompt)
        self.assertIn('"prerequisites"', system)
        self.assertEqual(result['explanation'], 'Explanation')
        self.graph.add_message.assert_called_once_with('session', 'assistant', 'Explanation')

    def test_new_concept_uses_profile_without_concept_state(self):
        self.graph.find_concept.return_value = None
        with patch.object(self.learn, '_upsert', return_value=('new', 'Attention')):
            self.learn.learn('Attention')
        self.assertIn('Visual examples', self.llm.complete_json.call_args.args[1])
        self.graph.understands_state.assert_not_called()

    def test_exact_alias_preserves_canonical_identity_and_fills_embedding(self):
        self.graph.find_concept.return_value = {'id': 'saved', 'name': 'Attention'}
        self.graph.upsert_concept.return_value = 'saved'
        self.llm.embed.return_value = [[0.1, 0.2]]
        result = self.learn._upsert('Self attention', 'Neutral definition', 'learning')
        self.assertEqual(result, ('saved', 'Attention'))
        self.learn.extract.resolve.assert_not_called()
        self.graph.upsert_concept.assert_called_once_with(
            'Attention', 'Neutral definition', ['Self attention'], '', [0.1, 0.2], 'learning')
        query = self.graph.run.call_args.args[0]
        self.assertIn('c.embedding IS NULL OR size(c.embedding) = 0', query)
        self.assertEqual(self.graph.run.call_args.kwargs, {'cid': 'saved', 'embedding': [0.1, 0.2]})

    def test_unmatched_concept_still_uses_resolution(self):
        self.graph.find_concept.return_value = None
        self.llm.embed.return_value = [[0.3]]
        self.learn.extract.resolve.return_value = 'Attention'
        self.graph.upsert_concept.return_value = 'resolved'
        self.assertEqual(self.learn._upsert('Attending', 'Definition', 'suggested'),
                         ('resolved', 'Attention'))
        self.learn.extract.resolve.assert_called_once_with('Attending', 'Definition', [0.3])

    def test_invalid_source_does_not_invoke_model(self):
        self.graph.source_exists.return_value = False
        with self.assertRaises(KeyError):
            self.learn.learn('Attention', source_id='missing')
        self.llm.complete_json.assert_not_called()

    def test_model_failure_remains_retryable(self):
        self.graph.session_info.return_value = {
            'consolidated': False, 'person_id': 'paul', 'concept_id': 'concept',
            'level': 3, 'last_activity': 'today'}
        self.llm.complete_json.side_effect = RuntimeError('Model unavailable')
        with self.assertRaises(self.memory.ConsolidationError):self.memory.consolidate_session('session')
        self.graph.mark_consolidated.assert_not_called()
        self.graph.write_understands.assert_not_called()
        self.llm.complete_json.side_effect = None
        self.llm.complete_json.return_value = {'covered': ['Attention'],'evidence':[],'observations':[],'changes':[]}
        self.assertTrue(self.memory.consolidate_session('session'))
        self.assertTrue(any('s.consolidated=true' in call.args[0] for call in self.graph.run.call_args_list))

    def test_assistant_only_session_is_completed_without_model(self):
        self.graph.session_info.return_value = {
            'consolidated': False, 'person_id': 'paul', 'concept_id': 'concept'}
        self.graph.session_messages.return_value = [{'role': 'assistant', 'content': 'Hello'}]
        self.assertFalse(self.memory.consolidate_session('session'))
        self.llm.complete_json.assert_not_called()
        self.assertTrue(any('s.consolidated=true' in call.args[0] for call in self.graph.run.call_args_list))


if __name__ == '__main__':
    unittest.main()
