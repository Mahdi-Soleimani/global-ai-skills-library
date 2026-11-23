"""Disposable inert fixtures exercise documented host layouts, never user Agents."""
import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from host_adapters import (
    HOST_LAYOUTS, MARKER, FIXTURE_PREFIX, _checked_fixture,
    _target_for_fixture, _test_at_fixture, _path_within_fixture,
    list_host_adapters, rehearse_host_fixture,
)


class HostAdapterTests(unittest.TestCase):
    def test_matrix_consistent_and_explicitly_not_verified_with_real_hosts(self):
        matrix = list_host_adapters()
        self.assertEqual(matrix['status'], 'codex_isolated_discovery_verified_other_hosts_unverified')
        self.assertTrue(matrix['real_installation_available'])
        self.assertEqual(set(matrix['real_installation_supported_hosts']),
                         {'codex','cursor','claude-code'})
        self.assertEqual(matrix['real_installation_scope'],'project_only')
        self.assertEqual(matrix['real_installation_platform'],'POSIX_only')
        self.assertTrue(matrix['real_installation_requires_local_tty'])
        self.assertFalse(matrix['cursor_and_claude_live_host_discovery_verified'])
        self.assertTrue(matrix['real_host_probe_performed'])
        self.assertEqual(matrix['real_host_probe_scope'], 'disposable_home_only')
        self.assertEqual(set(HOST_LAYOUTS), {'codex', 'cursor', 'claude-code', 'claude-desktop', 'generic-mcp'})
        self.assertEqual(HOST_LAYOUTS['codex']['project'], '.agents/skills')
        self.assertEqual(HOST_LAYOUTS['cursor']['user'], '.cursor/skills')
        self.assertEqual(HOST_LAYOUTS['claude-code']['project'], '.claude/skills')
        self.assertEqual(HOST_LAYOUTS['claude-desktop']['kind'], 'manual_account_zip_upload')
        self.assertTrue(HOST_LAYOUTS['codex']['verified_with_real_host'])
        self.assertEqual(set(HOST_LAYOUTS['codex']['verified_capabilities']),
                         {'project_skill_discovery','user_skill_discovery','skills_list','isolated_fixture_rollback'})
        for name in ('cursor','claude-code','claude-desktop','generic-mcp'):
            self.assertFalse(HOST_LAYOUTS[name]['verified_with_real_host'])

    def test_each_filesystem_host_and_scope_restores_inert_previous_version(self):
        for agent in ('codex', 'cursor', 'claude-code'):
            for scope in ('project', 'user'):
                with self.subTest(agent=agent, scope=scope):
                    result = rehearse_host_fixture(agent, scope, 'upgrade')
                    self.assertEqual(result['status'], 'fixture_rollback_verified')
                    self.assertTrue(result['original_version_restored'])
                    self.assertTrue(result['user_note_preserved'])
                    self.assertTrue(result['fixture_rollback_performed'])
                    self.assertFalse(result['real_skill_installed'])
                    self.assertFalse(result['real_host_files_modified'])
                    self.assertFalse(result['third_party_code_executed'])

    def test_each_filesystem_host_fresh_install_is_reversed_to_empty(self):
        for agent in ('codex', 'cursor', 'claude-code'):
            with self.subTest(agent=agent):
                result = rehearse_host_fixture(agent, 'project', 'fresh')
                self.assertEqual(result['status'], 'fixture_rollback_verified')
                self.assertTrue(result['original_version_restored'])

    def test_existing_skills_never_overwritten_without_explicit_backup(self):
        for agent in ('codex', 'cursor', 'claude-code'):
            with self.subTest(agent=agent):
                result = rehearse_host_fixture(agent, 'user', 'conflict')
                self.assertEqual(result['status'], 'existing_target_requires_explicit_backup')
                self.assertTrue(result['existing_skill_preserved'])
                self.assertTrue(result['user_note_preserved'])
                self.assertFalse(result['fixture_rollback_performed'])

    def test_symlink_targets_are_blocked_and_sentinels_preserved(self):
        for agent in ('codex', 'cursor', 'claude-code'):
            with self.subTest(agent=agent):
                result = rehearse_host_fixture(agent, 'project', 'symlink')
                self.assertEqual(result['status'], 'blocked_symlink_target')
                self.assertTrue(result['external_fixture_sentinel_preserved'])
                self.assertFalse(result['real_host_files_modified'])

    def test_claude_desktop_never_pretends_to_have_local_skill_path(self):
        for scope in ('user', 'project'):
            result = rehearse_host_fixture('claude-desktop', scope, 'upgrade')
            self.assertEqual(result['status'], 'no_filesystem_adapter')
            self.assertEqual(result['supported_install_channel'], 'manual_account_zip_upload')
            self.assertFalse(result['fixture_rollback_performed'])

    def test_generic_mcp_must_not_get_invented_skill_path(self):
        result = rehearse_host_fixture('generic-mcp', 'user')
        self.assertEqual(result['status'], 'no_filesystem_adapter')
        self.assertEqual(result['supported_install_channel'], 'no_standard_skill_directory')

    def test_rejects_invalid_agents_and_scenarios_without_touching_any_host(self):
        for kwargs in ({'agent': 'codex/../../etc'}, {'agent': 'codex', 'scope': '../home'},
                       {'agent': 'codex', 'scenario': 'dangerous'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                rehearse_host_fixture(**kwargs)

    def test_non_fixture_directory_refused_even_with_marker(self):
        with tempfile.TemporaryDirectory(prefix='not-gasl-fixture-') as path:
            root = Path(path)
            (root / MARKER).write_bytes(b'INERT_HOST_FIXTURE_ONLY\n')
            with self.assertRaisesRegex(ValueError, 'dedicated temporary'):
                _checked_fixture(root)

    def test_corrupt_fixture_marker_rejected(self):
        with tempfile.TemporaryDirectory(prefix=FIXTURE_PREFIX) as path:
            root = Path(path)
            (root / MARKER).write_text('untrusted marker')
            with self.assertRaisesRegex(ValueError, 'marker missing'):
                _checked_fixture(root)

    def test_symlink_in_fixture_parent_refused(self):
        with tempfile.TemporaryDirectory(prefix=FIXTURE_PREFIX) as path:
            root = Path(path)
            (root / MARKER).write_bytes(b'INERT_HOST_FIXTURE_ONLY\n')
            (root / 'workspace').symlink_to(root / 'outside')
            with self.assertRaisesRegex(ValueError, 'Symlink'):
                _target_for_fixture(root, 'codex', 'project', 'fixture-skill')

    def test_invalid_skill_slug_does_not_escape_fixture(self):
        with tempfile.TemporaryDirectory(prefix=FIXTURE_PREFIX) as path:
            root = Path(path)
            (root / MARKER).write_bytes(b'INERT_HOST_FIXTURE_ONLY\n')
            for bad in ('..', '../etc', '/root', '.secret', 'a/b', 'A-UPPER', '', '\\escape'):
                with self.subTest(slug=bad), self.assertRaisesRegex(ValueError, 'Unsafe Skill slug'):
                    _target_for_fixture(root, 'cursor', 'project', bad)

    def test_fixture_path_escape_directly_rejected(self):
        with tempfile.TemporaryDirectory(prefix=FIXTURE_PREFIX) as path:
            root = Path(path)
            (root / MARKER).write_bytes(b'INERT_HOST_FIXTURE_ONLY\n')
            for candidate in ('../external', '/etc/passwd', 'workspace/../../outside', 'workspace\\evil'):
                with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                    _path_within_fixture(root, candidate)

    def test_fixture_is_deleted_after_rehearsal_and_real_homes_never_used(self):
        before = set(Path(tempfile.gettempdir()).glob(FIXTURE_PREFIX + '*'))
        result = rehearse_host_fixture('codex', 'project', 'upgrade')
        after = set(Path(tempfile.gettempdir()).glob(FIXTURE_PREFIX + '*'))
        self.assertEqual(before, after)
        self.assertFalse(result['real_host_files_modified'])

    def test_invalid_rehearsal_scenario_checked_against_fixture(self):
        with tempfile.TemporaryDirectory(prefix=FIXTURE_PREFIX) as path:
            root = Path(path)
            (root / MARKER).write_bytes(b'INERT_HOST_FIXTURE_ONLY\n')
            with self.assertRaisesRegex(ValueError, 'Unknown inert fixture scenario'):
                _test_at_fixture(root, 'codex', 'project', 'unsupported')


if __name__ == '__main__':
    unittest.main()
