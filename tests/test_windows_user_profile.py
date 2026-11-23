"""Native Windows SID and NTFS ACL checks; no real Agent profile is modified."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT/"tools"))

import windows_user_profile as wp
import user_profile_install as up


@unittest.skipUnless(os.name == "nt", "Native Windows token and ACL tests")
class WindowsUserProfileSecurityTests(unittest.TestCase):
    def setUp(self):
        self.current = wp.current_profile()
        self.sid = self.current["sid"]
        self.home = self.current["profile"]

    def test_current_profile_matches_token_environment_and_home(self):
        self.assertRegex(self.sid, r"^S-1-")
        self.assertEqual(self.current["drive_type"], 3)
        self.assertEqual(os.path.normcase(str(self.home)),
                         os.path.normcase(str(Path.home().resolve(strict=True))))
        self.assertEqual(os.path.normcase(str(self.home)),
                         os.path.normcase(str(Path(os.environ["USERPROFILE"]).resolve(strict=True))))
        self.assertTrue(self.current["acl"]["owner_sid_matches"])
        self.assertTrue(self.current["acl"]["dacl_present"])
        self.assertEqual(self.current["acl"]["untrusted_write_aces"], 0)

    def test_profile_identity_is_opaque_and_stable(self):
        first = wp.profile_identity(self.home)
        second = wp.profile_identity(self.home)
        self.assertEqual(first, second)
        self.assertRegex(first, r"^[a-f0-9]{64}$")
        self.assertNotIn(self.sid, first)
        self.assertNotIn(str(self.home), first)

    def test_owned_disposable_home_and_tree_pass_sid_acl_checks(self):
        with tempfile.TemporaryDirectory(prefix="gasl-home-acl-") as temp:
            root = Path(temp)
            (root/"nested").mkdir()
            (root/"nested"/"SKILL.md").write_text("INERT WINDOWS PROFILE FIXTURE")
            self.assertTrue(wp.verify_owned_path(root, self.sid, directory=True))
            self.assertTrue(wp.verify_owned_tree(root, self.sid))
            os.link(root/"nested"/"SKILL.md", root/"hardlink.txt")
            with self.assertRaisesRegex(ValueError, "hard-link alias"):
                wp.verify_owned_tree(root, self.sid)
            self.assertEqual(
                wp.profile_identity(root),
                wp.profile_identity(root),
            )

    def test_wrong_owner_sid_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="gasl-home-owner-") as temp:
            with self.assertRaisesRegex(ValueError, "not owned by the current account SID"):
                wp.verify_owned_path(Path(temp), "S-1-5-21-0-0-0-99999", directory=True)

    def test_everyone_write_ace_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="gasl-home-broad-acl-") as temp:
            root = Path(temp)
            grant = subprocess.run(
                ["icacls", str(root), "/grant", "*S-1-1-0:(OI)(CI)M"],
                capture_output=True, text=True,
            )
            if grant.returncode:
                self.skipTest("Runner does not allow editing ACLs on disposable temp directory")
            try:
                with self.assertRaisesRegex(ValueError, "untrusted SID"):
                    wp.verify_owned_path(root, self.sid, directory=True)
            finally:
                subprocess.run(
                    ["icacls", str(root), "/remove:g", "*S-1-1-0"],
                    capture_output=True, text=True,
                )

    def test_reparse_point_in_profile_path_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="gasl-home-junction-") as temp:
            base = Path(temp)
            outside = base/"outside"
            outside.mkdir()
            junction = base/"redirect"
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
                capture_output=True, text=True,
            )
            if result.returncode:
                self.skipTest("Runner does not permit disposable NTFS Junction creation")
            try:
                self.assertTrue(junction.is_junction())
                with self.assertRaisesRegex(ValueError, "reparse point"):
                    wp.assert_no_reparse_components(junction/"child")
            finally:
                junction.rmdir()

    def test_user_installer_requires_explicit_native_ci_gate_until_acceptance(self):
        with patch.dict(os.environ, {"GASL_ENABLE_WINDOWS_USER_PROFILE_CI": ""}):
            with self.assertRaisesRegex(ValueError, "disabled pending native SID/ACL"):
                up._root(self.home)

    def test_user_installer_accepts_only_non_elevated_current_token_profile(self):
        with patch("windows_user_profile.current_profile",
                   return_value={**self.current, "elevated": False}):
            self.assertEqual(up._root(self.home), self.home)
        with patch("windows_user_profile.current_profile",
                   return_value={**self.current, "elevated": True}):
            with self.assertRaisesRegex(ValueError, "elevated Windows token"):
                up._root(self.home)

    def test_user_installer_rejects_another_existing_directory(self):
        with tempfile.TemporaryDirectory(prefix="gasl-not-home-") as temp:
            with patch("windows_user_profile.current_profile",
                       return_value={**self.current, "elevated": False}):
                with self.assertRaisesRegex(ValueError, "current Windows token profile"):
                    up._root(Path(temp))

    def test_thread_impersonation_is_rejected_before_profile_identity(self):
        with patch("windows_user_profile._reject_thread_impersonation",
                   side_effect=ValueError("Refusing an impersonated Windows thread token")):
            with self.assertRaisesRegex(ValueError, "impersonated Windows thread"):
                wp._token_identity()

    def test_windows_cli_imports_without_posix_account_modules(self):
        self.assertIsNone(up.pwd)
        self.assertTrue(wp.current_profile()["sid"].startswith("S-1-"))


if __name__ == "__main__":
    unittest.main()
