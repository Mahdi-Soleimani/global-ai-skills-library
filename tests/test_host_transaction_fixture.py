"""Phase 22: all writes and recovery remain in self-created inert temp fixtures."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from host_adapters import _target_for_fixture, MARKER, FIXTURE_PREFIX, SKILL_V1, SKILL_V2
from host_probe import probe_hosts
from host_transaction_fixture import (
    _new_root, _expected_previous, prepare_transaction, advance_transaction,
    recover_transaction, rehearse_interrupted_transaction,
)


class HostProbeTests(unittest.TestCase):
    def test_no_host_binary_does_not_claim_skill_discovery(self):
        lookup = Mock(return_value=None)
        report = probe_hosts(which=lookup)
        self.assertFalse(report['host_process_executed'])
        self.assertFalse(report['skill_discovery_verified'])
        self.assertFalse(report['real_host_files_modified'])
        self.assertEqual(report['hosts']['codex']['integration_status'], 'cli_not_available_for_probe')
        self.assertEqual(report['hosts']['cursor']['integration_status'], 'cli_not_available_for_probe')
        self.assertEqual(report['hosts']['claude-code']['integration_status'], 'cli_not_available_for_probe')
        self.assertEqual(lookup.call_count, 3)

    def test_visible_executable_still_does_not_count_as_discovery(self):
        report = probe_hosts(which=lambda _: '/usr/bin/mock-cli')
        for agent in ('codex', 'cursor', 'claude-code'):
            self.assertEqual(report['hosts'][agent]['integration_status'],
                             'binary_detected_not_executed')
            self.assertFalse(report['hosts'][agent]['host_skill_discovery_verified'])
        self.assertEqual(report['hosts']['claude-desktop']['integration_status'],
                         'not_an_automated_local_cli_adapter')


class HostTransactionFixtureTests(unittest.TestCase):
    def setUp(self):
        self.directory, self.root = _new_root()
        self.addCleanup(self.directory.cleanup)

    def _target(self, agent='codex', scope='project'):
        return _target_for_fixture(self.root, agent, scope, 'fixture-skill')

    def test_full_crash_recovery_matrix_over_three_hosts_two_scopes(self):
        for agent in ('codex', 'cursor', 'claude-code'):
            for scope in ('project', 'user'):
                for upgrade in (True, False):
                    for checkpoint in ('prepared', 'old_backed_up', 'new_activated'):
                        with self.subTest(agent=agent, scope=scope, upgrade=upgrade, checkpoint=checkpoint):
                            outcome = rehearse_interrupted_transaction(agent, scope,
                                         upgrade=upgrade, stop_after=checkpoint)
                            self.assertEqual(outcome['status'], 'inert_fixture_recovery_verified')
                            self.assertTrue(outcome['recovered_original_version'])
                            self.assertFalse(outcome['real_host_files_modified'])
                            self.assertFalse(outcome['real_skill_installed'])
                            self.assertFalse(outcome['third_party_code_executed'])
                            self.assertFalse(outcome['production_install_enabled'])

    def test_restores_original_version_and_user_edits_after_interruption(self):
        prepare_transaction(self.root, 'cursor', 'user', upgrade=True)
        advance_transaction(self.root, stop_after='new_activated')
        out = recover_transaction(self.root)
        self.assertEqual(out['status'], 'inert_fixture_recovery_verified')
        self.assertTrue(_expected_previous(self._target('cursor', 'user')))
        self.assertFalse((self.root / '.gasl-inert-transaction.json').exists())
        self.assertFalse((self.root / 'backup').is_symlink())

    def test_prepared_transaction_can_be_recovered_before_any_copy(self):
        prepare_transaction(self.root, 'codex', 'project', upgrade=False)
        advance_transaction(self.root, stop_after='prepared')
        out = recover_transaction(self.root)
        self.assertTrue(out['recovered_original_version'])
        self.assertFalse(self._target().exists())

    def test_modified_activated_target_is_not_overwritten_even_if_backup_exists(self):
        prepare_transaction(self.root, 'codex', 'project', upgrade=True)
        advance_transaction(self.root, stop_after='new_activated')
        target = self._target()
        (target / 'SKILL.md').write_text('USER_EDITED_AFTER_ACTIVATION')
        with self.assertRaisesRegex(ValueError, 'modified after activation'):
            recover_transaction(self.root)
        self.assertEqual((target / 'SKILL.md').read_text(), 'USER_EDITED_AFTER_ACTIVATION')
        self.assertTrue(any((self.root / 'backup').iterdir()))

    def test_modified_existing_backup_fails_closed_before_deleting_new_target(self):
        prepare_transaction(self.root, 'codex', 'project', upgrade=True)
        advance_transaction(self.root, stop_after='new_activated')
        backup = next((self.root / 'backup').iterdir())
        (backup / 'user-note.txt').write_text('CHANGED_BACKUP')
        with self.assertRaisesRegex(ValueError, 'modified backup'):
            recover_transaction(self.root)
        self.assertEqual((self._target() / 'SKILL.md').read_bytes(), SKILL_V2)
        self.assertEqual((backup / 'user-note.txt').read_text(), 'CHANGED_BACKUP')

    def test_modified_stage_before_commit_is_rejected(self):
        payload = prepare_transaction(self.root, 'codex', 'project', upgrade=True)
        stage = self.root / 'stage' / payload['transaction'] / 'SKILL.md'
        stage.write_text('ALTERED STAGE')
        with self.assertRaisesRegex(ValueError, 'staging bytes changed'):
            advance_transaction(self.root, stop_after='old_backed_up')
        self.assertTrue(_expected_previous(self._target()))
        with self.assertRaisesRegex(ValueError, 'modified staged files'):
            recover_transaction(self.root)

    def test_symlink_to_external_target_is_never_replaced(self):
        payload = prepare_transaction(self.root, 'codex', 'project', upgrade=True)
        advance_transaction(self.root, stop_after='old_backed_up')
        sentinel = self.root / 'sentinel-outside'
        sentinel.write_text('INERT_SENTINEL_UNTOUCHED')
        target = self._target()
        target.symlink_to(sentinel)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            recover_transaction(self.root)
        self.assertEqual(sentinel.read_text(), 'INERT_SENTINEL_UNTOUCHED')

    def test_corrupt_journal_is_rejected_before_touching_files(self):
        prepare_transaction(self.root, 'codex', 'project', upgrade=True)
        journal = self.root / '.gasl-inert-transaction.json'
        original = json.loads(journal.read_text())
        original['agent'] = '../danger'
        journal.write_text(json.dumps(original))
        with self.assertRaisesRegex(ValueError, 'Unknown host adapter'):
            recover_transaction(self.root)
        self.assertTrue(_expected_previous(self._target()))

    def test_account_upload_hosts_are_not_local_transaction_targets(self):
        for agent in ('claude-desktop', 'generic-mcp'):
            with self.subTest(agent=agent):
                with self.assertRaisesRegex(ValueError, 'cannot install filesystem fixtures'):
                    prepare_transaction(self.root, agent, 'project', upgrade=True)
        self.assertFalse((self.root / '.gasl-inert-transaction.json').exists())

    def test_refuses_user_supplied_nonfixture_directory(self):
        with tempfile.TemporaryDirectory(prefix='not-a-gasl-test-') as tmp:
            fake = Path(tmp)
            (fake / MARKER).write_bytes(b'INERT_HOST_FIXTURE_ONLY\n')
            with self.assertRaisesRegex(ValueError, 'dedicated temporary'):
                prepare_transaction(fake, 'codex', 'project', upgrade=True)

    def test_two_concurrent_unrecovered_transactions_not_allowed(self):
        prepare_transaction(self.root, 'codex', 'project', upgrade=True)
        with self.assertRaisesRegex(ValueError, 'Unfinished'):
            prepare_transaction(self.root, 'cursor', 'project', upgrade=True)

    def test_invalid_checkpoint_never_starts_transaction(self):
        with self.assertRaisesRegex(ValueError, 'Unknown inert transaction checkpoint'):
            advance_transaction(self.root, stop_after='dangerous')
        self.assertFalse((self.root / 'stage').exists())

    def test_stage_and_backup_remain_in_temporary_workspace(self):
        payload = prepare_transaction(self.root, 'codex', 'project', upgrade=True)
        for sub in ('stage/' + payload['transaction'], '.gasl-inert-transaction.json'):
            self.assertTrue((self.root / sub).exists())
        result = recover_transaction(self.root)
        self.assertFalse(result['real_host_files_modified'])
        self.assertTrue(_expected_previous(self._target()))


if __name__ == '__main__':
    unittest.main()
