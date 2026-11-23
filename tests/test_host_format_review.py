"""Phase 38: verified private ZIP, read-only cross-Host Skill format evidence."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from host_format_review import _simple_frontmatter, review_host_format
from queue_ingest import git_blob
from tests import test_install_bundle as bundle_fixture


class HostFormatReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = bundle_fixture.PrivateInstallBundleTests(
            'test_private_zip_contains_only_pinned_files_and_is_verified')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.content['skills/demo/SKILL.md'] = (
            b'---\nname: demo\ndescription: Safe inert test skill\n---\n'
            b'# PRIVATE_BUNDLE_SENTINEL_NOT_FOR_OUTPUT\n')
        self.fixture.row['skill_md_blob_sha'] = git_blob(
            self.fixture.content['skills/demo/SKILL.md'])
        self.folder, _ = self.fixture._package()
        self.bundle = self.fixture._prepare()
        self.plan_id = self.bundle['plan_id']

    def review(self, host='codex', scope='user'):
        return review_host_format(
            self.plan_id, host, scope, root=self.fixture.root,
            lookup=self.fixture.lookup)

    def test_all_documented_hosts_are_static_only(self):
        for host, expected_path in (
            ('codex', '.agents/skills'),
            ('cursor', '.cursor/skills'),
            ('claude-code', '.claude/skills'),
        ):
            with self.subTest(host=host):
                result = self.review(host)
                self.assertEqual(result['format_status'],
                                 'simple_frontmatter_shape_detected')
                self.assertEqual(result['documented_skill_directory'], expected_path)
                self.assertTrue(result['source_git_blob_verified'])
                self.assertEqual(result['skill_name'], 'demo')
                self.assertFalse(result['host_discovery_verified_by_this_check'])
                self.assertFalse(result['cross_host_compatibility_proven'])
                self.assertFalse(result['installation_allowed'])
                self.assertFalse(result['real_host_files_modified'])
                self.assertFalse(result['third_party_skill_executed'])
                self.assertNotIn('PRIVATE_BUNDLE_SENTINEL', json.dumps(result))

    def test_project_and_user_scope_do_not_write_any_host_directories(self):
        for scope in ('project', 'user'):
            self.assertEqual(self.review('cursor', scope)['scope'], scope)
        for path in ('.agents', '.cursor', '.claude'):
            self.assertFalse((self.fixture.root/path).exists())

    def test_non_supported_hosts_are_rejected(self):
        for host in ('claude-desktop', 'generic-mcp', '../../escape'):
            with self.subTest(host=host), self.assertRaisesRegex(ValueError, 'supported'):
                self.review(host)

    def test_duplicate_and_multiline_frontmatter_need_manual_review(self):
        data = (b'---\nname: demo\ndescription: |\n'
                b'  multiline\nname: demo\n---\nbody\n')
        fields, checks = _simple_frontmatter(data)
        self.assertIn('duplicate_frontmatter_key', checks)
        self.assertIn('multiline_description_requires_review', checks)

    def test_nested_yaml_is_not_silently_accepted_as_simple(self):
        _, checks = _simple_frontmatter(
            b'---\nname: demo\ndescription: Simple\nmetadata:\n  owner: Example\n---\nbody\n')
        self.assertIn('complex_yaml_requires_manual_review', checks)

    def test_missing_frontmatter_is_not_assumed_portable(self):
        fields, checks = _simple_frontmatter(b'# no frontmatter')
        self.assertEqual(fields, {})
        self.assertEqual(checks, ['missing_frontmatter_opening'])

    def test_invalid_or_mismatching_slug_requires_manual_review(self):
        fields, problems = _simple_frontmatter(
            b'---\nname: ..bad\ndescription: Inert\n---\nbody\n')
        self.assertIn('nonportable_name', problems)
        fields, problems = _simple_frontmatter(
            b'---\nname: other\ndescription: Inert\n---\nbody\n')
        self.assertEqual(fields['name'], 'other')

    def test_non_utf8_frontmatter_is_rejected_as_evidence(self):
        self.assertEqual(_simple_frontmatter(b'\xff')[1], ['invalid_utf8'])

    def test_tampered_archive_fails_before_format_review(self):
        path = Path(self.bundle['archive_path'])
        path.write_bytes(path.read_bytes() + b'tamper')
        with self.assertRaisesRegex(ValueError, 'archive hash'):
            self.review('claude-code')

    def test_modified_downloaded_source_invalidates_pinned_review(self):
        (self.folder/'SKILL.md').write_bytes(b'altered after private ZIP creation')
        with self.assertRaisesRegex(ValueError, 'no longer matches'):
            self.review('cursor')

    def test_sidecar_changed_source_pin_does_not_count_as_evidence(self):
        path = Path(self.bundle['metadata_path'])
        meta = json.loads(path.read_text())
        meta['source_commit_sha'] = 'b'*40
        path.write_text(json.dumps(meta))
        with self.assertRaisesRegex(ValueError, 'no longer matches'):
            self.review('codex')


if __name__ == '__main__':
    unittest.main()
