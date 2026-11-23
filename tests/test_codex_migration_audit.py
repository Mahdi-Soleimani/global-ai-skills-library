"""Cross-platform read-only migration audit on self-authored local records."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import codex_migration_audit as audit
import codex_project_install as legacy
from fixture_bundle_install import _inventory


class MigrationAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='gasl-migration-audit-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / '.git').mkdir()
        self.state = self.root / '.gasl-managed'
        self.target = self.root / '.agents' / 'skills' / 'demo'
        self.target.mkdir(parents=True)
        self.receipt = self.state / 'receipts' / 'demo.json'
        self.receipt.parent.mkdir(parents=True)
        self.backups = self.state / 'backups' / 'demo'
        self.backups.mkdir(parents=True)
        self.active = self.version('1', [])
        self.write(self.receipt, self.active)

    def write(self, path, value):
        path.write_bytes(legacy._serialized(value))

    def version(self, counter, ids):
        (self.target / 'SKILL.md').write_bytes(('---\nname: demo\n---\n# INERT ' + counter).encode())
        return {'schema': legacy.SCHEMA, 'action': 'replace_install' if ids else 'fresh_install',
                'slug': 'demo', 'transaction': counter * 32, 'plan_id': counter * 64,
                'binding': 'a' * 64, 'files': _inventory(self.target),
                **({'backup_ids': ids} if ids else {})}

    def replace(self, counter):
        ident = counter * 32
        backup = self.backups / ident
        backup.mkdir()
        (backup / 'SKILL.md').write_bytes((self.target / 'SKILL.md').read_bytes())
        self.write(backup.with_suffix('.json'), {
            'schema': legacy.SCHEMA, 'kind': 'pre_replace_backup', 'slug': 'demo',
            'backup_id': ident, 'transaction': ident, 'previous_receipt': self.active,
            'files': _inventory(backup),
        })
        self.active = self.version(counter, self.active.get('backup_ids', []) + [ident])
        self.write(self.receipt, self.active)
        return backup

    def snapshot(self):
        return {p.relative_to(self.root).as_posix():
                hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
                for p in self.root.rglob('*')}

    def check(self, reason=None):
        before = self.snapshot()
        result = audit.audit_legacy_migration('demo', self.root)
        self.assertEqual(before, self.snapshot())
        for flag in ('migration_performed', 'migration_write_allowed',
                     'local_tty_approval_collected', 'upstream_provenance_revalidated',
                     'historical_ownership_independently_verified', 'real_host_files_modified',
                     'third_party_skill_executed', 'rollback_implementation_verified',
                     'cooperative_lock_acquired'):
            self.assertIs(result[flag], False)
        self.assertNotIn(str(self.root), json.dumps(result))
        if reason is not None:
            self.assertEqual(result['status'], 'blocked')
            self.assertEqual(result['reason_code'], reason)
            self.assertIsNone(result['candidate_metadata_sha256'])
        else:
            self.assertEqual(result['status'], 'candidate_metadata_verified_read_only')
            self.assertRegex(result['source_snapshot_sha256'], '^[a-f0-9]{64}$')
            self.assertRegex(result['candidate_metadata_sha256'], '^[a-f0-9]{64}$')
        return result

    def test_fresh_receipt_is_deterministic_and_readonly(self):
        first = self.check()
        self.assertEqual(first, self.check())
        self.assertEqual(first['candidate_record_count'], 1)
        self.assertFalse((self.state / 'hosts').exists())
        self.assertFalse((self.state / '.lock').exists())

    def test_complete_two_backup_chain_is_mapped_in_memory(self):
        self.replace('2')
        self.replace('3')
        result = self.check()
        self.assertEqual(result['backup_count'], 2)
        self.assertEqual(result['candidate_record_count'], 3)
        before = result['source_snapshot_sha256']
        self.receipt.write_bytes(self.receipt.read_bytes() + b' ')
        after = self.check()
        self.assertNotEqual(before, after['source_snapshot_sha256'])
        self.assertEqual(result['candidate_metadata_sha256'], after['candidate_metadata_sha256'])

    def test_changed_active_and_backup_files_fail_closed(self):
        backup = self.replace('2')
        original = (self.target / 'SKILL.md').read_bytes()
        (self.target / 'SKILL.md').write_bytes(b'LOCAL EDIT')
        self.check('active_inventory_mismatch')
        (self.target / 'SKILL.md').write_bytes(original)
        (backup / 'SKILL.md').write_bytes(b'LOCAL BACKUP EDIT')
        self.check('backup_inventory_mismatch')

    def test_unrecognized_backup_and_wrong_lineage_are_refused(self):
        backup = self.replace('2')
        extra = self.backups / 'unknown'
        extra.write_bytes(b'KEEP')
        self.check('unknown_or_missing_backup_entries')
        extra.unlink()
        manifest_path = backup.with_suffix('.json')
        manifest = json.loads(manifest_path.read_bytes())
        manifest['previous_receipt']['backup_ids'] = ['f' * 32]
        self.write(manifest_path, manifest)
        self.check('backup_lineage_mismatch')

    def test_unmanaged_origin_is_not_upgraded_to_pinned(self):
        backup = self.replace('2')
        manifest = json.loads(backup.with_suffix('.json').read_bytes())
        manifest['previous_receipt'] = None
        self.write(backup.with_suffix('.json'), manifest)
        self.check('unmanaged_backup_requires_manual_review')

    def test_unsupported_historical_semantics_preserved(self):
        self.active['manual_ownership_attested'] = True
        self.write(self.receipt, self.active)
        self.check('historical_fields_require_explicit_semantics')

    def test_all_pending_or_alternate_records_block(self):
        for relative, reason in (
            ('journals/demo.json', 'legacy_recovery_required'),
            ('stage/unknown', 'legacy_recovery_required'),
            ('uninstalled/demo.json', 'uninstall_marker_requires_explicit_semantics'),
            ('hosts/codex/receipts/demo.json', 'destination_ownership_or_pending_state'),
            ('hosts/codex/journals/demo.json', 'destination_ownership_or_pending_state'),
            ('hosts/codex/uninstalled/demo.json', 'destination_ownership_or_pending_state'),
            ('hosts/codex/backups/demo/unknown', 'destination_ownership_or_pending_state'),
            ('hosts/codex/stage/unknown', 'destination_ownership_or_pending_state'),
        ):
            with self.subTest(relative=relative):
                path = self.state / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'PRESERVE')
                try:
                    self.check(reason)
                finally:
                    path.unlink()

    def test_unknown_legacy_history_and_missing_receipt_are_not_adopted(self):
        self.receipt.unlink()
        self.check('no_legacy_active_receipt')
        (self.backups / 'unowned').write_bytes(b'KEEP')
        self.check('unowned_history_requires_manual_review')

    def test_duplicate_json_keys_and_hardlink_refused(self):
        original = self.receipt.read_bytes()
        self.receipt.write_bytes(b'{"schema":"x","schema":"y"}')
        self.check('duplicate_json_key')
        self.receipt.write_bytes(original)
        alias = self.root / 'alias'
        os.link(self.receipt, alias)
        self.check('unsafe_record')
        alias.unlink()
        os.link(self.target / 'SKILL.md', alias)
        self.check('hardlinked_inventory')

    def test_observable_concurrent_change_blocks(self):
        original = audit._snapshot
        def changed(root, slug):
            result = original(root, slug)
            self.receipt.write_bytes(self.receipt.read_bytes() + b' ')
            return result
        with patch.object(audit, '_snapshot', side_effect=changed):
            result = audit.audit_legacy_migration('demo', self.root)
        self.assertEqual(result['reason_code'], 'state_changed_during_audit')
        self.assertFalse(result['migration_write_allowed'])

    @unittest.skipUnless(os.name == 'posix', 'Windows reserved filename portability case')
    def test_posix_file_that_cannot_be_represented_on_windows_is_blocked(self):
        (self.target / 'CON.txt').write_bytes(b'INERT')
        self.active['files'] = _inventory(self.target)
        self.write(self.receipt, self.active)
        self.check('invalid_or_unsafe_local_evidence')

    def test_reserved_windows_skill_name_blocked_on_every_platform(self):
        report = audit.audit_legacy_migration('con', self.root)
        self.assertEqual(report['status'], 'blocked')
        self.assertFalse(report['migration_write_allowed'])

    def test_cli_json_and_blocked_exit_status_without_writes(self):
        command = [sys.executable, str(ROOT / 'tools/gasl.py'), 'codex-migration-audit',
                   '--selected-root', str(self.root), '--skill-name', 'demo']
        before = self.snapshot()
        run = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['status'], 'candidate_metadata_verified_read_only')
        self.assertEqual(before, self.snapshot())
        self.receipt.unlink()
        before = self.snapshot()
        run = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertEqual(json.loads(run.stdout)['status'], 'blocked')
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
