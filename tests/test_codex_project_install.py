"""Phase 40 real project installer, exercised ONLY in disposable synthetic Git repos."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from codex_project_install import (
    preview_install, install_fresh, uninstall, recover,
    _install_phrase, _remove_phrase, _replace_phrase, _journal, _receipt,
    _paths, _backup_dir, _backup_manifest, _checked_backup, preview_replace,
    replace_existing, SCHEMA,
)
import codex_project_install as installer
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
        self.version_counter = 1

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


    def make_next_bundle(self, body=b'# Inert replacement version 2\n'):
        source = (b'---\nname: demo\ndescription: Inert file-only test Skill v2\n---\n'
                  + body)
        self.fixture.content['skills/demo/SKILL.md'] = source
        self.fixture.row['skill_md_blob_sha'] = git_blob(source)
        self.version_counter += 1
        self.fixture.row['commit_sha'] = hashlib.sha1(
            source + str(self.version_counter).encode()).hexdigest()
        self.fixture.row['tree_sha'] = hashlib.sha1(
            b'tree:' + source + str(self.version_counter).encode()).hexdigest()
        self.folder, _ = self.fixture._package()
        return self.fixture._prepare(agent='codex', scope='project')

    def existing_skill(self):
        target = self.target()
        target.mkdir(parents=True)
        (target/'SKILL.md').write_bytes(
            b'---\nname: demo\ndescription: Previous user Skill\n---\n# Original\n')
        (target/'user-note.txt').write_text('KEEP THIS ORIGINAL FILE\n')
        from fixture_bundle_install import _inventory
        return _inventory(target)

    def replace(self, plan_id=None, reader=None, binding=None):
        selected_plan = plan_id or self.plan_id
        preview = preview_replace(selected_plan, self.project,
                                  bundle_root=self.fixture.root, lookup=self.fixture.lookup)
        phrase = _replace_phrase('demo', selected_plan, preview['state_binding_id'])
        return replace_existing(
            selected_plan, self.project,
            binding or preview['state_binding_id'],
            bundle_root=self.fixture.root, lookup=self.fixture.lookup,
            reader=reader or (lambda _: phrase))

    def test_replace_preview_is_read_only_and_reports_existing_unmanaged_skill(self):
        old_files = self.existing_skill()
        preview = preview_replace(self.plan_id, self.project,
                                  bundle_root=self.fixture.root, lookup=self.fixture.lookup)
        self.assertTrue(preview['eligible_for_replace'])
        self.assertFalse(preview['existing_install_managed_by_gasl'])
        self.assertEqual(preview['existing_file_count'], len(old_files))
        self.assertFalse(preview['replacement_performed'])
        self.assertEqual((self.target()/'user-note.txt').read_text(), 'KEEP THIS ORIGINAL FILE\n')
        self.assertFalse((self.project/'.gasl-managed').exists())

    def test_replace_unmanaged_skill_keeps_full_verified_backup(self):
        old_files = self.existing_skill()
        result = self.replace()
        self.assertEqual(result['status'], 'codex_project_skill_replaced')
        self.assertTrue(result['previous_skill_restorable'])
        state = self.state()
        backup = _backup_dir(state, 'demo', result['backup_id'])
        manifest_path = _backup_manifest(state, 'demo', result['backup_id'])
        from fixture_bundle_install import _inventory
        self.assertEqual(_inventory(backup), old_files)
        self.assertTrue((backup/'user-note.txt').is_file())
        manifest = _checked_backup(json.loads(manifest_path.read_text()),
                                   'demo', result['backup_id'])
        self.assertIsNone(manifest['previous_receipt'])
        receipt = json.loads(_receipt(state, 'demo').read_text())
        self.assertEqual(receipt['action'], 'replace_install')
        self.assertEqual(receipt['backup_ids'], [result['backup_id']])
        self.assertFalse((self.target()/'user-note.txt').exists())
        self.assertTrue((self.target()/'SKILL.md').read_bytes().endswith(
            b'# No scripts are run during any test.\n'))

    def test_replace_managed_skill_preserves_previous_receipt_in_backup(self):
        self.matching_install()
        previous_receipt = json.loads(_receipt(self.state(), 'demo').read_text())
        new_bundle = self.make_next_bundle()
        result = self.replace(new_bundle['plan_id'])
        manifest = _checked_backup(
            json.loads(_backup_manifest(self.state(), 'demo', result['backup_id']).read_text()),
            'demo', result['backup_id'])
        self.assertEqual(manifest['previous_receipt'], previous_receipt)
        self.assertEqual(manifest['files'], previous_receipt['files'])
        current = json.loads(_receipt(self.state(), 'demo').read_text())
        self.assertEqual(current['plan_id'], new_bundle['plan_id'])
        self.assertEqual(current['backup_ids'], [result['backup_id']])

    def test_repeated_replacement_preserves_all_verified_backup_history(self):
        self.existing_skill()
        first = self.replace()
        second_bundle = self.make_next_bundle(b'# Inert replacement version 3\n')
        second = self.replace(second_bundle['plan_id'])
        current = json.loads(_receipt(self.state(), 'demo').read_text())
        self.assertEqual(current['backup_ids'], [first['backup_id'], second['backup_id']])
        for backup_id in current['backup_ids']:
            manifest = _checked_backup(
                json.loads(_backup_manifest(self.state(), 'demo', backup_id).read_text()),
                'demo', backup_id)
            from fixture_bundle_install import _inventory
            self.assertEqual(_inventory(_backup_dir(self.state(), 'demo', backup_id)),
                             manifest['files'])

    def test_replace_requires_exact_interactive_confirmation(self):
        old_files = self.existing_skill()
        p = preview_replace(self.plan_id, self.project,
                            bundle_root=self.fixture.root, lookup=self.fixture.lookup)
        with self.assertRaisesRegex(ValueError, 'approval'):
            self.replace(reader=lambda _: 'NO')
        from fixture_bundle_install import _inventory
        self.assertEqual(_inventory(self.target()), old_files)
        self.assertFalse((self.project/'.gasl-managed').exists())

    def test_replace_stale_target_binding_blocks_before_confirmation(self):
        self.existing_skill()
        p = preview_replace(self.plan_id, self.project,
                            bundle_root=self.fixture.root, lookup=self.fixture.lookup)
        (self.target()/'late-note.txt').write_text('added after preview')
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.replace(binding=p['state_binding_id'], reader=lambda _: '')
        self.assertTrue((self.target()/'late-note.txt').exists())

    def test_replace_modified_managed_skill_refuses_and_preserves_user_edit(self):
        self.matching_install()
        (self.target()/'user-edit.txt').write_text('DO NOT DELETE')
        new_bundle = self.make_next_bundle()
        with self.assertRaisesRegex(ValueError, 'changed since installation'):
            preview_replace(new_bundle['plan_id'], self.project,
                            bundle_root=self.fixture.root, lookup=self.fixture.lookup)
        self.assertEqual((self.target()/'user-edit.txt').read_text(), 'DO NOT DELETE')

    def test_uninstall_retains_verified_previous_version_backups(self):
        self.existing_skill()
        replaced = self.replace()
        removed = uninstall('demo', self.project,
                            reader=lambda _: _remove_phrase('demo', self.plan_id))
        self.assertTrue(removed['backups_retained'])
        self.assertEqual(removed['retained_backup_ids'], [replaced['backup_id']])
        self.assertTrue(_backup_dir(self.state(), 'demo', replaced['backup_id']).is_dir())
        self.assertFalse(_receipt(self.state(), 'demo').exists())

    def test_recover_interrupted_replace_after_old_directory_moved(self):
        old_files = self.existing_skill()
        original_new = installer._new
        calls = {'count': 0}
        def fail_backup_manifest(path, data):
            calls['count'] += 1
            if calls['count'] == 2:
                raise OSError('injected failure after old directory was moved')
            return original_new(path, data)
        from unittest.mock import patch
        with patch.object(installer, '_new', side_effect=fail_backup_manifest):
            with self.assertRaisesRegex(OSError, 'injected failure'):
                self.replace()
        self.assertFalse(self.target().exists())
        recovered = recover('demo', self.project)
        self.assertEqual(recovered['status'], 'interrupted_replacement_rolled_back')
        from fixture_bundle_install import _inventory
        self.assertEqual(_inventory(self.target()), old_files)
        self.assertFalse(_journal(self.state(), 'demo').exists())
        self.assertFalse(any((self.state()/'backups'/'demo').glob('*.json')))

    def test_recover_interrupted_replace_after_new_directory_activated(self):
        old_files = self.existing_skill()
        from unittest.mock import patch
        with patch.object(installer, '_atomic_record',
                          side_effect=OSError('injected receipt commit failure')):
            with self.assertRaisesRegex(OSError, 'receipt commit'):
                self.replace()
        self.assertTrue(self.target().is_dir())
        recovered = recover('demo', self.project)
        self.assertEqual(recovered['status'], 'interrupted_replacement_rolled_back')
        from fixture_bundle_install import _inventory
        self.assertEqual(_inventory(self.target()), old_files)
        self.assertFalse(_receipt(self.state(), 'demo').exists())
        self.assertFalse(_journal(self.state(), 'demo').exists())

    def test_recovery_refuses_modified_new_target_without_destroying_backup(self):
        self.existing_skill()
        from unittest.mock import patch
        with patch.object(installer, '_atomic_record',
                          side_effect=OSError('injected receipt commit failure')):
            with self.assertRaises(OSError):
                self.replace()
        backup_root = self.state()/'backups'/'demo'
        backup = next(path for path in backup_root.iterdir() if path.is_dir())
        (self.target()/'user-edit.txt').write_text('USER DATA')
        with self.assertRaisesRegex(ValueError, 'target changed'):
            recover('demo', self.project)
        self.assertEqual((self.target()/'user-edit.txt').read_text(), 'USER DATA')
        self.assertTrue((backup/'user-note.txt').exists())

    def test_recovery_validates_backup_before_removing_new_target(self):
        self.existing_skill()
        from unittest.mock import patch
        with patch.object(installer, '_atomic_record',
                          side_effect=OSError('injected receipt commit failure')):
            with self.assertRaises(OSError):
                self.replace()
        backup_root = self.state()/'backups'/'demo'
        backup = next(path for path in backup_root.iterdir() if path.is_dir())
        (backup/'user-note.txt').write_text('TAMPERED BACKUP')
        with self.assertRaisesRegex(ValueError, 'backup changed'):
            recover('demo', self.project)
        self.assertTrue((self.target()/'SKILL.md').is_file())
        self.assertEqual((backup/'user-note.txt').read_text(), 'TAMPERED BACKUP')

    def test_recover_commit_marker_keeps_replacement_and_backup(self):
        self.existing_skill()
        result = self.replace()
        state = self.state()
        receipt = json.loads(_receipt(state, 'demo').read_text())
        manifest = json.loads(_backup_manifest(state, 'demo', result['backup_id']).read_text())
        # Recreate the last durable journal checkpoint: receipt already committed.
        _journal(state, 'demo').write_text(json.dumps({
            'schema': SCHEMA, 'slug': 'demo', 'operation': 'replace',
            'transaction': result['backup_id'], 'backup_id': result['backup_id'],
            'previous_receipt': manifest['previous_receipt'],
            'old_files': manifest['files'], 'new_files': receipt['files'],
            'receipt': receipt,
        }))
        recovered = recover('demo', self.project)
        self.assertEqual(recovered['status'], 'replacement_commit_recovered')
        self.assertTrue(self.target().is_dir())
        self.assertTrue(_backup_dir(state, 'demo', result['backup_id']).is_dir())
        self.assertFalse(_journal(state, 'demo').exists())

    def test_replace_refuses_symlink_inside_existing_skill(self):
        target = self.target()
        target.mkdir(parents=True)
        (target/'SKILL.md').write_text(
            '---\nname: demo\ndescription: old\n---\n')
        outside = Path(self.tmp.name)/'outside'
        outside.write_text('DO NOT READ OR CHANGE')
        (target/'link.txt').symlink_to(outside)
        with self.assertRaises(ValueError):
            preview_replace(self.plan_id, self.project,
                            bundle_root=self.fixture.root, lookup=self.fixture.lookup)
        self.assertEqual(outside.read_text(), 'DO NOT READ OR CHANGE')

    def test_next_replace_refuses_if_retained_backup_was_modified(self):
        self.existing_skill()
        first = self.replace()
        backup = _backup_dir(self.state(), 'demo', first['backup_id'])
        (backup/'user-note.txt').write_text('TAMPERED')
        next_bundle = self.make_next_bundle(b'# Inert replacement version 4\n')
        with self.assertRaisesRegex(ValueError, 'backup changed'):
            preview_replace(next_bundle['plan_id'], self.project,
                            bundle_root=self.fixture.root, lookup=self.fixture.lookup)


if __name__ == '__main__':
    unittest.main()
