"""Actual native-schema transactions with self-authored inert temporary packages."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import codex_native_review as review
import host_project_install as native
from codex_backup_review import review_codex_backups, format_backup_review
from codex_provenance_compare import compare_codex_provenance, format_provenance_comparison
from tests import test_windows_project_transactions as native_fixtures


class NativeReviewTests(unittest.TestCase):
    def setUp(self):
        self.case = native_fixtures.WindowsProjectTransactionTests('test_complete_replace_restore_preserves_versions')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root = self.case.project.resolve()
        self.target = self.case.target('codex')
        self.state = self.case.state('codex')
        # Only the host-selection guard is patched on POSIX. All actual
        # filesystem transactions and native schema validators still run.
        if os.name != 'nt':
            patcher = patch.object(native, '_host', return_value='codex')
            patcher.start()
            self.addCleanup(patcher.stop)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() if p.is_file() else None
                for p in self.root.rglob('*')}

    def check_readonly(self, operation):
        before = self.snapshot()
        report = operation()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(report['real_host_files_modified'])
        self.assertFalse(report['approval_granted'])
        self.assertFalse(report['third_party_skill_executed'])
        self.assertNotIn(str(self.root), json.dumps(report))
        return report

    def install(self):
        self.case.install('codex', self.case.prepare('codex'))

    def replace(self):
        self.install()
        return self.case.replace('codex', self.case.next_plan('codex'))['backup_id']

    def remove(self):
        preview = native.preview_uninstall('codex', self.root, 'demo')
        with patch('sys.stdin.isatty', return_value=True):
            return native.uninstall('codex', self.root, 'demo', preview['state_binding_id'],
                                    reader=self.case.consent)['archived_backup_id']

    def test_empty_unmanaged_pending_states_are_readonly(self):
        self.assertEqual(self.check_readonly(lambda: review.review('demo', self.root))['lifecycle'],
                         'no_backups')
        self.assertFalse(self.state.exists())
        self.target.mkdir(parents=True)
        (self.target/'SKILL.md').write_bytes(b'LOCAL')
        self.assertEqual(self.check_readonly(lambda: review.review('demo', self.root))['lifecycle'],
                         'unmanaged_target')
        journal = native._journal(self.state, 'demo')
        journal.parent.mkdir(parents=True)
        journal.write_bytes(b'PENDING')
        self.assertEqual(self.check_readonly(lambda: review.review('demo', self.root))['lifecycle'],
                         'pending_transaction')

    def test_native_backup_preview_uses_correct_binding_and_command(self):
        ident = self.replace()
        report = self.check_readonly(lambda: review.review('demo', self.root, backup_id=ident))
        self.assertEqual(report['ownership_store'], 'native_host_scoped')
        self.assertEqual(report['backup_count'], 1)
        self.assertEqual(report['selected']['state_binding_id'],
                         native.preview_restore('codex', self.root, 'demo', ident)['state_binding_id'])
        self.assertIn('host-project-install --host codex --action restore', report['selected']['recovery_command'])
        self.assertIn('PowerShell', format_backup_review(report))
        self.assertFalse(report['historical_project_ownership_verified'])

    def test_provenance_compare_and_restore_ancestry(self):
        ident = self.replace()
        report = self.check_readonly(lambda: review.compare('demo', self.root, left_id='active', right_id=ident))
        self.assertFalse(report['comparison']['same_local_file_inventory'])
        self.assertFalse(report['comparison']['proves_same_upstream_source'])
        self.assertTrue(all('_files' not in version for version in report['versions']))
        self.assertNotIn(str(self.root), format_provenance_comparison(report))
        before = native.preview_restore('codex', self.root, 'demo', ident)
        with patch('sys.stdin.isatty', return_value=True):
            native.restore('codex', self.root, 'demo', ident, before['state_binding_id'],
                           reader=self.case.consent)
        result = self.check_readonly(lambda: review.compare('demo', self.root, left_id='active', right_id=ident))
        self.assertTrue(result['comparison']['same_local_file_inventory'])
        self.assertFalse(result['comparison']['proves_same_upstream_source'])

    def test_identical_backup_restore_refused_by_review_and_transaction(self):
        ident = self.replace()
        preview = native.preview_restore('codex', self.root, 'demo', ident)
        with patch('sys.stdin.isatty', return_value=True):
            native.restore('codex', self.root, 'demo', ident, preview['state_binding_id'],
                           reader=self.case.consent)
        before = self.snapshot()
        row = next(x for x in review.review('demo', self.root)['backups']
                   if x['backup_id'] == ident)
        self.assertFalse(row['eligible_for_recovery'])
        with self.assertRaisesRegex(ValueError, 'identical'):
            native.preview_restore('codex', self.root, 'demo', ident)
        with self.assertRaisesRegex(ValueError, 'identical'):
            native.restore('codex', self.root, 'demo', ident, preview['state_binding_id'],
                           reader=lambda _: self.fail('Consent must not be requested'))
        self.assertEqual(self.snapshot(), before)

    def test_archive_and_reinstall_review_preserve_local_only_claims(self):
        self.install()
        ident = self.remove()
        report = self.check_readonly(lambda: review.review('demo', self.root, backup_id=ident))
        self.assertEqual(report['lifecycle'], 'uninstalled_owned')
        self.assertEqual(report['ownership_evidence'], 'native_local_archive_marker_not_project_bound')
        self.assertIn('--action reinstall', report['selected']['recovery_command'])
        self.assertFalse(report['historical_project_ownership_verified'])
        with patch('sys.stdin.isatty', return_value=True):
            native.reinstall('codex', self.root, 'demo', ident, report['selected']['state_binding_id'],
                             reader=self.case.consent)
        result = self.check_readonly(lambda: review.compare('demo', self.root, left_id='active', right_id=ident))
        self.assertTrue(result['comparison']['same_local_file_inventory'])

    def test_tampered_backup_or_receipt_cannot_be_reviewed(self):
        ident = self.replace()
        receipt = native._receipt(self.state, 'demo')
        data = receipt.read_bytes()
        record = json.loads(data)
        record['unexpected_provenance'] = True
        receipt.write_text(json.dumps(record), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Unknown native receipt fields'):
            review.review('demo', self.root)
        receipt.write_bytes(data)
        (native._backup(self.state, 'demo', ident)/'SKILL.md').write_bytes(b'EDIT')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Native backup contents changed'):
            review.compare('demo', self.root)
        self.assertEqual(self.snapshot(), before)

    def test_archive_collision_and_legacy_namespace_refused(self):
        self.install()
        self.remove()
        self.target.mkdir()
        with self.assertRaisesRegex(ValueError, 'Archived native target is occupied'):
            review.review('demo', self.root)
        self.target.rmdir()
        alternate = self.root/'.gasl-managed'/'receipts'/'demo.json'
        alternate.parent.mkdir(exist_ok=True)
        alternate.write_bytes(b'PRESERVE LEGACY')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'explicit migration required'):
            review.review('demo', self.root)
        self.assertEqual(self.snapshot(), before)

    @unittest.skipUnless(os.name == 'nt', 'Native Windows public routing')
    def test_public_windows_review_and_compare_route_to_native_store(self):
        ident = self.replace()
        report = self.check_readonly(lambda: review_codex_backups('demo', self.root, backup_id=ident))
        self.assertEqual(report['ownership_store'], 'native_host_scoped')
        result = self.check_readonly(lambda: compare_codex_provenance(
            'demo', self.root, left_id='active', right_id=ident))
        self.assertEqual(result['ownership_store'], 'native_host_scoped')


if __name__ == '__main__':
    unittest.main()
