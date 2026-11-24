"""Compatibility routing and legacy evidence on disposable, authored fixtures."""
import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import gasl
import codex_legacy_reconcile as reconcile
import codex_project_install as legacy
import host_project_install as native
import host_project_wizard as wizard
from fixture_bundle_install import _inventory
from tests import test_windows_project_transactions as fixtures


class NativeCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.WindowsProjectTransactionTests(
            'test_complete_replace_restore_preserves_versions')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.project = self.case.project.resolve()
        if os.name != 'nt':
            for module in (native, wizard):
                patcher = patch.object(module, '_host', return_value='codex')
                patcher.start()
                self.addCleanup(patcher.stop)

    def command(self, action, **kwargs):
        args = argparse.Namespace(action=action, selected_root=self.project,
                                  skill_name='demo', plan_id=None, backup_id=None,
                                  state_binding_id=None)
        vars(args).update(kwargs)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.object(gasl, 'ROOT', self.case.bundle_root):
            gasl._windows_codex_project_command(args)
        return json.loads(output.getvalue())

    def test_native_alias_preview_and_full_lifecycle(self):
        plan = self.case.prepare('codex')
        # Lookup is fixture-specific; preview via actual engine, while alias
        # routing is exercised through the CLI with existing native records.
        self.case.install('codex', plan)
        nextplan = self.case.next_plan('codex')
        ident = self.case.replace('codex', nextplan)['backup_id']
        self.assertEqual(self.command('list-backups')['backup_count'], 1)
        with self.assertRaises(SystemExit):
            self.command('list-uninstalled-backups')
        preview = self.command('preview-restore', backup_id=ident)
        self.assertEqual(preview['state_binding_id'],
                         native.preview_restore('codex', self.project, 'demo', ident)['state_binding_id'])
        with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', self.case.consent):
            self.command('restore-backup', backup_id=ident, state_binding_id=preview['state_binding_id'])
        preview = self.command('preview-uninstall')
        with self.assertRaisesRegex(SystemExit, 'state-binding-id'):
            self.command('uninstall')
        with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', self.case.consent):
            archived = self.command('uninstall', state_binding_id=preview['state_binding_id'])
        ident = archived['archived_backup_id']
        self.assertEqual(self.command('list-uninstalled-backups')['lifecycle'], 'uninstalled_owned')
        with self.assertRaises(SystemExit):
            self.command('list-backups')
        preview = self.command('preview-reinstall', backup_id=ident)
        with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', self.case.consent):
            self.command('reinstall-backup', backup_id=ident, state_binding_id=preview['state_binding_id'])
        self.assertTrue(self.case.target('codex').is_dir())

    def test_alias_install_replace_and_recover_dispatch(self):
        for action in ('preview', 'install', 'preview-replace', 'replace', 'recover'):
            with self.subTest(action=action), patch.object(gasl, 'cmd_host_project_install') as dispatch:
                args = argparse.Namespace(action=action, selected_root=self.project,
                    skill_name='demo', plan_id='a'*64, backup_id=None, state_binding_id='b'*64)
                gasl._windows_codex_project_command(args)
                actual = dispatch.call_args.args[0]
                self.assertEqual(actual.host, 'codex')
                self.assertEqual(actual.action, action)
                self.assertEqual(actual.state_binding_id, args.state_binding_id)

    def test_legacy_writes_refused_before_native_dispatch(self):
        for action in ('preview-legacy-reinstall', 'reinstall-legacy-backup'):
            with patch.object(gasl, 'cmd_host_project_install') as dispatch:
                with self.assertRaisesRegex(SystemExit, 'not enabled on Windows'):
                    self.command(action)
                dispatch.assert_not_called()
        self.assertFalse((self.project/'.gasl-managed').exists())

    @unittest.skipUnless(os.name == 'nt', 'Actual Windows compatibility command')
    def test_windows_public_cli_and_explorer_handoff(self):
        from codex_explorer_handoff import inspect_handoff, install_from_explorer
        source_id = self.case.fixture.row['source_record_id']
        root = self.case.bundle_root
        lookup = self.case.fixture.lookup
        preview = inspect_handoff(source_id, self.project, root=root, lookup=lookup)
        self.assertEqual(preview['host'], 'codex')
        self.assertFalse(preview['real_host_modified'])
        with patch('sys.stdin.isatty', return_value=False):
            with self.assertRaisesRegex(ValueError, 'interactive TTY'):
                install_from_explorer(source_id, self.project, root=root, lookup=lookup,
                                       reader=self.case.consent, printer=lambda _: None)
        with patch('sys.stdin.isatty', return_value=True):
            result = install_from_explorer(source_id, self.project, root=root, lookup=lookup,
                                           reader=self.case.consent, printer=lambda _: None)
        self.assertEqual(result['status'], 'host_project_wizard_completed')
        self.assertTrue(self.case.state('codex').is_dir())
        run = subprocess.run([sys.executable, str(ROOT/'tools/gasl.py'),
            'codex-project-install', '--action', 'list-backups', '--selected-root',
            str(self.project), '--skill-name', 'demo'], capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['ownership_store'], 'native_host_scoped')


class PortableOrphanAuditTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        (self.root/'.git').mkdir()
        self.state = self.root/'.gasl-managed'
        self.ident = 'a'*32
        self.folder = self.state/'backups'/'demo'/self.ident
        self.folder.mkdir(parents=True)
        (self.folder/'SKILL.md').write_bytes(b'---\nname: demo\n---\nINERT ONLY\n')
        self.manifest = self.folder.with_suffix('.json')
        self.manifest.write_bytes(legacy._serialized({
            'schema': legacy.SCHEMA, 'kind': 'pre_replace_backup', 'slug': 'demo',
            'backup_id': self.ident, 'transaction': self.ident,
            'previous_receipt': None, 'files': _inventory(self.folder),
        }))

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() if p.is_file() else None
                for p in self.root.rglob('*')}

    def test_unowned_history_stays_unowned_and_readonly(self):
        before = self.snapshot()
        report = reconcile.audit_portable_legacy_backups('demo', self.root)
        self.assertFalse(report['historical_project_ownership_verified'])
        self.assertFalse(report['reconciliation_write_enabled'])
        self.assertTrue(report['manual_ownership_attestation_required'])
        self.assertEqual(report['backup_count'], 1)
        self.assertEqual(before, self.snapshot())

    def test_tampered_file_and_hardlinked_manifest_refused(self):
        skill = self.folder/'SKILL.md'
        data = skill.read_bytes()
        skill.write_bytes(b'CHANGED')
        with self.assertRaisesRegex(ValueError, 'Changed legacy backup'):
            reconcile.audit_portable_legacy_backups('demo', self.root)
        skill.write_bytes(data)
        alias = self.root/'alias'
        os.link(self.manifest, alias)
        with self.assertRaisesRegex(ValueError, 'unsafe_record'):
            reconcile.audit_portable_legacy_backups('demo', self.root)

    def test_pending_stage_and_alternate_namespace_refused(self):
        stage = self.state/'stage'
        stage.mkdir()
        (stage/'unknown').write_bytes(b'KEEP')
        with self.assertRaisesRegex(ValueError, 'pending ownership state'):
            reconcile.audit_portable_legacy_backups('demo', self.root)
        (stage/'unknown').unlink()
        receipt = self.state/'hosts/codex/receipts/demo.json'
        receipt.parent.mkdir(parents=True)
        receipt.write_bytes(b'KEEP')
        with self.assertRaisesRegex(ValueError, 'explicit migration required'):
            reconcile.audit_portable_legacy_backups('demo', self.root)

    @unittest.skipUnless(os.name == 'nt', 'Native Windows orphan route')
    def test_public_orphan_audit_and_write_refusal_on_windows(self):
        report = reconcile.audit_legacy_backups('demo', self.root)
        self.assertFalse(report['reconciliation_write_enabled'])
        with self.assertRaisesRegex(ValueError, 'not enabled on Windows'):
            reconcile.preview_legacy_reinstall('demo', self.root, self.ident)


if __name__ == '__main__':
    unittest.main()
