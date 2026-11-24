"""Make Windows exclusions explicit, reviewed and coupled to replacement tests.

This is a scope consistency check, not proof of one-to-one test equivalence.
"""
import ast
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WindowsRegressionScopeTests(unittest.TestCase):
    def test_exact_workflow_exclusions_and_replacement_scope(self):
        policy = json.loads((ROOT/'config/windows-regression-scope.json').read_text())
        self.assertEqual(policy['schema'], 'gasl-windows-regression-scope-v1')
        self.assertIs(policy['production_legacy_migration_enabled'], False)
        self.assertIs(policy['windows_legacy_write_enabled'], False)
        rows = policy['excluded_test_modules']
        workflow = (ROOT/'.github/workflows/gasl-cross-platform.yml').read_text()
        ignored = re.findall(r'--ignore=(tests/[a-z_]+\.py)', workflow)
        expected = [row['path'] for row in rows]
        self.assertEqual(len(expected), len(set(expected)))
        self.assertEqual(sorted(ignored), sorted(expected))
        self.assertEqual(len(rows), 6)
        for row in rows:
            with self.subTest(path=row['path']):
                tree = ast.parse((ROOT/row['path']).read_text(encoding='utf-8'))
                count = sum(isinstance(n, ast.FunctionDef) and n.name.startswith('test_')
                            for n in ast.walk(tree))
                self.assertEqual(count, row['test_methods'])
                self.assertTrue(row['limitation'])
                self.assertTrue(row['replacement'])
                for path in row['replacement']:
                    self.assertNotIn(path, ignored)
                    self.assertTrue((ROOT/path).is_file())


if __name__ == '__main__':
    unittest.main()
