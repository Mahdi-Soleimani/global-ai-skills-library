"""Phase 52: terminal-only user-profile Wizard, synthetic HOME and inert Skills."""
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))

from tests.test_user_profile_install import UserProfileInstallTests
import user_profile_wizard as wizard
import user_profile_install as up


class UserProfileWizardTests(unittest.TestCase):
    def setUp(self):
        self.case=UserProfileInstallTests("test_readonly_preview_all_three_hosts_and_paths")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.fixture=self.case.fixture
        self.root=self.case.root
        self.profile=self.case.profile
        self.id=self.fixture.row["source_record_id"]
        self.wizard_root_patch=patch("user_profile_wizard._root",
                                     side_effect=self.case._fake_root)
        self.wizard_root_patch.start()
        self.addCleanup(self.wizard_root_patch.stop)

    def prepare(self,host):
        return self.case._package(host)

    def preview(self,host):
        return wizard.inspect_handoff(self.id,self.profile,host,root=self.root,
                                      lookup=self.fixture.lookup)

    def invoke(self,host,*,action="install",reader=None,download=False,printer=lambda x:None):
        return wizard.install_from_explorer(
            self.id,self.profile,host,action=action,
            root=self.root,lookup=self.fixture.lookup,
            reader=reader or self.case._consent,printer=printer,
            download_if_missing=download)

    def test_readonly_preview_for_all_host_profiles(self):
        for host in up.HOSTS:
            with self.subTest(host=host):
                self.prepare(host)
                result=self.preview(host)
                self.assertTrue(result["requires_current_os_home"])
                self.assertTrue(result["current_os_home_verified"])
                self.assertEqual(result["scope"],"user")
                self.assertEqual(result["host"],host)
                self.assertFalse(result["real_host_modified"])
                self.assertFalse(result["skill_executed"])
                self.assertEqual(result["cursor_may_sync_to_cloud_agents"],host=="cursor")
                self.assertFalse(self.case._path(host).exists())

    def test_no_tty_refuses_every_host_before_any_write(self):
        for host in up.HOSTS:
            with self.subTest(host=host):
                self.prepare(host)
                with patch("sys.stdin.isatty",return_value=False):
                    with self.assertRaisesRegex(ValueError,"local interactive TTY"):
                        self.invoke(host)
                self.assertFalse(self.case._path(host).exists())

    def test_existing_verified_private_zip_install_requires_exact_scope_phrase(self):
        for host in up.HOSTS:
            with self.subTest(host=host):
                self.prepare(host)
                texts=[]
                with patch("sys.stdin.isatty",return_value=True):
                    result=self.invoke(host,printer=texts.append)
                self.assertEqual(result["status"],"host_user_wizard_completed")
                self.assertTrue(result["user_profile_modified"])
                self.assertTrue(self.case._path(host).is_dir())
                self.assertTrue(any("GLOBAL USER PROFILE" in x for x in texts))
                self.assertFalse(result["skill_executed"])

    def test_cursor_cloud_sync_warning_is_present_before_approval(self):
        self.prepare("cursor")
        prompts=[]
        messages=[]
        def reader(prompt):
            prompts.append(prompt)
            return self.case._consent(prompt)
        with patch("sys.stdin.isatty",return_value=True):
            self.invoke("cursor",reader=reader,printer=messages.append)
        self.assertTrue(any("CURSOR WARNING" in x and "Cloud Agents" in x
                            for x in messages))
        self.assertTrue(any("CURSOR-SYNC-RISK" in x for x in prompts))
        self.assertTrue(any("ALL PROJECTS" in x for x in prompts))

    def test_missing_private_zip_requires_two_separate_approvals(self):
        host="claude-code"
        plan=self.prepare(host)
        folder=self.root/"private"/"install-bundles"
        (folder/(plan+".zip")).unlink()
        (folder/(plan+".json")).unlink()
        prompts=[]
        def reader(prompt):
            prompts.append(prompt)
            return prompt.split("Type EXACTLY: ",1)[1].split("\n",1)[0]
        with patch("sys.stdin.isatty",return_value=True):
            result=self.invoke(host,reader=reader)
        self.assertEqual(len(prompts),2)
        self.assertIn("PREPARE USER-WIDE",prompts[0])
        self.assertIn("INSTALL USER PROFILE",prompts[1])
        self.assertTrue(result["user_profile_modified"])

    def test_optional_pinned_download_requires_independent_consent(self):
        host="codex"
        plan=self.prepare(host)
        shutil.rmtree(self.case.fixture_case.folder)
        calls=[]
        def download(source_id,root,execute):
            calls.append((source_id,root,execute))
            self.fixture._package()
            return {"status":"downloaded","executed":False,"installed":False}
        prompts=[]
        def reader(prompt):
            prompts.append(prompt)
            return prompt.split("Type EXACTLY: ",1)[1].split("\n",1)[0]
        with patch("sys.stdin.isatty",return_value=True), patch(
            "on_demand.download_skill",side_effect=download
        ):
            result=self.invoke(host,download=True,reader=reader)
        self.assertEqual(calls,[(self.id,self.root,True)])
        self.assertEqual(len(prompts),2)
        self.assertIn("DOWNLOAD USER-WIDE",prompts[0])
        self.assertIn("INSTALL USER PROFILE",prompts[1])
        self.assertTrue(self.case._path(host).exists())
        self.assertTrue(result["user_profile_modified"])

    def test_declined_download_preserves_home_and_does_not_network(self):
        host="cursor"
        self.prepare(host)
        shutil.rmtree(self.case.fixture_case.folder)
        with patch("sys.stdin.isatty",return_value=True), patch(
            "on_demand.download_skill",side_effect=AssertionError("network invoked")
        ):
            with self.assertRaisesRegex(ValueError,"not authorized"):
                self.invoke(host,download=True,reader=lambda _:"NO")
        self.assertFalse(self.case._path(host).exists())
        self.assertFalse(self.case._state(host).exists())

    def test_wrong_final_phrase_refused_even_if_package_verified(self):
        host="codex"
        self.prepare(host)
        with patch("sys.stdin.isatty",return_value=True):
            with self.assertRaisesRegex(ValueError,"phrase"):
                self.invoke(host,reader=lambda _: "NO")
        self.assertFalse(self.case._path(host).exists())

    def test_existing_unmanaged_global_skill_is_never_overwritten(self):
        host="claude-code"
        self.prepare(host)
        target=self.case._path(host)
        target.mkdir(parents=True)
        (target/"SKILL.md").write_text("PRIVATE UNMANAGED CONTENT")
        with patch("sys.stdin.isatty",return_value=True):
            with self.assertRaisesRegex(ValueError,"GASL-owned"):
                self.invoke(host,action="replace")
        self.assertEqual((target/"SKILL.md").read_text(),"PRIVATE UNMANAGED CONTENT")

    def test_replace_only_on_explicit_command_retains_old_archive(self):
        host="codex"
        first=self.prepare(host)
        self.case._install(host,first)
        self.case._next(host)
        with patch("sys.stdin.isatty",return_value=True):
            result=self.invoke(host,action="replace")
        self.assertTrue(result["user_profile_modified"])
        self.assertEqual(result["action"],"replace")
        self.assertEqual(len(up.list_backups(host,self.profile,"demo")["backups"]),1)

    def test_corrupt_existing_zip_refused_without_rebuilding(self):
        host="cursor"
        plan=self.prepare(host)
        archive=self.root/"private"/"install-bundles"/(plan+".zip")
        archive.write_bytes(b"UNTRUSTED")
        with patch("sys.stdin.isatty",return_value=True):
            with self.assertRaises(ValueError):
                self.invoke(host,reader=lambda _:self.fail("must not ask for consent"))
        self.assertEqual(archive.read_bytes(),b"UNTRUSTED")
        self.assertFalse(self.case._path(host).exists())

    def test_unknown_host_and_no_real_home_crossover(self):
        with self.assertRaises(ValueError):
            self.preview("unknown")
        with self.assertRaisesRegex(ValueError,"Only selected inert fake HOME"):
            wizard.inspect_handoff(self.id,ROOT,"codex",root=self.root,
                                   lookup=self.fixture.lookup)


if __name__=="__main__":
    unittest.main()
