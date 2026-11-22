"""Phase 30: expiring one-time receipt bound to exact isolated fixture state."""
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
from fixture_transaction_v2 import (
    preview_fixture_consent, enact_fixture_transaction, recover_fixture_transaction,
    _exclusive_fixture_lock,
)
import fixture_explicit_consent as c


class TestFixtureConsentReceipts(unittest.TestCase):
    def setUp(self):
        self.package = test_install_bundle.PrivateInstallBundleTests(
            'test_private_zip_contains_only_pinned_files_and_is_verified')
        self.package.setUp()
        self.addCleanup(self.package.doCleanups)
        self.package._package()
        self.bundle_root = self.package.root
        self.pid = self.package._plan()['plan_id']
        self.package._prepare()
        self.temp, self.fixture = _new_root()
        self.addCleanup(self.temp.cleanup)
        (self.fixture / 'workspace').mkdir()
        (self.fixture / 'home').mkdir()

    def old_version(self, host='codex', scope='project'):
        target=_target_for_fixture(self.fixture,host,scope,'demo')
        target.mkdir(parents=True)
        (target/'SKILL.md').write_bytes(b'---\nname: old-inert\n---\n')
        (target/'original-note.txt').write_bytes(b'PRESERVE_ORIGINAL_SENTINEL\n')
        return target

    def request(self,host='codex',scope='project',action='install',pid=None,ttl=120):
        return c.request_fixture_consent(self.fixture,self.bundle_root,pid or self.pid,
                                         host,scope,action,ttl_seconds=ttl)

    def confirm(self,request,phrase=None):
        return c.confirm_fixture_consent(self.fixture,self.bundle_root,
             request['request_id'], request['confirmation_phrase'] if phrase is None else phrase)

    def enact(self,request,host='codex',scope='project',action='install',pid=None,checkpoint='activated'):
        preview=preview_fixture_consent(self.fixture,self.bundle_root,pid or self.pid,host,scope,action)
        return enact_fixture_transaction(self.fixture,self.bundle_root,pid or self.pid,
                      host,scope,action,preview['approval_challenge'],
                      checkpoint=checkpoint,consent_request_id=request['request_id'])

    def test_real_cli_without_tty_never_auto_confirms(self):
        args=[str(ROOT/'gasl'),'consent-fixture-interactive',
            '--plan-id',self.pid,'--agent','codex','--scope','project',
            '--action','install','--acknowledge-fixture-only','GASL_DISPOSABLE_FIXTURE_ONLY']
        result=subprocess.run(args,input='',text=True,capture_output=True,timeout=20)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Interactive TTY required', result.stderr)
        self.assertFalse((self.fixture/'workspace/.agents').exists())

    def test_invalid_cli_fixture_acknowledgement_blocks_all_confirmation(self):
        args=[str(ROOT/'gasl'),'consent-fixture-interactive',
            '--plan-id',self.pid,'--agent','codex','--scope','project',
            '--action','install','--acknowledge-fixture-only','WRONG']
        result=subprocess.run(args,input='',text=True,capture_output=True,timeout=20)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Exact disposable fixture acknowledgment',result.stderr)
        self.assertFalse((self.fixture/'workspace/.agents').exists())

    def test_request_never_installs_and_is_not_approved(self):
        request=self.request()
        self.assertEqual(request['status'],'pending_explicit_fixture_confirmation')
        self.assertRegex(request['request_id'],'^[a-f0-9]{32}$')
        self.assertTrue(request['confirmation_phrase'].startswith('APPROVE GASL FIXTURE INSTALL CODEX PROJECT'))
        self.assertFalse(request['human_confirmation_recorded'])
        self.assertFalse(request['real_host_files_modified'])
        self.assertFalse(request['production_installation_enabled'])
        self.assertFalse((self.fixture/'workspace/.agents').exists())
        status=c.inspect_fixture_receipt(self.fixture)
        self.assertEqual(status['status'],'pending')
        self.assertNotIn(str(self.fixture),json.dumps(request))
        self.assertNotIn(str(self.bundle_root),json.dumps(request))

    def test_wrong_phrase_keeps_pending_without_staging(self):
        request=self.request()
        for phrase in ('', 'yes', request['confirmation_phrase'].lower(),request['confirmation_phrase'][:-1]):
            with self.subTest(phrase=phrase), self.assertRaisesRegex(ValueError,'Exact explicit fixture confirmation'):
                self.confirm(request,phrase)
            self.assertEqual(c.inspect_fixture_receipt(self.fixture)['status'],'pending')
            self.assertFalse((self.fixture/'stage').exists())

    def test_unapproved_receipt_never_authorizes_transaction(self):
        request=self.request()
        with self.assertRaisesRegex(ValueError,'not approved'):
            self.enact(request)
        self.assertEqual(c.inspect_fixture_receipt(self.fixture)['status'],'pending')
        self.assertFalse((self.fixture/'stage').exists())

    def test_approved_receipt_consumed_once_before_install(self):
        request=self.request()
        approved=self.confirm(request)
        self.assertEqual(approved['status'],'fixture_confirmation_recorded')
        self.assertFalse(approved['real_user_identity_verified'])
        self.assertEqual(c.inspect_fixture_receipt(self.fixture)['status'],'approved')
        enacted=self.enact(request)
        self.assertTrue(enacted['one_time_fixture_receipt_consumed'])
        self.assertEqual(c.inspect_fixture_receipt(self.fixture)['status'],'consumed')
        self.assertEqual((_target_for_fixture(self.fixture,'codex','project','demo')/'SKILL.md').read_bytes(),
                         self.package.content['skills/demo/SKILL.md'])
        self.assertTrue(recover_fixture_transaction(self.fixture)['previous_files_restored'])
        with self.assertRaisesRegex(ValueError,'already used'):
            self.enact(request)
        self.assertFalse((_target_for_fixture(self.fixture,'codex','project','demo')).exists())

    def test_approved_request_cannot_be_confirmed_twice(self):
        request=self.request()
        self.confirm(request)
        with self.assertRaisesRegex(ValueError,'already confirmed'):
            self.confirm(request)

    def test_second_consent_request_refused_after_existing_pending_or_consumed(self):
        r=self.request()
        with self.assertRaisesRegex(ValueError,'cannot be replaced'):
            self.request()
        self.confirm(r)
        self.enact(r)
        recover_fixture_transaction(self.fixture)
        with self.assertRaisesRegex(ValueError,'cannot be replaced'):
            self.request()

    def test_wrong_request_identifier_rejected(self):
        r=self.request()
        with self.assertRaisesRegex(ValueError,'invalid'):
            c.confirm_fixture_consent(self.fixture,self.bundle_root,'0'*32,r['confirmation_phrase'])
        self.assertEqual(c.inspect_fixture_receipt(self.fixture)['status'],'pending')

    def test_confirmation_in_a_separate_os_process_is_persisted_and_consumable(self):
        request=self.request()
        code=('import json,sys;sys.path.insert(0,sys.argv[1]);'
              'from fixture_explicit_consent import confirm_fixture_consent;'
              'print(json.dumps(confirm_fixture_consent(sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5])))')
        result=subprocess.run([sys.executable,'-c',code,str(ROOT/'tools'),
             str(self.fixture),str(self.bundle_root),request['request_id'],
             request['confirmation_phrase']],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr[-250:])
        self.assertEqual(json.loads(result.stdout)['status'],'fixture_confirmation_recorded')
        self.assertEqual(c.inspect_fixture_receipt(self.fixture)['status'],'approved')
        outcome=self.enact(request)
        self.assertTrue(outcome['one_time_fixture_receipt_consumed'])
        self.assertTrue(recover_fixture_transaction(self.fixture)['previous_files_restored'])

    def test_hardlinked_receipt_is_rejected_before_any_write(self):
        request=self.request()
        receipt=self.fixture/c.RECEIPT_PATH
        other=self.fixture/'untrusted-hardlink'
        os.link(receipt,other)
        with self.assertRaisesRegex(ValueError,'missing or invalid'):
            self.confirm(request)
        self.assertTrue(other.is_file())
        self.assertFalse((self.fixture/'stage').exists())

    def test_expired_before_confirmation_is_refused_without_target_changes(self):
        with patch.object(c.time,'time',return_value=1_700_000_000):
            request=self.request(ttl=30)
        with patch.object(c.time,'time',return_value=1_700_000_032), self.assertRaisesRegex(ValueError,'expired'):
            self.confirm(request)
        self.assertEqual(c.inspect_fixture_receipt(self.fixture)['status'],'pending')
        self.assertFalse((self.fixture/'workspace/.agents').exists())

    def test_expired_after_confirmation_before_enact_is_refused(self):
        with patch.object(c.time,'time',return_value=1_700_000_000):
            request=self.request(ttl=30)
            self.confirm(request)
        with patch.object(c.time,'time',return_value=1_700_000_045), self.assertRaisesRegex(ValueError,'expired'):
            self.enact(request)
        self.assertEqual(c.inspect_fixture_receipt(self.fixture)['status'],'approved')
        self.assertFalse((self.fixture/'stage').exists())

    def test_changed_target_before_confirmation_fails_closed(self):
        request=self.request()
        target=self.old_version()
        with self.assertRaisesRegex(ValueError,'does not match exact prior target'):
            self.confirm(request)
        self.assertEqual((target/'original-note.txt').read_bytes(),b'PRESERVE_ORIGINAL_SENTINEL\n')

    def test_changed_prior_file_after_approval_fails_closed(self):
        target=self.old_version()
        request=self.request(action='replace')
        self.confirm(request)
        (target/'SKILL.md').write_bytes(b'USER_EDITED_AFTER_CONSENT\n')
        with self.assertRaisesRegex(ValueError,'does not match exact prior target|consent challenge mismatch|approval does not match'):
            self.enact(request,action='replace')
        self.assertEqual((target/'SKILL.md').read_bytes(),b'USER_EDITED_AFTER_CONSENT\n')
        self.assertEqual(c.inspect_fixture_receipt(self.fixture)['status'],'approved')

    def test_changed_private_zip_after_approval_fails_closed(self):
        request=self.request()
        self.confirm(request)
        zipfile=self.bundle_root/'private/install-bundles'/f'{self.pid}.zip'
        zipfile.write_bytes(zipfile.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'ZIP digest'):
            self.enact(request)
        self.assertFalse((self.fixture/'stage').exists())

    def test_signature_tampering_prevents_confirmation_and_consumption(self):
        request=self.request()
        receipt=self.fixture/c.RECEIPT_PATH
        body=json.loads(receipt.read_text())
        body['action']='replace'
        receipt.write_text(json.dumps(body))
        with self.assertRaisesRegex(ValueError,'signature mismatch'):
            self.confirm(request)
        with self.assertRaisesRegex(ValueError,'signature mismatch'):
            self.enact(request)
        self.assertFalse((self.fixture/'stage').exists())

    def test_signing_key_tampering_refuses_and_does_not_expose_secret(self):
        request=self.request()
        key=self.fixture/c.KEY_PATH
        key.write_bytes(b'0'*32)
        with self.assertRaisesRegex(ValueError,'signature mismatch'):
            self.confirm(request)
        self.assertFalse((self.fixture/'stage').exists())

    def test_signing_key_permissions_are_0600_and_never_in_public_status(self):
        request=self.request()
        key=self.fixture/c.KEY_PATH
        self.assertEqual(key.stat().st_mode & 0o077, 0)
        self.assertNotIn(key.read_bytes().hex(),json.dumps(c.inspect_fixture_receipt(self.fixture)))

    def test_symlinked_receipt_and_key_refused_without_touching_target(self):
        request=self.request()
        (self.fixture/c.RECEIPT_PATH).unlink()
        sentinel=self.fixture/'outside-sentinel'
        sentinel.write_text('ORIGINAL')
        (self.fixture/c.RECEIPT_PATH).symlink_to(sentinel)
        with self.assertRaises(ValueError):
            self.confirm(request)
        self.assertEqual(sentinel.read_text(),'ORIGINAL')
        self.assertFalse((self.fixture/'stage').exists())

    def test_wrong_package_host_scope_action_cannot_redeem_receipt(self):
        request=self.request()
        self.confirm(request)
        for host,scope,action,pid in (
            ('cursor','project','install',self.pid),
            ('codex','user','install',self.pid),
            ('codex','project','replace',self.pid),
            ('codex','project','install','0'*64),
        ):
            with self.subTest(host=host,scope=scope,action=action), self.assertRaises((ValueError,FileNotFoundError)):
                self.enact(request,host=host,scope=scope,action=action,pid=pid)
        self.assertEqual(c.inspect_fixture_receipt(self.fixture)['status'],'approved')

    def test_cancelled_after_approval_will_not_be_consumed_unless_enacted(self):
        request=self.request()
        self.confirm(request)
        self.assertEqual(c.inspect_fixture_receipt(self.fixture)['status'],'approved')
        self.assertFalse((self.fixture/'stage').exists())
        self.assertFalse((self.fixture/'workspace/.agents').exists())

    def test_receipt_consumed_before_staging_failure_and_not_reusable(self):
        request=self.request()
        self.confirm(request)
        from unittest.mock import patch as mock_patch
        import fixture_transaction_v2 as v2
        with mock_patch.object(v2,'stage_bundle_fixture',side_effect=OSError('simulated disk full')):
            with self.assertRaisesRegex(OSError,'disk full'):
                self.enact(request)
        self.assertEqual(c.inspect_fixture_receipt(self.fixture)['status'],'consumed')
        with self.assertRaisesRegex(ValueError,'already used'):
            self.enact(request)

    def test_cross_process_replay_after_rollback_rejected(self):
        r=self.request()
        self.confirm(r)
        self.enact(r)
        recover_fixture_transaction(self.fixture)
        child='''import sys
sys.path.insert(0,sys.argv[1])
from fixture_transaction_v2 import preview_fixture_consent,enact_fixture_transaction
fixture,root,pid,req=sys.argv[2:]
preview=preview_fixture_consent(fixture,root,pid,'codex','project','install')
enact_fixture_transaction(fixture,root,pid,'codex','project','install',preview['approval_challenge'],consent_request_id=req)
'''
        run=subprocess.run([sys.executable,'-c',child,str(ROOT/'tools'),str(self.fixture),
                            str(self.bundle_root),self.pid,r['request_id']],capture_output=True,text=True,timeout=20)
        self.assertNotEqual(run.returncode,0)
        self.assertIn('already used',run.stderr)
        self.assertFalse((_target_for_fixture(self.fixture,'codex','project','demo')).exists())

    def test_two_phase_real_file_rollback_36_cases(self):
        count=0
        for host in ('codex','cursor','claude-code'):
            for scope in ('project','user'):
                plan_id=(self.pid if (host,scope)==('codex','project') else
                         self.package._prepare(host,scope)['plan_id'])
                for action in ('install','replace'):
                    for checkpoint in ('staged','backed_up','activated'):
                        with self.subTest(host=host,scope=scope,action=action,checkpoint=checkpoint):
                            temporary,root=_new_root()
                            try:
                                (root/'workspace').mkdir()
                                (root/'home').mkdir()
                                if action=='replace':
                                    target=_target_for_fixture(root,host,scope,'demo')
                                    target.mkdir(parents=True)
                                    (target/'SKILL.md').write_bytes(b'---\nname: inert-old-version\n---\n')
                                r=c.request_fixture_consent(root,self.bundle_root,plan_id,host,scope,action)
                                c.confirm_fixture_consent(root,self.bundle_root,r['request_id'],r['confirmation_phrase'])
                                preview=preview_fixture_consent(root,self.bundle_root,plan_id,host,scope,action)
                                result=enact_fixture_transaction(root,self.bundle_root,plan_id,host,scope,
                                     action,preview['approval_challenge'],checkpoint=checkpoint,
                                     consent_request_id=r['request_id'])
                                self.assertTrue(result['one_time_fixture_receipt_consumed'])
                                self.assertEqual(c.inspect_fixture_receipt(root)['status'],'consumed')
                                self.assertTrue(recover_fixture_transaction(root)['previous_files_restored'])
                                count+=1
                            finally:
                                temporary.cleanup()
        self.assertEqual(count,36)


if __name__=='__main__':
    unittest.main()
