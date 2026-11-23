"""Synthetic tests for local terminal installation handoff from Explorer.

No real user Git projects, Codex profiles, or third-party Skill code are used.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools"))

from tests import test_codex_project_install as fixtures
from codex_explorer_handoff import (
    inspect_handoff, install_from_explorer, _prepare_phrase,
)
from codex_project_install import _install_phrase, _replace_phrase, _receipt
from install_bundle import verify_private_bundle
from install_lifecycle import plan_install


class CodexExplorerHandoffTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.ProjectInstallTests("test_genuine_install_and_uninstall_in_temporary_project")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root = self.case.fixture.root
        self.lookup = self.case.fixture.lookup
        self.id = self.case.fixture.row["source_record_id"]
        self.project = self.case.project
        self.target = self.case.target()

    def inspect(self):
        return inspect_handoff(self.id, self.project, root=self.root, lookup=self.lookup)

    def run_wizard(self, reader=None, action="install"):
        return install_from_explorer(
            self.id, self.project, action=action, root=self.root,
            lookup=self.lookup, reader=reader, printer=lambda _: None)

    def test_readonly_preview_does_not_mutate_project(self):
        result = self.inspect()
        self.assertEqual(result["schema"], "gasl-codex-explorer-install-handoff-v1")
        self.assertEqual(result["agent"], "codex")
        self.assertEqual(result["scope"], "project")
        self.assertEqual(result["plan_id"], self.case.plan_id)
        self.assertTrue(result["eligible_for_bundle_preparation"])
        self.assertTrue(result["local_package_verified"])
        self.assertFalse(result["installation_performed"])
        self.assertFalse(result["real_agent_paths_modified"])
        self.assertNotIn(str(self.project), json.dumps(result))
        self.assertFalse((self.project/".agents").exists())

    def test_without_actual_tty_never_installs_even_with_forged_reader(self):
        with patch("sys.stdin.isatty", return_value=False):
            with self.assertRaisesRegex(ValueError, "local interactive TTY"):
                self.run_wizard(reader=lambda _: _install_phrase("demo", self.case.plan_id, "a"*64))
        self.assertFalse(self.target.exists())
        self.assertFalse(_receipt(self.case.state(), "demo").exists())

    def test_existing_verified_zip_installs_only_after_exact_install_phrase(self):
        outputs = []
        with patch("sys.stdin.isatty", return_value=True):
            result = install_from_explorer(
                self.id, self.project, root=self.root, lookup=self.lookup,
                reader=self._answer_install,
                printer=outputs.append)
        self.assertEqual(result["result"]["status"], "codex_project_skill_installed")
        self.assertTrue(self.target.is_dir())
        self.assertTrue(_receipt(self.case.state(), "demo").is_file())
        self.assertTrue(any("requires_human_tty_confirmation" in text for text in outputs))
        self.assertFalse(result["third_party_skill_executed"])
        self.assertFalse(result["user_profile_modified"])

    def _answer_install(self, prompt):
        # Read the actual exact challenge shown by existing installer.
        self.assertIn("Type EXACTLY:", prompt)
        self.assertIn("INSTALL DEMO", prompt)
        return prompt.split("Type EXACTLY: ",1)[1].split("\n",1)[0]

    def test_wrong_consent_preserves_all_real_project_files(self):
        with patch("sys.stdin.isatty", return_value=True):
            with self.assertRaisesRegex(ValueError, "approval phrase"):
                self.run_wizard(reader=lambda _: "WRONG")
        self.assertFalse(self.target.exists())

    def test_missing_zip_requires_two_distinct_live_approvals(self):
        store=self.root/"private"/"install-bundles"
        (store/(self.case.plan_id+".zip")).unlink()
        (store/(self.case.plan_id+".json")).unlink()
        prompts=[]
        def reader(prompt):
            prompts.append(prompt)
            if "PREPARE PRIVATE CODEX ZIP" in prompt:
                return _prepare_phrase(self.case.plan_id)
            return self._answer_install(prompt)
        with patch("sys.stdin.isatty", return_value=True):
            result=self.run_wizard(reader=reader)
        self.assertEqual(len(prompts),2)
        self.assertTrue(self.target.exists())
        self.assertEqual(
            verify_private_bundle(self.case.plan_id,root=self.root)["status"],
            "private_bundle_integrity_verified")
        self.assertTrue(result["installed_by_existing_transactional_installer"])

    def test_declining_zip_preparation_causes_no_agent_or_bundle_write(self):
        store=self.root/"private"/"install-bundles"
        (store/(self.case.plan_id+".zip")).unlink()
        (store/(self.case.plan_id+".json")).unlink()
        with patch("sys.stdin.isatty",return_value=True):
            with self.assertRaisesRegex(ValueError, "was not approved"):
                self.run_wizard(reader=lambda _: "")
        self.assertFalse(self.target.exists())
        self.assertFalse((store/(self.case.plan_id+".zip")).exists())

    def test_missing_pinned_download_fails_before_agent_write(self):
        folder=self.case.folder
        import shutil
        shutil.rmtree(folder)
        with patch("sys.stdin.isatty",return_value=True):
            with self.assertRaisesRegex(ValueError, "unavailable, incomplete"):
                self.run_wizard(reader=lambda _: self.fail("No prompt expected"))
        self.assertFalse(self.target.exists())

    def test_no_silent_overwrite_even_with_signed_zip(self):
        self.target.mkdir(parents=True)
        (self.target/"SKILL.md").write_text("USER OWNED")
        with patch("sys.stdin.isatty",return_value=True):
            with self.assertRaisesRegex(ValueError,"cannot overwrite"):
                self.run_wizard(reader=lambda _: "WRONG")
        self.assertEqual((self.target/"SKILL.md").read_text(),"USER OWNED")

    def test_replace_requires_explicit_action_and_keeps_previous_version(self):
        self.case.matching_install()
        next_bundle = self.case.make_next_bundle(
            b"---\nname: demo\ndescription: New inert version\n---\n# v2\n")
        self.assertNotEqual(next_bundle["plan_id"],self.case.plan_id)
        replacement_id = self.case.fixture.row["source_record_id"]
        # Same source record ID, but fixture points to the new reviewed package.
        # Ensure the new plan is selected, not a stale initial plan.
        with patch("sys.stdin.isatty",return_value=True):
            result=install_from_explorer(
                replacement_id,self.project,action="replace",root=self.root,
                lookup=self.lookup,
                reader=lambda prompt: self._answer_replace(prompt),
                printer=lambda _:None)
        self.assertEqual(result["action"],"replace")
        self.assertTrue(result["result"]["previous_skill_restorable"])
        self.assertTrue(self.target.is_dir())
        self.assertTrue((self.case.state()/"backups"/"demo").is_dir())

    def _answer_replace(self,prompt):
        self.assertIn("REPLACE DEMO",prompt)
        return prompt.split("Type EXACTLY: ",1)[1].split("\n",1)[0]

    def test_wrong_action_or_unknown_git_root_is_refused(self):
        with patch("sys.stdin.isatty",return_value=True):
            with self.assertRaises(ValueError):
                self.run_wizard(action="delete-anything")
        with self.assertRaises(ValueError):
            inspect_handoff(self.id,self.root,root=self.root,lookup=self.lookup)

    def test_invalid_existing_private_zip_fails_closed_not_rebuilt(self):
        path=self.root/"private"/"install-bundles"/(self.case.plan_id+".zip")
        path.write_bytes(b"corrupted by other process")
        with patch("sys.stdin.isatty",return_value=True):
            with self.assertRaises((ValueError,KeyError)):
                self.run_wizard(reader=lambda _:self.fail("Must refuse before approval"))
        self.assertEqual(path.read_bytes(),b"corrupted by other process")
        self.assertFalse(self.target.exists())

    def test_explicit_download_opt_in_refusal_has_no_network_or_host_write(self):
        import shutil
        shutil.rmtree(self.case.folder)
        with patch("sys.stdin.isatty", return_value=True), patch(
            "on_demand.download_skill", side_effect=AssertionError("network must not run")
        ):
            with self.assertRaisesRegex(ValueError, "not approved"):
                install_from_explorer(
                    self.id, self.project, root=self.root, lookup=self.lookup,
                    download_if_missing=True, reader=lambda _: "",
                    printer=lambda _: None)
        self.assertFalse(self.target.exists())

    def test_explicit_pinned_download_uses_independent_consent_then_installs(self):
        import shutil
        shutil.rmtree(self.case.folder)
        requests = []
        def download(src, root, execute):
            requests.append((src, root, execute))
            self.case.fixture._package()
            return {"status": "downloaded", "source_record_id": src,
                    "installed": False, "executed": False}
        prompts = []
        def reader(text):
            prompts.append(text)
            if "DOWNLOAD PINNED SKILL" in text:
                from install_lifecycle import plan_install
                plan = plan_install(self.id,"codex","project",root=self.root,lookup=self.lookup)
                return ("DOWNLOAD PINNED SKILL " + self.id.upper() +
                        " " + plan["pinned_version"]["commit_sha"][:12].upper())
            return self._answer_install(text)
        with patch("sys.stdin.isatty", return_value=True), patch(
            "on_demand.download_skill", side_effect=download
        ):
            result=install_from_explorer(
                self.id,self.project,root=self.root,lookup=self.lookup,
                download_if_missing=True,reader=reader,printer=lambda _:None)
        self.assertEqual(requests,[(self.id,self.root,True)])
        self.assertEqual(len(prompts),2)
        self.assertEqual(result["result"]["status"],"codex_project_skill_installed")

    def test_opt_in_download_is_not_triggered_when_package_is_valid(self):
        with patch("sys.stdin.isatty",return_value=True), patch(
            "on_demand.download_skill", side_effect=AssertionError("unnecessary fetch")
        ):
            result=install_from_explorer(
                self.id,self.project,root=self.root,lookup=self.lookup,
                download_if_missing=True,reader=self._answer_install,printer=lambda _:None)
        self.assertTrue(result["installed_by_existing_transactional_installer"])

    def test_preview_never_needs_tty_and_never_prepares_bundle(self):
        with patch("sys.stdin.isatty",return_value=False):
            preview=self.inspect()
        self.assertEqual(preview["status"],"codex_install_handoff_preview_only")
        self.assertFalse((self.project/".agents").exists())
