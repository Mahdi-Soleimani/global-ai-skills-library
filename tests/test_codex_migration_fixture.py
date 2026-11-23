"""Real file operations and abrupt process-exit recovery, inert temp roots only."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import codex_migration_fixture as m
import codex_migration_audit as audit
import codex_project_install as legacy
import host_project_install as native
from host_transaction_fixture import _new_root
from transaction_file_lock import exclusive_lock_file


class MigrationFixtureTests(unittest.TestCase):
    def fixture(self, count=2):
        temporary, root = m.new_fixture(count)
        self.addCleanup(temporary.cleanup)
        return root

    def snapshot(self, path):
        return {p.relative_to(path).as_posix(): p.read_bytes() if p.is_file() else None
                for p in path.rglob('*')}

    def crash(self, root, operation, checkpoint):
        # os._exit deliberately skips Python finally blocks and cleanup.
        code = (
            'import os,sys;from pathlib import Path;'
            'sys.path.insert(0,sys.argv[1]);import codex_migration_fixture as m;'
            'getattr(m,sys.argv[2])(Path(sys.argv[3]),checkpoint='
            'lambda name: os._exit(73) if name==sys.argv[4] else None)'
        )
        child = subprocess.run([sys.executable, '-c', code, str(ROOT / 'tools'),
                                operation, str(root), checkpoint],
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(child.returncode, 73, child.stderr)

    def assert_restored(self, root, before):
        project = root / m.PROJECT
        self.assertEqual(self.snapshot(project), before)
        self.assertFalse((root / m.ORIGINAL).exists())
        self.assertFalse((root / m.STAGED).exists())
        self.assertEqual(audit.audit_legacy_migration(m.SLUG, project)['status'],
                         'candidate_metadata_verified_read_only')

    def test_success_preserves_archive_and_active_bytes_then_exact_rollback(self):
        for count in (0, 2, 3):
            with self.subTest(count=count):
                root = self.fixture(count)
                project = root / m.PROJECT
                before = self.snapshot(project)
                old_state = self.snapshot(project / legacy.STATE)
                active = self.snapshot(project / '.agents')
                result = m.rehearse_migration(root)
                self.assertTrue(result['native_inventory_verified'])
                self.assertFalse(result['production_migration_enabled'])
                self.assertEqual(self.snapshot(root / m.ORIGINAL), old_state)
                self.assertEqual(self.snapshot(project / '.agents'), active)
                self.assertFalse((project / legacy.STATE / 'receipts').exists())
                self.assertTrue((project / legacy.STATE / 'hosts/codex/receipts' /
                                 (m.SLUG + '.json')).is_file())
                self.assertEqual(m.recover_migration(root)['status'],
                                 'disposable_migration_rolled_back')
                self.assert_restored(root, before)
                self.assertEqual(m.recover_migration(root)['status'], 'already_restored')

    def test_abrupt_process_exit_at_every_apply_checkpoint(self):
        for count in (0, 2, 3):
            for checkpoint in m.CHECKPOINTS:
                with self.subTest(count=count, checkpoint=checkpoint):
                    root = self.fixture(count)
                    before = self.snapshot(root / m.PROJECT)
                    self.crash(root, 'rehearse_migration', checkpoint)
                    self.assertTrue((root / m.PROJECT / m.JOURNAL).is_file())
                    self.assertTrue(m.recover_migration(root)['original_records_restored'])
                    self.assert_restored(root, before)

    def test_abrupt_process_exit_during_rollback_is_repeatable(self):
        for checkpoint in ('candidate_removed', 'original_restored', 'staging_cleaned'):
            with self.subTest(checkpoint=checkpoint):
                root = self.fixture()
                before = self.snapshot(root / m.PROJECT)
                m.rehearse_migration(root)
                self.crash(root, 'recover_migration', checkpoint)
                self.assertTrue(m.recover_migration(root)['original_records_restored'])
                self.assert_restored(root, before)

    def test_partial_candidate_stage_is_recoverable_if_exact(self):
        root = self.fixture()
        before = self.snapshot(root / m.PROJECT)
        self.crash(root, 'rehearse_migration', 'journal_written')
        _, candidate, _, _, _ = m._expected(2)
        path, data = next(iter(candidate.items()))
        partial = root / m.STAGED / path
        partial.parent.mkdir(parents=True)
        partial.write_bytes(data)
        m.recover_migration(root)
        self.assert_restored(root, before)

    def test_tampered_evidence_refuses_rollback_without_mutation(self):
        for location in ('archive', 'candidate', 'journal', 'active'):
            with self.subTest(location=location):
                root = self.fixture()
                m.rehearse_migration(root)
                project = root / m.PROJECT
                paths = {
                    'archive': root / m.ORIGINAL / 'receipts' / (m.SLUG + '.json'),
                    'candidate': project / legacy.STATE / 'hosts/codex/receipts' / (m.SLUG + '.json'),
                    'journal': project / m.JOURNAL,
                    'active': project / '.agents/skills' / m.SLUG / 'SKILL.md',
                }
                paths[location].write_bytes(b'USER EDIT - PRESERVE')
                before = self.snapshot(root)
                with self.assertRaises(ValueError):
                    m.recover_migration(root)
                self.assertEqual(self.snapshot(root), before)

    def test_unknown_candidate_entry_refuses_rollback(self):
        root = self.fixture()
        m.rehearse_migration(root)
        (root / m.PROJECT / legacy.STATE / 'unexpected').write_bytes(b'PRESERVE')
        before = self.snapshot(root)
        with self.assertRaisesRegex(ValueError, 'Unexpected migration fixture entry'):
            m.recover_migration(root)
        self.assertEqual(self.snapshot(root), before)

    def test_hardlink_candidate_refuses_rollback(self):
        root = self.fixture()
        m.rehearse_migration(root)
        receipt = root / m.PROJECT / legacy.STATE / 'hosts/codex/receipts' / (m.SLUG + '.json')
        with tempfile.TemporaryDirectory() as outside:
            alias = Path(outside) / 'alias'
            os.link(receipt, alias)
            before = self.snapshot(root)
            with self.assertRaisesRegex(ValueError, 'Unexpected migration fixture file'):
                m.recover_migration(root)
            self.assertEqual(self.snapshot(root), before)
            self.assertEqual(alias.read_bytes(), receipt.read_bytes())

    def test_pending_journal_blocks_both_engines_and_second_apply(self):
        root = self.fixture()
        self.crash(root, 'rehearse_migration', 'original_archived')
        project = root / m.PROJECT
        before = self.snapshot(root)
        with self.assertRaisesRegex(ValueError, 'migration journal exists'):
            legacy._paths(project, m.SLUG)
        with patch.object(native, '_host', return_value='codex'):
            with self.assertRaisesRegex(ValueError, 'migration journal exists'):
                native._paths(project, 'codex', m.SLUG)
        self.assertEqual(audit.audit_legacy_migration(m.SLUG, project)['reason_code'],
                         'migration_recovery_required')
        with self.assertRaisesRegex(ValueError, 'requires recovery'):
            m.rehearse_migration(root)
        self.assertEqual(self.snapshot(root), before)
        m.recover_migration(root)

    def test_other_marked_fixture_is_refused_without_lock_or_mutation(self):
        temp, root = _new_root()
        self.addCleanup(temp.cleanup)
        before = self.snapshot(root)
        with self.assertRaises((ValueError, OSError)):
            m.rehearse_migration(root)
        self.assertEqual(self.snapshot(root), before)
        self.assertFalse((root / m.LOCK).exists())

    def test_concurrent_process_refused_by_native_fixture_lock(self):
        root = self.fixture()
        code = ('import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
                'import codex_migration_fixture as m;m.rehearse_migration(Path(sys.argv[2]))')
        with exclusive_lock_file(root / m.LOCK):
            before = self.snapshot(root / m.PROJECT)
            child = subprocess.run([sys.executable, '-c', code, str(ROOT / 'tools'), str(root)],
                                   capture_output=True, text=True, timeout=15)
            self.assertNotEqual(child.returncode, 0)
            self.assertEqual(self.snapshot(root / m.PROJECT), before)
        self.assertEqual(m.recover_migration(root)['status'], 'already_restored')


if __name__ == '__main__':
    unittest.main()
