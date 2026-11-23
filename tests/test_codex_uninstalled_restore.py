"""Phase 43: explicit reinstatement after uninstall, only in disposable Git projects."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import codex_project_install as installer
import codex_uninstalled_restore as archived
from tests import test_codex_project_install as fixture_module


class UninstalledBackupTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture_module.ProjectInstallTests('test_genuine_install_and_uninstall_in_temporary_project')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.project = self.case.project
        self.slug = 'demo'

    @property
    def target(self):
        return self.case.target()

    @property
    def state(self):
        return self.case.state()

    def initial_uninstall(self):
        self.case.matching_install()
        result = installer.uninstall('demo', self.project,
             reader=lambda _: installer._remove_phrase('demo', self.case.plan_id))
        self.assertFalse(self.target.exists())
        self.assertFalse(installer._receipt(self.state, 'demo').exists())
        return result

    def preview(self, backup_id):
        return archived.preview_reinstall('demo', self.project, backup_id)

    def reinstall(self, backup_id, *, binding=None, reader=None):
        p = self.preview(backup_id)
        marker = archived._read_marker(self.project, 'demo', self.state)
        phrase = archived._reinstall_phrase(
            'demo', backup_id, marker['uninstall_event_id'], p['state_binding_id'])
        return archived.reinstall_backup(
            'demo', self.project, backup_id,
            binding if binding is not None else p['state_binding_id'],
            reader=(lambda _: phrase) if reader is None else reader)

    def test_fresh_uninstall_archives_active_skill_and_records_ownership(self):
        old = self.case.fixture.content['skills/demo/SKILL.md']
        removed = self.initial_uninstall()
        self.assertTrue(removed['uninstall_ownership_marker_recorded'])
        self.assertEqual(removed['status'], 'codex_project_skill_uninstalled')
        self.assertEqual(len(removed['retained_backup_ids']), 1)
        selected = removed['archived_last_active_backup_id']
        self.assertEqual(selected, removed['retained_backup_ids'][-1])
        self.assertEqual(
            (archived._backup_dir(self.state, 'demo', selected)/'SKILL.md').read_bytes(), old)
        marker = archived._read_marker(self.project, 'demo', self.state)
        self.assertEqual(marker['last_receipt']['plan_id'], self.case.plan_id)
        self.assertEqual(marker['backup_ids'], removed['retained_backup_ids'])
        listing = archived.list_uninstalled_backups('demo', self.project)
        self.assertEqual(listing['backup_count'], 1)
        self.assertTrue(listing['backups'][0]['last_active_before_uninstall'])
        self.assertEqual(listing['backups'][0]['upstream_plan_id'], self.case.plan_id)
        self.assertNotIn(str(self.project), json.dumps(listing))

    def test_uninstalled_preview_is_read_only_and_fresh_install_blocked(self):
        removed = self.initial_uninstall()
        p = self.preview(removed['archived_last_active_backup_id'])
        self.assertEqual(p['status'], 'codex_uninstalled_backup_reinstall_preview_only')
        self.assertTrue(p['uninstall_ownership_verified'])
        self.assertFalse(p['reinstall_performed'])
        self.assertFalse(self.target.exists())
        self.assertFalse(installer._journal(self.state, 'demo').exists())
        fresh = self.case.preview()
        self.assertFalse(fresh['eligible_for_fresh_install'])
        self.assertTrue(fresh['retained_uninstall_ownership_exists'])

    def test_reinstall_active_archive_restores_previous_files_without_consuming_backup(self):
        old = self.case.fixture.content['skills/demo/SKILL.md']
        removed = self.initial_uninstall()
        selected = removed['archived_last_active_backup_id']
        result = self.reinstall(selected)
        self.assertEqual(result['status'], 'codex_uninstalled_skill_reinstalled_from_backup')
        self.assertTrue(result['backup_history_retained'])
        self.assertEqual((self.target/'SKILL.md').read_bytes(), old)
        self.assertEqual((archived._backup_dir(self.state,'demo',selected)/'SKILL.md').read_bytes(),old)
        self.assertTrue(archived._marker_path(self.state,'demo').exists())
        receipt = installer._checked_receipt(
            installer._load(installer._receipt(self.state,'demo')), 'demo')
        self.assertEqual(receipt['action'], 'reinstall_backup')
        self.assertEqual(receipt['source_kind'], 'pinned')
        self.assertEqual(receipt['backup_ids'], [selected])
        self.assertEqual(receipt['uninstall_event_id'], selected)
        self.assertFalse(installer._journal(self.state,'demo').exists())

    def test_chained_history_survives_uninstall_and_selecting_older_backup(self):
        self.case.existing_skill()
        initial = self.case.replace()
        second = self.case.make_next_bundle(b'# Inert v3\n')
        next_step = self.case.replace(second['plan_id'])
        current = (self.target/'SKILL.md').read_bytes()
        last_receipt = installer._load(installer._receipt(self.state,'demo'))
        removed = installer.uninstall('demo', self.project, reader=lambda _:
                                       installer._remove_phrase('demo', second['plan_id']))
        self.assertEqual(len(removed['retained_backup_ids']), 3)
        listing = archived.list_uninstalled_backups('demo',self.project)
        self.assertEqual([x['backup_id'] for x in listing['backups']],
                         removed['retained_backup_ids'])
        self.assertEqual(listing['backups'][0]['source_kind'],'unmanaged')
        self.assertTrue(listing['backups'][2]['last_active_before_uninstall'])
        restored = self.reinstall(initial['backup_id'])
        self.assertEqual(restored['restored_source_kind'], 'unmanaged')
        self.assertTrue((self.target/'user-note.txt').is_file())
        rec=installer._load(installer._receipt(self.state,'demo'))
        self.assertEqual(rec['backup_ids'],removed['retained_backup_ids'])
        self.assertEqual(rec['source_kind'],'unmanaged')
        self.assertTrue(rec['unmanaged_restore_plan_id_derived'])
        self.assertEqual(
            (archived._backup_dir(self.state,'demo',removed['archived_last_active_backup_id'])
             /'SKILL.md').read_bytes(),current)

    def test_uninstall_reinstall_second_uninstall_updates_owner_history(self):
        initial = self.initial_uninstall()
        self.reinstall(initial['archived_last_active_backup_id'])
        again = installer.uninstall('demo',self.project,reader=lambda _:
                                   installer._remove_phrase('demo',self.case.plan_id))
        self.assertEqual(len(again['retained_backup_ids']),2)
        self.assertEqual(again['retained_backup_ids'][0],
                         initial['archived_last_active_backup_id'])
        self.assertNotEqual(again['archived_last_active_backup_id'],
                            initial['archived_last_active_backup_id'])
        listing=archived.list_uninstalled_backups('demo',self.project)
        self.assertEqual(listing['backup_count'],2)
        self.reinstall(again['archived_last_active_backup_id'])
        self.assertTrue(self.target.is_dir())

    def test_reinstall_refuses_wrong_phrase_and_noninteractive_cli(self):
        removed = self.initial_uninstall()
        selected = removed['archived_last_active_backup_id']
        with self.assertRaisesRegex(ValueError,'approval'):
            self.reinstall(selected,reader=lambda _: 'NO')
        self.assertFalse(self.target.exists())
        assert not installer._journal(self.state,'demo').exists()
        args=[str(ROOT/'gasl'),'codex-project-install',
              '--selected-root',str(self.project),'--skill-name','demo',
              '--backup-id',selected]
        preview=subprocess.run(args+['--action','preview-reinstall'],
                               check=True,text=True,capture_output=True)
        p=json.loads(preview.stdout)
        self.assertNotIn(str(self.project),preview.stdout)
        refused=subprocess.run(args+['--action','reinstall-backup',
                         '--state-binding-id',p['state_binding_id']],
                         text=True,capture_output=True)
        self.assertNotEqual(refused.returncode,0)
        self.assertIn('local interactive TTY',refused.stderr)
        self.assertFalse(self.target.exists())
        listing=subprocess.run(args+['--action','list-uninstalled-backups'],
                               check=True,text=True,capture_output=True)
        self.assertEqual(json.loads(listing.stdout)['backup_count'],1)

    def test_pre_phase43_orphan_without_tombstone_fails_closed(self):
        removed=self.initial_uninstall()
        marker=archived._marker_path(self.state,'demo')
        marker.unlink()
        selected=removed['archived_last_active_backup_id']
        with self.assertRaisesRegex(ValueError,'No project-bound uninstall'):
            self.preview(selected)
        self.assertTrue(archived._backup_dir(self.state,'demo',selected).exists())

    def test_symlink_or_tampered_marker_refuses_without_touching_backup(self):
        removed=self.initial_uninstall()
        selected=removed['archived_last_active_backup_id']
        path=archived._marker_path(self.state,'demo')
        original=path.read_text()
        value=json.loads(original)
        value['target_sha256']='0'*64
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'ownership marker'):
            self.preview(selected)
        path.write_text(original)
        real=Path(self.case.tmp.name)/'marker-original.json'
        path.rename(real)
        path.symlink_to(real)
        with self.assertRaisesRegex(ValueError,'Symlinked'):
            self.preview(selected)
        self.assertTrue(archived._backup_dir(self.state,'demo',selected).is_dir())

    def test_foreign_backup_target_collision_and_receipt_collision_refused(self):
        removed=self.initial_uninstall()
        selected=removed['archived_last_active_backup_id']
        with self.assertRaisesRegex(ValueError,'Invalid selected'):
            self.preview('../escape')
        with self.assertRaisesRegex(ValueError,'not owned'):
            self.preview('a'*32)
        self.target.mkdir(parents=True)
        (self.target/'SKILL.md').write_text('FOREIGN USER SKILL')
        with self.assertRaisesRegex(ValueError,'absent'):
            self.preview(selected)
        self.assertEqual((self.target/'SKILL.md').read_text(),'FOREIGN USER SKILL')
        (self.target/'SKILL.md').unlink()
        self.target.rmdir()
        installer._receipt(self.state,'demo').write_text('untrusted')
        with self.assertRaisesRegex(ValueError,'Existing GASL receipt'):
            self.preview(selected)

    def test_backup_tamper_and_unrelated_history_tamper_refused(self):
        self.case.existing_skill()
        first=self.case.replace()
        removed=installer.uninstall('demo',self.project,reader=lambda _:
                                   installer._remove_phrase('demo',self.case.plan_id))
        old=archived._backup_dir(self.state,'demo',first['backup_id'])
        old_note=old/'user-note.txt'
        old_note.write_text('TAMPERED')
        with self.assertRaisesRegex(ValueError,'backup changed'):
            self.preview(removed['archived_last_active_backup_id'])
        self.assertEqual(old_note.read_text(),'TAMPERED')

    def test_interrupted_reinstall_before_activation_rolls_back_stage(self):
        removed=self.initial_uninstall()
        selected=removed['archived_last_active_backup_id']
        original_new=installer._new
        def fail_after_journal(path,data):
            original_new(path,data)
            if data.get('operation')=='reinstall':
                raise OSError('injected crash after journal before install')
        with patch.object(archived,'_new',side_effect=fail_after_journal):
            with self.assertRaisesRegex(OSError,'crash after journal'):
                self.reinstall(selected)
        self.assertFalse(self.target.exists())
        self.assertTrue(installer._journal(self.state,'demo').exists())
        recovered=installer.recover('demo',self.project)
        self.assertEqual(recovered['status'],'interrupted_reinstall_rolled_back')
        self.assertFalse(self.target.exists())
        self.assertFalse(installer._journal(self.state,'demo').exists())
        self.reinstall(selected)
        self.assertTrue(self.target.exists())

    def test_interrupted_reinstall_after_activation_rolls_back_target(self):
        removed=self.initial_uninstall()
        selected=removed['archived_last_active_backup_id']
        original_new=archived._new
        def fail_receipt(path,data):
            if path.resolve() == installer._receipt(self.state,'demo').resolve():
                raise OSError('injected failure before receipt')
            return original_new(path,data)
        with patch.object(archived,'_new',side_effect=fail_receipt):
            with self.assertRaisesRegex(OSError,'before receipt'):
                self.reinstall(selected)
        self.assertTrue(self.target.exists())
        recovered=installer.recover('demo',self.project)
        self.assertEqual(recovered['status'],'interrupted_reinstall_rolled_back')
        self.assertFalse(self.target.exists())
        self.assertTrue(archived._backup_dir(self.state,'demo',selected).exists())

    def test_interrupted_reinstall_after_receipt_commit_finishes(self):
        removed=self.initial_uninstall()
        selected=removed['archived_last_active_backup_id']
        original_new=archived._new
        def fail_after_receipt(path,data):
            original_new(path,data)
            if path.resolve() == installer._receipt(self.state,'demo').resolve():
                raise OSError('injected crash after receipt')
        with patch.object(archived,'_new',side_effect=fail_after_receipt):
            with self.assertRaisesRegex(OSError,'after receipt'):
                self.reinstall(selected)
        recovered=installer.recover('demo',self.project)
        self.assertEqual(recovered['status'],'reinstall_commit_recovered')
        self.assertTrue(self.target.exists())
        self.assertFalse(installer._journal(self.state,'demo').exists())

    def test_changed_target_after_failed_reinstall_preserves_user_edit(self):
        removed=self.initial_uninstall()
        selected=removed['archived_last_active_backup_id']
        with patch.object(archived,'_new',side_effect=lambda p,d:
                          (_ for _ in ()).throw(OSError('fail')) if p.resolve()==installer._receipt(self.state,'demo').resolve()
                          else installer._new(p,d)):
            with self.assertRaises(OSError):
                self.reinstall(selected)
        (self.target/'note.txt').write_text('USER DATA')
        with self.assertRaisesRegex(ValueError,'Installed target changed'):
            installer.recover('demo',self.project)
        self.assertEqual((self.target/'note.txt').read_text(),'USER DATA')
        self.assertTrue(installer._journal(self.state,'demo').exists())

    def test_interrupted_uninstall_after_archive_move_restores_previous_target(self):
        self.case.matching_install()
        before=(self.target/'SKILL.md').read_bytes()
        old_new=installer._new
        def fail_new_manifest(path,data):
            if data.get('kind')=='pre_replace_backup':
                raise OSError('injected after archived rename')
            return old_new(path,data)
        with patch.object(installer,'_new',side_effect=fail_new_manifest):
            with self.assertRaisesRegex(OSError,'archived rename'):
                installer.uninstall('demo',self.project,reader=lambda _:
                                    installer._remove_phrase('demo',self.case.plan_id))
        self.assertFalse(self.target.exists())
        recovered=installer.recover('demo',self.project)
        self.assertEqual(recovered['status'],'interrupted_archived_uninstall_rolled_back')
        self.assertEqual((self.target/'SKILL.md').read_bytes(),before)
        self.assertFalse(archived._marker_path(self.state,'demo').exists())

    def test_interrupted_uninstall_after_marker_write_restores_receipt_and_target(self):
        self.case.matching_install()
        old_new=installer._new
        def fail_after_marker(path,data):
            old_new(path,data)
            if data.get('kind')=='uninstalled_codex_project_skill':
                raise OSError('injected after marker creation')
        with patch.object(installer,'_new',side_effect=fail_after_marker):
            with self.assertRaisesRegex(OSError,'after marker'):
                installer.uninstall('demo',self.project,reader=lambda _:
                                   installer._remove_phrase('demo',self.case.plan_id))
        self.assertTrue(archived._marker_path(self.state,'demo').exists())
        recovered=installer.recover('demo',self.project)
        self.assertEqual(recovered['status'],'interrupted_archived_uninstall_rolled_back')
        self.assertFalse(archived._marker_path(self.state,'demo').exists())
        self.assertTrue(self.target.exists())

    def test_interrupted_uninstall_after_receipt_deletion_finishes_archive(self):
        self.case.matching_install()
        old_sync=installer._sync
        receipt_parent=installer._receipt(self.state,'demo').parent
        def fail_after_receipt_deleted(path):
            if path.resolve() == receipt_parent.resolve() and not installer._receipt(self.state,'demo').exists():
                raise OSError('injected crash after receipt removed')
            return old_sync(path)
        with patch.object(installer,'_sync',side_effect=fail_after_receipt_deleted):
            with self.assertRaisesRegex(OSError,'after receipt removed'):
                installer.uninstall('demo',self.project,reader=lambda _:
                                   installer._remove_phrase('demo',self.case.plan_id))
        recovered=installer.recover('demo',self.project)
        self.assertEqual(recovered['status'],'archived_uninstall_commit_recovered')
        self.assertFalse(self.target.exists())
        self.assertEqual(archived.list_uninstalled_backups(
            'demo',self.project)['backup_count'],1)

    def test_second_uninstall_interruption_restores_previous_ownership_marker(self):
        first=self.initial_uninstall()
        self.reinstall(first['archived_last_active_backup_id'])
        marker_before=archived._read_marker(self.project,'demo',self.state)
        old_atomic=installer._atomic_record
        def fail_after_update(path,data,old):
            old_atomic(path,data,old)
            if data.get('kind')=='uninstalled_codex_project_skill':
                raise OSError('injected after marker replacement')
        with patch.object(installer,'_atomic_record',side_effect=fail_after_update):
            with self.assertRaisesRegex(OSError,'marker replacement'):
                installer.uninstall('demo',self.project,reader=lambda _:
                                    installer._remove_phrase('demo',self.case.plan_id))
        restored=installer.recover('demo',self.project)
        self.assertEqual(restored['status'],'interrupted_archived_uninstall_rolled_back')
        self.assertEqual(archived._read_marker(self.project,'demo',self.state),
                         marker_before)
        self.assertTrue(self.target.exists())


if __name__ == '__main__':
    unittest.main()
