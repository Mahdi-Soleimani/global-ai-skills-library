"""Phase 39: synthetic full pinned ZIP transaction and Host discovery regressions."""
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from codex_pinned_bundle_e2e import ACKNOWLEDGEMENT, verify_pinned_bundle_lifecycle
from queue_ingest import git_blob
from tests import test_install_bundle as bundle_fixture


class PinnedCodexBundleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = bundle_fixture.PrivateInstallBundleTests(
            'test_private_zip_contains_only_pinned_files_and_is_verified')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.content['skills/demo/SKILL.md'] = (
            b'---\nname: demo\ndescription: Inert local regression fixture\n---\n'
            b'# Dummy skill\nNo subprocesses or dependencies.\n')
        self.fixture.row['skill_md_blob_sha'] = git_blob(
            self.fixture.content['skills/demo/SKILL.md'])
        self.folder, _ = self.fixture._package()
        self.bundle = self.fixture._prepare(agent='codex', scope='user')
        self.tmp = tempfile.TemporaryDirectory(prefix='gasl-phase39-test-')
        self.addCleanup(self.tmp.cleanup)
        self.binary = Path(self.tmp.name) / 'fake-executable'
        self.binary.write_text('placeholder\n', encoding='utf-8')
        self.binary.chmod(self.binary.stat().st_mode | stat.S_IXUSR)

    def fake_query(self, mode='normal'):
        calls = []
        def query(binary, root, project, name, skill_file):
            self.assertEqual(binary, self.binary)
            self.assertEqual(project, root / 'workspace')
            self.assertEqual(name, 'demo')
            self.assertEqual(skill_file, root / 'home/.agents/skills/demo/SKILL.md')
            self.assertNotEqual(root, self.fixture.root)
            self.assertTrue(str(root).startswith(tempfile.gettempdir()))
            exists = skill_file.is_file()
            calls.append(exists)
            if mode == 'exception':
                raise ValueError('Malformed mock protocol')
            if mode == 'preexisting' and len(calls) == 1:
                exists = True
            if mode == 'always_absent':
                exists = False
            if mode == 'stale_after' and len(calls) == 3:
                exists = True
            if exists:
                return [{'name': name,
                         'path': str(skill_file) + ('.bad' if mode == 'wrong_path' else ''),
                         'enabled': mode != 'disabled'}]
            return []
        return query, calls

    def verify(self, query=None, *, plan_id=None, ack=ACKNOWLEDGEMENT, binary=None):
        return verify_pinned_bundle_lifecycle(
            binary if binary is not None else self.binary,
            plan_id if plan_id is not None else self.bundle['plan_id'],
            ack, bundle_root=self.fixture.root, lookup=self.fixture.lookup,
            query=query if query is not None else self.fake_query()[0])

    def test_full_zip_staged_discovered_and_rolled_back(self):
        query, calls = self.fake_query()
        result = self.verify(query)
        self.assertEqual(result['status'],
                         'real_codex_pinned_full_bundle_discovery_and_rollback_verified')
        self.assertEqual(calls, [False, True, False])
        self.assertEqual(result['file_count'], 2)
        for flag in ('pinned_package_and_format_checked', 'target_preflight_state_bound',
                     'absent_before_install',
                     'full_pinned_zip_temporarily_staged_and_activated',
                     'exact_skill_discovered_and_enabled', 'fixture_rollback_verified',
                     'absent_after_rollback', 'temporary_profile_deleted'):
            self.assertTrue(result[flag], flag)
        for flag in ('real_user_authorization_collected', 'real_host_files_modified',
                     'real_home_or_codex_profile_accessed', 'third_party_skill_executed',
                     'skill_commands_or_dependencies_executed', 'model_turn_started',
                     'authentication_performed', 'production_installation_enabled'):
            self.assertFalse(result[flag], flag)
        self.assertNotIn(str(self.fixture.root), json.dumps(result))
        self.assertFalse((self.fixture.root / 'home').exists())

    def test_wrong_ack_and_unknown_plan_fail_before_host(self):
        query, calls = self.fake_query()
        bad = self.verify(query, ack='ALLOW_REAL_INSTALL')
        self.assertEqual(bad['reason_code'], 'exact_disposable_bundle_acknowledgement_required')
        bad = self.verify(query, plan_id='0'*64)
        self.assertEqual(bad['reason_code'], 'pinned_bundle_verification_failed')
        self.assertEqual(calls, [])

    def test_symlink_and_missing_codex_binary_rejected(self):
        self.assertEqual(self.verify(binary=Path(self.tmp.name)/'missing')['reason_code'],
                         'absolute_regular_codex_executable_required')
        link = Path(self.tmp.name)/'link'
        link.symlink_to(self.binary)
        self.assertEqual(self.verify(binary=link)['reason_code'],
                         'absolute_regular_codex_executable_required')

    def test_preexisting_or_disabled_or_wrong_path_never_succeeds(self):
        for mode in ('preexisting', 'always_absent', 'disabled', 'wrong_path'):
            with self.subTest(mode=mode):
                query, _ = self.fake_query(mode)
                result = self.verify(query)
                self.assertEqual(result['status'], 'blocked')
                self.assertTrue(result['temporary_profile_deleted'])
                if mode != 'preexisting':
                    self.assertTrue(result['fixture_rollback_verified'])

    def test_stale_host_listing_after_rollback_is_detected(self):
        query, calls = self.fake_query('stale_after')
        result = self.verify(query)
        self.assertEqual(calls, [False, True, False])
        self.assertEqual(result['reason_code'], 'codex_still_discovers_removed_skill')
        self.assertTrue(result['fixture_rollback_verified'])
        self.assertFalse(result['absent_after_rollback'])

    def test_protocol_exception_cleans_fixture(self):
        result = self.verify(self.fake_query('exception')[0])
        self.assertEqual(result['status'], 'blocked')
        self.assertTrue(result['temporary_profile_deleted'])

    def test_zip_tamper_refused_before_host(self):
        zip_path = Path(self.bundle['archive_path'])
        zip_path.write_bytes(zip_path.read_bytes()+b'bad')
        query, calls = self.fake_query()
        result = self.verify(query)
        self.assertEqual(result['reason_code'], 'pinned_bundle_verification_failed')
        self.assertEqual(calls, [])

    def test_changed_source_after_zip_creation_refused(self):
        (self.folder/'SKILL.md').write_bytes(b'tampered')
        query, calls = self.fake_query()
        self.assertEqual(self.verify(query)['reason_code'], 'pinned_bundle_verification_failed')
        self.assertEqual(calls, [])

    def test_wrong_host_or_scope_bundle_refused(self):
        other = self.fixture._prepare(agent='cursor',scope='user')
        query, calls = self.fake_query()
        self.assertEqual(self.verify(query,plan_id=other['plan_id'])['reason_code'],
                         'pinned_bundle_verification_failed')
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
