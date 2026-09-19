import unittest
from unittest.mock import patch
from app import translations

class TranslationTests(unittest.TestCase):
    @patch('app.translations.graph.run')
    @patch('app.translations.llm.complete_json')
    def test_cache_duplicates_and_language_isolation(self, complete, run):
        run.return_value = []
        complete.return_value = ['A concept']
        self.assertEqual(translations.translate(['Een concept', 'Een concept'], 'en'), ['A concept', 'A concept'])
        rows = run.call_args.kwargs['rows']
        self.assertEqual(len(rows), 1)
        key = rows[0]['key']
        run.reset_mock(); run.return_value = [{'key':key, 'text':'A concept'}]; complete.reset_mock()
        self.assertEqual(translations.translate(['Een concept'], 'en'), ['A concept'])
        complete.assert_not_called()
        run.return_value = []; complete.return_value = ['Een concept']
        translations.translate(['Een concept'], 'nl')
        self.assertNotEqual(key, run.call_args.kwargs['rows'][0]['key'])

    @patch('app.translations.graph.run', return_value=[])
    @patch('app.translations.llm.complete_json', return_value=['Only one'])
    def test_invalid_batch_never_saved(self, complete, run):
        with self.assertRaises(ValueError): translations.translate(['One', 'Two'], 'en')
        self.assertEqual(run.call_count, 1)
