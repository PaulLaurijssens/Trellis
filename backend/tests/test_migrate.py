import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class MigrateTests(unittest.TestCase):
    def setUp(self):
        pkg = types.ModuleType('migrate_test_app')
        pkg.__path__ = [str(Path(__file__).resolve().parents[1] / 'app')]
        self.graph = MagicMock()
        self.graph._split_cypher.side_effect = lambda text: [s.strip() for s in text.split(';') if s.strip() and not s.strip().startswith('//')]
        self.graph._now.return_value = 'now'
        self.modules = patch.dict(sys.modules, {'migrate_test_app': pkg, 'migrate_test_app.graph': self.graph})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.migrate = importlib.import_module('migrate_test_app.migrate')
        self.migrate.graph = self.graph
        self.dir = tempfile.mkdtemp()
        for name, body in [('001_first.cypher', 'MATCH (n) SET n.a = 1;'), ('002_second.cypher', '// comment\nMATCH (n) SET n.b = 2;\nMATCH (n) SET n.c = 3;'), ('notes.md', 'x')]:
            Path(self.dir, name).write_text(body)

    def version(self, v):
        self.graph.run.side_effect = lambda q, **p: [{'v': v}] if q.startswith('MATCH (s:Schema') else []

    def test_fresh_database_applies_all_in_order(self):
        self.version(None)
        self.assertEqual(self.migrate.apply(self.dir), ['001_first.cypher', '002_second.cypher'])
        writes = [c.kwargs.get('v') for c in self.graph.run.call_args_list if 'v' in c.kwargs]
        self.assertEqual(writes, [1, 2])

    def test_second_run_applies_nothing(self):
        self.version(2)
        self.assertEqual(self.migrate.pending(self.dir), [])
        self.assertEqual(self.migrate.apply(self.dir), [])

    def test_partial_version_resumes(self):
        self.version(1)
        self.assertEqual(self.migrate.apply(self.dir), ['002_second.cypher'])

    def test_duplicate_numbers_refused(self):
        Path(self.dir, '002_other.cypher').write_text('MATCH (n) RETURN n;')
        with self.assertRaises(ValueError):
            self.migrate.files(self.dir)

    def test_missing_directory_is_empty(self):
        self.assertEqual(self.migrate.files(os.path.join(self.dir, 'nope')), [])


if __name__ == '__main__':
    unittest.main()
