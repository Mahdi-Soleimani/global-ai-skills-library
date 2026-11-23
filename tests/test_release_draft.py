"""Synthetic private MVP release packaging. Never publish a public Release."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools"))

from release_draft import (
    STATIC_FILES, inspect_release, build_release_draft, verify_release_draft
)


class ReleaseDraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gasl-release-draft-fixture-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/"repository"
        self.root.mkdir()
        subprocess.run(["git","init","-q",str(self.root)],check=True,capture_output=True)
        for name in STATIC_FILES:
            path = self.root/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text("Fixture file " + name + "\n",encoding="utf-8")
        code=self.root/"tools"/"gasl.py"
        code.parent.mkdir(exist_ok=True)
        code.write_text("print('INERT SOURCE - NOT EXECUTED')\n")
        config=self.root/"config"/"taxonomy.json"
        config.parent.mkdir(exist_ok=True)
        config.write_text('{"categories":[]}\n')
        (self.root/".gitignore").write_text("private/\n")
        subprocess.run(["git","-C",str(self.root),"add","-A"],check=True,capture_output=True)
        self.commit()

    def commit(self):
        subprocess.run(["git","-C",str(self.root),"-c","user.name=GASL Test",
                        "-c","user.email=test@example.invalid","commit","-qm","synthetic fixture"],
                       check=True,capture_output=True)

    def test_inspect_is_readonly_and_public_release_blocked(self):
        report=inspect_release(self.root)
        self.assertEqual(report["status"],"local_release_readiness_only")
        self.assertFalse(report["project_license_declared"])
        self.assertFalse(report["public_release_allowed"])
        self.assertIn("project_license_not_selected",report["public_release_blockers"])
        self.assertGreater(report["tracked_package_files"],10)
        self.assertFalse((self.root/"private").exists())

    def test_build_and_verify_private_deterministic_zip(self):
        (self.root/"personal-secret.env").write_text("DO_NOT_INCLUDE")
        built=build_release_draft(self.root)
        self.assertTrue(built["relative_archive"].startswith("private/release-drafts/"))
        self.assertFalse(built["public_release_allowed"])
        verified=verify_release_draft(self.root)
        self.assertEqual(verified["archive_sha256"],built["archive_sha256"])
        path=self.root/built["relative_archive"]
        with zipfile.ZipFile(path) as zf:
            names=zf.namelist()
            self.assertIn("gasl-mvp/tools/gasl.py",names)
            self.assertIn("gasl-mvp/web/index.html",names)
            self.assertIn("gasl-mvp/RELEASE-MANIFEST.json",names)
            self.assertFalse(any("personal-secret" in name for name in names))
            self.assertFalse(any("private/" in name for name in names))
            manifest=json.loads(zf.read("gasl-mvp/RELEASE-MANIFEST.json"))
            self.assertFalse(manifest["public_release_allowed"])
        path.unlink()
        (path.parent/(path.name+".json")).unlink()
        built_again=build_release_draft(self.root)
        self.assertEqual(built_again["archive_sha256"],built["archive_sha256"])

    def test_refuses_overwrite_existing_draft(self):
        build_release_draft(self.root)
        with self.assertRaisesRegex(ValueError, "already exists"):
            build_release_draft(self.root)

    def test_detects_altered_zip_and_preserves_it(self):
        result=build_release_draft(self.root)
        file=self.root/result["relative_archive"]
        file.write_bytes(b"UNTRUSTED REPLACEMENT")
        with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
            verify_release_draft(self.root)
        self.assertEqual(file.read_bytes(),b"UNTRUSTED REPLACEMENT")

    def test_dirty_tracked_file_refuses_before_private_write(self):
        (self.root/"README.md").write_text("Edited after commit")
        with self.assertRaisesRegex(ValueError, "uncommitted"):
            build_release_draft(self.root)
        self.assertFalse((self.root/"private").exists())

    def test_tracked_symlink_refused_and_external_file_preserved(self):
        original=self.root/"README.md"
        original.unlink()
        outside=Path(self.tmp.name)/"outside-secret.txt"
        outside.write_text("DO NOT READ")
        original.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            inspect_release(self.root)
        self.assertEqual(outside.read_text(),"DO NOT READ")

    def test_untracked_files_and_private_directory_never_included(self):
        (self.root/"tools"/"hidden.py").write_text("print('private')\n")
        (self.root/"private"/"secret").parent.mkdir()
        (self.root/"private"/"secret").write_text("MY PRIVATE KEY")
        built=build_release_draft(self.root)
        with zipfile.ZipFile(self.root/built["relative_archive"]) as zf:
            data=b"\n".join(zf.read(x) for x in zf.namelist())
            self.assertNotIn(b"MY PRIVATE KEY",data)
            self.assertNotIn(b"private')",data)

    def test_author_provided_project_license_included_but_no_public_autopublish(self):
        (self.root/"LICENSE").write_text("Synthetic user-supplied license\n")
        subprocess.run(["git","-C",str(self.root),"add","LICENSE"],
                       check=True,capture_output=True)
        self.commit()
        report=inspect_release(self.root)
        self.assertTrue(report["project_license_declared"])
        self.assertFalse(report["public_release_allowed"])
        result=build_release_draft(self.root)
        with zipfile.ZipFile(self.root/result["relative_archive"]) as zf:
            self.assertIn("gasl-mvp/LICENSE",zf.namelist())

    def test_invalid_git_root_fails_before_read(self):
        folder=Path(self.tmp.name)/"not-git"
        folder.mkdir()
        with self.assertRaises(ValueError):
            inspect_release(folder)

    def test_missing_required_tracked_runtime_file_refused(self):
        subprocess.run(["git","-C",str(self.root),"rm","web/index.html"],
                       check=True,capture_output=True)
        self.commit()
        with self.assertRaisesRegex(ValueError,"Required runtime"):
            inspect_release(self.root)


if __name__ == "__main__":
    unittest.main()
