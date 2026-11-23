"""Phase 40 real project installer, exercised ONLY in disposable synthetic Git repos."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from codex_project_install import (
    preview_install, install_fresh, uninstall, recover,
    _install_phrase, _remove_phrase, _journal, _receipt, _paths, SCHEMA,
)
from queue_ingest import git_blob
from tests import test_install_bundle as bundle_fixture


class ProjectInstallTests(unittest.TestCase):
    def setUp(self):
        fixture = bundle_fixture.PrivateInstallBundleTests(
            'test_private_zip_contains_only_pinned_files_and_is_verified')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        fixture.content['skills/demo/SKILL.md'] = (
            b'---\nname: demo\ndescription: Inert file-only test Skill\n---\n'
            b'# No scripts are run during any test.\n')
        fixture.row['skill_md_blob_sha'] = git_blob(fixture.content['skills/demo/SKILL.md'])
        self.folder, _ = fixture._package()
        self.bundle = fixture._prepare(agent='codex', scope='project')
        self.tmp = tempfile.TemporaryDirectory(prefix='gasl-phase40-project-')
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)/'project'
        self.project.mkdir()
        (self.project/'.git').mkdir()
        self.plan_id = self.bundle['plan_id']

    def preview(self):
        return preview_install(self.plan_id, self.project,
                               bundle_root=self.fixture.root, lookup=self.fixture.lookup)

    def install(self, reader=None, binding=None):
        p = self.preview()
        return install_fresh(
            self.plan_id, self.project, binding or p['state_binding_id'],
            bundle_root=self.fixture.root, lookup=self.fixture.lookup,
            reader=reader)

    def matching_install(self):
        p = self.preview()
        phrase = _install_phrase('demo', self.plan_id, p['state_binding_id'])
        return self.install(reader=lambda _: phrase)

    def target(self):
        return self.project/'.agents/skills/demo'

    def state(self):
        return self.project/'.gasl-managed'

    def test_readonly_preview_and_no_user_path_leak(self):
        p = self.preview()
        self.assertTrue(p['eligible_for_fresh_install'])
        self.assertFalse(p['installation_performed'])
        self.assertFalse((self.project/'.agents').exists())
        self.assertNotIn(str(self.project), json.dumps(p))

    def test_genuine_install_and_uninstall_in_temporary_project(self):
        installed = self.matching_install()
        self.assertEqual(installed['status'], 'codex_project_skill_installed')
        self.assertEqual(installed['file_count'], 2)
        self.assertTrue(self.target().is_dir())
        self.assertEqual((self.target()/'SKILL.md').read_bytes(),
                         self.fixture.content['skills/demo/SKILL.md'])
        receipt = _receipt(self.state(), 'demo')
        self.assertTrue(receipt.is_file())
        self.assertFalse(self.preview()['eligible_for_fresh_install'])
        removed = uninstall('demo', self.project,
                            reader=lambda _: _remove_phrase('demo', self.plan_id))
        self.assertEqual(removed['status'], 'codex_project_skill_uninstalled')
        self.assertFalse(self.target().exists())
        self.assertFalse(receipt.exists())
        self.assertTrue((self.project/'.git').exists())

    def test_wrong_or_missing_interactive_consent_refused_without_files(self):
        p = self.preview()
        with self.assertRaisesRegex(ValueError, 'approval'):
            self.install(reader=lambda _: 'WRONG')
        self.assertFalse((self.project/'.agents').exists())
        with self.assertRaisesRegex(ValueError, 'Interactive'):
            self.install(reader=lambda _: '')
        self.assertFalse(self.target().exists())

    def test_stale_preflight_binding_blocks(self):
        p = self.preview()
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.install(binding='0'*64, reader=lambda _: '')
        self.assertFalse(self.target().exists())

    def test_unknown_project_or_user_home_refused(self):
        bad = Path(self.tmp.name)/'not-git'
        bad.mkdir()
        with self.assertRaisesRegex(ValueError, 'Git project root'):
            preview_install(self.plan_id, bad, bundle_root=self.fixture.root,
                            lookup=self.fixture.lookup)

    def test_existing_skill_is_never_replaced(self):
        self.target().mkdir(parents=True)
        old = self.target()/'SKILL.md'
        old.write_text('USER_CONTENT_DO_NOT_TOUCH')
        p = self.preview()
        self.assertEqual(p['prior_target_state'], 'existing_skill_collision')
        self.assertFalse(p['eligible_for_fresh_install'])
        with self.assertRaisesRegex(ValueError, 'occupied'):
            self.install(reader=lambda _: '')
        self.assertEqual(old.read_text(), 'USER_CONTENT_DO_NOT_TOUCH')

    def test_uninstall_preserves_user_edits(self):
        self.matching_install()
        note = self.target()/'note.txt'
        note.write_text('MY_PERSONAL_NOTES')
        with self.assertRaisesRegex(ValueError, 'changed'):
            uninstall('demo', self.project, reader=lambda _: '')
        self.assertEqual(note.read_text(), 'MY_PERSONAL_NOTES')
        self.assertTrue(_receipt(self.state(), 'demo').is_file())

    def test_missing_receipt_refuses_uninstall(self):
        self.target().mkdir(parents=True)
        (self.target()/'SKILL.md').write_text('not managed')
        with self.assertRaisesRegex(ValueError, 'Missing'):
            uninstall('demo', self.project, reader=lambda _: '')

    def test_recover_activated_install_without_receipt(self):
        self.matching_install()
        state = self.state()
        receipt_file = _receipt(state, 'demo')
        receipt = json.loads(receipt_file.read_text())
        receipt_file.unlink()
        _journal(state,'demo').write_text(json.dumps({
            'schema': SCHEMA, 'slug':'demo',
            'operation':'install', 'receipt':receipt}))
        result = recover('demo',self.project)
        self.assertEqual(result['status'], 'partial_install_rolled_back')
        self.assertFalse(self.target().exists())

    def test_recover_completed_install_journal_retains_installed(self):
        self.matching_install()
        state = self.state()
        receipt = json.loads(_receipt(state,'demo').read_text())
        _journal(state,'demo').write_text(json.dumps({
            'schema':SCHEMA,'slug':'demo','operation':'install','receipt':receipt}))
        self.assertEqual(recover('demo', self.project)['status'],
                         'installed_receipt_committed')
        self.assertTrue(self.target().is_dir())

    def test_recover_uninstall_after_target_retired(self):
        self.matching_install()
        state = self.state()
        receipt = json.loads(_receipt(state,'demo').read_text())
        retired = state/'stage'/('retired-'+receipt['transaction'])
        self.target().rename(retired)
        _receipt(state,'demo').unlink()
        _journal(state,'demo').write_text(json.dumps({
            'schema':SCHEMA,'slug':'demo',
            'operation':'uninstall','receipt':receipt}))
        result = recover('demo',self.project)
        self.assertEqual(result['status'],'interrupted_uninstall_restored')
        self.assertTrue(self.target().is_dir())
        self.assertTrue(_receipt(state,'demo').exists())

    def test_zip_tamper_refuses_before_any_write(self):
        archive = Path(self.bundle['archive_path'])
        archive.write_bytes(archive.read_bytes() + b'corruption')
        with self.assertRaisesRegex(ValueError,'archive hash'):
            self.preview()
        self.assertFalse((self.project/'.agents').exists())

    def test_original_package_drift_refuses_before_any_write(self):
        (self.folder/'SKILL.md').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'no longer matches'):
            self.preview()
        self.assertFalse((self.project/'.agents').exists())

    def test_symlink_target_refused(self):
        outside = Path(self.tmp.name)/'outside'
        outside.mkdir()
        (self.project/'.agents').symlink_to(outside)
        with self.assertRaises(ValueError):
            self.preview()
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
