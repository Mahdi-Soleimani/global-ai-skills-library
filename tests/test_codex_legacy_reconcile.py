"""Phase 44: inert, disposable projects for attested legacy backup recovery."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import codex_project_install as installer
import codex_legacy_reconcile as legacy
import codex_uninstalled_restore as archived
from tests import test_codex_project_install as existing


class LegacyReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.case = existing.ProjectInstallTests(
            'test_genuine_install_and_uninstall_in_temporary_project')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root = self.case.project
        self.slug = 'demo'
        self.target = self.case.target()
        self.state = self.case.state()

    def orphan(self, *, managed=False, chain=1):
        """Emulate a *pre-43* uninstall: receipt/target deleted, backups remain."""
        if managed:
            self.case.matching_install()
        else:
            self.case.existing_skill()
        self.case.replace() if not managed else self.case.replace(
            self.case.make_next_bundle(b'# Inert prior historical source\n')['plan_id'])
        if chain == 2:
            latest = self.case.make_next_bundle(b'# Historical source version 3\n')
            self.case.replace(latest['plan_id'])
        prior = installer._load(installer._receipt(self.state, self.slug))
        ids = prior['backup_ids']
        installer._remove_verified_dir(self.target, prior['files'])
        installer._receipt(self.state, self.slug).unlink()
        self.assertFalse(self.target.exists())
        self.assertFalse(archived._marker_path(self.state,self.slug).exists())
        self.assertEqual(len(ids),chain)
        return ids

    def reinstate(self, selected, *, reader=None, binding=None):
        plan = legacy.preview_legacy_reinstall(self.slug, self.root, selected)
        expected = legacy._phrase(self.slug, selected, plan['state_binding_id'])
        return legacy.reinstall_legacy_backup(
            self.slug, self.root, selected,
            binding if binding is not None else plan['state_binding_id'],
            reader=(lambda _: expected) if reader is None else reader)

    def test_audit_legacy_orphan_is_read_only_and_never_proves_ownership(self):
        ids = self.orphan()
        report = legacy.audit_legacy_backups(self.slug,self.root)
        self.assertEqual(report['backup_count'],1)
        self.assertEqual(report['backups'][0]['backup_id'],ids[0])
        self.assertFalse(report['historical_project_ownership_verified'])
        self.assertTrue(report['manual_ownership_attestation_required'])
        self.assertNotIn(str(self.root),json.dumps(report))
        p=legacy.preview_legacy_reinstall(self.slug,self.root,ids[0])
        self.assertFalse(p['historical_project_ownership_verified'])
        self.assertTrue(p['will_not_claim_upstream_pin'])
        self.assertTrue(p['requires_local_tty_confirmation'])
        self.assertFalse(p['reinstall_performed'])
        self.assertFalse(installer._journal(self.state,self.slug).exists())
        self.assertFalse(installer._receipt(self.state,self.slug).exists())

    def test_attested_reinstall_recovers_unmanaged_original_notes_and_retains_backup(self):
        ids = self.orphan()
        original = (installer._backup_dir(self.state,'demo',ids[0])/'SKILL.md').read_bytes()
        result=self.reinstate(ids[0])
        self.assertEqual(result['status'],'legacy_skill_reinstalled_with_manual_ownership_attestation')
        self.assertFalse(result['historical_project_ownership_verified'])
        self.assertTrue(result['manual_ownership_attested'])
        self.assertEqual((self.target/'SKILL.md').read_bytes(),original)
        self.assertEqual((self.target/'user-note.txt').read_text(),'KEEP THIS ORIGINAL FILE\n')
        self.assertEqual((installer._backup_dir(self.state,'demo',ids[0])/'SKILL.md').read_bytes(),original)
        receipt=installer._load(installer._receipt(self.state,'demo'))
        self.assertEqual(receipt['action'],'legacy_reconcile_install')
        self.assertEqual(receipt['source_kind'],'unmanaged')
        self.assertTrue(receipt['legacy_identity_derived'])
        self.assertFalse(receipt['historical_project_ownership_verified'])
        self.assertEqual(receipt['backup_ids'],ids)
        self.assertEqual(receipt['legacy_selected_backup_id'],ids[0])
        self.assertFalse(installer._journal(self.state,self.slug).exists())

    def test_complete_multi_backup_chain_can_be_reinstalled_from_older_version(self):
        ids=self.orphan(chain=2)
        report=legacy.audit_legacy_backups(self.slug,self.root)
        self.assertEqual([x['backup_id'] for x in report['backups']],ids)
        self.assertTrue(report['ancestry_complete'])
        result=self.reinstate(ids[0])
        self.assertTrue((self.target/'user-note.txt').is_file())
        self.assertEqual(installer._load(
            installer._receipt(self.state,'demo'))['backup_ids'],ids)
        self.assertTrue(installer._backup_dir(self.state,'demo',ids[1]).is_dir())

    def test_historical_managed_receipt_is_informational_not_recertified(self):
        ids=self.orphan(managed=True)
        audit=legacy.audit_legacy_backups(self.slug,self.root)
        self.assertEqual(audit['backups'][0]['upstream_plan_id_in_historical_receipt'],
                         self.case.plan_id)
        result=self.reinstate(ids[0])
        self.assertEqual(result['status'],'legacy_skill_reinstalled_with_manual_ownership_attestation')
        receipt=installer._load(installer._receipt(self.state,'demo'))
        self.assertNotEqual(receipt['plan_id'],self.case.plan_id)
        self.assertEqual(receipt['source_kind'],'unmanaged')
        self.assertFalse(receipt['historical_project_ownership_verified'])

    def test_subsequent_real_uninstall_creates_phase43_marker_and_preserves_legacy_history(self):
        ids=self.orphan()
        self.reinstate(ids[0])
        receipt=installer._load(installer._receipt(self.state,'demo'))
        removed=installer.uninstall('demo',self.root,reader=lambda _:
            installer._remove_phrase('demo',receipt['plan_id']))
        self.assertTrue(removed['uninstall_ownership_marker_recorded'])
        self.assertEqual(removed['retained_backup_ids'][:1],ids)
        self.assertEqual(len(removed['retained_backup_ids']),2)
        marker=archived._read_marker(self.root,'demo',self.state)
        self.assertEqual(marker['last_receipt'],receipt)
        self.assertFalse(self.target.exists())
        selected=removed['archived_last_active_backup_id']
        p=archived.preview_reinstall('demo',self.root,selected)
        phrase=archived._reinstall_phrase(
            'demo',selected,marker['uninstall_event_id'],p['state_binding_id'])
        result=archived.reinstall_backup(
            'demo',self.root,selected,p['state_binding_id'],reader=lambda _:phrase)
        self.assertTrue(result['reinstall_performed'])
        self.assertTrue(self.target.is_dir())

    def test_approval_required_and_noninteractive_cli_refused(self):
        ids=self.orphan()
        with self.assertRaisesRegex(ValueError,'approval'):
            self.reinstate(ids[0],reader=lambda _: 'NO')
        commands=[str(ROOT/'gasl'),'codex-project-install',
                  '--selected-root',str(self.root),'--skill-name','demo']
        audit=subprocess.run(commands+['--action','audit-legacy-backups'],
                             text=True,capture_output=True,check=True)
        self.assertEqual(json.loads(audit.stdout)['backup_count'],1)
        result=subprocess.run(commands+[
            '--action','preview-legacy-reinstall','--backup-id',ids[0]],
            text=True,capture_output=True,check=True)
        p=json.loads(result.stdout)
        self.assertNotIn(str(self.root),result.stdout)
        denied=subprocess.run(commands+[
            '--action','reinstall-legacy-backup','--backup-id',ids[0],
            '--state-binding-id',p['state_binding_id']],
            text=True,capture_output=True)
        self.assertNotEqual(denied.returncode,0)
        self.assertIn('local interactive TTY',denied.stderr)
        self.assertFalse(self.target.exists())

    def test_malformed_unknown_backup_and_missing_history_refused(self):
        ids=self.orphan(chain=2)
        with self.assertRaisesRegex(ValueError,'32-hex'):
            legacy.preview_legacy_reinstall(self.slug,self.root,'../outside')
        with self.assertRaisesRegex(ValueError,'not in verified'):
            legacy.preview_legacy_reinstall(self.slug,self.root,'f'*32)
        installer._backup_manifest(self.state,'demo',ids[0]).unlink()
        with self.assertRaisesRegex(ValueError,'Unpaired'):
            legacy.audit_legacy_backups(self.slug,self.root)
        self.assertFalse(self.target.exists())

    def test_foreign_or_disjoint_ancestry_rejected(self):
        ids=self.orphan(chain=2)
        path=installer._backup_manifest(self.state,'demo',ids[1])
        info=json.loads(path.read_text())
        info['previous_receipt']['backup_ids']=[]
        path.write_text(json.dumps(info))
        with self.assertRaises(ValueError):
            legacy.audit_legacy_backups(self.slug,self.root)

    def test_symlink_modified_backup_and_unexpected_archive_entry_rejected(self):
        ids=self.orphan()
        backup=installer._backup_dir(self.state,'demo',ids[0])
        note=backup/'user-note.txt'
        note.write_text('CHANGED')
        with self.assertRaisesRegex(ValueError,'Changed legacy backup'):
            legacy.audit_legacy_backups(self.slug,self.root)
        note.write_text('KEEP THIS ORIGINAL FILE\n')
        malicious=self.state/'backups/demo/extra.txt'
        malicious.write_text('Do not follow')
        with self.assertRaisesRegex(ValueError,'Unexpected entry'):
            legacy.audit_legacy_backups(self.slug,self.root)
        malicious.unlink()
        outside=Path(self.case.tmp.name)/'unrelated.txt'
        outside.write_text('DO NOT TOUCH')
        note.unlink()
        note.symlink_to(outside)
        with self.assertRaises(ValueError):
            legacy.audit_legacy_backups(self.slug,self.root)
        self.assertEqual(outside.read_text(),'DO NOT TOUCH')

    def test_existing_target_receipt_journal_or_marker_blocks_claim(self):
        ids=self.orphan()
        self.target.mkdir(parents=True)
        (self.target/'SKILL.md').write_text('USER OWNED')
        with self.assertRaisesRegex(ValueError,'empty Skill destination'):
            legacy.audit_legacy_backups(self.slug,self.root)
        self.assertEqual((self.target/'SKILL.md').read_text(),'USER OWNED')
        (self.target/'SKILL.md').unlink()
        self.target.rmdir()
        receipt=installer._receipt(self.state,'demo')
        receipt.write_text('unknown')
        with self.assertRaisesRegex(ValueError,'Existing receipt'):
            legacy.audit_legacy_backups(self.slug,self.root)
        receipt.unlink()
        marker=archived._marker_path(self.state,'demo')
        marker.write_text('old marker')
        with self.assertRaisesRegex(ValueError,'Existing receipt'):
            legacy.audit_legacy_backups(self.slug,self.root)
        marker.unlink()
        journal=installer._journal(self.state,'demo')
        journal.write_text('active other operation')
        with self.assertRaisesRegex(ValueError,'Existing receipt'):
            legacy.audit_legacy_backups(self.slug,self.root)

    def test_stale_preflight_binding_rejected_without_writes(self):
        ids=self.orphan()
        preview=legacy.preview_legacy_reinstall(self.slug,self.root,ids[0])
        prior=installer._backup_manifest(self.state,'demo',ids[0])
        info=json.loads(prior.read_text())
        info['reviewer_note']='added later'
        prior.write_text(json.dumps(info))
        with self.assertRaisesRegex(ValueError,'since preview'):
            legacy.reinstall_legacy_backup(
                self.slug,self.root,ids[0],preview['state_binding_id'],reader=lambda _: '')
        self.assertFalse(self.target.exists())

    def test_crash_after_journal_before_activation_rolls_back_stage(self):
        ids=self.orphan()
        old=legacy._new
        def error(path,data):
            old(path,data)
            if data.get('operation')=='legacy_reinstall':
                raise OSError('injected crash after journal')
        with patch.object(legacy,'_new',side_effect=error):
            with self.assertRaisesRegex(OSError,'crash after journal'):
                self.reinstate(ids[0])
        recovered=installer.recover('demo',self.root)
        self.assertEqual(recovered['status'],'interrupted_legacy_reinstall_rolled_back')
        self.assertFalse(self.target.exists())
        self.assertFalse(installer._journal(self.state,'demo').exists())

    def test_crash_after_activated_before_receipt_restores_absent_target(self):
        ids=self.orphan()
        old=legacy._new
        def error(path,data):
            if path.resolve()==installer._receipt(self.state,'demo').resolve():
                raise OSError('injected legacy receipt failure')
            return old(path,data)
        with patch.object(legacy,'_new',side_effect=error):
            with self.assertRaisesRegex(OSError,'legacy receipt failure'):
                self.reinstate(ids[0])
        self.assertTrue(self.target.exists())
        recovered=installer.recover('demo',self.root)
        self.assertEqual(recovered['status'],'interrupted_legacy_reinstall_rolled_back')
        self.assertFalse(self.target.exists())
        self.assertTrue(installer._backup_dir(self.state,'demo',ids[0]).exists())

    def test_committed_receipt_crash_is_finalized_not_rolled_back(self):
        ids=self.orphan()
        old=legacy._new
        def error(path,data):
            old(path,data)
            if path.resolve()==installer._receipt(self.state,'demo').resolve():
                raise OSError('crash after commit')
        with patch.object(legacy,'_new',side_effect=error):
            with self.assertRaisesRegex(OSError,'crash after commit'):
                self.reinstate(ids[0])
        result=installer.recover('demo',self.root)
        self.assertEqual(result['status'],'legacy_reinstall_commit_recovered')
        self.assertTrue(self.target.exists())
        self.assertFalse(installer._journal(self.state,'demo').exists())

    def test_modified_target_during_recovery_is_preserved(self):
        ids=self.orphan()
        with patch.object(legacy,'_new',side_effect=lambda path,data:
                          (_ for _ in ()).throw(OSError('inject'))
                          if path.resolve()==installer._receipt(self.state,'demo').resolve()
                          else installer._new(path,data)):
            with self.assertRaises(OSError):
                self.reinstate(ids[0])
        (self.target/'user-edit.txt').write_text('KEEP THIS EDIT')
        with self.assertRaisesRegex(ValueError,'preserve user edits'):
            installer.recover('demo',self.root)
        self.assertEqual((self.target/'user-edit.txt').read_text(),'KEEP THIS EDIT')
        self.assertTrue(installer._journal(self.state,'demo').exists())

    def test_missing_project_or_bad_skill_slug_is_refused(self):
        ids=self.orphan()
        with self.assertRaises(ValueError):
            legacy.audit_legacy_backups('../bad',self.root)
        with self.assertRaises(ValueError):
            legacy.audit_legacy_backups('demo',Path(self.case.tmp.name))

    def test_static_frontmatter_must_name_exact_selected_skill(self):
        ids=self.orphan()
        backup=installer._backup_dir(self.state,'demo',ids[0])
        changed=b'---\nname: wrong-skill\ndescription: inert\n---\n# Not demo\n'
        (backup/'SKILL.md').write_bytes(changed)
        manifest_path=installer._backup_manifest(self.state,'demo',ids[0])
        info=json.loads(manifest_path.read_text())
        import hashlib
        for item in info['files']:
            if item['path']=='SKILL.md':
                item['sha256']=hashlib.sha256(changed).hexdigest()
        manifest_path.write_text(json.dumps(info))
        with self.assertRaisesRegex(ValueError,'name does not match'):
            legacy.audit_legacy_backups(self.slug,self.root)
        self.assertFalse(self.target.exists())

    def test_changed_historical_manifest_during_interrupted_install_blocks_recovery(self):
        ids=self.orphan()
        old=legacy._new
        def fail(path,data):
            if path.resolve()==installer._receipt(self.state,'demo').resolve():
                raise OSError('injected crash')
            return old(path,data)
        with patch.object(legacy,'_new',side_effect=fail):
            with self.assertRaises(OSError):
                self.reinstate(ids[0])
        manifest_path=installer._backup_manifest(self.state,'demo',ids[0])
        value=json.loads(manifest_path.read_text())
        value['late_note']='changed during pending transaction'
        manifest_path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'manifests changed'):
            installer.recover('demo',self.root)
        self.assertTrue(self.target.exists())
        self.assertTrue(installer._journal(self.state,'demo').exists())

    def test_fresh_install_cannot_bypass_unresolved_legacy_backups(self):
        ids=self.orphan()
        preview=self.case.preview()
        self.assertTrue(preview['unresolved_legacy_backup_evidence_exists'])
        self.assertFalse(preview['eligible_for_fresh_install'])
        with self.assertRaisesRegex(ValueError,'stale preflight|Destination occupied'):
            installer.install_fresh(self.case.plan_id,self.root,
                                   preview['state_binding_id'],
                                   bundle_root=self.case.fixture.root,
                                   lookup=self.case.fixture.lookup,
                                   reader=lambda _:'')
        self.assertTrue(installer._backup_dir(self.state,'demo',ids[0]).is_dir())
        self.assertFalse(self.target.exists())

    def test_replacement_of_unmanaged_target_cannot_ignore_unclaimed_history(self):
        ids=self.orphan()
        self.target.mkdir(parents=True)
        (self.target/'SKILL.md').write_text(
            '---\nname: demo\ndescription: user owned\n---\n# User\n')
        with self.assertRaisesRegex(ValueError,'Unresolved legacy Backup history'):
            installer.preview_replace(self.case.plan_id,self.root,
                                      bundle_root=self.case.fixture.root,
                                      lookup=self.case.fixture.lookup)
        self.assertTrue((self.target/'SKILL.md').exists())
        self.assertTrue(installer._backup_dir(self.state,'demo',ids[0]).exists())
