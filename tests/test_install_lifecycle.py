"""Phase 20 safe install-preview and simulated lifecycle regression cases."""
import hashlib
import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from install_lifecycle import plan_install, simulate, simulation_status, AGENTS, SCOPES
from queue_ingest import git_blob, ingest, make_plan, package_location


class InstallLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gasl-phase20-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'config').mkdir()
        (self.root / 'registry').mkdir()
        (self.root / 'config/policy.json').write_text(json.dumps({
            'max_file_size_bytes': 10000, 'max_skill_size_bytes': 20000,
            'public_mirror_spdx_allowlist': ['MIT'],
        }))
        self.content = {'skills/demo/SKILL.md': b'# Controlled fixture\nSafe documentation.\n',
                        'skills/demo/references/about.md': b'No executable code.\n'}
        self.row = {
            'source_record_id': 'GASL-SRC-fixture', 'skill_name': 'demo',
            'repository': 'Org/Repo', 'source_path': 'skills/demo/SKILL.md',
            'commit_sha': 'a' * 40, 'tree_sha': 'b' * 40,
            'skill_md_blob_sha': git_blob(self.content['skills/demo/SKILL.md']),
            'snapshot_status': 'verified_commit_pinned',
            'license_spdx': 'MIT', 'source_url': 'https://example.invalid/source',
            'research_leads': [],
        }
        self.lookup = lambda key, root: dict(self.row) if key == self.row['source_record_id'] else None

    def _package(self):
        tree = {'sha': self.row['tree_sha'], 'truncated': False,
                'tree': [{'path': p, 'type': 'blob', 'mode': '100644',
                          'size': len(data), 'sha': git_blob(data)}
                         for p, data in self.content.items()]}
        plan = make_plan({**self.row, 'skill_path': self.row['source_path']}, tree,
                         json.loads((self.root / 'config/policy.json').read_text()))
        ingest(self.root, plan, fetch=lambda plan, item: self.content[item['path']],
               manifest_path=self.root / 'registry/test-private-manifest.json')
        folder = package_location(self.root, plan)
        return folder, folder / 'source.json'

    def _plan(self, agent='codex', scope='project'):
        return plan_install(self.row['source_record_id'], agent, scope,
                            root=self.root, lookup=self.lookup)

    def test_plan_does_not_create_private_ledger_or_agent_directory(self):
        p = self._plan()
        self.assertEqual(p['local_package']['status'], 'not_downloaded')
        self.assertFalse(p['simulation_apply_eligible'])
        self.assertFalse(p['installation_allowed'])
        self.assertFalse(p['actual_install_enabled'])
        self.assertFalse(p['destination_modified'])
        self.assertFalse((self.root / 'private').exists())
        self.assertFalse((self.root / '.codex').exists())
        self.assertEqual(p['compatibility']['status'], 'not_declared')
        self.assertEqual(p['logical_destination'], 'preview:codex:project')

    def test_source_id_exact_pinned_hash_determines_plan_identity(self):
        p = self._plan()
        self.assertEqual(len(p['plan_id']), 64)
        self.assertEqual(p['plan_id'], self._plan()['plan_id'])
        self.assertNotEqual(p['plan_id'], self._plan(agent='cursor')['plan_id'])
        self.assertNotEqual(p['plan_id'], self._plan(scope='user')['plan_id'])
        self.row['commit_sha'] = 'c' * 40
        self.assertNotEqual(p['plan_id'], self._plan()['plan_id'])

    def test_unknown_agent_and_scope_fail_early(self):
        with self.assertRaisesRegex(ValueError, 'Unknown agent'):
            self._plan(agent='my-agent/../../bad')
        with self.assertRaisesRegex(ValueError, 'Scope'):
            self._plan(scope='../../outside')
        self.assertFalse((self.root / 'private').exists())

    def test_legacy_or_missing_pinned_blob_cannot_be_planned(self):
        self.row['snapshot_status'] = 'legacy_snapshot_unpinned'
        with self.assertRaisesRegex(ValueError, 'Exact commit'):
            self._plan()
        self.row['snapshot_status'] = 'verified_commit_pinned'
        self.row['skill_md_blob_sha'] = None
        with self.assertRaisesRegex(ValueError, 'Exact commit'):
            self._plan()

    def test_planner_inspects_package_without_rewriting_source_manifest(self):
        folder, source = self._package()
        before = source.read_bytes()
        p = self._plan()
        self.assertEqual(before, source.read_bytes())
        self.assertEqual(p['local_package']['status'], 'downloaded_verified')
        self.assertTrue(p['local_package']['pinned_skill_blob_ok'])
        self.assertTrue(p['simulation_apply_eligible'])
        self.assertFalse(p['compatibility']['host_integration_verified'])
        self.assertEqual(p['local_package']['actionable_findings'], 0)
        self.assertFalse((self.root / 'private').exists())

    def test_tampered_package_is_not_eligible_and_cannot_be_simulated(self):
        folder, source = self._package()
        (folder / 'SKILL.md').write_text('# changed main skill\n')
        p = self._plan()
        self.assertFalse(p['simulation_apply_eligible'])
        self.assertEqual(p['local_package']['status'], 'integrity_failed')
        with self.assertRaisesRegex(ValueError, 'verified, non-flagged'):
            simulate('apply', p['plan_id'], acknowledgement=p['plan_id'], root=self.root, plan=p)
        self.assertFalse((self.root / 'private').exists())

    def test_unlisted_file_blocks_simulated_apply(self):
        folder, _ = self._package()
        (folder / 'unknown.py').write_text('print(123)')
        p = self._plan()
        self.assertEqual(p['local_package']['status'], 'integrity_failed')
        self.assertFalse(p['simulation_apply_eligible'])

    def test_actionable_security_scan_blocks_simulated_apply(self):
        self.content['skills/demo/scripts/process.py'] = b'import os\nos.system("echo not executed")\n'
        self.row['skill_md_blob_sha'] = git_blob(self.content['skills/demo/SKILL.md'])
        self._package()
        p = self._plan()
        self.assertEqual(p['local_package']['security_status'], 'manual_review_required')
        self.assertFalse(p['simulation_apply_eligible'])
        self.assertIn('static_security_review_required', p['warnings'])

    def test_declared_compatibility_never_proves_host_integration(self):
        self.row['compatibility'] = 'Codex specific format'
        p = self._plan()
        self.assertEqual(p['compatibility']['status'], 'declared_match_unverified')
        self.assertFalse(p['compatibility']['host_integration_verified'])
        self.assertFalse(p['installation_allowed'])
        self.assertEqual(self._plan('cursor')['compatibility']['status'],
                         'declared_nonmatching_unverified')

    def test_unknown_license_warning_does_not_restrict_source_discovery(self):
        self.row['license_spdx'] = 'NOASSERTION'
        p = self._plan()
        self.assertEqual(p['license_spdx'], 'NOASSERTION')
        self.assertIn('license_terms_require_review', p['warnings'])
        self.assertFalse(p['installation_allowed'])

    def test_simulated_apply_and_rollback_are_transactional_with_hash_chain(self):
        self._package()
        plan = self._plan()
        sentinel = self.root / 'user-agent-home' / 'skills'
        sentinel.parent.mkdir()
        sentinel.write_text('PRESERVE_AGENTS', encoding='utf-8')
        initial_status = simulation_status(plan['plan_id'], root=self.root)
        self.assertEqual(initial_status['status'], 'never_simulated')
        self.assertFalse((self.root / 'private').exists())
        applied = simulate('apply', plan['plan_id'], acknowledgement=plan['plan_id'],
                           plan=plan, root=self.root)
        self.assertEqual(applied['status'], 'simulated_active')
        self.assertFalse(applied['real_installation_performed'])
        self.assertFalse(applied['agent_files_modified'])
        self.assertEqual(simulation_status(plan['plan_id'], root=self.root)['status'], 'simulated_active')
        reverted = simulate('rollback', plan['plan_id'], acknowledgement=plan['plan_id'], root=self.root)
        self.assertEqual(reverted['status'], 'simulated_rolled_back')
        self.assertEqual(reverted['event_sequence'], 2)
        self.assertEqual(simulation_status(plan['plan_id'], root=self.root)['status'], 'simulated_rolled_back')
        self.assertEqual(sentinel.read_text(), 'PRESERVE_AGENTS')
        self.assertFalse((self.root / '.codex').exists())
        self.assertFalse((self.root / '.cursor').exists())
        self.assertTrue((self.root / 'private/install-simulation/events.sqlite3').exists())

    def test_duplicate_simulation_apply_rejected_without_appending(self):
        self._package()
        plan = self._plan()
        simulate('apply', plan['plan_id'], acknowledgement=plan['plan_id'], plan=plan, root=self.root)
        with self.assertRaisesRegex(ValueError, 'already simulated as active'):
            simulate('apply', plan['plan_id'], acknowledgement=plan['plan_id'], plan=plan, root=self.root)
        self.assertEqual(simulation_status(plan['plan_id'], root=self.root)['event_count'], 1)

    def test_bad_acknowledgement_is_rejected_before_ledger_creation(self):
        self._package()
        plan = self._plan()
        with self.assertRaisesRegex(ValueError, 'Explicit acknowledgement'):
            simulate('apply', plan['plan_id'], acknowledgement='f' * 64, plan=plan, root=self.root)
        self.assertFalse((self.root / 'private').exists())

    def test_apply_rejects_changed_version_or_agent_without_ledger(self):
        self._package()
        plan = self._plan()
        mismatch = self._plan(agent='cursor')
        with self.assertRaisesRegex(ValueError, 'exact current plan'):
            simulate('apply', plan['plan_id'], acknowledgement=plan['plan_id'],
                     plan=mismatch, root=self.root)
        self.assertFalse((self.root / 'private').exists())

    def test_rollback_of_nonexistent_plan_fails_without_file_creation(self):
        pid = 'a' * 64
        with self.assertRaisesRegex(ValueError, 'No active simulated installation ledger'):
            simulate('rollback', pid, acknowledgement=pid, root=self.root)
        self.assertFalse((self.root / 'private').exists())

    def test_double_rollback_blocks_without_changing_history(self):
        self._package()
        p = self._plan()
        simulate('apply', p['plan_id'], acknowledgement=p['plan_id'], plan=p, root=self.root)
        simulate('rollback', p['plan_id'], acknowledgement=p['plan_id'], root=self.root)
        with self.assertRaisesRegex(ValueError, 'Only a simulated active'):
            simulate('rollback', p['plan_id'], acknowledgement=p['plan_id'], root=self.root)
        self.assertEqual(simulation_status(p['plan_id'], root=self.root)['event_count'], 2)

    def test_tampered_ledger_is_rejected_fail_closed(self):
        self._package()
        p = self._plan()
        simulate('apply', p['plan_id'], acknowledgement=p['plan_id'], plan=p, root=self.root)
        ledger = self.root / 'private/install-simulation/events.sqlite3'
        con = sqlite3.connect(str(ledger))
        con.execute("UPDATE events SET payload = ? WHERE sequence = 1", ('{"plan_id":"' + p['plan_id'] + '"}',))
        con.commit()
        con.close()
        with self.assertRaisesRegex(ValueError, 'tampering detected'):
            simulation_status(p['plan_id'], root=self.root)
        with self.assertRaisesRegex(ValueError, 'tampering detected'):
            simulate('rollback', p['plan_id'], acknowledgement=p['plan_id'], root=self.root)

    def test_status_bad_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, 'valid SHA-256 plan ID'):
            simulation_status('../../escape', root=self.root)
        self.assertFalse((self.root / 'private').exists())

    def test_concurrent_duplicate_apply_records_exactly_one_event(self):
        self._package()
        p = self._plan()
        def run(_):
            try:
                simulate('apply', p['plan_id'], acknowledgement=p['plan_id'],
                         plan=p, root=self.root)
                return 'applied'
            except ValueError as exc:
                self.assertIn('already simulated as active', str(exc))
                return 'rejected_duplicate'
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = sorted(executor.map(run, (0, 1)))
        self.assertEqual(outcomes, ['applied', 'rejected_duplicate'])
        self.assertEqual(simulation_status(p['plan_id'], root=self.root)['event_count'], 1)

    def test_ledger_symlink_outside_workspace_is_blocked(self):
        self._package()
        p = self._plan()
        folder = self.root / 'private/install-simulation'
        folder.mkdir(parents=True)
        fake = self.root / 'external.sqlite3'
        fake.write_bytes(b'private sentinel')
        (folder / 'events.sqlite3').symlink_to(fake)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            simulation_status(p['plan_id'], root=self.root)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            simulate('apply', p['plan_id'], acknowledgement=p['plan_id'],
                     plan=p, root=self.root)
        self.assertEqual(fake.read_bytes(), b'private sentinel')

    def test_rollback_does_not_require_unavailable_or_re_pinned_source(self):
        self._package()
        p = self._plan()
        simulate('apply', p['plan_id'], acknowledgement=p['plan_id'],
                 plan=p, root=self.root)
        # A historical *simulation* must be revertible after catalog refresh.
        self.row['commit_sha'] = 'c' * 40
        result = simulate('rollback', p['plan_id'], acknowledgement=p['plan_id'], root=self.root)
        self.assertEqual(result['status'], 'simulated_rolled_back')
        self.assertFalse(result['real_installation_performed'])

    def test_reapply_after_rollback_is_new_simulated_event_only(self):
        self._package()
        p = self._plan()
        simulate('apply', p['plan_id'], acknowledgement=p['plan_id'], plan=p, root=self.root)
        simulate('rollback', p['plan_id'], acknowledgement=p['plan_id'], root=self.root)
        again = simulate('apply', p['plan_id'], acknowledgement=p['plan_id'], plan=p, root=self.root)
        self.assertEqual(again['event_sequence'], 3)
        self.assertEqual(simulation_status(p['plan_id'], root=self.root)['status'], 'simulated_active')


if __name__ == '__main__':
    unittest.main()
