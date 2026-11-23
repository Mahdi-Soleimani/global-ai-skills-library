"""Phase 53 native Windows project transactions, only temporary inert Git fixtures.

Run on windows-latest using CPython 3.13. No actual Agent, HOME, or Skill is used.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools"))
import host_project_install as hp
from transaction_file_lock import (
    supported_platform, exclusive_lock_file, require_windows_filename_safety,
)
from queue_ingest import git_blob
from tests import test_codex_project_install as fixtures


@unittest.skipUnless(os.name == "nt", "Native Windows-only tests")
class WindowsProjectTransactionTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.ProjectInstallTests(
            "test_genuine_install_and_uninstall_in_temporary_project")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.fixture = self.case.fixture
        self.project = self.case.project
        self.bundle_root = self.fixture.root
        self.version = 0

    def prepare(self, host):
        return self.fixture._prepare(agent=host, scope="project")["plan_id"]

    def state(self, host):
        return self.project/".gasl-managed"/"hosts"/host

    def target(self, host):
        prefix={"codex":".agents","cursor":".cursor","claude-code":".claude"}[host]
        return self.project/prefix/"skills"/"demo"

    @staticmethod
    def consent(prompt):
        return prompt.split("Type EXACTLY: ",1)[1].split("\n",1)[0]

    def preview(self, host, plan):
        return hp.preview_install(plan,self.project,host,
                                  bundle_root=self.bundle_root,lookup=self.fixture.lookup)

    def install(self, host, plan):
        review=self.preview(host,plan)
        with patch("sys.stdin.isatty",return_value=True):
            return hp.install(plan,self.project,host,review["state_binding_id"],
                              bundle_root=self.bundle_root,lookup=self.fixture.lookup,
                              reader=self.consent)

    def next_plan(self,host):
        self.version+=1
        source=(b"---\nname: demo\ndescription: Inert Windows Skill\n---\n"
                + ("# TEST ONLY VERSION %d\n" % self.version).encode())
        self.fixture.content["skills/demo/SKILL.md"]=source
        self.fixture.row["skill_md_blob_sha"]=git_blob(source)
        self.fixture.row["commit_sha"]=hashlib.sha1(source).hexdigest()
        self.fixture.row["tree_sha"]=hashlib.sha1(b"tree"+source).hexdigest()
        self.fixture._package()
        return self.prepare(host)

    def replace(self,host,plan):
        check=hp.preview_replace(plan,self.project,host,
                                 bundle_root=self.bundle_root,lookup=self.fixture.lookup)
        with patch("sys.stdin.isatty",return_value=True):
            return hp.replace(plan,self.project,host,check["state_binding_id"],
                              bundle_root=self.bundle_root,lookup=self.fixture.lookup,
                              reader=self.consent)

    def test_windows_package_manifest_paths_are_canonical_posix(self):
        from queue_ingest import package_location
        folder=package_location(
            self.fixture.root,
            {**self.fixture.row, "skill_path":self.fixture.row["source_path"]}
        )
        metadata=json.loads((folder/"source.json").read_text(encoding="utf-8"))
        for item in metadata["files"]:
            self.assertTrue(item["local_path"].startswith("catalog/"))
            self.assertNotIn("\\",item["local_path"])
        self.assertEqual(len(metadata["files"]),2)

    def test_windows_msvcrt_platform_lock_available(self):
        self.assertTrue(supported_platform())

    def test_install_and_receipt_three_hosts(self):
        for host in ("codex","cursor","claude-code"):
            with self.subTest(host=host):
                plan=self.prepare(host)
                check=self.preview(host,plan)
                self.assertFalse(check["real_host_modified"])
                self.assertFalse(self.target(host).exists())
                result=self.install(host,plan)
                self.assertEqual(result["status"],"host_project_skill_installed")
                self.assertTrue((self.target(host)/"SKILL.md").is_file())
                self.assertTrue(hp._receipt(self.state(host),"demo").is_file())
                self.assertFalse(result["skill_executed"])
        self.assertEqual(len({(self.target(host)/"SKILL.md").read_bytes()
                              for host in ("codex","cursor","claude-code")}),1)
        self.assertFalse((self.project/"SKILL.md").exists())

    def test_all_hosts_state_separated(self):
        for host in ("codex","cursor","claude-code"):
            self.install(host,self.prepare(host))
        receipts=[hp._receipt(self.state(host),"demo") for host in
                  ("codex","cursor","claude-code")]
        self.assertEqual(len(set(str(x) for x in receipts)),3)
        for host,receipt in zip(("codex","cursor","claude-code"),receipts):
            self.assertEqual(json.loads(receipt.read_text())["host"],host)

    def test_wrong_tty_approval_or_missing_tty_refused(self):
        host="codex"
        plan=self.prepare(host)
        check=self.preview(host,plan)
        with patch("sys.stdin.isatty",return_value=False):
            with self.assertRaisesRegex(ValueError,"local interactive TTY"):
                hp.install(plan,self.project,host,check["state_binding_id"],
                           bundle_root=self.bundle_root,lookup=self.fixture.lookup,
                           reader=self.consent)
        with patch("sys.stdin.isatty",return_value=True):
            with self.assertRaisesRegex(ValueError,"approval phrase"):
                hp.install(plan,self.project,host,check["state_binding_id"],
                           bundle_root=self.bundle_root,lookup=self.fixture.lookup,
                           reader=lambda _:"WRONG")
        self.assertFalse(self.target(host).exists())

    def test_complete_replace_restore_preserves_versions(self):
        for host in ("codex","cursor","claude-code"):
            with self.subTest(host=host):
                self.install(host,self.prepare(host))
                original=(self.target(host)/"SKILL.md").read_bytes()
                nextplan=self.next_plan(host)
                result=self.replace(host,nextplan)
                backup=result["backup_id"]
                self.assertEqual((self.state(host)/"backups"/"demo"/backup/"SKILL.md").read_bytes(),original)
                check=hp.preview_restore(host,self.project,"demo",backup)
                with patch("sys.stdin.isatty",return_value=True):
                    restored=hp.restore(host,self.project,"demo",backup,
                                        check["state_binding_id"],reader=self.consent)
                self.assertEqual((self.target(host)/"SKILL.md").read_bytes(),original)
                self.assertEqual(len(restored["retained_backup_ids"]),2)

    def test_uninstall_archive_and_reinstall(self):
        for host in ("codex","cursor","claude-code"):
            with self.subTest(host=host):
                self.install(host,self.prepare(host))
                original=(self.target(host)/"SKILL.md").read_bytes()
                review=hp.preview_uninstall(host,self.project,"demo")
                with patch("sys.stdin.isatty",return_value=True):
                    result=hp.uninstall(host,self.project,"demo",review["state_binding_id"],
                                        reader=self.consent)
                self.assertFalse(self.target(host).exists())
                self.assertFalse(hp.list_backups(host,self.project,"demo")["active"])
                ident=result["archived_backup_id"]
                preview=hp.preview_reinstall(host,self.project,"demo",ident)
                with patch("sys.stdin.isatty",return_value=True):
                    restored=hp.reinstall(host,self.project,"demo",ident,
                                           preview["state_binding_id"],reader=self.consent)
                self.assertEqual(restored["status"],"host_project_skill_reinstalled_from_archive")
                self.assertEqual((self.target(host)/"SKILL.md").read_bytes(),original)

    def test_unmanaged_skill_user_edits_never_overwritten(self):
        host="cursor"
        plan=self.prepare(host)
        target=self.target(host)
        target.mkdir(parents=True)
        (target/"SKILL.md").write_text("PERSONAL WINDOWS CONTENT")
        with self.assertRaisesRegex(ValueError,"unoccupied"):
            self.preview(host,plan)
        with self.assertRaisesRegex(ValueError,"GASL-owned"):
            hp.preview_replace(plan,self.project,host,
                               bundle_root=self.bundle_root,lookup=self.fixture.lookup)
        self.assertEqual((target/"SKILL.md").read_text(),"PERSONAL WINDOWS CONTENT")

    def test_crash_during_install_recovers_exact_files(self):
        host="codex"
        plan=self.prepare(host)
        with patch("sys.stdin.isatty",return_value=True), patch(
            "host_project_install._store_receipt",side_effect=OSError("simulated crash")
        ):
            with self.assertRaisesRegex(OSError,"simulated crash"):
                self.install(host,plan)
        self.assertTrue(hp._journal(self.state(host),"demo").is_file())
        result=hp.recover(host,self.project,"demo")
        self.assertEqual(result["status"],"host_project_incomplete_transaction_rolled_back")
        self.assertFalse(self.target(host).exists())

    def test_crash_after_replacement_activation_restores_old(self):
        host="claude-code"
        self.install(host,self.prepare(host))
        old=(self.target(host)/"SKILL.md").read_bytes()
        nextplan=self.next_plan(host)
        with patch("sys.stdin.isatty",return_value=True), patch(
            "host_project_install._store_receipt",side_effect=OSError("simulated crash")
        ):
            with self.assertRaisesRegex(OSError,"simulated crash"):
                self.replace(host,nextplan)
        result=hp.recover(host,self.project,"demo")
        self.assertEqual(result["status"],"host_project_incomplete_transaction_rolled_back")
        self.assertEqual((self.target(host)/"SKILL.md").read_bytes(),old)
        self.assertEqual(hp.list_backups(host,self.project,"demo")["backups"],[])

    def test_recovery_never_deletes_user_edit_to_activated_files(self):
        host="cursor"
        self.install(host,self.prepare(host))
        nextplan=self.next_plan(host)
        with patch("sys.stdin.isatty",return_value=True), patch(
            "host_project_install._store_receipt",side_effect=OSError("simulated crash")
        ):
            with self.assertRaises(OSError):
                self.replace(host,nextplan)
        note=self.target(host)/"KEEP-FOREVER.txt"
        note.write_text("USER DATA")
        with self.assertRaisesRegex(ValueError,"edited"):
            hp.recover(host,self.project,"demo")
        self.assertEqual(note.read_text(),"USER DATA")
        self.assertTrue(hp._journal(self.state(host),"demo").exists())

    def test_native_windows_lock_is_exclusive_across_processes(self):
        import tempfile
        lock=Path(self.case.tmp.name)/"win.lock"
        script=("import sys,time;sys.path.insert(0,sys.argv[2]);"
                "from transaction_file_lock import exclusive_lock_file;"
                "l=exclusive_lock_file(sys.argv[1]);l.__enter__();print('LOCKED',flush=True);"
                "time.sleep(1.5);l.__exit__(None,None,None)")
        process=subprocess.Popen([sys.executable,"-c",script,str(lock),str(ROOT/"tools")],
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(),"LOCKED")
            with self.assertRaisesRegex(ValueError,"lock busy"):
                with exclusive_lock_file(lock,attempts=3,pause_seconds=0.05):
                    self.fail("Windows lock was acquired twice concurrently")
            process.wait(timeout=5)
            self.assertEqual(process.returncode,0,process.stderr.read())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_windows_reserved_names_are_rejected(self):
        for name in ("NUL","con.txt","AUX.md","COM1.log","foo:ADS","a?b",
                     "trailing.","trailing ","ok/PRN.txt","a\\b"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError,"Windows"):
                    require_windows_filename_safety(name)
        self.assertEqual(require_windows_filename_safety("references/about.md"),
                         "references/about.md")

    def test_ntfs_junction_target_refused_when_supported(self):
        outside=Path(self.case.tmp.name)/"external"
        outside.mkdir()
        target=self.target("cursor")
        target.parent.mkdir(parents=True)
        command=["cmd","/c","mklink","/J",str(target),str(outside)]
        result=subprocess.run(command,capture_output=True,text=True)
        if result.returncode:
            self.skipTest("Runner does not permit junction creation")
        self.assertTrue(target.is_junction())
        try:
            with self.assertRaisesRegex(ValueError,"Symlink|junction"):
                self.preview("cursor",self.prepare("cursor"))
            self.assertEqual(list(outside.iterdir()),[])
        finally:
            target.rmdir()

    def test_wrong_plan_scope_is_refused(self):
        plan=self.prepare("codex")
        with self.assertRaises(ValueError):
            self.preview("cursor",plan)


if __name__=="__main__":
    unittest.main()
