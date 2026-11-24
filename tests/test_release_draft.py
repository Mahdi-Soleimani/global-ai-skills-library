"""Synthetic private MVP release packaging. Never publish a public Release."""
import hashlib
import os
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
        subprocess.run(["git","init","-q","--object-format=sha1","--initial-branch=main",str(self.root)],
                       check=True,capture_output=True)
        for key, value in (("core.autocrlf", "false"), ("core.filemode", "false"),
                           ("commit.gpgsign", "false")):
            subprocess.run(["git","-C",str(self.root),"config",key,value],
                           check=True,capture_output=True)
        for name in STATIC_FILES:
            path = self.root/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(("Fixture file " + name + "\n").encode("utf-8"))
        code=self.root/"tools"/"gasl.py"
        code.parent.mkdir(exist_ok=True)
        code.write_bytes(b"print('INERT SOURCE - NOT EXECUTED')\n")
        config=self.root/"config"/"taxonomy.json"
        config.parent.mkdir(exist_ok=True)
        config.write_bytes(b'{"categories":[]}\n')
        (self.root/".gitignore").write_bytes(b"private/\n")
        subprocess.run(["git","-C",str(self.root),"add","-A"],check=True,capture_output=True)
        self.commit()

    def commit(self):
        env = dict(os.environ, GIT_AUTHOR_DATE="2000-01-01T00:00:00+00:00",
                   GIT_COMMITTER_DATE="2000-01-01T00:00:00+00:00",
                   GIT_AUTHOR_NAME="GASL Test", GIT_AUTHOR_EMAIL="test@example.invalid",
                   GIT_COMMITTER_NAME="GASL Test", GIT_COMMITTER_EMAIL="test@example.invalid")
        subprocess.run(["git","-C",str(self.root),"-c","user.name=GASL Test",
                        "-c","user.email=test@example.invalid","commit","-qm","synthetic fixture"],
                       check=True,capture_output=True,env=env)

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

    def test_cross_platform_canonical_golden_digest(self):
        built = build_release_draft(self.root)
        verified = verify_release_draft(self.root)
        self.assertTrue(verified["canonical_archive_encoding_verified"])
        self.assertEqual(built["source_commit"], "1acbffeba382a741282e9c5431e30a9f1e3e7d8f")
        self.assertEqual(built["archive_sha256"], "fd1a3faa4d41191e433e32b966e1a916665cef565f20fa0c8bf6cf172b0a72ef")
        print("CANONICAL_FIXTURE", built["source_commit"], built["archive_sha256"])
        with zipfile.ZipFile(self.root/built["relative_archive"]) as archive:
            self.assertTrue(all(x.compress_type == zipfile.ZIP_STORED for x in archive.infolist()))

    def test_legacy_compressed_archive_content_verified_but_not_canonical(self):
        def change(entries):
            for info, _ in entries:
                info.compress_type = zipfile.ZIP_DEFLATED
            return entries
        self.forge(change)
        report = verify_release_draft(self.root)
        self.assertTrue(report["content_bound_to_commit_tree"])
        self.assertFalse(report["canonical_archive_encoding_verified"])
        self.assertEqual(report["archive_encoding"], "noncanonical_content_verified")

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

    def forge(self, change):
        built = build_release_draft(self.root)
        path = self.root/built["relative_archive"]
        sidecar = path.with_suffix(".zip.json")
        with zipfile.ZipFile(path) as archive:
            entries = [(item, archive.read(item)) for item in archive.infolist()]
        entries = change(entries)
        with zipfile.ZipFile(path, "w") as archive:
            for info, data in entries:
                archive.writestr(info, data)
        meta = json.loads(sidecar.read_bytes())
        meta["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        sidecar.write_text(json.dumps(meta), encoding="utf-8")
        return path

    def test_self_consistent_forged_zip_cannot_claim_original_commit(self):
        def change(entries):
            manifest = json.loads(entries[-1][1])
            for index, (info, data) in enumerate(entries[:-1]):
                if info.filename == "gasl-mvp/tools/gasl.py":
                    altered = b"FORGED SOURCE NOT EXECUTED"
                    entries[index] = (info, altered)
                    row = next(x for x in manifest["files"] if x["path"] == "tools/gasl.py")
                    row.update(bytes=len(altered), sha256=hashlib.sha256(altered).hexdigest())
            entries[-1] = (entries[-1][0], json.dumps(manifest).encode())
            return entries
        path = self.forge(change)
        original = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "committed source tree"):
            verify_release_draft(self.root)
        self.assertEqual(path.read_bytes(), original)

    def test_index_hidden_worktree_change_never_enters_archive(self):
        path = self.root/"tools/gasl.py"
        committed = subprocess.check_output(["git", "-C", str(self.root), "show", "HEAD:tools/gasl.py"])
        subprocess.run(["git", "-C", str(self.root), "update-index", "--assume-unchanged", "tools/gasl.py"],
                       check=True, capture_output=True)
        path.write_bytes(b"PRIVATE LOCAL EDIT")
        result = build_release_draft(self.root)
        with zipfile.ZipFile(self.root/result["relative_archive"]) as archive:
            self.assertEqual(archive.read("gasl-mvp/tools/gasl.py"), committed)
        self.assertTrue(verify_release_draft(self.root)["content_bound_to_commit_tree"])
        self.assertEqual(path.read_bytes(), b"PRIVATE LOCAL EDIT")

    def test_duplicate_sidecar_keys_refused(self):
        result = build_release_draft(self.root)
        path = self.root/result["relative_archive"]
        sidecar = path.with_suffix(".zip.json")
        raw = sidecar.read_text()
        sidecar.write_text(raw.replace('"schema":', '"schema":"forged","schema":', 1))
        with self.assertRaisesRegex(ValueError, "Duplicate release JSON"):
            verify_release_draft(self.root)

    def test_oversized_compressed_manifest_refused_before_decode(self):
        from release_draft import MAX_MANIFEST_BYTES
        path = self.forge(lambda entries: entries[:-1] + [
            (entries[-1][0], b" " * (MAX_MANIFEST_BYTES + 1))])
        with self.assertRaisesRegex(ValueError, "oversized draft archive member"):
            verify_release_draft(self.root)
        self.assertTrue(path.exists())

    def test_hardlinked_draft_refused_without_modification(self):
        built = build_release_draft(self.root)
        path = self.root/built["relative_archive"]
        alias = Path(self.tmp.name)/"alias.zip"
        os.link(path, alias)
        with self.assertRaisesRegex(ValueError, "Unsafe or oversized release record"):
            verify_release_draft(self.root)
        self.assertEqual(path.read_bytes(), alias.read_bytes())

    def test_missing_manifest_entry_cannot_be_rehashed_as_valid_release(self):
        def change(entries):
            manifest = json.loads(entries[-1][1])
            manifest["files"] = [x for x in manifest["files"] if x["path"] != "README.md"]
            return [(i, d) for i, d in entries[:-1] if i.filename != "gasl-mvp/README.md"] + [
                (entries[-1][0], json.dumps(manifest).encode())]
        self.forge(change)
        with self.assertRaisesRegex(ValueError, "committed source tree"):
            verify_release_draft(self.root)

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
