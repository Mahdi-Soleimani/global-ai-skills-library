"""Phase 51: both real POSIX Host adapters exercised ONLY with inert Git fixtures."""
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))

import host_project_install as h
from queue_ingest import git_blob
from tests import test_codex_project_install as original_fixture


class HostProjectInstallTests(unittest.TestCase):
    def setUp(self):
        self.case=original_fixture.ProjectInstallTests(
            "test_genuine_install_and_uninstall_in_temporary_project")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.fixture=self.case.fixture
        self.project=self.case.project
        self.root=self.fixture.root
        self.source_id=self.fixture.row["source_record_id"]
        self.next_counter=1

    def setup_host(self,host):
        bundle=self.fixture._prepare(agent=host,scope="project")
        return bundle["plan_id"]

    def preview(self,host,plan_id):
        return h.preview_install(plan_id,self.project,host,
                                 bundle_root=self.root,lookup=self.fixture.lookup)

    def target(self,host):
        return self.project/(".cursor" if host=="cursor" else ".claude")/"skills"/"demo"

    def state(self,host):
        return self.project/".gasl-managed"/"hosts"/host

    def consent(self,prompt):
        self.assertIn("Type EXACTLY:",prompt)
        return prompt.split("Type EXACTLY: ",1)[1].split("\n",1)[0]

    def install(self,host,plan_id):
        p=self.preview(host,plan_id)
        with patch("sys.stdin.isatty",return_value=True):
            return h.install(plan_id,self.project,host,p["state_binding_id"],
                             bundle_root=self.root,lookup=self.fixture.lookup,
                             reader=self.consent)

    def next_bundle(self,host):
        self.next_counter+=1
        source=(b"---\nname: demo\ndescription: Updated inert fixture\n---\n"
                + ("# Inert version %d; no code\n" % self.next_counter).encode())
        self.fixture.content["skills/demo/SKILL.md"]=source
        self.fixture.row["skill_md_blob_sha"]=git_blob(source)
        self.fixture.row["commit_sha"]=hashlib.sha1(source).hexdigest()
        self.fixture.row["tree_sha"]=hashlib.sha1(b"tree:"+source).hexdigest()
        self.fixture._package()
        return self.setup_host(host)

    def replace(self,host,plan_id):
        p=h.preview_replace(plan_id,self.project,host,
                            bundle_root=self.root,lookup=self.fixture.lookup)
        with patch("sys.stdin.isatty",return_value=True):
            return h.replace(plan_id,self.project,host,p["state_binding_id"],
                             bundle_root=self.root,lookup=self.fixture.lookup,
                             reader=self.consent)

    def test_preview_and_fresh_real_file_install_both_host_layouts(self):
        for host in h.HOSTS:
            with self.subTest(host=host):
                plan_id=self.setup_host(host)
                before=self.preview(host,plan_id)
                self.assertEqual(before["host"],host)
                self.assertEqual(before["relative_target"],
                                 (".cursor" if host=="cursor" else ".claude")+"/skills/demo")
                self.assertFalse(before["real_host_modified"])
                self.assertFalse(self.target(host).exists())
                installed=self.install(host,plan_id)
                self.assertTrue(self.target(host).is_dir())
                self.assertEqual(installed["status"],"host_project_skill_installed")
                self.assertTrue((self.state(host)/"receipts"/"demo.json").is_file())
                self.assertFalse(installed["skill_executed"])

    def test_independent_host_state_and_no_codex_path_writes(self):
        cursor_id=self.setup_host("cursor")
        self.install("cursor",cursor_id)
        self.assertFalse((self.project/".agents").exists())
        claude_id=self.setup_host("claude-code")
        self.assertNotEqual(cursor_id,claude_id)
        self.install("claude-code",claude_id)
        self.assertTrue(self.target("cursor").exists())
        self.assertTrue(self.target("claude-code").exists())
        self.assertFalse((self.project/".agents").exists())
        self.assertNotEqual(
            (self.state("cursor")/"receipts"/"demo.json").read_text(),
            (self.state("claude-code")/"receipts"/"demo.json").read_text())

    def test_no_tty_no_write_even_with_valid_simulated_reader(self):
        for host in h.HOSTS:
            with self.subTest(host=host):
                plan_id=self.setup_host(host)
                p=self.preview(host,plan_id)
                with patch("sys.stdin.isatty",return_value=False):
                    with self.assertRaisesRegex(ValueError,"local interactive TTY"):
                        h.install(plan_id,self.project,host,p["state_binding_id"],
                                  bundle_root=self.root,lookup=self.fixture.lookup,
                                  reader=self.consent)
                self.assertFalse(self.target(host).exists())

    def test_refuse_stale_binding_and_wrong_phrase(self):
        for host in h.HOSTS:
            with self.subTest(host=host):
                plan_id=self.setup_host(host)
                with patch("sys.stdin.isatty",return_value=True):
                    with self.assertRaisesRegex(ValueError,"Stale"):
                        h.install(plan_id,self.project,host,"0"*64,bundle_root=self.root,
                                  lookup=self.fixture.lookup,reader=self.consent)
                    p=self.preview(host,plan_id)
                    with self.assertRaisesRegex(ValueError,"phrase"):
                        h.install(plan_id,self.project,host,p["state_binding_id"],
                                  bundle_root=self.root,lookup=self.fixture.lookup,
                                  reader=lambda _: "WRONG")
                self.assertFalse(self.target(host).exists())

    def test_replace_preserves_entire_original_and_restore_keeps_current(self):
        for host in h.HOSTS:
            with self.subTest(host=host):
                v1=self.setup_host(host)
                self.install(host,v1)
                original=(self.target(host)/"SKILL.md").read_bytes()
                v2=self.next_bundle(host)
                res=self.replace(host,v2)
                self.assertTrue((self.target(host)/"SKILL.md").read_bytes()!=original)
                saved=res["backup_id"]
                self.assertEqual(
                    (self.state(host)/"backups"/"demo"/saved/"SKILL.md").read_bytes(),original)
                pre=h.preview_restore(host,self.project,"demo",saved)
                with patch("sys.stdin.isatty",return_value=True):
                    restored=h.restore(host,self.project,"demo",saved,
                                       pre["state_binding_id"],reader=self.consent)
                self.assertEqual((self.target(host)/"SKILL.md").read_bytes(),original)
                self.assertEqual(len(restored["retained_backup_ids"]),2)
                self.assertEqual(
                    h.list_backups(host,self.project,"demo")["active"],True)
                self.assertTrue(
                    (self.state(host)/"backups"/"demo"/
                     restored["preserved_previous_backup_id"]/"SKILL.md").is_file())

    def test_uninstall_archives_and_reinstall_restores_selected_backup(self):
        for host in h.HOSTS:
            with self.subTest(host=host):
                plan_id=self.setup_host(host)
                self.install(host,plan_id)
                original=(self.target(host)/"SKILL.md").read_bytes()
                preview=h.preview_uninstall(host,self.project,"demo")
                with patch("sys.stdin.isatty",return_value=True):
                    gone=h.uninstall(host,self.project,"demo",
                                     preview["state_binding_id"],reader=self.consent)
                self.assertFalse(self.target(host).exists())
                self.assertFalse((self.state(host)/"receipts"/"demo.json").exists())
                self.assertEqual(h.list_backups(host,self.project,"demo")["active"],False)
                with self.assertRaises(ValueError):
                    self.preview(host,plan_id)
                previous=gone["archived_backup_id"]
                pre=h.preview_reinstall(host,self.project,"demo",previous)
                with patch("sys.stdin.isatty",return_value=True):
                    installed=h.reinstall(host,self.project,"demo",previous,
                                          pre["state_binding_id"],reader=self.consent)
                self.assertEqual((self.target(host)/"SKILL.md").read_bytes(),original)
                self.assertEqual(installed["status"],
                                 "host_project_skill_reinstalled_from_archive")
                self.assertTrue((self.state(host)/"receipts"/"demo.json").exists())
                self.assertFalse((self.state(host)/"uninstalled"/"demo.json").exists())

    def test_existing_unmanaged_skill_requires_separate_review_not_overwritten(self):
        for host in h.HOSTS:
            with self.subTest(host=host):
                plan=self.setup_host(host)
                dest=self.target(host)
                dest.mkdir(parents=True)
                (dest/"SKILL.md").write_text("USER NOTES: DO NOT MODIFY")
                with self.assertRaisesRegex(ValueError,"unoccupied"):
                    self.preview(host,plan)
                with self.assertRaisesRegex(ValueError,"GASL-owned"):
                    h.preview_replace(plan,self.project,host,
                                      bundle_root=self.root,lookup=self.fixture.lookup)
                self.assertEqual((dest/"SKILL.md").read_text(),
                                 "USER NOTES: DO NOT MODIFY")

    def test_user_edits_block_managed_replace_and_uninstall(self):
        for host in h.HOSTS:
            with self.subTest(host=host):
                v1=self.setup_host(host)
                self.install(host,v1)
                note=self.target(host)/"extra-user-file.txt"
                note.write_text("KEEP ME")
                with self.assertRaisesRegex(ValueError,"contents changed"):
                    h.preview_uninstall(host,self.project,"demo")
                v2=self.next_bundle(host)
                with self.assertRaisesRegex(ValueError,"contents changed"):
                    h.preview_replace(v2,self.project,host,
                                      bundle_root=self.root,lookup=self.fixture.lookup)
                self.assertEqual(note.read_text(),"KEEP ME")

    def test_zip_tamper_refused_before_writing_host_files(self):
        for host in h.HOSTS:
            with self.subTest(host=host):
                plan=self.setup_host(host)
                zip_file=self.root/"private"/"install-bundles"/(plan+".zip")
                zip_file.write_bytes(zip_file.read_bytes()+b"MALFORMED")
                with self.assertRaisesRegex(ValueError,"hash mismatch"):
                    self.preview(host,plan)
                self.assertFalse(self.target(host).exists())

    def test_wrong_host_bundle_never_accepted(self):
        plan=self.setup_host("cursor")
        with self.assertRaises(ValueError):
            self.preview("claude-code",plan)

    def test_symlink_project_target_refused(self):
        for host in h.HOSTS:
            with self.subTest(host=host):
                plan=self.setup_host(host)
                outside=self.project/"safe-external-folder"
                outside.mkdir(exist_ok=True)
                dest=self.target(host)
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.symlink_to(outside)
                with self.assertRaises(ValueError):
                    self.preview(host,plan)
                self.assertEqual(list(outside.iterdir()),[])

    def test_recovery_interrupted_fresh_install_removes_only_owned_files(self):
        for host in h.HOSTS:
            with self.subTest(host=host):
                plan=self.setup_host(host)
                with patch("sys.stdin.isatty",return_value=True), patch(
                    "host_project_install._store_receipt",side_effect=OSError("simulated crash")
                ):
                    with self.assertRaisesRegex(OSError,"simulated crash"):
                        self.install(host,plan)
                self.assertTrue(self.target(host).exists())
                self.assertTrue(h._journal(self.state(host),"demo").exists())
                result=h.recover(host,self.project,"demo")
                self.assertEqual(result["status"],
                                 "host_project_incomplete_transaction_rolled_back")
                self.assertFalse(self.target(host).exists())

    def test_recovery_after_replacement_activation_restores_old_version(self):
        for host in h.HOSTS:
            with self.subTest(host=host):
                v1=self.setup_host(host)
                self.install(host,v1)
                old=(self.target(host)/"SKILL.md").read_bytes()
                v2=self.next_bundle(host)
                with patch("sys.stdin.isatty",return_value=True), patch(
                    "host_project_install._store_receipt",side_effect=OSError("simulated crash")
                ):
                    with self.assertRaisesRegex(OSError,"simulated crash"):
                        self.replace(host,v2)
                result=h.recover(host,self.project,"demo")
                self.assertEqual(result["status"],
                                 "host_project_incomplete_transaction_rolled_back")
                self.assertEqual((self.target(host)/"SKILL.md").read_bytes(),old)
                self.assertEqual(h.list_backups(host,self.project,"demo")["backups"],[])

    def test_recovery_refuses_to_delete_user_modified_activated_skill(self):
        host="cursor"
        v1=self.setup_host(host)
        self.install(host,v1)
        v2=self.next_bundle(host)
        with patch("sys.stdin.isatty",return_value=True), patch(
            "host_project_install._store_receipt",side_effect=OSError("simulated crash")
        ):
            with self.assertRaises(OSError):
                self.replace(host,v2)
        extra=self.target(host)/"IMPORTANT-NOTE.txt"
        extra.write_text("MY FILE")
        with self.assertRaisesRegex(ValueError,"edited"):
            h.recover(host,self.project,"demo")
        self.assertEqual(extra.read_text(),"MY FILE")
        self.assertTrue(h._journal(self.state(host),"demo").exists())

    def test_recovery_uninstall_mid_archive_restores_ownership(self):
        for host in h.HOSTS:
            with self.subTest(host=host):
                plan=self.setup_host(host)
                self.install(host,plan)
                before=(self.target(host)/"SKILL.md").read_bytes()
                preview=h.preview_uninstall(host,self.project,"demo")
                raw_new=h._new
                def fail_marker(path,value):
                    if "uninstalled" in path.parts:
                        raise OSError("crash before archive marker")
                    return raw_new(path,value)
                with patch("sys.stdin.isatty",return_value=True), patch(
                    "host_project_install._new",side_effect=fail_marker
                ):
                    with self.assertRaisesRegex(OSError,"crash before archive"):
                        h.uninstall(host,self.project,"demo",
                                    preview["state_binding_id"],reader=self.consent)
                fixed=h.recover(host,self.project,"demo")
                self.assertEqual(fixed["status"],
                                 "host_project_incomplete_transaction_rolled_back")
                self.assertEqual((self.target(host)/"SKILL.md").read_bytes(),before)

    def test_recovery_completed_install_journal_only_finalizes(self):
        host="cursor"
        plan=self.setup_host(host)
        self.install(host,plan)
        state=self.state(host)
        receipt=h._load(h._receipt(state,"demo"))
        h._write_journal(state,host,"demo","install",receipt["transaction"],
                         receipt,None,new_files=receipt["files"])
        fixed=h.recover(host,self.project,"demo")
        self.assertEqual(fixed["status"],"host_project_committed_transaction_finalized")
        self.assertTrue(self.target(host).exists())

    def test_pending_journal_blocks_any_new_preview(self):
        host="claude-code"
        plan=self.setup_host(host)
        self.install(host,plan)
        state=self.state(host)
        receipt=h._load(h._receipt(state,"demo"))
        h._write_journal(state,host,"demo","install",receipt["transaction"],
                         receipt,None,new_files=receipt["files"])
        with self.assertRaisesRegex(ValueError,"recover"):
            h.preview_uninstall(host,self.project,"demo")

    def test_unknown_host_and_home_scope_disallowed(self):
        plan=self.setup_host("cursor")
        with self.assertRaisesRegex(
                ValueError, "Bundle is not bound" if os.name == "nt" else "Only Cursor"):
            self.preview("codex",plan)
        with self.assertRaises(ValueError):
            h.preview_install(plan,self.root,"cursor",
                              bundle_root=self.root,lookup=self.fixture.lookup)



    def test_stale_backup_manifest_metadata_binding_prevents_restore(self):
        host="cursor"
        v1=self.setup_host(host)
        self.install(host,v1)
        v2=self.next_bundle(host)
        res=self.replace(host,v2)
        bid=res["backup_id"]
        original_preview=h.preview_restore(host,self.project,"demo",bid)
        path=h._manifest(self.state(host),"demo",bid)
        record=json.loads(path.read_text())
        record["previous_receipt"]["binding"]="f"*64
        path.write_text(json.dumps(record))
        with patch("sys.stdin.isatty",return_value=True):
            with self.assertRaisesRegex(ValueError,"changed since preflight"):
                h.restore(host,self.project,"demo",bid,
                          original_preview["state_binding_id"],reader=self.consent)
        self.assertTrue(self.target(host).is_dir())
        self.assertFalse(h._journal(self.state(host),"demo").exists())

    def test_missing_backup_history_refuses_restore_instead_of_guessing(self):
        host="claude-code"
        v1=self.setup_host(host)
        self.install(host,v1)
        v2=self.next_bundle(host)
        res=self.replace(host,v2)
        h._manifest(self.state(host),"demo",res["backup_id"]).unlink()
        with self.assertRaises(ValueError):
            h.list_backups(host,self.project,"demo")
        with self.assertRaises(ValueError):
            h.preview_restore(host,self.project,"demo",res["backup_id"])
        self.assertTrue(self.target(host).is_dir())

    def test_interrupted_restore_after_activation_keeps_original(self):
        host="cursor"
        v1=self.setup_host(host)
        self.install(host,v1)
        v2=self.next_bundle(host)
        res=self.replace(host,v2)
        previous=(self.target(host)/"SKILL.md").read_bytes()
        pre=h.preview_restore(host,self.project,"demo",res["backup_id"])
        with patch("sys.stdin.isatty",return_value=True), patch(
            "host_project_install._store_receipt",side_effect=OSError("crash during restore")
        ):
            with self.assertRaisesRegex(OSError,"crash during restore"):
                h.restore(host,self.project,"demo",res["backup_id"],
                          pre["state_binding_id"],reader=self.consent)
        undone=h.recover(host,self.project,"demo")
        self.assertEqual(undone["status"],"host_project_incomplete_transaction_rolled_back")
        self.assertEqual((self.target(host)/"SKILL.md").read_bytes(),previous)
        self.assertEqual(len(h.list_backups(host,self.project,"demo")["backups"]),1)

    def test_interrupted_reinstall_retains_uninstall_marker_and_archive(self):
        host="claude-code"
        v1=self.setup_host(host)
        self.install(host,v1)
        pre=h.preview_uninstall(host,self.project,"demo")
        with patch("sys.stdin.isatty",return_value=True):
            removed=h.uninstall(host,self.project,"demo",
                                pre["state_binding_id"],reader=self.consent)
        bid=removed["archived_backup_id"]
        preview=h.preview_reinstall(host,self.project,"demo",bid)
        with patch("sys.stdin.isatty",return_value=True), patch(
            "host_project_install._store_receipt",side_effect=OSError("crash during reinstall")
        ):
            with self.assertRaisesRegex(OSError,"crash during reinstall"):
                h.reinstall(host,self.project,"demo",bid,
                            preview["state_binding_id"],reader=self.consent)
        self.assertTrue(self.target(host).exists())
        recovered=h.recover(host,self.project,"demo")
        self.assertEqual(recovered["status"],"host_project_incomplete_transaction_rolled_back")
        self.assertFalse(self.target(host).exists())
        self.assertTrue((self.state(host)/"uninstalled"/"demo.json").exists())
        self.assertEqual(h.list_backups(host,self.project,"demo")["active"],False)

    def test_recovery_completed_reinstall_finalizes_without_rolling_back(self):
        host="cursor"
        plan=self.setup_host(host)
        self.install(host,plan)
        pre=h.preview_uninstall(host,self.project,"demo")
        with patch("sys.stdin.isatty",return_value=True):
            removed=h.uninstall(host,self.project,"demo",pre["state_binding_id"],reader=self.consent)
        bid=removed["archived_backup_id"]
        pre=h.preview_reinstall(host,self.project,"demo",bid)
        with patch("sys.stdin.isatty",return_value=True):
            done=h.reinstall(host,self.project,"demo",bid,
                             pre["state_binding_id"],reader=self.consent)
        state=self.state(host)
        receipt=h._load(h._receipt(state,"demo"))
        marker={
            "schema":h.SCHEMA,"host":host,"scope":"project","slug":"demo",
            "status":"uninstalled_archive","archive_id":bid,
            "backup_ids":removed["retained_backup_ids"],
            "last_receipt":h._load(h._manifest(state,"demo",bid))["previous_receipt"],
        }
        h._write_journal(state,host,"demo","reinstall",receipt["transaction"],
                         receipt,None,new_files=receipt["files"],
                         selected_id=bid,marker=marker)
        finalized=h.recover(host,self.project,"demo")
        self.assertEqual(finalized["status"],"host_project_committed_transaction_finalized")
        self.assertTrue(self.target(host).exists())
        self.assertFalse(h._journal(state,"demo").exists())

    def test_uninstall_marker_tamper_refuses_reinstall_without_touching_archive(self):
        host="cursor"
        plan=self.setup_host(host)
        self.install(host,plan)
        preview=h.preview_uninstall(host,self.project,"demo")
        with patch("sys.stdin.isatty",return_value=True):
            gone=h.uninstall(host,self.project,"demo",preview["state_binding_id"],
                             reader=self.consent)
        marker=h._marker(self.state(host),"demo")
        record=json.loads(marker.read_text())
        record["backup_ids"]=[]
        marker.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError,"chain"):
            h.preview_reinstall(host,self.project,"demo",gone["archived_backup_id"])
        self.assertFalse(self.target(host).exists())
        self.assertTrue(h._backup(self.state(host),"demo",gone["archived_backup_id"]).exists())

    def test_zip_mutation_during_consent_is_rejected_without_host_write(self):
        host="claude-code"
        plan=self.setup_host(host)
        preview=self.preview(host,plan)
        zip_path=self.root/"private"/"install-bundles"/(plan+".zip")
        def mutate(prompt):
            zip_path.write_bytes(zip_path.read_bytes()+b"CHANGED_AFTER_PREVIEW")
            return self.consent(prompt)
        with patch("sys.stdin.isatty",return_value=True):
            with self.assertRaisesRegex(ValueError,"hash mismatch"):
                h.install(plan,self.project,host,preview["state_binding_id"],
                          bundle_root=self.root,lookup=self.fixture.lookup,
                          reader=mutate)
        self.assertFalse(self.target(host).exists())
        self.assertFalse(h._journal(self.state(host),"demo").exists())

    def test_corrupt_recovery_journal_refused_and_preserved(self):
        host="cursor"
        plan=self.setup_host(host)
        self.install(host,plan)
        receipt=h._load(h._receipt(self.state(host),"demo"))
        h._write_journal(self.state(host),host,"demo","install",
                         receipt["transaction"],receipt,None,new_files=receipt["files"])
        journal=h._journal(self.state(host),"demo")
        record=json.loads(journal.read_text())
        record["host"]="claude-code"
        journal.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError,"Invalid host transaction"):
            h.recover(host,self.project,"demo")
        self.assertTrue(journal.exists())
        self.assertTrue(self.target(host).is_dir())

    def test_symlink_state_lock_rejected_without_following_it(self):
        host="claude-code"
        plan=self.setup_host(host)
        preview=self.preview(host,plan)
        outside=self.project/"outside-lock.txt"
        outside.write_text("KEEP OUTSIDE")
        state=self.state(host)
        state.mkdir(parents=True,exist_ok=True)
        (state/".lock").symlink_to(outside)
        with patch("sys.stdin.isatty",return_value=True):
            with self.assertRaisesRegex(ValueError,"Unsafe host transaction lock"):
                h.install(plan,self.project,host,preview["state_binding_id"],
                          bundle_root=self.root,lookup=self.fixture.lookup,
                          reader=self.consent)
        self.assertFalse(self.target(host).exists())
        self.assertEqual(outside.read_text(),"KEEP OUTSIDE")

    def test_orphan_backup_records_are_not_silently_adopted(self):
        host="cursor"
        plan=self.setup_host(host)
        folder=self.state(host)/"backups"/"demo"
        folder.mkdir(parents=True)
        (folder/"orphan.txt").write_text("UNMANAGED")
        with self.assertRaisesRegex(ValueError,"Unowned backup history"):
            self.preview(host,plan)
        self.assertEqual((folder/"orphan.txt").read_text(),"UNMANAGED")

    def test_recovery_before_backup_manifest_exists_is_safe(self):
        host="claude-code"
        v1=self.setup_host(host)
        self.install(host,v1)
        old=(self.target(host)/"SKILL.md").read_bytes()
        v2=self.next_bundle(host)
        original_new=h._new
        def fail_manifest(path,record):
            if path.parent.name=="demo" and path.suffix==".json":
                raise OSError("crash before backup manifest")
            return original_new(path,record)
        with patch("sys.stdin.isatty",return_value=True), patch(
            "host_project_install._new",side_effect=fail_manifest
        ):
            with self.assertRaisesRegex(OSError,"crash before backup manifest"):
                self.replace(host,v2)
        fixed=h.recover(host,self.project,"demo")
        self.assertEqual(fixed["status"],"host_project_incomplete_transaction_rolled_back")
        self.assertEqual((self.target(host)/"SKILL.md").read_bytes(),old)
        self.assertEqual(h.list_backups(host,self.project,"demo")["backups"],[])

    def test_committed_replace_journal_recovery_keeps_new_backup(self):
        host="cursor"
        v1=self.setup_host(host)
        self.install(host,v1)
        v2=self.next_bundle(host)
        with patch("sys.stdin.isatty",return_value=True), patch(
            "host_project_install._finish_journal",side_effect=OSError("crash after commit")
        ):
            with self.assertRaisesRegex(OSError,"crash after commit"):
                self.replace(host,v2)
        current=(self.target(host)/"SKILL.md").read_bytes()
        recovered=h.recover(host,self.project,"demo")
        self.assertEqual(recovered["status"],"host_project_committed_transaction_finalized")
        self.assertEqual((self.target(host)/"SKILL.md").read_bytes(),current)
        self.assertEqual(len(h.list_backups(host,self.project,"demo")["backups"]),1)

    def test_committed_uninstall_journal_recovery_keeps_archive(self):
        host="claude-code"
        plan=self.setup_host(host)
        self.install(host,plan)
        pre=h.preview_uninstall(host,self.project,"demo")
        with patch("sys.stdin.isatty",return_value=True), patch(
            "host_project_install._finish_journal",side_effect=OSError("crash after uninstall")
        ):
            with self.assertRaisesRegex(OSError,"crash after uninstall"):
                h.uninstall(host,self.project,"demo",pre["state_binding_id"],
                            reader=self.consent)
        self.assertFalse(self.target(host).exists())
        self.assertTrue(h._marker(self.state(host),"demo").is_file())
        finalized=h.recover(host,self.project,"demo")
        self.assertEqual(finalized["status"],"host_project_committed_transaction_finalized")
        self.assertFalse(self.target(host).exists())
        self.assertEqual(len(h.list_backups(host,self.project,"demo")["backups"]),1)

    def test_uninstall_one_host_preserves_second_host_same_skill(self):
        for host in h.HOSTS:
            self.install(host,self.setup_host(host))
        other=(self.target("claude-code")/"SKILL.md").read_bytes()
        pre=h.preview_uninstall("cursor",self.project,"demo")
        with patch("sys.stdin.isatty",return_value=True):
            h.uninstall("cursor",self.project,"demo",
                        pre["state_binding_id"],reader=self.consent)
        self.assertFalse(self.target("cursor").exists())
        self.assertEqual((self.target("claude-code")/"SKILL.md").read_bytes(),other)
        self.assertTrue(h._receipt(self.state("claude-code"),"demo").is_file())

if __name__=="__main__":
    unittest.main()
