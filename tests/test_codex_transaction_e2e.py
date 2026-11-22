"""Synthetic subprocess tests for real Codex install/list/rollback integration module.

A fake Codex Host here only validates the protocol implementation. Real vendor
proof must come from the separate pinned-CLI GitHub Actions run.
"""
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from codex_transaction_e2e import _synthetic_inert_bundle, verify_full_codex_lifecycle
from fixture_transaction_v2 import preview_fixture_consent
from host_transaction_fixture import _new_root
from codex_discovery_probe import SKILL_NAME, SKILL_BODY


class CodexFixtureTransactionEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gasl-fake-codex-e2e-')
        self.addCleanup(self.temp.cleanup)
        self.binary = Path(self.temp.name) / 'fake-codex'

    def fake_host(self, mode='follow_filesystem'):
        body = '''#!/usr/bin/env python3
import json,os,sys
assert sys.argv[1:] == ['app-server']
assert 'OPENAI_API_KEY' not in os.environ and 'GITHUB_TOKEN' not in os.environ
assert os.environ['HOME'].startswith(os.environ['TMPDIR'].rsplit('/',1)[0])
assert os.environ['CODEX_HOME'].startswith(os.environ['HOME'].rsplit('/',1)[0])
first=json.loads(sys.stdin.readline())
assert first['method']=='initialize'
print(json.dumps({'id':0,'result':{'userAgent':'GASL test Host'}}),flush=True)
notification=json.loads(sys.stdin.readline())
assert notification['method']=='initialized'
listing=json.loads(sys.stdin.readline())
assert listing['method']=='skills/list'
assert listing['params']['forceReload'] is True
cwd=listing['params']['cwds'][0]
assert cwd==os.getcwd() or os.path.realpath(cwd)==os.path.realpath(os.getcwd())
expected=os.path.join(cwd,'.agents','skills','gasl-discovery-probe','SKILL.md')
mode=%r
exists=os.path.exists(expected)
if exists:
    with open(expected,'rb') as source:
        assert source.read()==%r
if mode=='always_present':exists=True
if mode=='always_absent':exists=False
if mode=='malformed':
    print('not json',flush=True)
else:
    skills=[{'name':'gasl-discovery-probe','path':expected,'enabled':True}] if exists else []
    if skills and mode=='disabled':skills[0]['enabled']=False
    print(json.dumps({'id':1,'result':{'data':[{'cwd':cwd,'skills':skills,'errors':[]}]}}),flush=True)
sys.stdin.read()
''' % (mode, SKILL_BODY)
        self.binary.write_text(body, encoding='utf-8')
        self.binary.chmod(self.binary.stat().st_mode | stat.S_IXUSR)
        return self.binary

    def test_full_filesystem_sensitive_lifecycle_with_synthetic_host(self):
        result=verify_full_codex_lifecycle(self.fake_host())
        self.assertEqual(result['status'],'real_codex_inert_install_discovery_rollback_verified')
        self.assertTrue(result['absent_before_install'])
        self.assertTrue(result['inert_skill_discovered_after_install'])
        self.assertTrue(result['absent_after_rollback'])
        self.assertTrue(result['fixture_rollback_verified'])
        for key in ('model_turn_started','authentication_performed',
                    'third_party_skill_installed_or_executed',
                    'real_host_files_modified','production_installation_enabled'):
            self.assertFalse(result[key])
        self.assertNotIn(str(self.temp.name),json.dumps(result))

    def test_one_time_fixture_receipt_e2e_with_synthetic_host(self):
        result=verify_full_codex_lifecycle(self.fake_host(),
                    require_one_time_fixture_receipt=True)
        self.assertEqual(result['status'],'real_codex_inert_install_discovery_rollback_verified')
        self.assertTrue(result['one_time_fixture_receipt_consumed'])
        self.assertFalse(result['human_confirmation_verified'])
        self.assertTrue(result['absent_after_rollback'])
        self.assertFalse(result['third_party_skill_installed_or_executed'])

    def test_one_time_receipt_does_not_override_bad_host_discovery(self):
        result=verify_full_codex_lifecycle(self.fake_host('always_absent'),
                    require_one_time_fixture_receipt=True)
        self.assertEqual(result['reason_code'], 'codex_failed_to_discover_installed_inert_skill')
        self.assertTrue(result['one_time_fixture_receipt_consumed'])
        self.assertFalse(result['human_confirmation_verified'])
        self.assertFalse(result['fixture_rollback_verified'])

    def test_already_present_host_result_rejected_before_transaction(self):
        result=verify_full_codex_lifecycle(self.fake_host('always_present'))
        self.assertEqual(result['reason_code'],'inert_skill_unexpectedly_preexisting')
        self.assertFalse(result['fixture_rollback_verified'])

    def test_host_that_never_discovers_installed_skill_fails_closed(self):
        result=verify_full_codex_lifecycle(self.fake_host('always_absent'))
        self.assertEqual(result['reason_code'],'codex_failed_to_discover_installed_inert_skill')
        self.assertFalse(result['inert_skill_discovered_after_install'])
        self.assertFalse(result['fixture_rollback_verified'])

    def test_malformed_vendor_protocol_fails_closed(self):
        result=verify_full_codex_lifecycle(self.fake_host('malformed'))
        self.assertEqual(result['reason_code'],'codex_e2e_protocol_or_fixture_error')
        self.assertFalse(result['inert_skill_discovered_after_install'])

    def test_vendor_returns_disabled_skill_is_never_accepted(self):
        result=verify_full_codex_lifecycle(self.fake_host('disabled'))
        self.assertEqual(result['reason_code'],'codex_failed_to_discover_installed_inert_skill')

    def test_missing_or_symlinked_vendor_cli_rejected_before_profile_creation(self):
        self.assertEqual(verify_full_codex_lifecycle('codex')['reason_code'],
                         'absolute_regular_codex_executable_required')
        self.assertEqual(verify_full_codex_lifecycle(Path(self.temp.name)/'absent')['reason_code'],
                         'absolute_regular_codex_executable_required')
        binary=self.fake_host()
        link=binary.parent/'linked-host'
        link.symlink_to(binary)
        self.assertEqual(verify_full_codex_lifecycle(link)['reason_code'],
                         'absolute_regular_codex_executable_required')

    def test_synthetic_zip_validates_v28_exact_fixture_target_binding(self):
        temp,root=_new_root()
        try:
            (root/'workspace').mkdir()
            (root/'home').mkdir()
            pid=_synthetic_inert_bundle(root)
            self.assertEqual(len(pid),64)
            preview=preview_fixture_consent(root,root,pid,'codex','project','install')
            self.assertEqual(preview['plan_id'],pid)
            self.assertFalse(preview['real_user_authorization_collected'])
            self.assertFalse((root/'workspace/.agents').exists())
        finally:
            temp.cleanup()

    def test_full_flow_never_touches_normal_current_directory(self):
        before=set(Path.cwd().iterdir())
        result=verify_full_codex_lifecycle(self.fake_host())
        self.assertEqual(result['status'],'real_codex_inert_install_discovery_rollback_verified')
        self.assertEqual(set(Path.cwd().iterdir()),before)


if __name__ == '__main__':
    unittest.main()
