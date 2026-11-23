"""Synthetic Codex Host tests for the approval-gated third-party discovery probe."""
import hashlib
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from codex_third_party_discovery import (
    approval_phrase, verify_third_party_codex_discovery,
)
from queue_ingest import git_blob
from tests.test_codex_discovery_probe import _fixture_popen

SKILL = (
    b'---\nname: python-mcp-server-generator\n'
    b'description: Inert discovery-only test content\n---\n'
    b'# Test fixture\nNo commands are executed by this test.\n'
)
SOURCE_ID = 'GASL-SRC-4231997ac2c731ce1fe3'
SKILL_NAME = 'python-mcp-server-generator'
BLOB = git_blob(SKILL)


class ThirdPartyCodexDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gasl-third-party-discovery-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill_file = self.root / 'SKILL.md'
        self.skill_file.write_bytes(SKILL)
        self.binary = self.root / 'fake-codex'

    def fake_host(self, mode='normal'):
        body = '''#!/usr/bin/env python3
import json,os,sys
assert sys.argv[1:] == ['app-server']
assert 'OPENAI_API_KEY' not in os.environ and 'GITHUB_TOKEN' not in os.environ
root=os.path.realpath(os.environ['TMPDIR'] + '/..')
assert os.path.realpath(os.environ['HOME']).startswith(root + os.sep)
assert os.path.realpath(os.environ['CODEX_HOME']).startswith(root + os.sep)
assert os.environ['HOME'] != os.environ['CODEX_HOME']
first=json.loads(sys.stdin.readline())
assert first['method']=='initialize'
print(json.dumps({'id':0,'result':{'userAgent':'GASL fake Codex'}}),flush=True)
notification=json.loads(sys.stdin.readline())
assert notification['method']=='initialized'
listing=json.loads(sys.stdin.readline())
assert listing['method']=='skills/list'
assert listing['params']['forceReload'] is True
cwd=listing['params']['cwds'][0]
name=os.environ['GASL_TEST_SKILL_NAME']
expected=os.environ['GASL_TEST_SKILL_PATH']
mode=%r
exists=os.path.isfile(expected)
if mode=='always_present':exists=True
if mode=='always_absent':exists=False
if mode=='malformed':
    print('not json',flush=True)
else:
    path=expected if mode!='wrong_path' else expected+'.wrong'
    skills=[{'name':name,'path':path,'enabled':mode!='disabled'}] if exists else []
    print(json.dumps({'id':1,'result':{'data':[{'cwd':cwd,'skills':skills,'errors':[]}]}}),flush=True)
''' % mode
        self.binary.write_text(body, encoding='utf-8')
        self.binary.chmod(self.binary.stat().st_mode | stat.S_IXUSR)
        return self.binary

    def run_probe(self, mode='normal', expected_blob=BLOB, skill_file=None):
        return verify_third_party_codex_discovery(
            self.fake_host(mode), skill_file or self.skill_file,
            source_record_id=SOURCE_ID, skill_name=SKILL_NAME,
            expected_git_blob=expected_blob, popen=_fixture_popen)

    def test_exact_pinned_skill_is_discovered_and_removed_from_disposable_home(self):
        result = self.run_probe()
        self.assertEqual(result['status'],
                         'verified_temporary_third_party_codex_discovery_and_rollback')
        self.assertTrue(result['injected_test_transport'])
        self.assertTrue(result['source_git_blob_verified'])
        self.assertTrue(result['absent_before_install'])
        self.assertTrue(result['third_party_skill_temporarily_installed'])
        self.assertTrue(result['exact_skill_discovered_and_enabled'])
        self.assertTrue(result['absent_after_rollback'])
        self.assertTrue(result['temporary_profile_deleted'])
        for key in ('model_turn_started', 'authentication_performed',
                    'third_party_skill_executed', 'skill_commands_or_dependencies_executed',
                    'real_home_or_codex_profile_accessed', 'real_host_files_modified',
                    'production_installation_enabled'):
            self.assertFalse(result[key])

    def test_source_blob_mismatch_fails_before_codex_process(self):
        result = self.run_probe(expected_blob='0' * 40)
        self.assertEqual(result['reason_code'], 'pinned_skill_git_blob_mismatch')
        self.assertFalse(result['source_git_blob_verified'])
        self.assertFalse(result['third_party_skill_temporarily_installed'])

    def test_frontmatter_name_mismatch_fails_before_codex_process(self):
        bad = self.root / 'bad.md'
        bad.write_bytes(SKILL.replace(SKILL_NAME.encode(), b'wrong-skill-name', 1))
        result = self.run_probe(skill_file=bad, expected_blob=git_blob(bad.read_bytes()))
        self.assertEqual(result['reason_code'], 'skill_frontmatter_name_mismatch')
        self.assertFalse(result['third_party_skill_temporarily_installed'])

    def test_preexisting_same_name_is_rejected(self):
        result = self.run_probe(mode='always_present')
        self.assertEqual(result['reason_code'],
                         'same_name_skill_preexists_in_disposable_profile')
        self.assertTrue(result['temporary_profile_deleted'])
        self.assertFalse(result['third_party_skill_temporarily_installed'])

    def test_codex_must_discover_exact_enabled_skill(self):
        for mode in ('always_absent', 'disabled', 'wrong_path'):
            with self.subTest(mode=mode):
                result = self.run_probe(mode=mode)
                self.assertEqual(result['reason_code'],
                                 'codex_did_not_discover_exact_enabled_skill')
                self.assertTrue(result['temporary_profile_deleted'])
                self.assertFalse(result['exact_skill_discovered_and_enabled'])

    def test_malformed_codex_protocol_fails_and_cleans_temporary_profile(self):
        result = self.run_probe(mode='malformed')
        self.assertEqual(result['reason_code'], 'codex_protocol_or_temporary_profile_error')
        self.assertTrue(result['temporary_profile_deleted'])

    def test_missing_or_symlinked_codex_binary_is_rejected(self):
        missing = self.root / 'missing-codex'
        result = verify_third_party_codex_discovery(
            missing, self.skill_file, source_record_id=SOURCE_ID,
            skill_name=SKILL_NAME, expected_git_blob=BLOB)
        self.assertEqual(result['reason_code'], 'absolute_regular_codex_executable_required')
        link = self.root / 'codex-link'
        try:
            link.symlink_to(self.fake_host())
        except OSError as exc:
            if os.name == 'nt' and getattr(exc, 'winerror', None) == 1314:
                self.skipTest('Windows runner cannot create a disposable symbolic link')
            raise
        result = verify_third_party_codex_discovery(
            link, self.skill_file, source_record_id=SOURCE_ID,
            skill_name=SKILL_NAME, expected_git_blob=BLOB)
        self.assertEqual(result['reason_code'], 'absolute_regular_codex_executable_required')

    @unittest.skipUnless(os.name == 'nt', 'Windows live Host gate')
    def test_default_vendor_transport_remains_gated_before_source_copy(self):
        result = verify_third_party_codex_discovery(
            self.fake_host(), self.skill_file, source_record_id=SOURCE_ID,
            skill_name=SKILL_NAME, expected_git_blob=BLOB)
        self.assertEqual(result['reason_code'], 'windows_live_host_probe_not_yet_verified')
        self.assertFalse(result['injected_test_transport'])
        self.assertFalse(result['third_party_skill_temporarily_installed'])

    def test_approval_phrase_is_bound_to_source_skill_and_blob(self):
        phrase = approval_phrase(SOURCE_ID, SKILL_NAME, BLOB)
        self.assertIn(SOURCE_ID.upper(), phrase)
        self.assertIn(BLOB[:12].upper(), phrase)
        self.assertIn('DISPOSABLE CODEX USER HOME', phrase)
        with self.assertRaises(ValueError):
            approval_phrase('GASL-SRC-invalid', SKILL_NAME, BLOB)


if __name__ == '__main__':
    unittest.main()
