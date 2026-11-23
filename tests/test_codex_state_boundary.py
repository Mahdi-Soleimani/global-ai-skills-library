"""Reject conflicting Codex state schemas without changing either history."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import codex_project_install as legacy
import host_project_install as native


class CodexStateBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='gasl-schema-boundary-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / '.git').mkdir()
        self.old = self.root / '.gasl-managed'
        self.new = self.old / 'hosts' / 'codex'

    def test_each_alternate_record_type_blocks_readonly_paths(self):
        for current, other in ((legacy, self.new), (native, self.old)):
            for relative in ('receipts/demo.json', 'journals/demo.json',
                             'uninstalled/demo.json', 'backups/demo/version.json',
                             'stage/unknown-transaction'):
                with self.subTest(engine=current.__name__, path=relative):
                    record = other / relative
                    record.parent.mkdir(parents=True, exist_ok=True)
                    record.write_bytes(b'PRESERVE UNKNOWN SCHEMA')
                    try:
                        if current is legacy:
                            action = lambda: legacy._paths(self.root, 'demo')
                        else:
                            # POSIX does not expose native Codex as a production
                            # adapter; only the routing guard is tested here.
                            action = lambda: native._paths(self.root, 'codex', 'demo')
                        with patch.object(native, '_host', return_value='codex'):
                            with self.assertRaisesRegex(ValueError, 'explicit migration required'):
                                action()
                        self.assertEqual(record.read_bytes(), b'PRESERVE UNKNOWN SCHEMA')
                        self.assertFalse((self.root / '.agents').exists())
                    finally:
                        record.unlink()

    def test_other_skill_and_other_host_state_do_not_conflict(self):
        record = self.new / 'receipts' / 'different.json'
        record.parent.mkdir(parents=True)
        record.write_bytes(b'OTHER SKILL')
        self.assertEqual(legacy._paths(self.root, 'demo')[2], self.old)
        record = self.old / 'uninstalled' / 'demo.json'
        record.parent.mkdir()
        record.write_bytes(b'LEGACY ARCHIVE')
        self.assertEqual(native._paths(self.root, 'cursor', 'demo')[2],
                         self.old / 'hosts' / 'cursor')

    def test_unsafe_alternate_directory_fails_closed(self):
        self.new.mkdir(parents=True)
        (self.new / 'receipts').write_bytes(b'NOT DIRECTORY')
        with self.assertRaisesRegex(ValueError, 'Unsafe alternate'):
            legacy._paths(self.root, 'demo')

    @unittest.skipUnless(os.name == 'nt', 'Native Windows Codex coordination')
    def test_native_windows_lock_checks_legacy_history_without_creating_target(self):
        marker = self.old / 'uninstalled' / 'demo.json'
        marker.parent.mkdir(parents=True)
        marker.write_bytes(b'LEGACY ARCHIVE')
        with self.assertRaisesRegex(ValueError, 'explicit migration required'):
            with native._lock(self.root, 'codex', 'demo'):
                self.fail('Legacy archive must block the alternate engine')
        self.assertFalse(self.new.exists())
        self.assertFalse((self.root / '.agents').exists())
        self.assertEqual(marker.read_bytes(), b'LEGACY ARCHIVE')


if __name__ == '__main__':
    unittest.main()
