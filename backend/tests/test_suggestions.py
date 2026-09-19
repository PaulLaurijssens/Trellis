"""Contract checks with isolated modules; never connects to a model or database."""
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


class SuggestionTests(unittest.TestCase):
    def setUp(self):
        package = types.ModuleType('suggestion_test_app')
        package.__path__ = [str(Path(__file__).resolve().parents[1] / 'app')]
        self.llm = MagicMock()
        self.modules = patch.dict(sys.modules, {
            'suggestion_test_app': package,
            'suggestion_test_app.llm': self.llm,
            'neo4j': MagicMock(),
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.graph = importlib.import_module('suggestion_test_app.graph')
        self.suggestions = importlib.import_module('suggestion_test_app.suggestions')
        self.item = dict(name='Vectors', definition='A mathematical object', reason='Needed for attention',
                         relation='PREREQUISITE_OF', direction='suggested_to_current')

    def test_validation_rejects_self_duplicate_bad_relation_and_caps_three(self):
        items = [self.item, self.item, {**self.item, 'name': 'Attention'},
                 {**self.item, 'name': 'Invalid', 'relation': 'DELETE'},
                 *[{**self.item, 'name': f'Extra {i}'} for i in range(8)]]
        result = self.suggestions.validate({'suggestions': items}, 'Attention')
        self.assertEqual([i['name'] for i in result], ['Vectors', 'Extra 0', 'Extra 1'])
        self.assertEqual(self.suggestions.validate({'suggestions': None}, 'Attention'), [])

    def test_model_failure_is_optional(self):
        self.llm.litellm.completion.side_effect = RuntimeError('offline')
        with patch.object(self.graph, 'find_concept', return_value=None), patch.object(self.graph, 'create_session_suggestions') as persist:
            with self.assertLogs(self.suggestions.log, level='WARNING'):
                self.assertEqual(self.suggestions.propose('s', 'p', 'Attention', 'hello', 'answer', 1), [])
            persist.assert_not_called()

    def transaction(self, state='pending', direction='suggested_to_current', found=True, existing=True):
        tx = MagicMock()
        row = {'proposal': {**self.item, 'state': state, 'direction': direction}, 'current_id': 'attention'}
        def run(query, **params):
            result = MagicMock()
            if 'suggestion_lock' in query:
                result.single.return_value = row if found else None
            elif 'ORDER BY c.name' in query and not existing:
                result.single.return_value = None
            elif 'RETURN c.id AS id' in query:
                result.single.return_value = {'id': 'vectors', 'name': 'Canonical Vectors'}
            return result
        tx.run.side_effect = run
        session = self.graph.driver.session.return_value.__enter__.return_value
        session.execute_write.side_effect = lambda callback: callback(tx)
        return tx

    def test_ownership_failure_never_writes_concepts(self):
        tx = self.transaction(found=False)
        with self.assertRaises(KeyError):
            self.graph.act_on_suggestion('s', 'other', 'explore')
        self.assertEqual(tx.run.call_count, 1)
        self.assertEqual(tx.run.call_args.kwargs['pid'], 'other')

    def test_dismiss_never_creates_concepts(self):
        tx = self.transaction()
        self.assertEqual(self.graph.act_on_suggestion('s', 'p', 'dismiss')['state'], 'dismissed')
        self.assertFalse(any('MERGE' in call.args[0] for call in tx.run.call_args_list))

    def test_accept_canonical_name_and_both_directions(self):
        for direction, expected in [('suggested_to_current', ('vectors', 'attention')),
                                    ('current_to_suggested', ('attention', 'vectors'))]:
            tx = self.transaction(direction=direction)
            result = self.graph.act_on_suggestion('s', 'p', 'save')
            self.assertEqual(result, {'id': 's', 'concept': 'Canonical Vectors', 'state': 'queued'})
            edge = next(c for c in tx.run.call_args_list if 'r:PREREQUISITE_OF' in c.args[0])
            self.assertEqual((edge.kwargs['a'], edge.kwargs['b']), expected)
            self.assertIn('MERGE', edge.args[0])

    def test_save_after_explore_does_not_downgrade(self):
        self.transaction(state='explored')
        self.assertEqual(self.graph.act_on_suggestion('s', 'p', 'save')['state'], 'explored')

    def test_new_concept_is_created_only_during_acceptance(self):
        tx = self.transaction(existing=False)
        self.graph.act_on_suggestion('s', 'p', 'save')
        creates = [c for c in tx.run.call_args_list if 'MERGE (c:Concept {name:' in c.args[0]]
        self.assertEqual(len(creates), 1)
        self.assertEqual(creates[0].kwargs['name'], 'vectors')
        self.assertEqual(creates[0].kwargs['status'], 'queued')
        self.assertFalse(any('MENTIONED_IN' in c.args[0] for c in tx.run.call_args_list))

    def test_accepted_retry_uses_identity_not_original_name(self):
        tx = self.transaction(state='queued')
        result = self.graph.act_on_suggestion('s', 'p', 'explore')
        self.assertEqual(result['concept'], 'Canonical Vectors')
        self.assertTrue(any('[:ACCEPTED_AS]->' in c.args[0] for c in tx.run.call_args_list))
        self.assertFalse(any('toLower(c.name)' in c.args[0] for c in tx.run.call_args_list))
        self.assertFalse(any('MERGE (c:Concept {name:' in c.args[0] for c in tx.run.call_args_list))

    def test_previous_dismissed_suggestions_are_passed_and_filtered(self):
        self.llm.parse_json.return_value = {'suggestions': [self.item]}
        with patch.object(self.graph, 'find_concept', return_value={'id': 'attention'}), \
             patch.object(self.graph, 'concept_suggestions', return_value=[{'name': 'Vectors', 'state': 'dismissed'}]), \
             patch.object(self.graph, 'create_session_suggestions', return_value=[]) as persist:
            self.assertEqual(self.suggestions.propose('s', 'p', 'Attention', 'hi', 'reply', 2), [])
        self.assertEqual(persist.call_args.args[-1], [])
        messages = self.llm.litellm.completion.call_args.kwargs['messages']
        self.assertIn('dismissed', messages[1]['content'])
        self.assertIn('canonical English', messages[0]['content'])

    def test_dismissed_cannot_be_accepted(self):
        tx = self.transaction(state='dismissed')
        with self.assertRaises(ValueError):
            self.graph.act_on_suggestion('s', 'p', 'save')
        self.assertEqual(tx.run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
