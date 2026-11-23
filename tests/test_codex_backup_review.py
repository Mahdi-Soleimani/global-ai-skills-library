"""Phase 45: one read-only UX for all Codex project Backup lifecycle states."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import codex_project_install as installer
import codex_uninstalled_restore as archived
import codex_legacy_reconcile as legacy
from codex_backup_review import review_codex_backups, format_backup_review
from tests import test_codex_project_install as fixtures


class UnifiedBackupReviewTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.ProjectInstallTests('test_genuine_install_and_uninstall_in_temporary_project')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root = self.case.project
        self.target = self.case.target()
        self.state = self.case.state()
        self.slug = 'demo'

    def review(self, backup_id=None):
        return review_codex_backups(self.slug, self.root, backup_id=backup_id)

    def owned(self):
        self.case.matching_install()
        return installer.uninstall('demo', self.root,
                                   reader=lambda _: installer._remove_phrase('demo', self.case.plan_id))

    def installed_with_unmanaged_backup(self):
        self.case.existing_skill()
        return self.case.replace()

    def orphan(self):
        replaced = self.installed_with_unmanaged_backup()
        receipt = installer._load(installer._receipt(self.state, 'demo'))
        installer._remove_verified_dir(self.target, receipt['files'])
        installer._receipt(self.state, 'demo').unlink()
        return replaced['backup_id']

    def assert_readonly(self, report):
        self.assertFalse(report['real_host_files_modified'])
        self.assertFalse(report['third_party_skill_executed'])
        self.assertFalse(report['approval_granted'])
        self.assertNotIn(str(self.root), json.dumps(report))
        self.assertNotIn(str(self.root), format_backup_review(report))

    def test_empty_project_no_backups_and_no_state_written(self):
        report=self.review()
        self.assertEqual(report['lifecycle'],'no_backups')
        self.assertEqual(report['backup_count'],0)
        self.assertFalse(report['available_recovery'])
        self.assert_readonly(report)
        self.assertFalse(self.state.exists())

    def test_installed_skill_without_history_is_readonly_not_implicitly_restorable(self):
        self.case.matching_install()
        report=self.review()
        self.assertEqual(report['lifecycle'],'installed')
        self.assertEqual(report['backup_count'],0)
        self.assertEqual(report['ownership_evidence'],'local_managed_receipt')
        self.assertFalse(report['available_recovery'])
        self.assert_readonly(report)
        self.assertTrue(self.target.exists())

    def test_installed_skill_merged_readable_options_and_exact_next_step(self):
        result=self.installed_with_unmanaged_backup()
        report=self.review()
        self.assertEqual(report['lifecycle'],'installed')
        self.assertEqual(report['backup_count'],1)
        self.assertEqual(report['backups'][0]['backup_id'],result['backup_id'])
        self.assertEqual(report['backups'][0]['provenance'],'local_unmanaged_version')
        self.assertTrue(report['backups'][0]['eligible_for_recovery'])
        self.assertIn('backup-review',report['review_command_template'])
        self.assert_readonly(report)
        self.assertFalse(installer._journal(self.state,'demo').exists())

    def test_specific_installed_backup_prepares_binding_without_approval_or_writes(self):
        result=self.installed_with_unmanaged_backup()
        before=installer._receipt(self.state,'demo').read_bytes()
        report=self.review(result['backup_id'])
        self.assertEqual(report['selected']['backup_id'],result['backup_id'])
        self.assertEqual(len(report['selected']['state_binding_id']),64)
        self.assertIn('--action restore-backup',report['selected']['recovery_command'])
        self.assertIn('--state-binding-id '+report['selected']['state_binding_id'],
                      report['selected']['recovery_command'])
        self.assertIn('GASL_SELECTED_PROJECT',report['selected']['recovery_command'])
        self.assertTrue(report['selected']['requires_real_local_tty_confirmation'])
        self.assertFalse(report['approval_granted'])
        self.assertEqual(installer._receipt(self.state,'demo').read_bytes(),before)
        self.assert_readonly(report)

    def test_installed_pinned_reference_is_not_reverified_upstream_claim(self):
        self.case.matching_install()
        newer=self.case.make_next_bundle()
        replaced=self.case.replace(newer['plan_id'])
        report=self.review(replaced['backup_id'])
        self.assertEqual(report['backups'][0]['provenance'],'local_recorded_pinned_plan')
        self.assertEqual(report['backups'][0]['historical_plan_reference'],self.case.plan_id)
        self.assertIn('do not certify upstream safety',report['safety_notice'])
        self.assert_readonly(report)

    def test_uninstalled_with_marker_prepares_separate_reinstall_path(self):
        removed=self.owned()
        report=self.review(removed['archived_last_active_backup_id'])
        self.assertEqual(report['lifecycle'],'uninstalled_owned')
        self.assertEqual(report['backup_count'],1)
        self.assertEqual(report['ownership_evidence'],'local_project_bound_uninstall_marker')
        self.assertTrue(report['backups'][0]['last_active_before_uninstall'])
        self.assertIn('--action reinstall-backup',report['selected']['recovery_command'])
        self.assertFalse(report['manual_ownership_attestation_required'])
        self.assertFalse(self.target.exists())
        self.assert_readonly(report)

    def test_orphaned_backup_requires_manual_attestation_not_certified_ownership(self):
        backup_id=self.orphan()
        report=self.review(backup_id)
        self.assertEqual(report['lifecycle'],'uninstalled_legacy')
        self.assertEqual(report['ownership_evidence'],'no_historical_ownership_proof')
        self.assertEqual(report['backups'][0]['provenance'],'unmanaged_historical')
        self.assertTrue(report['manual_ownership_attestation_required'])
        self.assertIs(report['historical_project_ownership_verified'],False)
        self.assertIn('historical project ownership',report['safety_notice'])
        self.assertIn('--action reinstall-legacy-backup',report['selected']['recovery_command'])
        self.assertTrue(report['selected']['manual_ownership_attestation_required'])
        self.assertIn('UNKNOWN',format_backup_review(report))
        self.assert_readonly(report)

    def test_a_managed_historical_reference_does_not_certify_legacy_ownership(self):
        self.case.matching_install()
        next_bundle=self.case.make_next_bundle()
        replaced=self.case.replace(next_bundle['plan_id'])
        receipt=installer._load(installer._receipt(self.state,'demo'))
        installer._remove_verified_dir(self.target,receipt['files'])
        installer._receipt(self.state,'demo').unlink()
        report=self.review(replaced['backup_id'])
        self.assertEqual(report['backups'][0]['provenance'],
                         'unverified_historical_receipt_reference')
        self.assertEqual(report['backups'][0]['historical_plan_reference'],self.case.plan_id)
        self.assertFalse(report['historical_project_ownership_verified'])
        self.assertIn('not freshly verified',format_backup_review(report))
        self.assert_readonly(report)

    def test_legacy_manually_attested_then_managed_preserves_historical_warning(self):
        backup=self.orphan()
        p=legacy.preview_legacy_reinstall('demo',self.root,backup)
        phrase=legacy._phrase('demo',backup,p['state_binding_id'])
        legacy.reinstall_legacy_backup('demo',self.root,backup,
                                     p['state_binding_id'],reader=lambda _:phrase)
        report=self.review()
        self.assertEqual(report['lifecycle'],'installed')
        self.assertEqual(report['current_version']['source_kind'],'unmanaged')
        self.assertIs(report['current_version']['historical_project_ownership_verified'],False)
        self.assertIn('manually reconciled',report['safety_notice'])
        self.assert_readonly(report)

    def test_unknown_backup_id_refuses_before_preview(self):
        result=self.installed_with_unmanaged_backup()
        with self.assertRaisesRegex(ValueError,'not present'):
            self.review('0'*32)
        self.assertTrue(self.target.is_dir())
        self.assertFalse(installer._journal(self.state,'demo').exists())

    def test_same_as_active_backup_not_offered_for_noop_restore(self):
        self.case.existing_skill()
        first=self.case.replace()
        from codex_project_install import preview_restore, restore_backup, _restore_phrase
        p=preview_restore('demo',self.root,first['backup_id'])
        restore_backup('demo',self.root,first['backup_id'],
            p['state_binding_id'],reader=lambda _: _restore_phrase(
                'demo',first['backup_id'],p['current_plan_id'],p['state_binding_id']))
        report=self.review()
        old=next(x for x in report['backups'] if x['backup_id']==first['backup_id'])
        self.assertFalse(old['eligible_for_recovery'])
        with self.assertRaisesRegex(ValueError,'identical'):
            self.review(first['backup_id'])

    def test_pending_transaction_blocks_selection_and_does_not_execute_recovery(self):
        self.case.matching_install()
        path=installer._journal(self.state,'demo')
        path.write_text('NOT A VALID JOURNAL')
        report=self.review()
        self.assertEqual(report['lifecycle'],'pending_transaction')
        self.assertFalse(report['available_recovery'])
        self.assertIn('--action recover',report['next_steps'][0])
        self.assertFalse(report['approval_granted'])
        self.assertEqual(path.read_text(),'NOT A VALID JOURNAL')
        with self.assertRaisesRegex(ValueError,'No backup selection'):
            self.review('0'*32)
        self.assert_readonly(report)

    def test_unmanaged_occupied_target_reports_blocker_not_replacement(self):
        self.case.existing_skill()
        report=self.review()
        self.assertEqual(report['lifecycle'],'unmanaged_target')
        self.assertFalse(report['available_recovery'])
        self.assertEqual(report['backups'],[])
        self.assertFalse(report['approval_granted'])
        self.assert_readonly(report)

    def test_missing_target_with_receipt_reports_inconsistency(self):
        self.case.matching_install()
        self.target.rename(self.root/'moved-for-test')
        report=self.review()
        self.assertEqual(report['lifecycle'],'missing_target_with_receipt')
        self.assertFalse(report['available_recovery'])
        self.assert_readonly(report)

    def test_tampered_or_symlinked_marker_is_never_rebranded_as_legacy(self):
        removed=self.owned()
        path=archived._marker_path(self.state,'demo')
        original=path.read_text()
        other=Path(self.case.tmp.name)/'marker-original'
        path.rename(other)
        path.symlink_to(other)
        with self.assertRaisesRegex(ValueError,'Symlinked'):
            self.review()
        path.unlink()
        path.write_text(original.replace('uninstalled_codex_project_skill','FAKE'))
        with self.assertRaises(ValueError):
            self.review()
        self.assertFalse(self.target.exists())

    def test_tampered_backup_is_not_a_valid_presented_choice(self):
        result=self.installed_with_unmanaged_backup()
        backup=installer._backup_dir(self.state,'demo',result['backup_id'])
        (backup/'user-note.txt').write_text('ALTERED BY SOMEONE')
        with self.assertRaisesRegex(ValueError,'backup changed'):
            self.review()
        self.assertEqual((backup/'user-note.txt').read_text(),'ALTERED BY SOMEONE')

    def test_cli_text_and_json_have_same_lifecycle_and_no_path_leaks(self):
        removed=self.owned()
        args=[str(ROOT/'gasl'),'backup-review','--skill-name','demo',
              '--selected-root',str(self.root),'--backup-id',
              removed['archived_last_active_backup_id']]
        text_output=subprocess.run(args,capture_output=True,text=True,check=True).stdout
        json_output=subprocess.run(args+['--format','json'],
                                   capture_output=True,text=True,check=True).stdout
        parsed=json.loads(json_output)
        self.assertEqual(parsed['lifecycle'],'uninstalled_owned')
        self.assertIn('GASL / Codex Backup Review',text_output)
        self.assertIn('--action reinstall-backup',text_output)
        self.assertNotIn(str(self.root),text_output)
        self.assertNotIn(str(self.root),json_output)
        self.assertFalse(self.target.exists())

    def test_cli_noninteractive_review_cannot_approve_installation(self):
        removed=self.owned()
        args=[str(ROOT/'gasl'),'backup-review','--skill-name','demo',
              '--selected-root',str(self.root),'--backup-id',
              removed['archived_last_active_backup_id'],'--format','json']
        preview=json.loads(subprocess.run(args,capture_output=True,text=True,check=True).stdout)
        binding=preview['selected']['state_binding_id']
        denied=subprocess.run([str(ROOT/'gasl'),'codex-project-install',
            '--action','reinstall-backup','--selected-root',str(self.root),
            '--skill-name','demo','--backup-id',removed['archived_last_active_backup_id'],
            '--state-binding-id',binding],capture_output=True,text=True)
        self.assertNotEqual(denied.returncode,0)
        self.assertIn('local interactive TTY',denied.stderr)
        self.assertFalse(self.target.exists())

    def test_unsafe_project_selection_and_name_refused(self):
        with self.assertRaises(ValueError):
            review_codex_backups('demo',Path(self.case.tmp.name))
        with self.assertRaises(ValueError):
            review_codex_backups('../bad',self.root)

    def test_installed_after_previous_uninstall_verifies_marker_chain(self):
        removed=self.owned()
        selected=removed['archived_last_active_backup_id']
        p=archived.preview_reinstall('demo',self.root,selected)
        marker=archived._read_marker(self.root,'demo',self.state)
        phrase=archived._reinstall_phrase('demo',selected,marker['uninstall_event_id'],
                                          p['state_binding_id'])
        archived.reinstall_backup('demo',self.root,selected,p['state_binding_id'],
                                   reader=lambda _:phrase)
        report=self.review()
        self.assertEqual(report['lifecycle'],'installed')
        self.assertEqual(report['backup_count'],1)
        self.assert_readonly(report)
        path=archived._marker_path(self.state,'demo')
        altered=json.loads(path.read_text())
        altered['backup_ids']=['f'*32]
        path.write_text(json.dumps(altered))
        with self.assertRaises(ValueError):
            self.review()
        self.assertTrue(self.target.exists())

    def test_human_readable_review_explains_backup_effect_and_exports_placeholder(self):
        result=self.installed_with_unmanaged_backup()
        text=format_backup_review(self.review(result['backup_id']))
        self.assertIn('saves the active version to a new Backup',text)
        self.assertIn('export GASL_SELECTED_PROJECT=',text)
        self.assertIn('READ ONLY',text)
        self.assertIn('did NOT approve',text)
        self.assertIn('No Skill was installed, executed, modified or approved',text)
        self.assertNotIn(str(self.root),text)

    def test_legacy_review_does_not_treat_historical_reference_as_verified_pin(self):
        backup_id=self.orphan()
        report=self.review(backup_id)
        self.assertFalse(report['upstream_provenance_revalidated'])
        self.assertFalse(report['historical_project_ownership_verified'])
        self.assertIn('UNKNOWN',format_backup_review(report))
        self.assertIn('After human ownership attestation',report['recovery_effect'])

    def test_uninstalled_unsafe_target_symlink_is_rejected_without_following(self):
        removed=self.owned()
        outside=Path(self.case.tmp.name)/'outside'
        outside.mkdir()
        (outside/'SKILL.md').write_text('DO NOT READ THIS FILE')
        self.target.symlink_to(outside,target_is_directory=True)
        try:
            report=self.review()
            self.assertEqual(report['lifecycle'],'occupied_unsafe_target')
            self.assertFalse(report['available_recovery'])
        except ValueError:
            pass  # host path preflight is permitted to reject early
        self.assertEqual((outside/'SKILL.md').read_text(),'DO NOT READ THIS FILE')
