"""Phase 52: user-profile transactions tested ONLY in isolated fake HOME roots.

Tests monkeypatch _root to return explicit temp fixtures. The production
_root validation is tested separately and NEVER permits actual HOME writes.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))

import user_profile_install as up
import windows_user_profile as windows_profile
REAL_PROFILE_ROOT_CHECK=up._root
from queue_ingest import git_blob
from tests import test_codex_project_install as inert


class UserProfileInstallTests(unittest.TestCase):
    def setUp(self):
        self.fixture_case=inert.ProjectInstallTests(
            "test_genuine_install_and_uninstall_in_temporary_project")
        self.fixture_case.setUp()
        self.addCleanup(self.fixture_case.doCleanups)
        self.fixture=self.fixture_case.fixture
        self.root=self.fixture.root
        self.profile=Path(self.fixture_case.tmp.name)/"inert-os-home"
        self.profile.mkdir()
        if os.name == "nt":
            sid = windows_profile.current_profile()["sid"]
            removed = subprocess.run(
                ["icacls", str(self.profile), "/inheritance:r"],
                capture_output=True, text=True,
            )
            self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
            granted = subprocess.run(
                ["icacls", str(self.profile), "/grant:r", f"*{sid}:(OI)(CI)F"],
                capture_output=True, text=True,
            )
            self.assertEqual(granted.returncode, 0, granted.stdout + granted.stderr)
            owned = subprocess.run(
                ["icacls", str(self.profile), "/setowner", f"*{sid}"],
                capture_output=True, text=True,
            )
            self.assertEqual(owned.returncode, 0, owned.stdout + owned.stderr)

            original_mkdir = up._mkdir_checked
            def mkdir_owned_fake_profile(path):
                original_mkdir(path)
                path = Path(path)
                if path.resolve().is_relative_to(self.profile.resolve()):
                    changed = subprocess.run(
                        ["icacls", str(path), "/setowner", f"*{sid}"],
                        capture_output=True, text=True,
                    )
                    if changed.returncode:
                        raise AssertionError(changed.stdout + changed.stderr)
            self.mkdir_patch = patch(
                "user_profile_install._mkdir_checked",
                side_effect=mkdir_owned_fake_profile,
            )
            self.mkdir_patch.start()
            self.addCleanup(self.mkdir_patch.stop)
        self.root_patch=patch("user_profile_install._root",
                              side_effect=self._fake_root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.version=0

    def _fake_root(self,selected):
        if Path(selected).resolve()!=self.profile.resolve():
            raise ValueError("Only selected inert fake HOME is supported in this fixture")
        return self.profile

    def _package(self,host):
        return self.fixture._prepare(agent=host,scope="user")["plan_id"]

    def _path(self,host):
        base={"codex":".agents","cursor":".cursor",
              "claude-code":".claude"}[host]
        return self.profile/base/"skills"/"demo"

    def _state(self,host):
        return self.profile/".gasl-managed"/"user"/"hosts"/host

    def _consent(self,prompt):
        self.assertIn("Type EXACTLY:",prompt)
        self.assertIn("USER PROFILE",prompt)
        return prompt.split("Type EXACTLY: ",1)[1].split("\n",1)[0]

    def _preview(self,host,plan_id):
        return up.preview_install(plan_id,self.profile,host,
                                  bundle_root=self.root,lookup=self.fixture.lookup)

    def _install(self,host,plan_id):
        check=self._preview(host,plan_id)
        with patch("sys.stdin.isatty",return_value=True):
            return up.install(plan_id,self.profile,host,check["state_binding_id"],
                              bundle_root=self.root,lookup=self.fixture.lookup,
                              reader=self._consent)

    def _next(self,host):
        self.version+=1
        source=(b"---\nname: demo\ndescription: New inert profile Skill\n---\n"+
                ("# no executable code, revision %d\n" % self.version).encode())
        self.fixture.content["skills/demo/SKILL.md"]=source
        self.fixture.row["skill_md_blob_sha"]=git_blob(source)
        self.fixture.row["commit_sha"]=hashlib.sha1(source+str(self.version).encode()).hexdigest()
        self.fixture.row["tree_sha"]=hashlib.sha1(b"tree:"+source+str(self.version).encode()).hexdigest()
        self.fixture._package()
        return self._package(host)

    def _replace(self,host,plan):
        before=up.preview_replace(plan,self.profile,host,
                                  bundle_root=self.root,lookup=self.fixture.lookup)
        with patch("sys.stdin.isatty",return_value=True):
            return up.replace(plan,self.profile,host,before["state_binding_id"],
                              bundle_root=self.root,lookup=self.fixture.lookup,
                              reader=self._consent)

    def test_readonly_preview_all_three_hosts_and_paths(self):
        for host in up.HOSTS:
            with self.subTest(host=host):
                plan=self._package(host)
                p=self._preview(host,plan)
                self.assertEqual(p["scope"],"user")
                self.assertEqual(p["host"],host)
                self.assertEqual(p["relative_target"],
                                 {"codex":".agents","cursor":".cursor",
                                  "claude-code":".claude"}[host]+"/skills/demo")
                self.assertFalse(p["real_host_modified"])
                self.assertTrue(p["user_scope_affects_all_local_projects"])
                self.assertEqual(p["cursor_may_sync_to_cloud_agents"],host=="cursor")
                self.assertFalse(self._path(host).exists())
                self.assertFalse(self._state(host).exists())

    def test_fresh_install_all_hosts_with_independent_receipts(self):
        for host in up.HOSTS:
            plan=self._package(host)
            made=self._install(host,plan)
            self.assertEqual(made["status"],"host_user_skill_installed")
            self.assertEqual(made["scope"],"user")
            self.assertTrue(self._path(host).is_dir())
            receipt=up._load(up._receipt(self._state(host),"demo"))
            self.assertEqual(receipt["profile_identity"],
                             up._profile_identity(self.profile))
            self.assertEqual(receipt["host"],host)
            self.assertFalse(made["skill_executed"])
        self.assertEqual(len({up._receipt(self._state(host),"demo").read_text()
                              for host in up.HOSTS}),3)
        self.assertFalse((self.profile/".agents"/"skills"/"other").exists())
        self.assertFalse((self.profile/".gasl-managed"/"receipts").exists())

    def test_refuse_without_tty_even_if_fake_consent_reader_is_supplied(self):
        for host in up.HOSTS:
            with self.subTest(host=host):
                plan=self._package(host)
                p=self._preview(host,plan)
                with patch("sys.stdin.isatty",return_value=False):
                    with self.assertRaisesRegex(ValueError,"local interactive TTY"):
                        up.install(plan,self.profile,host,p["state_binding_id"],
                                   bundle_root=self.root,lookup=self.fixture.lookup,
                                   reader=self._consent)
                self.assertFalse(self._path(host).exists())

    def test_wrong_phrase_and_stale_binding_refuse_writes(self):
        host="codex"
        plan=self._package(host)
        p=self._preview(host,plan)
        with patch("sys.stdin.isatty",return_value=True):
            with self.assertRaisesRegex(ValueError,"phrase"):
                up.install(plan,self.profile,host,p["state_binding_id"],
                           bundle_root=self.root,lookup=self.fixture.lookup,
                           reader=lambda _:"not approved")
            with self.assertRaisesRegex(ValueError,"Stale"):
                up.install(plan,self.profile,host,"f"*64,
                           bundle_root=self.root,lookup=self.fixture.lookup,
                           reader=self._consent)
        self.assertFalse(self._path(host).exists())

    def test_replace_restore_preserves_all_prior_versions(self):
        for host in up.HOSTS:
            with self.subTest(host=host):
                original=self._package(host)
                self._install(host,original)
                first=(self._path(host)/"SKILL.md").read_bytes()
                second=self._next(host)
                changed=self._replace(host,second)
                bid=changed["backup_id"]
                self.assertNotEqual((self._path(host)/"SKILL.md").read_bytes(),first)
                self.assertEqual((self._state(host)/"backups"/"demo"/bid/"SKILL.md").read_bytes(),first)
                restored=up.preview_restore(host,self.profile,"demo",bid)
                with patch("sys.stdin.isatty",return_value=True):
                    result=up.restore(host,self.profile,"demo",bid,restored["state_binding_id"],
                                      reader=self._consent)
                self.assertEqual((self._path(host)/"SKILL.md").read_bytes(),first)
                self.assertEqual(len(result["retained_backup_ids"]),2)
                self.assertEqual(len(up.list_backups(host,self.profile,"demo")["backups"]),2)

    def test_uninstall_reinstall_full_user_scope(self):
        for host in up.HOSTS:
            with self.subTest(host=host):
                plan=self._package(host)
                self._install(host,plan)
                before=(self._path(host)/"SKILL.md").read_bytes()
                p=up.preview_uninstall(host,self.profile,"demo")
                with patch("sys.stdin.isatty",return_value=True):
                    gone=up.uninstall(host,self.profile,"demo",p["state_binding_id"],
                                      reader=self._consent)
                self.assertFalse(self._path(host).exists())
                self.assertFalse(up._receipt(self._state(host),"demo").exists())
                self.assertTrue(up._marker(self._state(host),"demo").is_file())
                chosen=gone["archived_backup_id"]
                again=up.preview_reinstall(host,self.profile,"demo",chosen)
                with patch("sys.stdin.isatty",return_value=True):
                    restored=up.reinstall(host,self.profile,"demo",chosen,
                                          again["state_binding_id"],reader=self._consent)
                self.assertEqual((self._path(host)/"SKILL.md").read_bytes(),before)
                self.assertEqual(restored["scope"],"user")
                self.assertTrue(up._receipt(self._state(host),"demo").exists())

    def test_existing_unmanaged_user_skill_is_never_adopted(self):
        host="cursor"
        plan=self._package(host)
        target=self._path(host)
        target.mkdir(parents=True)
        (target/"SKILL.md").write_text("USER PERSONAL CONTENT")
        with self.assertRaisesRegex(ValueError,"unoccupied"):
            self._preview(host,plan)
        with self.assertRaisesRegex(ValueError,"GASL-owned"):
            up.preview_replace(plan,self.profile,host,
                               bundle_root=self.root,lookup=self.fixture.lookup)
        self.assertEqual((target/"SKILL.md").read_text(),"USER PERSONAL CONTENT")

    def test_user_edited_file_refuses_backup_or_uninstall(self):
        host="claude-code"
        plan=self._package(host)
        self._install(host,plan)
        note=self._path(host)/"important-personal.txt"
        note.write_text("KEEP USER FILE")
        with self.assertRaisesRegex(ValueError,"contents changed"):
            up.preview_uninstall(host,self.profile,"demo")
        self.assertEqual(note.read_text(),"KEEP USER FILE")

    def test_source_zip_tamper_refuses_install(self):
        host="codex"
        plan=self._package(host)
        archive=self.root/"private"/"install-bundles"/(plan+".zip")
        archive.write_bytes(b"altered")
        with self.assertRaises(ValueError):
            self._preview(host,plan)
        self.assertFalse(self._path(host).exists())

    def test_wrong_host_bound_plan_is_rejected(self):
        cursor=self._package("cursor")
        with self.assertRaises(ValueError):
            self._preview("codex",cursor)

    def test_symlink_destination_refused_and_external_file_preserved(self):
        host="cursor"
        plan=self._package(host)
        outside=self.profile/"safe-external"
        outside.mkdir()
        dest=self._path(host)
        dest.parent.mkdir(parents=True)
        if os.name == "nt":
            result=subprocess.run(["cmd","/c","mklink","/J",str(dest),str(outside)],
                                  capture_output=True,text=True)
            if result.returncode:
                self.skipTest("Runner does not permit disposable NTFS Junction creation")
        else:
            dest.symlink_to(outside)
        with self.assertRaises(ValueError):
            self._preview(host,plan)
        self.assertEqual(list(outside.iterdir()),[])
        if os.name == "nt":
            dest.rmdir()

    def test_crash_before_receipt_rolls_back_only_exact_bytes(self):
        host="codex"
        plan=self._package(host)
        with patch("sys.stdin.isatty",return_value=True), patch(
            "user_profile_install._store_receipt",side_effect=OSError("simulated process loss")
        ):
            with self.assertRaisesRegex(OSError,"process loss"):
                self._install(host,plan)
        self.assertTrue(self._path(host).exists())
        self.assertTrue(up._journal(self._state(host),"demo").exists())
        recovered=up.recover(host,self.profile,"demo")
        self.assertEqual(recovered["status"],"host_user_incomplete_transaction_rolled_back")
        self.assertFalse(self._path(host).exists())

    def test_crash_during_replace_restores_old_profile_skill(self):
        host="cursor"
        initial=self._package(host)
        self._install(host,initial)
        before=(self._path(host)/"SKILL.md").read_bytes()
        next_plan=self._next(host)
        with patch("sys.stdin.isatty",return_value=True), patch(
            "user_profile_install._store_receipt",side_effect=OSError("crash on replacement")
        ):
            with self.assertRaisesRegex(OSError,"crash on replacement"):
                self._replace(host,next_plan)
        result=up.recover(host,self.profile,"demo")
        self.assertEqual(result["status"],"host_user_incomplete_transaction_rolled_back")
        self.assertEqual((self._path(host)/"SKILL.md").read_bytes(),before)
        self.assertEqual(up.list_backups(host,self.profile,"demo")["backups"],[])

    def test_crash_modified_target_is_preserved(self):
        host="claude-code"
        first=self._package(host)
        self._install(host,first)
        second=self._next(host)
        with patch("sys.stdin.isatty",return_value=True), patch(
            "user_profile_install._store_receipt",side_effect=OSError("crash")
        ):
            with self.assertRaises(OSError):
                self._replace(host,second)
        note=self._path(host)/"never-delete.txt"
        note.write_text("MY FILE")
        with self.assertRaisesRegex(ValueError,"edited"):
            up.recover(host,self.profile,"demo")
        self.assertEqual(note.read_text(),"MY FILE")
        self.assertTrue(up._journal(self._state(host),"demo").exists())

    def test_profile_identity_does_not_change_on_same_account(self):
        first=up._profile_identity(self.profile)
        second=up._profile_identity(self.profile)
        self.assertEqual(first,second)
        self.assertEqual(len(first),64)
        self.assertNotIn(str(self.profile),first)

    def test_relocated_profile_cannot_reuse_foreign_receipt_even_if_files_copied(self):
        host="cursor"
        plan=self._package(host)
        self._install(host,plan)
        other=Path(self.fixture_case.tmp.name)/"another-inert-home"
        other.mkdir()
        original=self._state(host)
        moved_state=other/".gasl-managed"/"user"/"hosts"/host
        moved_state.parent.mkdir(parents=True)
        shutil.copytree(original,moved_state)
        new_target=other/".cursor"/"skills"/"demo"
        new_target.parent.mkdir(parents=True)
        shutil.copytree(self._path(host),new_target)
        with patch("user_profile_install._root",side_effect=lambda selected: other):
            with self.assertRaisesRegex(ValueError,"different user profile"):
                up.preview_uninstall(host,other,"demo")
        self.assertTrue(new_target.is_dir())
        self.assertTrue(self._path(host).is_dir())

    @unittest.skipIf(os.name == "nt", "Windows binds profile identity to token SID, not POSIX UID")
    def test_profile_uid_drift_invalidates_receipt(self):
        host="codex"
        plan=self._package(host)
        self._install(host,plan)
        uid=up.os.getuid()
        with patch("user_profile_install.os.getuid",return_value=uid+100000):
            with self.assertRaisesRegex(ValueError,"(different user profile|unsafe owner)"):
                up.preview_uninstall(host,self.profile,"demo")
        self.assertTrue(self._path(host).is_dir())

    def test_real_root_gate_refuses_fake_home_and_never_writes_real_home(self):
        with patch("user_profile_install._root",new=REAL_PROFILE_ROOT_CHECK):
            with self.assertRaisesRegex(ValueError,"(current OS account HOME|Refusing root|current Windows token profile|elevated Windows token)"):
                up._root(self.profile)
        self.assertFalse((self.profile/".agents").exists())
        self.assertFalse((self.profile/".cursor").exists())


    @unittest.skipIf(os.name == "nt", "Windows checks native DACL ACEs, not chmod mode bits")
    def test_world_writable_profile_state_refused_without_changes(self):
        host="cursor"
        plan=self._package(host)
        state=self._state(host)
        state.mkdir(parents=True)
        original_mode=state.stat().st_mode & 0o777
        try:
            state.chmod(0o777)
            with self.assertRaisesRegex(ValueError,"unsafe owner/permissions"):
                self._preview(host,plan)
        finally:
            state.chmod(original_mode)
        self.assertFalse(self._path(host).exists())

    @unittest.skipIf(os.name == "nt", "Windows checks native DACL ACEs, not chmod mode bits")
    def test_world_writable_agent_directory_refused(self):
        host="claude-code"
        plan=self._package(host)
        parent=self._path(host).parent
        parent.mkdir(parents=True)
        original_mode=parent.stat().st_mode & 0o777
        try:
            parent.chmod(0o777)
            with self.assertRaisesRegex(ValueError,"unsafe owner/permissions"):
                self._preview(host,plan)
        finally:
            parent.chmod(original_mode)
        self.assertFalse(self._path(host).exists())

    def test_backup_manifest_changed_requires_rejudgment_and_preserves_active(self):
        host="codex"
        first=self._package(host)
        self._install(host,first)
        second=self._next(host)
        out=self._replace(host,second)
        bid=out["backup_id"]
        manifest=up._manifest(self._state(host),"demo",bid)
        old=manifest.read_text()
        data=json.loads(old)
        data["profile_identity"]="f"*64
        manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,"(different profile|identity mismatch)"):
            up.preview_restore(host,self.profile,"demo",bid)
        self.assertTrue(self._path(host).is_dir())
        self.assertEqual(manifest.read_text(),json.dumps(data))

    def test_crash_during_uninstall_restores_original_user_skill(self):
        host="cursor"
        plan=self._package(host)
        self._install(host,plan)
        before=(self._path(host)/"SKILL.md").read_bytes()
        preview=up.preview_uninstall(host,self.profile,"demo")
        original_new=up._new
        def fail_marker(path,record):
            if "uninstalled" in path.parts:
                raise OSError("crash before user marker")
            return original_new(path,record)
        with patch("sys.stdin.isatty",return_value=True), patch(
            "user_profile_install._new",side_effect=fail_marker
        ):
            with self.assertRaisesRegex(OSError,"crash before user marker"):
                up.uninstall(host,self.profile,"demo",preview["state_binding_id"],
                              reader=self._consent)
        restored=up.recover(host,self.profile,"demo")
        self.assertEqual(restored["status"],"host_user_incomplete_transaction_rolled_back")
        self.assertEqual((self._path(host)/"SKILL.md").read_bytes(),before)

    def test_recovery_rejects_corrupted_other_account_journal(self):
        host="claude-code"
        plan=self._package(host)
        self._install(host,plan)
        state=self._state(host)
        receipt=up._load(up._receipt(state,"demo"))
        up._write_journal(state,host,"demo","install",receipt["transaction"],
                          receipt,None,new_files=receipt["files"])
        journal=up._journal(state,"demo")
        data=json.loads(journal.read_text())
        data["profile_identity"]="0"*64
        journal.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,"different user profile"):
            up.recover(host,self.profile,"demo")
        self.assertTrue(journal.exists())
        self.assertTrue(self._path(host).exists())

    def test_environment_home_spoof_does_not_bypass_passwd_check(self):
        import os
        with patch("user_profile_install._root",new=REAL_PROFILE_ROOT_CHECK):
            with patch.dict(os.environ,{"HOME":str(self.profile)}):
                with self.assertRaisesRegex(ValueError,"(current OS account HOME|current Windows token profile)"):
                    up._root(self.profile)
        self.assertFalse((self.profile/".agents").exists())

    def test_completed_install_journal_recovery_never_uninstalls_new_skill(self):
        host="cursor"
        plan=self._package(host)
        self._install(host,plan)
        state=self._state(host)
        receipt=up._load(up._receipt(state,"demo"))
        up._write_journal(state,host,"demo","install",receipt["transaction"],
                          receipt,None,new_files=receipt["files"])
        result=up.recover(host,self.profile,"demo")
        self.assertEqual(result["status"],"host_user_committed_transaction_finalized")
        self.assertTrue(self._path(host).is_dir())
        self.assertFalse(up._journal(state,"demo").exists())

if __name__=="__main__":
    unittest.main()
