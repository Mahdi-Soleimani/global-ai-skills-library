"""Phase 25: private ZIP handoff and verification, with synthetic pinned packages."""
import hashlib
import json
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from install_bundle import prepare_private_bundle, verify_private_bundle, _slug
from tests import test_install_lifecycle as previous_fixture


class PrivateInstallBundleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = previous_fixture.InstallLifecycleTests('test_plan_does_not_create_private_ledger_or_agent_directory')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self._plan = self.fixture._plan
        self._package = self.fixture._package
        self.lookup = self.fixture.lookup
        self.row = self.fixture.row
        self.content = self.fixture.content

    def _prepare(self, agent='codex', scope='project', acknowledgement=None):
        p = self._plan(agent=agent, scope=scope)
        return prepare_private_bundle(self.row['source_record_id'], agent, scope,
                  p['plan_id'] if acknowledgement is None else acknowledgement,
                  root=self.root, lookup=self.lookup)

    def test_private_zip_contains_only_pinned_files_and_is_verified(self):
        folder, source = self._package()
        original = source.read_bytes()
        result = self._prepare()
        self.assertEqual(result['status'], 'private_review_bundle_created')
        self.assertEqual(result['file_count'], 2)
        self.assertFalse(result['real_host_files_modified'])
        self.assertFalse(result['production_installation_enabled'])
        self.assertTrue(result['manual_review_required'])
        bundle = Path(result['archive_path'])
        self.assertTrue(bundle.is_file())
        self.assertEqual(bundle.parent, self.root / 'private/install-bundles')
        with zipfile.ZipFile(bundle) as zf:
            self.assertEqual(zf.namelist(), ['demo/SKILL.md', 'demo/references/about.md'])
            self.assertEqual(zf.read('demo/SKILL.md'), self.content['skills/demo/SKILL.md'])
            self.assertFalse(any('source.json' in x for x in zf.namelist()))
        self.assertEqual(source.read_bytes(), original)
        verified = verify_private_bundle(result['plan_id'], root=self.root)
        self.assertEqual(verified['status'], 'private_bundle_integrity_verified')
        self.assertFalse(verified['installation_approved'])
        self.assertFalse((self.root / '.agents').exists())
        self.assertFalse((self.root / '.cursor').exists())
        self.assertFalse((self.root / '.claude').exists())

    def test_legacy_manifest_hashes_work_without_claiming_missing_blob_evidence(self):
        folder, source = self._package()
        d = json.loads(source.read_text())
        for item in d['files']:
            item.pop('package_relative_path', None)
            item.pop('git_blob_sha', None)
        source.write_text(json.dumps(d))
        result = self._prepare()
        self.assertEqual(result['legacy_manifest_entries_without_git_blob_sha'], 2)
        meta = json.loads(Path(result['metadata_path']).read_text())
        self.assertFalse(meta['non_main_file_upstream_blob_evidence_complete'])
        self.assertTrue(meta['manual_review_required'])
        self.assertEqual(verify_private_bundle(result['plan_id'], root=self.root)['file_count'], 2)

    def test_bundles_are_byte_deterministic_for_two_scopes(self):
        self._package()
        one = self._prepare(agent='codex', scope='project')
        two = self._prepare(agent='codex', scope='user')
        self.assertNotEqual(one['plan_id'], two['plan_id'])
        self.assertEqual(one['archive_sha256'], two['archive_sha256'])

    def test_explicit_acknowledgement_required_before_any_directory_creation(self):
        self._package()
        with self.assertRaisesRegex(ValueError, 'exact plan ID acknowledgement'):
            self._prepare(acknowledgement='f' * 64)
        self.assertFalse((self.root / 'private/install-bundles').exists())

    def test_missing_download_does_not_create_bundle(self):
        with self.assertRaisesRegex(ValueError, 'missing, tampered'):
            self._prepare()
        self.assertFalse((self.root / 'private').exists())

    def test_tampered_main_skill_blob_is_not_exported(self):
        folder, _ = self._package()
        (folder / 'SKILL.md').write_text('# modified by another process')
        with self.assertRaisesRegex(ValueError, 'missing, tampered'):
            self._prepare()
        self.assertFalse((self.root / 'private').exists())

    def test_added_unlisted_file_is_not_exported(self):
        folder, _ = self._package()
        (folder / 'hidden.sh').write_text('#!/bin/sh\necho not executed\n')
        with self.assertRaisesRegex(ValueError, 'missing, tampered'):
            self._prepare()
        self.assertFalse((self.root / 'private').exists())

    def test_symlinked_file_is_rejected_without_reading_target(self):
        folder, _ = self._package()
        outside = self.root / 'outside-secret.txt'
        outside.write_text('PRIVATE_SENTINEL')
        (folder / 'SKILL.md').unlink()
        (folder / 'SKILL.md').symlink_to(outside)
        with self.assertRaises((ValueError, OSError)):
            self._prepare()
        self.assertEqual(outside.read_text(), 'PRIVATE_SENTINEL')
        self.assertFalse((self.root / 'private').exists())

    def test_output_sidecar_symlink_is_never_followed_or_removed(self):
        self._package()
        plan = self._plan()
        private_dir = self.root / 'private/install-bundles'
        private_dir.mkdir(parents=True)
        outside = self.root / 'do-not-overwrite.txt'
        outside.write_text('EXTERNAL_SENTINEL')
        sidecar = private_dir / (plan['plan_id'] + '.json')
        sidecar.symlink_to(outside)
        with self.assertRaises(ValueError):
            self._prepare()
        self.assertEqual(outside.read_text(), 'EXTERNAL_SENTINEL')
        self.assertTrue(sidecar.is_symlink())

    def test_private_storage_symlink_is_refused_before_writing(self):
        self._package()
        (self.root / 'private').mkdir()
        outside = self.root / 'outside-folder'
        outside.mkdir()
        (self.root / 'private/install-bundles').symlink_to(outside)
        with self.assertRaises(ValueError):
            self._prepare()
        self.assertEqual(list(outside.iterdir()), [])

    def test_existing_zip_refuses_overwrite(self):
        self._package()
        first = self._prepare()
        original = Path(first['archive_path']).read_bytes()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self._prepare()
        self.assertEqual(Path(first['archive_path']).read_bytes(), original)

    def test_corrupted_archive_detected_by_readonly_verify(self):
        self._package()
        result = self._prepare()
        bundle = Path(result['archive_path'])
        bundle.write_bytes(bundle.read_bytes() + b'bad appended bytes')
        with self.assertRaisesRegex(ValueError, 'archive hash mismatch'):
            verify_private_bundle(result['plan_id'], root=self.root)

    def test_tampered_sidecar_identity_rejected(self):
        self._package()
        result = self._prepare()
        path = Path(result['metadata_path'])
        data = json.loads(path.read_text())
        data['plan_id'] = '0' * 64
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'metadata mismatch'):
            verify_private_bundle(result['plan_id'], root=self.root)

    def test_unknown_license_is_visible_but_not_claimed_approved(self):
        self.row['license_spdx'] = 'NOASSERTION'
        self._package()
        result = self._prepare()
        self.assertTrue(result['license_review_required'])
        meta = json.loads(Path(result['metadata_path']).read_text())
        self.assertTrue(meta['license_review_required'])
        self.assertFalse(meta['host_installation_approved'])
        self.assertTrue(meta['manual_review_required'])
        self.assertEqual(meta['license_spdx'], 'NOASSERTION')

    def test_available_claude_desktop_has_manual_zip_only(self):
        self._package()
        result = self._prepare('claude-desktop', 'user')
        self.assertTrue(result['manual_review_required'])
        self.assertEqual(verify_private_bundle(result['plan_id'], root=self.root)['file_count'], 2)
        self.assertFalse((self.root / '.claude').exists())

    def test_generic_mcp_cannot_claim_zip_install(self):
        self._package()
        with self.assertRaisesRegex(ValueError, 'No supported manual'):
            prepare_private_bundle(self.row['source_record_id'], 'generic-mcp', 'user',
                                   '0' * 64, root=self.root, lookup=self.lookup)
        self.assertFalse((self.root / 'private').exists())

    def test_plan_from_wrong_source_sha_never_exports_downloaded_bytes(self):
        self._package()
        self.row['commit_sha'] = 'd' * 40
        with self.assertRaisesRegex(ValueError, 'missing, tampered'):
            self._prepare()
        self.assertFalse((self.root / 'private').exists())

    def test_non_ascii_skill_dir_falls_back_to_safe_slug(self):
        slug = _slug('skills/مهارت/SKILL.md', self.row['source_record_id'])
        self.assertRegex(slug, '^gasl-skill-[0-9a-f]{10}$')

    def test_codegen_template_security_signal_blocks_new_private_zip(self):
        self.content['skills/demo/scripts/generator.py'] = (
            'def make(tool):\n'
            '    return f"registerTool({tool[\'description\']})"\n'
        ).encode()
        self._package()
        self.assertEqual(self._plan()['local_package']['security_status'], 'manual_review_required')
        with self.assertRaisesRegex(ValueError, 'missing, tampered or statically flagged'):
            self._prepare()
        self.assertFalse((self.root / 'private').exists())

    def test_wildcard_cors_and_implicit_bind_block_private_zip(self):
        self.content['skills/demo/src/server.ts'] = (
            'res.setHeader("Access-Control-Allow-Origin", "*");\n'
            'createServer(handler).listen(port);\n'
        ).encode()
        self._package()
        plan = self._plan()
        self.assertFalse(plan['simulation_apply_eligible'])
        self.assertGreaterEqual(plan['local_package']['actionable_findings'], 2)
        with self.assertRaisesRegex(ValueError, 'missing, tampered or statically flagged'):
            self._prepare()
        self.assertFalse((self.root / 'private').exists())

    def test_script_fixture_with_actionable_security_finding_is_blocked(self):
        self.content['skills/demo/scripts/run.py'] = b'import os\nos.system("cat /etc/passwd")\n'
        self._package()
        with self.assertRaisesRegex(ValueError, 'missing, tampered'):
            self._prepare()
        self.assertFalse((self.root / 'private').exists())


if __name__ == '__main__':
    unittest.main()
