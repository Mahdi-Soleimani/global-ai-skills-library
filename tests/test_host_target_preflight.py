"""Phase 27: read-only exact target binding; only synthetic disposable roots."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from tests import test_install_bundle as bundle_fixture
from host_target_preflight import (
    _target_path, inspect_selected_target, verify_target_unchanged,
)


class TargetPreflightTests(unittest.TestCase):
    def setUp(self):
        self.bundle = bundle_fixture.PrivateInstallBundleTests(
            'test_private_zip_contains_only_pinned_files_and_is_verified')
        self.bundle.setUp()
        self.addCleanup(self.bundle.doCleanups)
        self.bundle._package()
        self.bundle_root = self.bundle.root
        self.plan_id = self.bundle._plan()['plan_id']
        self.bundle._prepare()
        self.temp = tempfile.TemporaryDirectory(prefix='gasl-phase27-selected-')
        self.addCleanup(self.temp.cleanup)
        self.selected = Path(self.temp.name)

    def inspect(self, agent='codex', scope='project', selected_root=None, pid=None):
        return inspect_selected_target(pid or self.plan_id, agent, scope,
            selected_root or self.selected, bundle_root=self.bundle_root)

    def test_absent_root_preflight_has_no_filesystem_side_effect(self):
        before = list(self.selected.iterdir())
        d = self.inspect()
        self.assertEqual(d['status'], 'read_only_target_preflight_completed')
        self.assertEqual(d['prior_target_state'], 'target_absent')
        self.assertEqual(d['relative_target'], '.agents/skills/demo')
        self.assertEqual(d['existing_file_count'], 0)
        self.assertEqual(list(self.selected.iterdir()), before)
        self.assertFalse(d['state_binding_is_authorization'])
        self.assertFalse(d['installation_allowed'])
        self.assertFalse(d['actual_install_enabled'])
        self.assertFalse(d['real_host_files_modified'])
        self.assertFalse(d['third_party_skill_executed'])
        self.assertTrue(d['no_user_paths_or_file_names_in_output'])
        self.assertNotIn(str(self.selected), json.dumps(d))
        self.assertNotIn(str(self.bundle_root), json.dumps(d))

    def test_two_readonly_runs_have_same_binding_without_writes(self):
        one = self.inspect()
        two = self.inspect()
        self.assertEqual(one['state_binding_id'], two['state_binding_id'])
        matched = verify_target_unchanged(self.plan_id, 'codex', 'project',
            self.selected, one['state_binding_id'], bundle_root=self.bundle_root)
        self.assertTrue(matched['state_binding_matches_previous_preflight'])
        self.assertEqual(list(self.selected.iterdir()), [])

    def test_explicit_existing_skill_collision_is_inspected_not_overwritten(self):
        target, _ = _target_path(self.selected, 'codex', 'project', 'demo')
        target.mkdir(parents=True)
        current = target / 'SKILL.md'
        current.write_text('PRIVATE_USER_SKILL_CONTENT_EXAMPLE\n')
        first = self.inspect()
        self.assertEqual(first['prior_target_state'], 'existing_skill_collision')
        self.assertEqual(first['existing_file_count'], 1)
        self.assertFalse(first['installation_allowed'])
        self.assertTrue(first['existing_files_read_only_for_hashing'])
        self.assertIn('existing_target_must_not_be_replaced_without_separate_specific_approval', first['warnings'])
        self.assertNotIn('PRIVATE_USER_SKILL_CONTENT_EXAMPLE', json.dumps(first))
        self.assertNotIn(str(target), json.dumps(first))
        self.assertEqual(current.read_text(), 'PRIVATE_USER_SKILL_CONTENT_EXAMPLE\n')

    def test_changed_existing_file_invalidates_previous_binding(self):
        target, _ = _target_path(self.selected, 'codex', 'project', 'demo')
        target.mkdir(parents=True)
        (target / 'SKILL.md').write_text('VERSION 1')
        first = self.inspect()
        (target / 'SKILL.md').write_text('VERSION 2')
        second = self.inspect()
        self.assertNotEqual(first['state_binding_id'], second['state_binding_id'])
        with self.assertRaisesRegex(ValueError, 'has changed'):
            verify_target_unchanged(self.plan_id,'codex','project',self.selected,
                                     first['state_binding_id'],bundle_root=self.bundle_root)
        self.assertEqual((target/'SKILL.md').read_text(), 'VERSION 2')

    def test_created_target_after_absent_plan_invalidates_previous_binding(self):
        first = self.inspect()
        target, _ = _target_path(self.selected, 'codex', 'project', 'demo')
        target.mkdir(parents=True)
        (target / 'SKILL.md').write_text('OTHER_INSTALL')
        with self.assertRaisesRegex(ValueError, 'has changed'):
            verify_target_unchanged(self.plan_id,'codex','project',self.selected,
                                     first['state_binding_id'],bundle_root=self.bundle_root)

    def test_changed_user_selected_root_invalidates_binding(self):
        first = self.inspect()
        another = self.selected/'other-root'
        another.mkdir()
        second = self.inspect(selected_root=another)
        self.assertNotEqual(first['state_binding_id'], second['state_binding_id'])
        self.assertNotEqual(first['selected_target_sha256'], second['selected_target_sha256'])

    def test_works_for_all_three_hosts_and_both_scopes(self):
        for agent in ('codex','cursor','claude-code'):
            for scope in ('project','user'):
                with self.subTest(agent=agent,scope=scope):
                    plan_id = (self.plan_id if (agent,scope)==('codex','project')
                               else self.bundle._prepare(agent,scope)['plan_id'])
                    report = self.inspect(agent,scope,pid=plan_id)
                    self.assertEqual(report['host'],agent)
                    self.assertEqual(report['scope'],scope)
                    self.assertEqual(report['prior_target_state'],'target_absent')
                    self.assertFalse(report['root_actual_role_verified'])
                    self.assertFalse(report['installation_allowed'])

    def test_wrong_agent_and_scope_are_rejected_by_bundle_identity(self):
        for agent,scope in (('cursor','project'),('codex','user'),('claude-code','project')):
            with self.subTest(agent=agent,scope=scope), self.assertRaisesRegex(ValueError,'not bound to this Host'):
                self.inspect(agent,scope)
        self.assertEqual(list(self.selected.iterdir()),[])

    def test_invalid_plan_or_binding_rejected(self):
        with self.assertRaisesRegex(ValueError,'Exact pinned Plan ID'):
            self.inspect(pid='not-a-hash')
        with self.assertRaisesRegex(ValueError,'Exact prior state binding'):
            verify_target_unchanged(self.plan_id,'codex','project',self.selected,
                                     'untrusted',bundle_root=self.bundle_root)

    def test_relative_or_nonexistent_root_rejected_without_creating_it(self):
        with self.assertRaisesRegex(ValueError,'existing absolute'):
            self.inspect(selected_root=Path('relative/unsafe'))
        absent = self.selected / 'does-not-exist'
        with self.assertRaisesRegex(ValueError,'existing absolute'):
            self.inspect(selected_root=absent)
        self.assertFalse(absent.exists())

    def test_symlinked_selected_root_rejected(self):
        link = self.selected / 'linked-root'
        link.symlink_to(self.selected, target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'existing absolute'):
            self.inspect(selected_root=link)
        self.assertTrue(link.is_symlink())

    def test_symlinked_host_prefix_rejected(self):
        sentinel = self.selected / 'external-dir'
        sentinel.mkdir()
        (self.selected / '.agents').symlink_to(sentinel, target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'Symlink'):
            self.inspect()
        self.assertEqual(list(sentinel.iterdir()), [])

    def test_symlinked_skill_target_rejected(self):
        parent = self.selected/'.agents/skills'
        parent.mkdir(parents=True)
        (parent/'demo').symlink_to(self.selected, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            self.inspect()

    def test_regular_file_in_target_parent_rejected(self):
        (self.selected/'.agents').write_text('not a directory')
        with self.assertRaisesRegex(ValueError,'Non-directory'):
            self.inspect()

    def test_existing_skill_directory_with_case_only_difference_is_blocked(self):
        parent = self.selected/'.agents/skills'
        parent.mkdir(parents=True)
        different_case = parent/'Demo'
        different_case.mkdir()
        (different_case/'SKILL.md').write_text('CASE_COLLISION_SENTINEL')
        with self.assertRaisesRegex(ValueError,'Case-insensitive Skill directory collision'):
            self.inspect()
        self.assertEqual((different_case/'SKILL.md').read_text(),'CASE_COLLISION_SENTINEL')

    def test_unknown_or_unsupported_host_is_refused(self):
        with self.assertRaisesRegex(ValueError,'filesystem Host'):
            self.inspect('claude-desktop')
        with self.assertRaisesRegex(ValueError,'filesystem Host'):
            self.inspect('generic-mcp')

    def test_invalid_existing_symlink_inside_skill_is_rejected(self):
        target, _ = _target_path(self.selected,'codex','project','demo')
        target.mkdir(parents=True)
        secret = self.selected/'never-read-sentinel'
        secret.write_text('DO_NOT_READ')
        (target/'SKILL.md').symlink_to(secret)
        with self.assertRaisesRegex(ValueError,'Symlink'):
            self.inspect()
        self.assertEqual(secret.read_text(),'DO_NOT_READ')

    def test_nested_user_added_empty_directory_is_rejected(self):
        target, _ = _target_path(self.selected,'codex','project','demo')
        (target/'empty-folder').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'Empty or untracked'):
            self.inspect()
        self.assertTrue((target/'empty-folder').is_dir())

    def test_corrupt_bundle_refused_before_inspecting_target(self):
        bundle = self.bundle_root/'private/install-bundles'/f'{self.plan_id}.zip'
        bundle.write_bytes(bundle.read_bytes()+b'CORRUPT')
        with self.assertRaisesRegex(ValueError,'ZIP digest'):
            self.inspect()
        self.assertEqual(list(self.selected.iterdir()),[])

    def test_bundle_license_and_legacy_evidence_warnings_retained(self):
        record = self.inspect()
        self.assertIn('source_license_requires_review',record['warnings']) if self.bundle.row.get('license_spdx') in (None,'NOASSERTION','UNKNOWN','') else None
        self.assertIn('live_host_target_compatibility_not_validated', record['warnings'])
        self.assertIn('real_user_install_approval_not_collected',record['warnings'])
        self.assertFalse(record['state_binding_is_authorization'])


if __name__ == '__main__':
    unittest.main()
