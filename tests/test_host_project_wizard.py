"""Phase 51 terminal-only Cursor/Claude wizard, disposable inert fixture tests."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))

from tests import test_host_project_install as fixture
import host_project_install as host_engine
from host_project_wizard import inspect_handoff,install_from_explorer


class HostProjectWizardTests(unittest.TestCase):
    def setUp(self):
        self.case=fixture.HostProjectInstallTests(
            "test_preview_and_fresh_real_file_install_both_host_layouts")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root=self.case.root
        self.project=self.case.project
        self.source=self.case.source_id

    def preview(self,host):
        return inspect_handoff(self.source,self.project,host,root=self.root,
                               lookup=self.case.fixture.lookup)

    def wizard(self,host,*,action="install",reader=None,download_if_missing=False):
        return install_from_explorer(
            self.source,self.project,host,action=action,
            root=self.root,lookup=self.case.fixture.lookup,
            reader=reader or self.case.consent,
            printer=lambda _:None,
            download_if_missing=download_if_missing)

    def test_readonly_source_preview_for_both_hosts(self):
        for host in host_engine.HOSTS:
            with self.subTest(host=host):
                self.case.setup_host(host)
                result=self.preview(host)
                self.assertEqual(result["host"],host)
                self.assertTrue(result["can_prepare_zip"])
                self.assertTrue(result["package_integrity_verified"])
                self.assertFalse(result["real_host_modified"])
                self.assertFalse(result["host_discovery_independently_verified"])
                self.assertFalse(self.case.target(host).exists())

    def test_tty_only_no_forged_approval(self):
        for host in host_engine.HOSTS:
            with self.subTest(host=host):
                self.case.setup_host(host)
                with patch("sys.stdin.isatty",return_value=False):
                    with self.assertRaisesRegex(ValueError,"local interactive TTY"):
                        self.wizard(host)
                self.assertFalse(self.case.target(host).exists())

    def test_wizard_installs_existing_verified_zip_in_temporary_project(self):
        for host in host_engine.HOSTS:
            with self.subTest(host=host):
                self.case.setup_host(host)
                with patch("sys.stdin.isatty",return_value=True):
                    result=self.wizard(host)
                self.assertEqual(result["status"],"host_project_wizard_completed")
                self.assertTrue(self.case.target(host).exists())
                self.assertFalse(result["user_profile_modified"])
                self.assertFalse(result["skill_executed"])

    def test_missing_zip_requires_separate_packaging_and_install_approvals(self):
        for host in host_engine.HOSTS:
            with self.subTest(host=host):
                plan=self.case.setup_host(host)
                folder=self.root/"private"/"install-bundles"
                (folder/(plan+".zip")).unlink()
                (folder/(plan+".json")).unlink()
                prompts=[]
                def reader(prompt):
                    prompts.append(prompt)
                    return prompt.split("Type EXACTLY: ",1)[1].split("\n",1)[0]
                with patch("sys.stdin.isatty",return_value=True):
                    result=self.wizard(host,reader=reader)
                self.assertEqual(len(prompts),2)
                self.assertIn("PREPARE",prompts[0])
                self.assertIn("INSTALL",prompts[1])
                self.assertTrue(self.case.target(host).exists())
                self.assertEqual(result["action"],"install")

    def test_missing_download_is_opt_in_and_requires_three_distinct_approvals(self):
        import shutil
        host="cursor"
        self.case.setup_host(host)
        shutil.rmtree(self.case.fixture.content_folder) if hasattr(
            self.case.fixture,"content_folder") else shutil.rmtree(self.case.case.folder)
        calls=[]
        def fake_download(source_id,root,execute):
            calls.append((source_id,root,execute))
            self.case.fixture._package()
            return {"status":"downloaded","installed":False,"executed":False}
        prompts=[]
        def reader(prompt):
            prompts.append(prompt)
            return prompt.split("Type EXACTLY: ",1)[1].split("\n",1)[0]
        with patch("sys.stdin.isatty",return_value=True), patch(
            "on_demand.download_skill",side_effect=fake_download):
            result=self.wizard(host,reader=reader,download_if_missing=True)
        self.assertEqual(calls,[(self.source,self.root,True)])
        self.assertEqual(len(prompts),2)  # existing private ZIP, no prepare needed
        self.assertIn("DOWNLOAD",prompts[0])
        self.assertIn("INSTALL",prompts[1])
        self.assertTrue(self.case.target(host).exists())

    def test_declined_download_stops_without_network_or_host_writes(self):
        import shutil
        host="claude-code"
        self.case.setup_host(host)
        shutil.rmtree(self.case.case.folder)
        with patch("sys.stdin.isatty",return_value=True), patch(
            "on_demand.download_skill",side_effect=AssertionError("network called")):
            with self.assertRaisesRegex(ValueError,"not authorized"):
                self.wizard(host,reader=lambda _: "",download_if_missing=True)
        self.assertFalse(self.case.target(host).exists())

    def test_invalid_zip_cannot_be_silently_recreated(self):
        host="cursor"
        plan=self.case.setup_host(host)
        path=self.root/"private"/"install-bundles"/(plan+".zip")
        path.write_bytes(b"INVALID ARCHIVE")
        with patch("sys.stdin.isatty",return_value=True):
            with self.assertRaises(ValueError):
                self.wizard(host,reader=lambda _:self.fail("No consent expected"))
        self.assertEqual(path.read_bytes(),b"INVALID ARCHIVE")
        self.assertFalse(self.case.target(host).exists())

    def test_explicit_replace_retains_prior_backup(self):
        host="claude-code"
        v1=self.case.setup_host(host)
        self.case.install(host,v1)
        self.case.next_bundle(host)
        with patch("sys.stdin.isatty",return_value=True):
            result=self.wizard(host,action="replace")
        self.assertEqual(result["action"],"replace")
        history=host_engine.list_backups(host,self.project,"demo")
        self.assertEqual(len(history["backups"]),1)

    def test_unmanaged_target_is_never_replaced_by_wizard(self):
        host="cursor"
        self.case.setup_host(host)
        dest=self.case.target(host)
        dest.mkdir(parents=True)
        (dest/"SKILL.md").write_text("PERSONAL")
        with patch("sys.stdin.isatty",return_value=True):
            with self.assertRaisesRegex(ValueError,"GASL-owned"):
                self.wizard(host,action="replace")
        self.assertEqual((dest/"SKILL.md").read_text(),"PERSONAL")

    def test_wrong_approval_phrase_has_no_project_write(self):
        host="cursor"
        self.case.setup_host(host)
        with patch("sys.stdin.isatty",return_value=True):
            with self.assertRaisesRegex(ValueError,"phrase"):
                self.wizard(host,reader=lambda _: "REJECT")
        self.assertFalse(self.case.target(host).exists())

    def test_refuses_unknown_host_and_non_git_root(self):
        if os.name == "nt":
            # Phase 53 deliberately supports Codex through the Windows-native
            # project adapter; it is not an unknown Host on Windows.
            result=self.preview("codex")
            self.assertEqual(result["host"],"codex")
            self.assertFalse(result["real_host_modified"])
        else:
            with self.assertRaises(ValueError):
                self.preview("codex")
        with self.assertRaises(ValueError):
            inspect_handoff(self.source,self.root,"cursor",root=self.root,
                            lookup=self.case.fixture.lookup)


if __name__=="__main__":
    unittest.main()
