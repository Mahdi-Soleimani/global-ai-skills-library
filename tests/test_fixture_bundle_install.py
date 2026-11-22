"""Phase 26: actual ZIP extraction/restore in disposable Host directories only."""
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from tests import test_install_bundle as bundle_fixture
from host_adapters import _target_for_fixture
from host_transaction_fixture import _new_root
from fixture_bundle_install import (
    _read_bundle, _same_inventory, _inventory, stage_bundle_fixture,
    activate_bundle_fixture, rollback_bundle_fixture, rehearse_private_bundle,
)


class FixtureBundleInstallTests(unittest.TestCase):
    def setUp(self):
        self.bundle_case = bundle_fixture.PrivateInstallBundleTests('test_private_zip_contains_only_pinned_files_and_is_verified')
        self.bundle_case.setUp()
        self.addCleanup(self.bundle_case.doCleanups)
        self.bundle_case._package()
        self.root = self.bundle_case.root
        self.plan = self.bundle_case._plan()
        self.pid = self.plan['plan_id']
        self.bundle_case._prepare()
        self.temp, self.fixture = _new_root()
        self.addCleanup(self.temp.cleanup)

    def _target(self, agent='codex', scope='project'):
        return _target_for_fixture(self.fixture, agent, scope, 'demo')

    def _prepare_old(self, agent='codex', scope='project'):
        target = self._target(agent, scope)
        target.mkdir(parents=True)
        (target / 'SKILL.md').write_bytes(b'Old inert fixture only\n')
        (target / 'user-note.txt').write_bytes(b'IMPORTANT_USER_SENTINEL\n')
        return _inventory(target)

    def test_real_file_materialization_and_rollback_on_disposable_codex_target(self):
        staged = stage_bundle_fixture(self.fixture, self.root, self.pid, 'codex','project',self.pid)
        self.assertEqual(staged['file_count'], 2)
        self.assertFalse(self._target().exists())
        activated = activate_bundle_fixture(self.fixture)
        self.assertEqual(activated['status'], 'fixture_bundle_activated')
        self.assertEqual((self._target()/'SKILL.md').read_bytes(),
                         self.bundle_case.content['skills/demo/SKILL.md'])
        self.assertEqual((self._target()/'references/about.md').read_bytes(),
                         self.bundle_case.content['skills/demo/references/about.md'])
        rolled = rollback_bundle_fixture(self.fixture)
        self.assertEqual(rolled['status'], 'fixture_bundle_rollback_verified')
        self.assertFalse(self._target().exists())
        self.assertFalse(rolled['real_host_files_modified'])
        self.assertFalse(rolled['third_party_skill_executed'])

    def test_real_upgrade_uses_backup_and_preserves_prior_user_note(self):
        old = self._prepare_old()
        stage_bundle_fixture(self.fixture,self.root,self.pid,'codex','project',self.pid,replace_existing=True)
        activate_bundle_fixture(self.fixture)
        self.assertEqual((self._target()/'SKILL.md').read_bytes(),
                         self.bundle_case.content['skills/demo/SKILL.md'])
        result = rollback_bundle_fixture(self.fixture)
        self.assertTrue(result['previous_files_restored'])
        self.assertTrue(_same_inventory(self._target(),old))
        self.assertEqual((self._target()/'user-note.txt').read_bytes(), b'IMPORTANT_USER_SENTINEL\n')

    def test_36_expected_recovery_checkpoints_over_host_scope_mode_matrix(self):
        count = 0
        for agent in ('codex','cursor','claude-code'):
            for scope in ('project','user'):
                plan_id = (self.pid if agent == 'codex' and scope == 'project'
                           else self.bundle_case._prepare(agent=agent, scope=scope)['plan_id'])
                for scenario in ('fresh','upgrade'):
                    for checkpoint in ('staged','backed_up','activated'):
                        with self.subTest(agent=agent, scope=scope, scenario=scenario, checkpoint=checkpoint):
                            outcome = rehearse_private_bundle(plan_id,agent,scope,
                                         plan_id,bundle_root=self.root,
                                         scenario=scenario,stop_after=checkpoint)
                            self.assertEqual(outcome['status'], 'fixture_bundle_rollback_verified')
                            self.assertEqual(outcome['file_count'], 2)
                            self.assertTrue(outcome['previous_files_restored'])
                            self.assertFalse(outcome['real_host_files_modified'])
                            self.assertFalse(outcome['production_installation_enabled'])
                            count += 1
        self.assertEqual(count,36)

    def test_preexisting_skill_conflict_has_no_overwrite(self):
        existing = self._prepare_old()
        with self.assertRaisesRegex(ValueError,'Existing Skill collision'):
            stage_bundle_fixture(self.fixture,self.root,self.pid,'codex','project',self.pid)
        self.assertTrue(_same_inventory(self._target(),existing))
        self.assertFalse((self.fixture/'.gasl-bundle-fixture-transaction.json').exists())

    def test_exact_plan_acknowledgement_required(self):
        with self.assertRaisesRegex(ValueError,'Exact plan acknowledgement'):
            stage_bundle_fixture(self.fixture,self.root,self.pid,'codex','project','f'*64)
        self.assertFalse((self.fixture/'stage').exists())

    def test_wrong_host_scope_plan_mismatch_refused_before_touching_files(self):
        for agent,scope in (('cursor','project'),('codex','user'),('claude-code','project')):
            with self.subTest(agent=agent,scope=scope), self.assertRaisesRegex(ValueError,'not bound to this Host'):
                stage_bundle_fixture(self.fixture,self.root,self.pid,agent,scope,self.pid)
        self.assertFalse((self.fixture/'stage').exists())

    def test_wrong_plan_id_and_unsupported_desktop_are_rejected(self):
        with self.assertRaises((ValueError,FileNotFoundError)):
            stage_bundle_fixture(self.fixture,self.root,'0'*64,'codex','project','0'*64)
        with self.assertRaisesRegex(ValueError,'Only documented filesystem'):
            stage_bundle_fixture(self.fixture,self.root,self.pid,'claude-desktop','project',self.pid)
        self.assertFalse((self.fixture/'stage').exists())

    def test_repeated_unfinished_transaction_rejected(self):
        stage_bundle_fixture(self.fixture,self.root,self.pid,'codex','project',self.pid)
        with self.assertRaisesRegex(ValueError,'Existing fixture transaction'):
            stage_bundle_fixture(self.fixture,self.root,self.pid,'codex','project',self.pid)
        rollback_bundle_fixture(self.fixture)

    def test_modified_activated_content_is_preserved_instead_of_overwritten(self):
        old = self._prepare_old()
        stage_bundle_fixture(self.fixture,self.root,self.pid,'codex','project',self.pid,replace_existing=True)
        activate_bundle_fixture(self.fixture)
        (self._target()/'SKILL.md').write_text('USER_EDITED_AFTER_INSTALL\n')
        with self.assertRaisesRegex(ValueError,'Activated files modified'):
            rollback_bundle_fixture(self.fixture)
        self.assertEqual((self._target()/'SKILL.md').read_text(),'USER_EDITED_AFTER_INSTALL\n')
        backup_root = self.fixture/'backup'
        self.assertEqual(len(list(backup_root.iterdir())),1)
        self.assertTrue(_same_inventory(next(backup_root.iterdir()),old))

    def test_user_added_empty_directory_is_preserved_instead_of_removed(self):
        self._prepare_old()
        stage_bundle_fixture(self.fixture,self.root,self.pid,'codex','project',self.pid,replace_existing=True)
        activate_bundle_fixture(self.fixture)
        extra = self._target()/'user-created-empty-directory'
        extra.mkdir()
        with self.assertRaisesRegex(ValueError,'Activated files modified'):
            rollback_bundle_fixture(self.fixture)
        self.assertTrue(extra.is_dir())
        self.assertTrue(any((self.fixture/'backup').iterdir()))

    def test_modified_backup_refuses_to_remove_activated_content(self):
        self._prepare_old()
        stage_bundle_fixture(self.fixture,self.root,self.pid,'codex','project',self.pid,replace_existing=True)
        activate_bundle_fixture(self.fixture)
        prior = next((self.fixture/'backup').iterdir())
        (prior/'user-note.txt').write_text('USER_CHANGED_BACKUP')
        with self.assertRaisesRegex(ValueError,'Backup modified'):
            rollback_bundle_fixture(self.fixture)
        self.assertEqual((self._target()/'SKILL.md').read_bytes(),
                         self.bundle_case.content['skills/demo/SKILL.md'])

    def test_symlinked_target_rejected_and_sentinel_untouched(self):
        sentinel = self.fixture/'outside-sentinel.txt'
        sentinel.write_text('NOT_A_TARGET')
        target = self._target()
        target.parent.mkdir(parents=True)
        target.symlink_to(sentinel)
        with self.assertRaisesRegex(ValueError,'Symlink'):
            stage_bundle_fixture(self.fixture,self.root,self.pid,'codex','project',self.pid,replace_existing=True)
        self.assertEqual(sentinel.read_text(),'NOT_A_TARGET')

    def test_corrupted_zip_not_materialized_even_if_sidecar_still_present(self):
        archive = self.root/'private/install-bundles'/f'{self.pid}.zip'
        archive.write_bytes(archive.read_bytes()+b'APPENDED')
        with self.assertRaisesRegex(ValueError,'ZIP digest'):
            stage_bundle_fixture(self.fixture,self.root,self.pid,'codex','project',self.pid)
        self.assertFalse((self.fixture/'stage').exists())

    def test_zip_main_skill_git_blob_mismatch_fail_closed(self):
        sidecar = self.root/'private/install-bundles'/f'{self.pid}.json'
        record=json.loads(sidecar.read_text())
        record['pinned_skill_md_blob_sha']='0'*40
        sidecar.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError,'main Skill Blob'):
            stage_bundle_fixture(self.fixture,self.root,self.pid,'codex','project',self.pid)

    def test_source_zip_symlink_entry_is_rejected_even_with_matching_sha(self):
        archive_path=self.root/'private/install-bundles'/f'{self.pid}.zip'
        sidecar_path=self.root/'private/install-bundles'/f'{self.pid}.json'
        sidecar=json.loads(sidecar_path.read_text())
        payload=[]
        with zipfile.ZipFile(archive_path) as source:
            for info in source.infolist():
                data=source.read(info.filename)
                if info.filename=='demo/references/about.md':
                    info.external_attr=(0o120777<<16)
                payload.append((info,data))
        with zipfile.ZipFile(archive_path,'w') as output:
            for info,data in payload:
                output.writestr(info,data)
        sidecar['archive_sha256']=hashlib.sha256(archive_path.read_bytes()).hexdigest()
        sidecar_path.write_text(json.dumps(sidecar))
        with self.assertRaisesRegex(ValueError,'ZIP contains link'):
            stage_bundle_fixture(self.fixture,self.root,self.pid,'codex','project',self.pid)
        self.assertFalse((self.fixture/'stage').exists())

    def test_zip_path_traversal_entry_rejected(self):
        archive_path=self.root/'private/install-bundles'/f'{self.pid}.zip'
        sidecar_path=self.root/'private/install-bundles'/f'{self.pid}.json'
        sidecar=json.loads(sidecar_path.read_text())
        rows=[]
        with zipfile.ZipFile(archive_path) as zf:
            for info in zf.infolist():
                data=zf.read(info.filename)
                if info.filename=='demo/references/about.md':
                    info.filename='demo/../../escape.txt'
                rows.append((info,data))
        with zipfile.ZipFile(archive_path,'w') as output:
            for info,data in rows:output.writestr(info,data)
        sidecar['archive_sha256']=hashlib.sha256(archive_path.read_bytes()).hexdigest()
        sidecar['entries'][1]['archive_path']='demo/../../escape.txt'
        sidecar_path.write_text(json.dumps(sidecar))
        with self.assertRaises(ValueError):
            stage_bundle_fixture(self.fixture,self.root,self.pid,'codex','project',self.pid)
        self.assertFalse((self.fixture/'escape.txt').exists())

    def test_conflict_scenario_preserves_dummy_previous_version(self):
        result=rehearse_private_bundle(self.pid,'codex','project',self.pid,
                                     bundle_root=self.root,scenario='conflict')
        self.assertEqual(result['status'],'existing_fixture_skill_preserved')
        self.assertTrue(result['original_files_unchanged'])

    def test_nonfixture_directory_refused(self):
        with tempfile.TemporaryDirectory(prefix='outside-gasl-') as scratch:
            with self.assertRaises(ValueError):
                stage_bundle_fixture(Path(scratch),self.root,self.pid,'codex','project',self.pid)

    def test_empty_target_cannot_be_upgraded(self):
        self._target().mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'Empty existing fixture target'):
            stage_bundle_fixture(self.fixture,self.root,self.pid,'codex','project',self.pid,replace_existing=True)
        self.assertFalse((self.fixture/'stage').exists())


if __name__ == '__main__':
    unittest.main()
