"""Phase 46: offline evidence comparison, only synthetic disposable Codex projects."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))

import codex_project_install as installer
import codex_uninstalled_restore as archived
import codex_legacy_reconcile as legacy
from codex_provenance_compare import compare_codex_provenance, format_provenance_comparison
from tests import test_codex_project_install as fixture_tests


class CodexProvenanceComparisonTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture_tests.ProjectInstallTests(
            'test_genuine_install_and_uninstall_in_temporary_project')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.project = self.case.project
        self.state = self.case.state()
        self.target = self.case.target()

    def summary(self, left=None, right=None):
        return compare_codex_provenance('demo', self.project, left_id=left, right_id=right)

    def before42_orphan(self, pinned=False):
        if pinned:
            self.case.matching_install()
            upgraded = self.case.make_next_bundle(b'---\nname: demo\ndescription: source v2\n---\n# Version two\n')
            result = self.case.replace(upgraded['plan_id'])
        else:
            self.case.existing_skill()
            result = self.case.replace()
        receipt = installer._load(installer._receipt(self.state, 'demo'))
        installer._remove_verified_dir(self.target, receipt['files'])
        installer._receipt(self.state, 'demo').unlink()
        return result['backup_id']

    def assert_safe(self, report):
        self.assertFalse(report['network_requests_performed'])
        self.assertFalse(report['installation_or_recovery_performed'])
        self.assertFalse(report['third_party_skill_executed'])
        self.assertFalse(report['real_host_files_modified'])
        self.assertFalse(report['approval_granted'])
        self.assertFalse(report['upstream_verification_performed'])
        self.assertNotIn(str(self.project), json.dumps(report))
        self.assertNotIn(str(self.project), format_provenance_comparison(report))
        for row in report['versions']:
            self.assertTrue(row['local_file_integrity_verified'])
            self.assertEqual(len(row['content_manifest_sha256']), 64)
            self.assertFalse(row['evidence']['historical_project_ownership_proven'])
            self.assertFalse(row['evidence']['upstream_authenticity_verified'])
            self.assertEqual(set(row['evidence']['upstream_checks'].values()), {'not_checked'})

    def test_empty_project_shows_no_version_and_no_state_files_written(self):
        report=self.summary()
        self.assertEqual(report['lifecycle'], 'no_backups')
        self.assertEqual(report['versions'], [])
        self.assertIsNone(report['comparison'])
        self.assertIn('blocked_reason', report)
        self.assertFalse(self.state.exists())
        self.assert_safe(report)

    def test_single_installed_version_local_receipt_without_upstream_claim(self):
        self.case.matching_install()
        report=self.summary()
        self.assertEqual(len(report['versions']), 1)
        active=report['versions'][0]
        self.assertEqual(active['role'],'active')
        self.assertEqual(active['recorded_plan_id'],self.case.plan_id)
        self.assertEqual(active['evidence']['source_plan_reference_evidence'],
                         'GASL_local_receipt_claim_only')
        self.assertEqual(active['evidence']['upstream_checks']['license_and_notices'],
                         'not_checked')
        self.assert_safe(report)

    def test_managed_pinned_backup_against_active_has_content_and_plan_difference(self):
        self.case.matching_install()
        next_bundle=self.case.make_next_bundle(
            b'---\nname: demo\ndescription: New inert Skill\n---\n# v2\n')
        replaced=self.case.replace(next_bundle['plan_id'])
        report=self.summary('active',replaced['backup_id'])
        self.assertEqual(len(report['versions']),2)
        self.assertEqual(report['versions'][1]['recorded_plan_id'],self.case.plan_id)
        self.assertFalse(report['comparison']['same_local_file_inventory'])
        self.assertFalse(report['comparison']['same_recorded_plan_reference'])
        self.assertGreaterEqual(report['comparison']['files_changed'],1)
        self.assertFalse(report['comparison']['proves_same_upstream_source'])
        self.assert_safe(report)

    def test_original_unmanaged_backup_has_no_previous_receipt(self):
        self.case.existing_skill()
        installed=self.case.replace()
        result=self.summary('active',installed['backup_id'])
        backup=result['versions'][1]
        self.assertIsNone(backup['recorded_plan_id'])
        self.assertEqual(backup['evidence']['source_plan_reference_evidence'],
                         'no_previous_GASL_receipt')
        self.assertEqual(backup['recorded_source_kind'],'unmanaged')
        self.assert_safe(result)

    def test_identical_contents_are_not_proof_of_same_upstream(self):
        self.case.matching_install()
        next_bundle=self.case.make_next_bundle(b'---\nname: demo\ndescription: version 2\n---\n# v2\n')
        changed=self.case.replace(next_bundle['plan_id'])
        p=installer.preview_restore('demo',self.project,changed['backup_id'])
        phrase=installer._restore_phrase('demo',changed['backup_id'],
            p['current_plan_id'],p['state_binding_id'])
        installer.restore_backup('demo',self.project,changed['backup_id'],
                                 p['state_binding_id'],reader=lambda _:phrase)
        result=self.summary('active',changed['backup_id'])
        self.assertTrue(result['comparison']['same_local_file_inventory'])
        self.assertFalse(result['comparison']['proves_same_upstream_source'])
        self.assertFalse(result['comparison']['proves_safe_or_trusted_content'])
        self.assert_safe(result)

    def test_backup_to_backup_comparison_shows_changed_counts_without_filenames(self):
        self.case.matching_install()
        b2=self.case.make_next_bundle(b'---\nname: demo\ndescription: inert v2\n---\n# v2\n')
        first=self.case.replace(b2['plan_id'])
        b3=self.case.make_next_bundle(b'---\nname: demo\ndescription: inert v3\n---\n# v3\n')
        second=self.case.replace(b3['plan_id'])
        result=self.summary(first['backup_id'],second['backup_id'])
        self.assertEqual(len(result['versions']),3)
        self.assertFalse(result['comparison']['same_local_file_inventory'])
        self.assertGreater(result['comparison']['files_changed'],0)
        self.assertNotIn('SKILL.md',json.dumps(result['comparison']))
        self.assert_safe(result)

    def test_uninstalled_with_marker_has_local_project_bound_evidence_only(self):
        self.case.matching_install()
        removed=installer.uninstall('demo',self.project,reader=lambda _:
            installer._remove_phrase('demo',self.case.plan_id))
        result=self.summary()
        self.assertEqual(result['lifecycle'],'uninstalled_owned')
        self.assertEqual(len(result['versions']),1)
        item=result['versions'][0]
        self.assertIn('project_bound',item['evidence']['local_ownership_evidence'])
        self.assertFalse(item['evidence']['historical_project_ownership_proven'])
        self.assertFalse(item['evidence']['upstream_authenticity_verified'])
        self.assert_safe(result)

    def test_legacy_historical_pinned_receipt_must_be_unverified(self):
        ident=self.before42_orphan(pinned=True)
        result=self.summary()
        self.assertEqual(result['lifecycle'],'uninstalled_legacy')
        self.assertIs(result['historical_project_ownership_verified'],False)
        self.assertEqual(result['versions'][0]['recorded_plan_id'],self.case.plan_id)
        self.assertTrue(result['versions'][0]['historical_upstream_reference_only'])
        self.assertEqual(result['versions'][0]['evidence']['source_plan_reference_evidence'],
                         'historical_receipt_reference_only')
        self.assertIn('ownership_unproven',
                      result['versions'][0]['evidence']['local_ownership_evidence'])
        self.assert_safe(result)

    def test_manually_reconciled_installed_skill_preserves_warning(self):
        ident=self.before42_orphan()
        p=legacy.preview_legacy_reinstall('demo',self.project,ident)
        legacy.reinstall_legacy_backup('demo',self.project,ident,p['state_binding_id'],
            reader=lambda _: legacy._phrase('demo',ident,p['state_binding_id']))
        result=self.summary()
        active=result['versions'][0]
        self.assertIn('manual_attestation',active['evidence']['local_ownership_evidence'])
        self.assertIs(result['historical_project_ownership_verified'],False)
        self.assert_safe(result)

    def test_bad_or_partial_version_pair_is_refused(self):
        self.case.matching_install()
        with self.assertRaisesRegex(ValueError,'Select both'):
            self.summary('active')
        with self.assertRaisesRegex(ValueError,'two distinct'):
            self.summary('active','active')
        with self.assertRaisesRegex(ValueError,'must exist'):
            self.summary('active','e'*32)
        self.assertTrue(self.target.exists())

    def test_legacy_version_cannot_claim_nonexistent_active(self):
        ident=self.before42_orphan()
        with self.assertRaisesRegex(ValueError,'must exist'):
            self.summary('active',ident)

    def test_corrupt_backup_manifest_or_archive_fails_closed(self):
        self.case.existing_skill()
        added=self.case.replace()
        file=installer._backup_dir(self.state,'demo',added['backup_id'])/'user-note.txt'
        file.write_text('TAMPERED')
        with self.assertRaises(ValueError):
            self.summary()
        self.assertEqual(file.read_text(),'TAMPERED')

    def test_pending_transaction_returns_blocked_status_and_no_file_changes(self):
        self.case.matching_install()
        journal=installer._journal(self.state,'demo')
        journal.write_text('PENDING')
        result=self.summary()
        self.assertEqual(result['lifecycle'],'pending_transaction')
        self.assertEqual(result['versions'],[])
        self.assertEqual(journal.read_text(),'PENDING')
        with self.assertRaisesRegex(ValueError,'blocked'):
            self.summary('active','f'*32)
        self.assert_safe(result)

    def test_no_network_or_subprocess_called_for_review(self):
        self.case.matching_install()
        with patch('urllib.request.urlopen',side_effect=AssertionError('NETWORK')):
            with patch('subprocess.run',side_effect=AssertionError('SUBPROCESS')):
                result=self.summary()
        self.assert_safe(result)

    def test_cli_default_text_and_json_comparison_are_consistent_and_private(self):
        self.case.matching_install()
        b2=self.case.make_next_bundle(b'---\nname: demo\ndescription: v2\n---\n# version2\n')
        changed=self.case.replace(b2['plan_id'])
        command=[str(ROOT/'gasl'),'provenance-compare','--selected-root',str(self.project),
                 '--skill-name','demo','--left','active','--right',changed['backup_id']]
        human=subprocess.run(command,capture_output=True,text=True,check=True).stdout
        raw=subprocess.run(command+['--format','json'],capture_output=True,text=True,check=True).stdout
        value=json.loads(raw)
        self.assertEqual(value['comparison']['left_version_id'],'active')
        self.assertIn('Comparing active vs',human)
        self.assertIn('NOT PERFORMED',human)
        self.assertNotIn(str(self.project),raw+human)
        self.assert_safe(value)

    def test_no_unapproved_install_generated_by_evidence_report(self):
        self.case.matching_install()
        report=self.summary()
        self.assertNotIn('recovery_command',json.dumps(report))
        self.assertFalse(report['approval_granted'])
        self.assertNotIn('state_binding_id',json.dumps(report))
        self.assertTrue(self.target.exists())

    def test_unmanaged_backup_marks_history_before_gasl_management(self):
        self.case.existing_skill()
        receipt=self.case.replace()
        row=self.summary()['versions'][1]
        self.assertEqual(row['evidence']['local_ownership_evidence'],
                         'historical_version_precedes_GASL_management')
        self.assertEqual(row['evidence']['local_owner_proof_type'],
                         'local_backup_inventory_only')
        self.assertFalse(row['evidence']['historical_project_ownership_proven'])

    def test_manual_attestation_warning_survives_archival_and_reinstallation(self):
        ident=self.before42_orphan()
        preview=legacy.preview_legacy_reinstall('demo',self.project,ident)
        legacy.reinstall_legacy_backup('demo',self.project,ident,
            preview['state_binding_id'],
            reader=lambda _:legacy._phrase('demo',ident,preview['state_binding_id']))
        current=installer._load(installer._receipt(self.state,'demo'))
        deleted=installer.uninstall('demo',self.project,reader=lambda _:
            installer._remove_phrase('demo',current['plan_id']))
        archived_report=self.summary()
        prior=next(v for v in archived_report['versions']
                   if v['version_id']==deleted['archived_last_active_backup_id'])
        self.assertIn('manual_attestation',prior['evidence']['local_ownership_evidence'])
        self.assertFalse(prior['evidence']['historical_project_ownership_proven'])
        selected=deleted['archived_last_active_backup_id']
        p=archived.preview_reinstall('demo',self.project,selected)
        marker=archived._read_marker(self.project,'demo',self.state)
        archived.reinstall_backup('demo',self.project,selected,p['state_binding_id'],
            reader=lambda _:archived._reinstall_phrase('demo',selected,
                marker['uninstall_event_id'],p['state_binding_id']))
        again=self.summary()
        self.assertIn('manual_attestation',
                      again['versions'][0]['evidence']['local_ownership_evidence'])

    def test_modified_active_skill_is_refused_without_mutation(self):
        self.case.matching_install()
        path=self.target/'SKILL.md'
        path.write_text('MANUAL EDIT')
        with self.assertRaisesRegex(ValueError,'changed'):
            self.summary()
        self.assertEqual(path.read_text(),'MANUAL EDIT')

    def test_project_guard_and_invalid_skill_name(self):
        with self.assertRaises(ValueError):
            compare_codex_provenance('demo',Path(self.case.tmp.name))
        with self.assertRaises(ValueError):
            compare_codex_provenance('../demo',self.project)
