"""Static scanner regression tests for code-generation injection and wildcard CORS."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from static_scan import scan_package


class StaticScanSecurityRuleTests(unittest.TestCase):
    def scan(self, files):
        temporary = tempfile.TemporaryDirectory(prefix='gasl-static-review-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        package = root / 'catalog' / 'fixture__repo' / 'demo'
        package.mkdir(parents=True)
        entries = []
        for relative, content in files.items():
            path = package / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            data = content.encode('utf-8')
            path.write_bytes(data)
            entries.append({
                'local_path': path.relative_to(root).as_posix(),
                'size_bytes': len(data),
                'sha256': hashlib.sha256(data).hexdigest(),
            })
        source = package / 'source.json'
        source.write_text(json.dumps({
            'repository': 'fixture/repo', 'skill_name': 'demo',
            'source_skill_path': 'skills/demo/SKILL.md',
            'commit_sha': 'a' * 40, 'files': entries,
        }), encoding='utf-8')
        return scan_package(source, root=root, persist=False), root

    def test_unescaped_description_interpolation_in_generated_source_is_flagged(self):
        result, _ = self.scan({
            'SKILL.md': '# Fixture\n',
            'scripts/generator.py': (
                'def generate(tool):\n'
                '    return f"registerTool(\\\'{tool[\'name\']}\\\', \'{tool[\'description\']}\')"\n'
            ),
        })
        matches = [x for x in result['findings']
                   if x['rule_id'] == 'UNESCAPED_DESCRIPTION_CODE_TEMPLATE']
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(result['security_status'], 'manual_review_required')
        self.assertFalse(result['execution_performed'])

    def test_json_encoded_description_is_not_flagged_by_template_rule(self):
        result, _ = self.scan({
            'SKILL.md': '# Fixture\n',
            'scripts/generator.py': (
                'import json\n'
                'def generate(tool):\n'
                '    description = json.dumps(tool["description"])\n'
                '    return "registerTool(" + description + ")"\n'
            ),
        })
        self.assertFalse(any(x['rule_id'] == 'UNESCAPED_DESCRIPTION_CODE_TEMPLATE'
                             for x in result['findings']))

    def test_wildcard_cors_is_flagged_for_manual_review(self):
        result, _ = self.scan({
            'SKILL.md': '# Fixture\n',
            'scripts/server.mjs': (
                'res.writeHead(204, {"Access-Control-Allow-Origin": "*"});\n'
                'res.setHeader("Access-Control-Allow-Origin", "*");\n'
            ),
        })
        matches = [x for x in result['findings'] if x['rule_id'] == 'WILDCARD_CORS_ORIGIN']
        self.assertEqual(len(matches), 2)
        self.assertEqual(result['security_status'], 'manual_review_required')

    def test_specific_cors_origin_is_not_flagged(self):
        result, _ = self.scan({
            'SKILL.md': '# Fixture\n',
            'scripts/server.mjs': 'res.setHeader("Access-Control-Allow-Origin", "https://example.com");\n',
        })
        self.assertFalse(any(x['rule_id'] == 'WILDCARD_CORS_ORIGIN'
                             for x in result['findings']))

    def test_implicit_node_bind_detected_in_typescript_and_generated_templates(self):
        result, _ = self.scan({
            'SKILL.md': '# Fixture\n',
            'scripts/generator.mjs': 'const generated = `createServer(fn).listen(port, () => {});`;\n',
            'src/server.ts': 'createServer(handler).listen(8787);\n',
        })
        found = [x for x in result['findings']
                 if x['rule_id'] == 'NODE_SERVER_IMPLICIT_ALL_INTERFACES']
        self.assertEqual(len(found), 2)
        self.assertEqual(result['security_status'], 'manual_review_required')

    def test_explicit_loopback_bind_is_not_flagged(self):
        result, _ = self.scan({
            'SKILL.md': '# Fixture\n',
            'src/server.ts': 'createServer(handler).listen(port, "127.0.0.1", () => {});\n',
        })
        self.assertFalse(any(x['rule_id'] == 'NODE_SERVER_IMPLICIT_ALL_INTERFACES'
                             for x in result['findings']))

    def test_typescript_wildcard_cors_is_also_scanned(self):
        result, _ = self.scan({
            'SKILL.md': '# Fixture\n',
            'src/server.ts': 'res.setHeader("Access-Control-Allow-Origin", "*");\n',
        })
        self.assertEqual([x['rule_id'] for x in result['findings']],
                         ['WILDCARD_CORS_ORIGIN'])

    def test_readonly_scan_does_not_rewrite_source_metadata(self):
        result, root = self.scan({'SKILL.md': '# Fixture\n'})
        source = root / 'catalog/fixture__repo/demo/source.json'
        self.assertNotIn('security_status', json.loads(source.read_text()))
        self.assertTrue(result['integrity_ok'])
        self.assertEqual(result['finding_count'], 0)

    def test_scanner_never_executes_package_scripts(self):
        sentinel = Path(tempfile.gettempdir()) / 'gasl-static-scan-must-not-execute'
        sentinel.unlink(missing_ok=True)
        result, _ = self.scan({
            'SKILL.md': '# Fixture\n',
            'scripts/do_not_run.py': (
                'from pathlib import Path\n'
                f'Path({str(sentinel)!r}).write_text("executed")\n'
            ),
        })
        self.assertFalse(sentinel.exists())
        self.assertFalse(result['execution_performed'])


if __name__ == '__main__':
    unittest.main()
