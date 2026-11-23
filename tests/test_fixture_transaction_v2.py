"""Phase 28 - real ZIP bytes, but only in disposable marked fixture profiles."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from tests import test_install_bundle
from host_adapters import _target_for_fixture
from host_transaction_fixture import _new_root
from fixture_bundle_install import _inventory, _same_inventory
import fixture_transaction_v2 as v2


class FixtureLockedInstallTests(unittest.TestCase):
    def setUp(self):
        self.bundle_case = test_install_bundle.PrivateInstallBundleTests(
            'test_private_zip_contains_only_pinned_files_and_is_verified')
        self.bundle_case.setUp()
        self.addCleanup(self.bundle_case.doCleanups)
        self.bundle_case._package()
        self.bundle_root = self.bundle_case.root
        self.plan_id = self.bundle_case._plan()['plan_id']
        self.bundle_case._prepare()
        self.temp, self.fixture = _new_root()
        self.addCleanup(self.temp.cleanup)
        (self.fixture / 'workspace').mkdir()
        (self.fixture / 'home').mkdir()

    def target(self, host='codex', scope='project'):
        return _target_for_fixture(self.fixture, host, scope, 'demo')

    def old_version(self, host='codex', scope='project'):
        target = self.target(host, scope)
        target.mkdir(parents=True)
        (target / 'SKILL.md').write_bytes(b'---\nname: old-inert\ndescription: fixture\n---\n')
        (target / 'user-note.txt').write_bytes(b'MUST_KEEP_THE_USER_NOTE\n')
        return _inventory(target)

    def preview(self, action='install', host='codex', scope='project', pid=None):
        return v2.preview_fixture_consent(self.fixture, self.bundle_root,
             pid or self.plan_id, host, scope, action)

    def enact(self, challenge, action='install', host='codex', scope='project',
              checkpoint='activated', pid=None):
        return v2.enact_fixture_transaction(self.fixture, self.bundle_root,
             pid or self.plan_id, host, scope, action, challenge, checkpoint=checkpoint)

    def test_preview_is_read_only_and_requires_correct_action(self):
        before = sorted(p.name for p in self.fixture.iterdir())
        receipt = self.preview()
        self.assertEqual(receipt['status'], 'fixture_only_consent_preview')
        self.assertRegex(receipt['approval_challenge'], '^[0-9a-f]{64}$')
        self.assertFalse(receipt['real_user_authorization_collected'])
        self.assertFalse(receipt['production_installation_enabled'])
        self.assertEqual(sorted(p.name for p in self.fixture.iterdir()), before)
        with self.assertRaisesRegex(ValueError, 'does not match exact prior target'):
            self.preview('replace')

    def test_fixture_approval_bound_to_exact_host_scope_action_and_version(self):
        original = self.preview()['approval_challenge']
        self.old_version()
        replaced = self.preview('replace')['approval_challenge']
        self.assertNotEqual(original, replaced)
        other = self.bundle_case._prepare(agent='cursor', scope='project')
        cursor = self.preview('install', 'cursor', 'project', other['plan_id'])
        self.assertNotEqual(original, cursor['approval_challenge'])
        with self.assertRaisesRegex(ValueError, 'consent challenge mismatch'):
            self.enact(original, action='replace')
        self.assertFalse((self.fixture / v2.JOURNAL).exists())

    def test_wrong_or_missing_exact_approval_blocks_all_stage_operations(self):
        receipt = self.preview()
        for consent in (None, '', '0'*64, receipt['state_binding_id']):
            with self.subTest(consent=consent), self.assertRaisesRegex(ValueError, 'consent challenge mismatch'):
                self.enact(consent)
            self.assertFalse((self.fixture / v2.JOURNAL).exists())
            self.assertFalse((self.fixture / 'stage').exists())

    def test_state_drift_after_preview_invalidates_approval(self):
        receipt = self.preview()
        self.old_version()
        with self.assertRaisesRegex(ValueError, 'does not match exact prior target'):
            self.enact(receipt['approval_challenge'])
        self.assertFalse((self.fixture / v2.JOURNAL).exists())
        self.assertEqual((self.target()/'user-note.txt').read_bytes(), b'MUST_KEEP_THE_USER_NOTE\n')

    def test_old_file_edit_after_preview_invalidates_approval(self):
        self.old_version()
        receipt = self.preview('replace')
        (self.target()/'SKILL.md').write_bytes(b'CHANGED AFTER APPROVAL')
        with self.assertRaisesRegex(ValueError, 'consent challenge mismatch'):
            self.enact(receipt['approval_challenge'], action='replace')
        self.assertEqual((self.target()/'SKILL.md').read_bytes(), b'CHANGED AFTER APPROVAL')

    def test_bad_zip_after_preview_fails_closed(self):
        receipt = self.preview()
        path = self.bundle_root/'private/install-bundles'/f'{self.plan_id}.zip'
        path.write_bytes(path.read_bytes()+b'CHANGED')
        with self.assertRaisesRegex(ValueError,'ZIP digest'):
            self.enact(receipt['approval_challenge'])
        self.assertFalse((self.fixture / v2.JOURNAL).exists())

    def test_real_fixture_staged_activation_and_new_process_recovery(self):
        old = self.old_version()
        receipt = self.preview('replace')
        output = self.enact(receipt['approval_challenge'],action='replace',checkpoint='activated')
        self.assertEqual(output['status'], 'fixture_bundle_activated')
        self.assertFalse(output['real_user_authorization_collected'])
        self.assertEqual(output['directory_fsync_supported'], os.name == 'posix')
        self.assertFalse(output['power_loss_durability_verified'])
        self.assertEqual((self.target()/'SKILL.md').read_bytes(),
                         self.bundle_case.content['skills/demo/SKILL.md'])
        code = ('import json,sys;sys.path.insert(0,sys.argv[1]);'
                'from fixture_transaction_v2 import recover_fixture_transaction;'
                'print(json.dumps(recover_fixture_transaction(sys.argv[2])))')
        child = subprocess.run([sys.executable, '-c', code, str(ROOT/'tools'),str(self.fixture)],
            cwd=str(self.fixture), capture_output=True, text=True, timeout=20)
        self.assertEqual(child.returncode,0,child.stderr[-250:])
        recovered=json.loads(child.stdout)
        self.assertTrue(recovered['recovery_revalidated_under_lock'])
        self.assertTrue(_same_inventory(self.target(),old))
        self.assertFalse((self.fixture/v2.JOURNAL).exists())
        self.assertEqual((self.target()/'user-note.txt').read_bytes(),b'MUST_KEEP_THE_USER_NOTE\n')

    def test_recovery_from_new_process_after_backup_checkpoint(self):
        original = self.old_version()
        receipt = self.preview('replace')
        self.enact(receipt['approval_challenge'],action='replace',checkpoint='backed_up')
        self.assertFalse(self.target().exists())
        code = ('import sys,json;sys.path.insert(0,sys.argv[1]);'
                'from fixture_transaction_v2 import recover_fixture_transaction;'
                'print(json.dumps(recover_fixture_transaction(sys.argv[2])))')
        child = subprocess.run([sys.executable,'-c',code,str(ROOT/'tools'),str(self.fixture)],
                               capture_output=True,text=True,timeout=20)
        self.assertEqual(child.returncode,0,child.stderr[-300:])
        self.assertTrue(json.loads(child.stdout)['previous_files_restored'])
        self.assertTrue(_same_inventory(self.target(),original))

    def test_advisory_lock_prevents_second_process_recovery(self):
        preview = self.preview()
        self.enact(preview['approval_challenge'],checkpoint='staged')
        code = ('import sys;sys.path.insert(0,sys.argv[1]);'
                'from fixture_transaction_v2 import recover_fixture_transaction;'
                'recover_fixture_transaction(sys.argv[2])')
        with v2._exclusive_fixture_lock(self.fixture):
            child = subprocess.run([sys.executable,'-c',code,str(ROOT/'tools'),str(self.fixture)],
                                  capture_output=True,text=True,timeout=15)
            self.assertNotEqual(child.returncode,0)
            self.assertIn('already locked',child.stderr)
            self.assertTrue((self.fixture/v2.JOURNAL).exists())
        self.assertTrue(v2.recover_fixture_transaction(self.fixture)['previous_files_restored'])

    def test_attempted_repeated_apply_with_unrecovered_journal_is_blocked(self):
        consent = self.preview()['approval_challenge']
        self.enact(consent,checkpoint='staged')
        with self.assertRaisesRegex(ValueError,'Unfinished fixture transaction'):
            self.enact(consent,checkpoint='activated')
        self.assertTrue(v2.recover_fixture_transaction(self.fixture)['previous_files_restored'])

    def test_locked_recovery_preserves_modified_active_skill(self):
        original = self.old_version()
        consent = self.preview('replace')['approval_challenge']
        self.enact(consent,action='replace')
        (self.target()/'SKILL.md').write_text('LOCAL_EDIT_AFTER_ACTIVATION')
        with self.assertRaisesRegex(ValueError,'Activated files modified'):
            v2.recover_fixture_transaction(self.fixture)
        self.assertEqual((self.target()/'SKILL.md').read_text(),'LOCAL_EDIT_AFTER_ACTIVATION')
        self.assertTrue(any((self.fixture/'backup').iterdir()))

    def test_locked_recovery_preserves_modified_backup(self):
        self.old_version()
        consent=self.preview('replace')['approval_challenge']
        self.enact(consent,action='replace')
        backup=next((self.fixture/'backup').iterdir())
        (backup/'user-note.txt').write_text('EDITED_BACKUP')
        with self.assertRaisesRegex(ValueError,'Backup modified'):
            v2.recover_fixture_transaction(self.fixture)
        self.assertTrue(self.target().exists())

    def test_symlinked_lock_path_refuses_external_sentinel(self):
        sentinel=self.fixture/'external-sentinel'
        sentinel.write_text('UNTOUCHED')
        (self.fixture/v2.LOCK).symlink_to(sentinel)
        consent=self.preview()['approval_challenge']
        with self.assertRaisesRegex(ValueError,'Symlink'):
            self.enact(consent)
        self.assertEqual(sentinel.read_text(),'UNTOUCHED')
        self.assertFalse((self.fixture/v2.JOURNAL).exists())

    def test_unsupported_locking_platform_fails_closed_before_creating_lock_file(self):
        consent=self.preview()['approval_challenge']
        with patch.object(v2,'supported_platform',return_value=False),self.assertRaisesRegex(RuntimeError,'unavailable'):
            self.enact(consent)
        self.assertFalse((self.fixture/v2.LOCK).exists())

    def test_corrupted_journal_cannot_be_recovered_destructively(self):
        old=self.old_version()
        consent=self.preview('replace')['approval_challenge']
        self.enact(consent,action='replace',checkpoint='backed_up')
        journal=self.fixture/v2.JOURNAL
        info=json.loads(journal.read_text())
        info['old_files'][0]['sha256']='0'*64
        journal.write_text(json.dumps(info))
        with self.assertRaises(ValueError):
            v2.recover_fixture_transaction(self.fixture)
        self.assertTrue(any((self.fixture/'backup').iterdir()))

    def test_hardlinked_fixture_lock_inode_is_rejected(self):
        lock = self.fixture/v2.LOCK
        lock.write_text('fixture-only lock inode')
        companion=self.fixture/'another-hardlink'
        os.link(lock,companion)
        with self.assertRaisesRegex(ValueError,'not a unique regular file'):
            with v2._exclusive_fixture_lock(self.fixture):
                pass
        self.assertEqual(companion.read_text(),'fixture-only lock inode')

    @unittest.skipUnless(os.name == 'nt', 'NTFS junction test')
    def test_junction_target_refused_before_any_transaction_write(self):
        outside = self.fixture/'outside'
        outside.mkdir()
        sentinel = outside/'sentinel.txt'
        sentinel.write_bytes(b'PRESERVE')
        junction = self.fixture/'workspace'/'.agents'
        child = subprocess.run(['cmd','/c','mklink','/J',str(junction),str(outside)],
                               capture_output=True, text=True, timeout=10)
        if child.returncode != 0:
            self.skipTest('Runner cannot create disposable NTFS junction')
        try:
            with self.assertRaisesRegex(ValueError,'Symlink|junction|reparse'):
                self.preview()
            self.assertFalse((self.fixture/v2.JOURNAL).exists())
            self.assertFalse((self.fixture/'stage').exists())
            self.assertEqual(sentinel.read_bytes(),b'PRESERVE')
        finally:
            junction.rmdir()

    def test_fsync_failure_after_stage_refuses_activation_and_can_recover(self):
        previous=self.old_version()
        consent=self.preview('replace')['approval_challenge']
        with patch.object(v2,'_sync_tree',side_effect=OSError('fixture fsync unavailable')):
            with self.assertRaisesRegex(OSError,'fsync unavailable'):
                self.enact(consent,action='replace')
        self.assertTrue(_same_inventory(self.target(),previous))
        self.assertTrue((self.fixture/v2.JOURNAL).exists())
        self.assertTrue(v2.recover_fixture_transaction(self.fixture)['previous_files_restored'])

    def test_external_target_change_between_staging_and_activation_fails_closed(self):
        self.old_version()
        receipt=self.preview('replace')
        old_stage=v2.stage_bundle_fixture
        def stage_then_change(*args,**kwargs):
            result=old_stage(*args,**kwargs)
            (self.target()/'SKILL.md').write_text('CHANGED_AFTER_STAGE')
            return result
        with patch.object(v2,'stage_bundle_fixture',side_effect=stage_then_change):
            with self.assertRaisesRegex(ValueError,'changed between consent and activation'):
                self.enact(receipt['approval_challenge'],action='replace')
        self.assertEqual((self.target()/'SKILL.md').read_text(),'CHANGED_AFTER_STAGE')
        self.assertTrue((self.fixture/v2.JOURNAL).exists())
        with self.assertRaisesRegex(ValueError,'Original Skill missing|Backup modified|Staged bundle modified'):
            # There is no valid original snapshot for a user-modified source;
            # recovery must refuse rather than erase or overwrite the change.
            v2.recover_fixture_transaction(self.fixture)

    def test_36_host_scope_action_checkpoint_combinations(self):
        cases=0
        for agent in ('codex','cursor','claude-code'):
            for scope in ('project','user'):
                plan=(self.plan_id if (agent,scope)==('codex','project')
                      else self.bundle_case._prepare(agent=agent,scope=scope)['plan_id'])
                for action in ('install','replace'):
                    for checkpoint in ('staged','backed_up','activated'):
                        with self.subTest(agent=agent,scope=scope,action=action,checkpoint=checkpoint):
                            output=v2.rehearse_locked_transaction(plan,agent,scope,plan,
                                bundle_root=self.bundle_root,action=action,checkpoint=checkpoint)
                            self.assertEqual(output['status'],'fixture_locked_transaction_rollback_verified')
                            self.assertTrue(output['previous_files_restored'])
                            self.assertTrue(output['approval_bound_to_fixture_state'])
                            self.assertFalse(output['real_host_files_modified'])
                            self.assertFalse(output['production_installation_enabled'])
                            cases+=1
        self.assertEqual(cases,36)


if __name__=='__main__':
    unittest.main()
