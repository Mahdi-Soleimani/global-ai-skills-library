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


    def prepare_managed_restore(self):
        """Install a pinned v1, replace with pinned v2, return both identities."""
        self.matching_install()
        original = (self.target()/'SKILL.md').read_bytes()
        upgraded = self.make_next_bundle(b'# Restorable pinned version two\n')
        replaced = self.replace(upgraded['plan_id'])
        self.assertNotEqual((self.target()/'SKILL.md').read_bytes(), original)
        return original, upgraded, replaced

    def restore(self, backup_id, reader=None, binding=None):
        p = installer.preview_restore('demo', self.project, backup_id)
        phrase = installer._restore_phrase(
            'demo', backup_id, p['current_plan_id'], p['state_binding_id'])
        return installer.restore_backup(
            'demo', self.project, backup_id,
            binding or p['state_binding_id'],
            reader=(lambda _: phrase) if reader is None else reader)

    def test_restore_preview_is_read_only_and_has_explicit_source_provenance(self):
        original, upgraded, first = self.prepare_managed_restore()
        p = installer.preview_restore('demo', self.project, first['backup_id'])
        self.assertEqual(p['status'], 'codex_project_backup_restore_preview_only')
        self.assertTrue(p['eligible_for_restore'])
        self.assertEqual(p['restored_source_kind'], 'pinned')
        self.assertEqual(p['restored_upstream_plan_id'], self.plan_id)
        self.assertEqual(p['current_plan_id'], upgraded['plan_id'])
        self.assertFalse(p['restore_performed'])
        self.assertNotIn(str(self.project), json.dumps(p))
        self.assertFalse(any((self.state()/'stage').iterdir()))
        self.assertFalse(_journal(self.state(), 'demo').exists())

    def test_restore_committed_managed_version_with_current_backup_preserved(self):
        original, upgraded, first = self.prepare_managed_restore()
        current = (self.target()/'SKILL.md').read_bytes()
        result = self.restore(first['backup_id'])
        self.assertEqual(result['status'], 'codex_project_skill_backup_restored')
        self.assertEqual((self.target()/'SKILL.md').read_bytes(), original)
        self.assertTrue(result['current_version_backed_up'])
        self.assertTrue(result['selected_backup_preserved'])
        self.assertNotEqual(result['saved_current_backup_id'], first['backup_id'])
        saved = _backup_dir(self.state(), 'demo', result['saved_current_backup_id'])
        self.assertEqual((saved/'SKILL.md').read_bytes(), current)
        old = _backup_dir(self.state(), 'demo', first['backup_id'])
        self.assertEqual((old/'SKILL.md').read_bytes(), original)
        old_manifest = _checked_backup(
            json.loads(_backup_manifest(self.state(), 'demo', first['backup_id']).read_text()),
            'demo', first['backup_id'])
        self.assertEqual(old_manifest['previous_receipt']['plan_id'], self.plan_id)
        receipt = json.loads(_receipt(self.state(), 'demo').read_text())
        self.assertEqual(receipt['plan_id'], self.plan_id)
        self.assertEqual(receipt['source_kind'], 'pinned')
        self.assertEqual(receipt['action'], 'restore_backup')
        self.assertEqual(receipt['backup_ids'],
                         [first['backup_id'], result['saved_current_backup_id']])

    def test_restore_unmanaged_backup_preserves_notes_and_marks_unpinned_origin(self):
        old_files = self.existing_skill()
        first = self.replace()
        restored = self.restore(first['backup_id'])
        self.assertEqual(restored['restored_source_kind'], 'unmanaged')
        self.assertEqual((self.target()/'user-note.txt').read_text(),
                         'KEEP THIS ORIGINAL FILE\n')
        from fixture_bundle_install import _inventory
        self.assertEqual(_inventory(self.target()), old_files)
        receipt = json.loads(_receipt(self.state(), 'demo').read_text())
        self.assertEqual(receipt['source_kind'], 'unmanaged')
        self.assertTrue(receipt['unmanaged_restore_plan_id_derived'])
        self.assertNotEqual(receipt['plan_id'], self.plan_id)
        self.assertEqual(len(receipt['plan_id']), 64)
        self.assertTrue(_backup_dir(
            self.state(), 'demo', restored['saved_current_backup_id']).is_dir())
        removed = uninstall('demo', self.project, reader=lambda _:
                            _remove_phrase('demo', receipt['plan_id']))
        self.assertTrue(removed['backups_retained'])
        self.assertFalse(self.target().exists())
        self.assertEqual(len(removed['retained_backup_ids']), 2)

    def test_restore_multiple_times_keeps_all_historical_backups(self):
        original, upgraded, first = self.prepare_managed_restore()
        v2 = (self.target()/'SKILL.md').read_bytes()
        one = self.restore(first['backup_id'])
        two = self.restore(one['saved_current_backup_id'])
        self.assertEqual((self.target()/'SKILL.md').read_bytes(), v2)
        history = json.loads(_receipt(self.state(), 'demo').read_text())['backup_ids']
        self.assertEqual(history, [first['backup_id'], one['saved_current_backup_id'],
                                   two['saved_current_backup_id']])
        from fixture_bundle_install import _inventory
        for ident in history:
            manifest = _checked_backup(
                json.loads(_backup_manifest(self.state(),'demo',ident).read_text()),
                'demo', ident)
            self.assertEqual(_inventory(_backup_dir(self.state(),'demo',ident)),
                             manifest['files'])
        self.assertEqual(
            (_backup_dir(self.state(),'demo',first['backup_id'])/'SKILL.md').read_bytes(),
            original)

    def test_restore_interactive_approval_refused_without_any_changes(self):
        original, upgraded, first = self.prepare_managed_restore()
        receipt_before = _receipt(self.state(),'demo').read_bytes()
        current = (self.target()/'SKILL.md').read_bytes()
        with self.assertRaisesRegex(ValueError, 'approval'):
            self.restore(first['backup_id'], reader=lambda _: 'NOT APPROVED')
        self.assertEqual(_receipt(self.state(),'demo').read_bytes(), receipt_before)
        self.assertEqual((self.target()/'SKILL.md').read_bytes(), current)
        self.assertFalse(_journal(self.state(),'demo').exists())
        self.assertEqual(list((self.state()/'backups'/'demo').glob('*.json')),
                         [_backup_manifest(self.state(),'demo',first['backup_id'])])

    def test_restore_stale_binding_refuses_after_another_completed_upgrade(self):
        original, upgraded, first = self.prepare_managed_restore()
        preview = installer.preview_restore('demo',self.project,first['backup_id'])
        other = self.make_next_bundle(b'# Pinned version three for stale binding\n')
        self.replace(other['plan_id'])
        with self.assertRaisesRegex(ValueError, 'changed since preview'):
            self.restore(first['backup_id'], binding=preview['state_binding_id'])
        self.assertIn(b'version three', (self.target()/'SKILL.md').read_bytes())

    def test_restore_refuses_changed_backup_and_changed_active_version(self):
        original, upgraded, first = self.prepare_managed_restore()
        backup = _backup_dir(self.state(),'demo',first['backup_id'])
        (backup/'SKILL.md').write_text('TAMPERED')
        with self.assertRaisesRegex(ValueError,'backup changed'):
            installer.preview_restore('demo',self.project,first['backup_id'])
        (backup/'SKILL.md').write_bytes(original)
        (self.target()/'new-note.txt').write_text('USER EDIT')
        with self.assertRaisesRegex(ValueError,'Installed Skill changed'):
            installer.preview_restore('demo',self.project,first['backup_id'])
        self.assertEqual((self.target()/'new-note.txt').read_text(),'USER EDIT')

    def test_restore_invalid_and_foreign_backup_id_is_rejected(self):
        original, upgraded, first = self.prepare_managed_restore()
        with self.assertRaisesRegex(ValueError,'Invalid selected backup'):
            installer.preview_restore('demo',self.project,'../outside')
        with self.assertRaisesRegex(ValueError,'not owned'):
            installer.preview_restore('demo',self.project,'a'*32)
        self.assertFalse((self.project/'.gasl-managed'/'backups'/'demo'/('a'*32)).exists())

    def test_restore_symlink_backup_directory_refused_without_following(self):
        original, upgraded, first = self.prepare_managed_restore()
        backup = _backup_dir(self.state(),'demo',first['backup_id'])
        outside = Path(self.tmp.name)/'outside-user'
        backup.rename(outside)
        backup.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            installer.preview_restore('demo',self.project,first['backup_id'])
        self.assertEqual((outside/'SKILL.md').read_bytes(),original)

    def test_restore_crash_after_current_backup_rename_recovers_current_version(self):
        original, upgraded, first = self.prepare_managed_restore()
        current = (self.target()/'SKILL.md').read_bytes()
        receipt_before = _receipt(self.state(),'demo').read_bytes()
        original_new = installer._new
        calls = {'n':0}
        def fail_on_current_backup_manifest(path,data):
            calls['n']+=1
            if calls['n']==2:
                raise OSError('injected crash after current backup')
            return original_new(path,data)
        from unittest.mock import patch
        with patch.object(installer, '_new',side_effect=fail_on_current_backup_manifest):
            with self.assertRaisesRegex(OSError,'crash after current backup'):
                self.restore(first['backup_id'])
        self.assertFalse(self.target().exists())
        result = recover('demo',self.project)
        self.assertEqual(result['status'],'interrupted_restore_rolled_back')
        self.assertEqual((self.target()/'SKILL.md').read_bytes(),current)
        self.assertEqual(_receipt(self.state(),'demo').read_bytes(),receipt_before)
        self.assertFalse(_journal(self.state(),'demo').exists())
        self.assertEqual((_backup_dir(self.state(),'demo',first['backup_id'])
                          /'SKILL.md').read_bytes(),original)

    def test_restore_crash_after_activation_rolls_back_without_losing_versions(self):
        original, upgraded, first = self.prepare_managed_restore()
        current = (self.target()/'SKILL.md').read_bytes()
        receipt_before = _receipt(self.state(),'demo').read_bytes()
        from unittest.mock import patch
        with patch.object(installer,'_atomic_record',
                          side_effect=OSError('injected restore receipt commit failure')):
            with self.assertRaisesRegex(OSError,'restore receipt commit'):
                self.restore(first['backup_id'])
        self.assertEqual((self.target()/'SKILL.md').read_bytes(),original)
        result = recover('demo',self.project)
        self.assertEqual(result['status'],'interrupted_restore_rolled_back')
        self.assertEqual((self.target()/'SKILL.md').read_bytes(),current)
        self.assertEqual(_receipt(self.state(),'demo').read_bytes(),receipt_before)
        self.assertFalse(_journal(self.state(),'demo').exists())

    def test_restore_recovery_refuses_modified_new_target_and_preserves_backups(self):
        original, upgraded, first = self.prepare_managed_restore()
        from unittest.mock import patch
        with patch.object(installer,'_atomic_record',side_effect=OSError('injected')):
            with self.assertRaises(OSError):
                self.restore(first['backup_id'])
        (self.target()/'user-edit.txt').write_text('DO NOT REMOVE')
        with self.assertRaisesRegex(ValueError,'target changed'):
            recover('demo',self.project)
        self.assertEqual((self.target()/'user-edit.txt').read_text(),'DO NOT REMOVE')
        self.assertEqual(len(list((self.state()/'backups'/'demo').glob('*.json'))),2)
        self.assertTrue(_journal(self.state(),'demo').exists())

    def test_restore_recovery_refuses_tampered_current_backup(self):
        original, upgraded, first = self.prepare_managed_restore()
        from unittest.mock import patch
        with patch.object(installer,'_atomic_record',side_effect=OSError('injected')):
            with self.assertRaises(OSError):
                self.restore(first['backup_id'])
        current_backup = next(
            p for p in (self.state()/'backups'/'demo').iterdir()
            if p.is_dir() and p.name != first['backup_id'])
        (current_backup/'SKILL.md').write_text('TAMPERED ACTIVE BACKUP')
        with self.assertRaisesRegex(ValueError,'Saved current-version backup changed'):
            recover('demo',self.project)
        self.assertTrue(self.target().is_dir())
        self.assertEqual((current_backup/'SKILL.md').read_text(),'TAMPERED ACTIVE BACKUP')

    def test_restore_recovery_after_committed_receipt_keeps_both_backups(self):
        original, upgraded, first = self.prepare_managed_restore()
        restored = self.restore(first['backup_id'])
        state = self.state()
        receipt = json.loads(_receipt(state,'demo').read_text())
        current_manifest = json.loads(
            _backup_manifest(state,'demo',restored['saved_current_backup_id']).read_text())
        selected_manifest = json.loads(
            _backup_manifest(state,'demo',first['backup_id']).read_text())
        _journal(state,'demo').write_text(json.dumps({
            'schema':SCHEMA,'slug':'demo','operation':'restore',
            'transaction':restored['saved_current_backup_id'],
            'current_backup_id':restored['saved_current_backup_id'],
            'selected_backup_id':first['backup_id'],
            'selected_manifest':selected_manifest,
            'previous_receipt':current_manifest['previous_receipt'],
            'receipt':receipt,
            'current_files':current_manifest['files'],
            'restored_files':selected_manifest['files'],
            'binding':receipt['binding'],
        }))
        result = recover('demo',self.project)
        self.assertEqual(result['status'],'restore_commit_recovered')
        self.assertTrue(result['backup_retained'])
        self.assertFalse(_journal(state,'demo').exists())
        self.assertEqual((self.target()/'SKILL.md').read_bytes(),original)
        self.assertTrue(
            _backup_dir(state,'demo',restored['saved_current_backup_id']).is_dir())

    def test_restore_pending_transaction_blocks_second_restore(self):
        original, upgraded, first = self.prepare_managed_restore()
        from unittest.mock import patch
        with patch.object(installer,'_atomic_record',side_effect=OSError('injected')):
            with self.assertRaises(OSError):
                self.restore(first['backup_id'])
        with self.assertRaisesRegex(ValueError,'Pending transaction'):
            installer.preview_restore('demo',self.project,first['backup_id'])
        self.assertTrue(_journal(self.state(),'demo').exists())


    def test_restore_refuses_noop_backup_with_identical_file_inventory(self):
        self.matching_install()
        same_bytes = self.fixture.content['skills/demo/SKILL.md']
        bundle = self.make_next_bundle(b'# Identical file inventory rejected\n')
        # Make a new distinct source pin whose SKILL.md content is exactly v1.
        # The new Plan ID differs while the installed bytes remain identical.
        self.fixture.content['skills/demo/SKILL.md'] = same_bytes
        self.fixture.row['skill_md_blob_sha'] = git_blob(same_bytes)
        self.fixture.row['commit_sha'] = hashlib.sha1(b'same-content-commit').hexdigest()
        self.fixture.row['tree_sha'] = hashlib.sha1(b'same-content-tree').hexdigest()
        self.fixture._package()
        same_bundle = self.fixture._prepare(agent='codex',scope='project')
        replaced = self.replace(same_bundle['plan_id'])
        with self.assertRaisesRegex(ValueError, 'byte-identical'):
            installer.preview_restore('demo',self.project,replaced['backup_id'])
        self.assertFalse(_journal(self.state(),'demo').exists())

    def test_restore_crash_after_journal_before_backup_rename_recovers(self):
        original, upgraded, first = self.prepare_managed_restore()
        current = (self.target()/'SKILL.md').read_bytes()
        before = _receipt(self.state(),'demo').read_bytes()
        old_new = installer._new
        def after_journal_created(path,data):
            old_new(path,data)
            if data.get('operation') == 'restore':
                raise OSError('injected crash after journaling')
        from unittest.mock import patch
        with patch.object(installer,'_new',side_effect=after_journal_created):
            with self.assertRaisesRegex(OSError,'after journaling'):
                self.restore(first['backup_id'])
        self.assertEqual((self.target()/'SKILL.md').read_bytes(),current)
        self.assertEqual(recover('demo',self.project)['status'],
                         'interrupted_restore_rolled_back')
        self.assertEqual(_receipt(self.state(),'demo').read_bytes(),before)
        self.assertEqual((self.target()/'SKILL.md').read_bytes(),current)
        self.assertFalse(_journal(self.state(),'demo').exists())

    def test_restore_commit_failure_after_atomic_receipt_write_finishes_commit(self):
        original, upgraded, first = self.prepare_managed_restore()
        original_atomic = installer._atomic_record
        def after_commit(path,data,old):
            original_atomic(path,data,old)
            raise OSError('injected crash after new receipt committed')
        from unittest.mock import patch
        with patch.object(installer,'_atomic_record',side_effect=after_commit):
            with self.assertRaisesRegex(OSError,'after new receipt'):
                self.restore(first['backup_id'])
        self.assertEqual((self.target()/'SKILL.md').read_bytes(),original)
        done = recover('demo',self.project)
        self.assertEqual(done['status'],'restore_commit_recovered')
        self.assertTrue(done['backup_retained'])
        self.assertFalse(_journal(self.state(),'demo').exists())

    def test_restore_recovery_refuses_selected_backup_tampering(self):
        original, upgraded, first = self.prepare_managed_restore()
        from unittest.mock import patch
        with patch.object(installer,'_atomic_record',side_effect=OSError('injected')):
            with self.assertRaises(OSError):
                self.restore(first['backup_id'])
        selected = _backup_dir(self.state(),'demo',first['backup_id'])
        (selected/'SKILL.md').write_text('MUTATED CHOSEN BACKUP')
        with self.assertRaisesRegex(ValueError,'backup changed'):
            recover('demo',self.project)
        self.assertTrue(_journal(self.state(),'demo').exists())
        self.assertEqual((selected/'SKILL.md').read_text(),'MUTATED CHOSEN BACKUP')

    def test_restore_cli_preview_only_and_unattended_restore_refused(self):
        import subprocess
        original, upgraded, first = self.prepare_managed_restore()
        args = [str(ROOT/'gasl'),'codex-project-install',
                '--selected-root',str(self.project),
                '--skill-name','demo','--backup-id',first['backup_id']]
        response = subprocess.run(
            args+['--action','preview-restore'],capture_output=True,text=True,
            check=True)
        preview=json.loads(response.stdout)
        self.assertEqual(preview['restored_upstream_plan_id'],self.plan_id)
        self.assertNotIn(str(self.project),response.stdout)
        self.assertFalse(_journal(self.state(),'demo').exists())
        pending = subprocess.run(
            args+['--action','restore-backup','--state-binding-id',
                  preview['state_binding_id']],capture_output=True,text=True)
        self.assertNotEqual(pending.returncode,0)
        self.assertIn('local interactive TTY',pending.stderr)
        self.assertFalse(_journal(self.state(),'demo').exists())
        self.assertIn(b'version two',(self.target()/'SKILL.md').read_bytes())



    def test_list_backups_shows_verified_history_without_local_paths(self):
        original, upgraded, first = self.prepare_managed_restore()
        listing = installer.list_backups('demo', self.project)
        self.assertEqual(listing['status'], 'codex_project_backups_listed_read_only')
        self.assertEqual(listing['backup_count'],1)
        self.assertEqual(listing['backups'][0]['backup_id'],first['backup_id'])
        self.assertEqual(listing['backups'][0]['source_kind'],'pinned')
        self.assertTrue(listing['backups'][0]['eligible_for_restore'])
        self.assertTrue(listing['backups'][0]['backup_integrity_verified'])
        self.assertNotIn(str(self.project),json.dumps(listing))
        self.assertFalse(_journal(self.state(),'demo').exists())
        selected = self.restore(first['backup_id'])
        after = installer.list_backups('demo',self.project)
        self.assertEqual(after['backup_count'],2)
        self.assertFalse(after['backups'][0]['eligible_for_restore'])
        self.assertTrue(after['backups'][1]['eligible_for_restore'])

    def test_list_backups_refuses_modified_retained_files(self):
        original, upgraded, first = self.prepare_managed_restore()
        archive = _backup_dir(self.state(),'demo',first['backup_id'])
        (archive/'SKILL.md').write_text('INVALID BACKUP')
        with self.assertRaisesRegex(ValueError,'backup changed'):
            installer.list_backups('demo',self.project)
        self.assertEqual((archive/'SKILL.md').read_text(),'INVALID BACKUP')

    def test_list_backups_cli_matches_library_and_is_readonly(self):
        import subprocess
        original, upgraded, first = self.prepare_managed_restore()
        command = [str(ROOT/'gasl'),'codex-project-install',
                   '--action','list-backups','--selected-root',str(self.project),
                   '--skill-name','demo']
        response=subprocess.run(command,check=True,capture_output=True,text=True)
        listing=json.loads(response.stdout)
        self.assertEqual(listing['backup_count'],1)
        self.assertEqual(listing['backups'][0]['backup_id'],first['backup_id'])
        self.assertNotIn(str(self.project),response.stdout)
        self.assertFalse(_journal(self.state(),'demo').exists())


if __name__ == '__main__':
    unittest.main()
