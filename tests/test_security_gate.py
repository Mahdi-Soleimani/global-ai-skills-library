"""Offline security-gate fixtures. No upstream Skill is executed or fetched."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from queue_ingest import git_blob, ingest, make_plan, package_location
from security_gate import audit_local_package
from static_scan import scan_package


class SecurityGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "config").mkdir()
        (self.root / "registry").mkdir()
        (self.root / "private").mkdir()
        (self.root / "config/policy.json").write_text(json.dumps({
            "max_file_size_bytes": 10_000,
            "max_skill_size_bytes": 20_000,
            "public_mirror_spdx_allowlist": ["MIT"],
        }))
        self.files = {"skills/demo/SKILL.md": b"# Demo\nUse this Skill to write safe documentation.\n"}
        self.row = {
            "repository": "Org/Repo", "source_path": "skills/demo/SKILL.md",
            "skill_path": "skills/demo/SKILL.md", "commit_sha": "a" * 40,
            "tree_sha": "b" * 40, "snapshot_status": "verified_commit_pinned",
            "skill_md_blob_sha": git_blob(self.files["skills/demo/SKILL.md"]),
            "license_spdx": "NOASSERTION", "research_leads": [],
        }

    def _make_package(self):
        tree = {"sha": self.row["tree_sha"], "truncated": False, "tree": [
            {"path": path, "type": "blob", "mode": "100644", "size": len(data),
             "sha": git_blob(data)} for path, data in self.files.items()
        ]}
        plan = make_plan(self.row, tree, json.loads((self.root / "config/policy.json").read_text()))
        ingest(self.root, plan, fetch=lambda plan, item: self.files[item["path"]],
               manifest_path=self.root / "private/on-demand-manifest.json")
        folder = package_location(self.root, plan)
        return folder, folder / "source.json"

    def test_verified_package_scanned_without_install_or_execution(self):
        folder, source = self._make_package()
        result = audit_local_package("source-demo", root=self.root, record=self.row)
        self.assertTrue(result["integrity_ok"])
        self.assertTrue(result["pinned_skill_blob_ok"])
        self.assertEqual(result["security_status"], "no_obvious_static_flags_not_approved")
        self.assertFalse(result["installation_allowed"])
        self.assertFalse(result["execution_allowed"])
        self.assertFalse(result["sandbox_executed"])
        self.assertTrue((self.root / result["security_report_path"]).exists())
        self.assertEqual(json.loads(source.read_text())["install_status"], "not_approved")
        self.assertEqual(result["finding_count"], 0)

    def test_suspicious_code_is_flagged_without_running(self):
        self.files["skills/demo/scripts/run.py"] = b"import os\nos.system('echo DO_NOT_EXECUTE')\n"
        _, source = self._make_package()
        result = audit_local_package("source-demo", root=self.root, record=self.row)
        self.assertEqual(result["security_status"], "manual_review_required")
        report = json.loads((self.root / result["security_report_path"]).read_text())
        self.assertTrue(any(f["rule_id"] == "SHELL_OR_PROCESS_SPAWN" for f in report["findings"]))
        self.assertFalse(report["execution_performed"])

    def test_info_only_test_harness_signals_remain_visible_without_actionable_flag(self):
        self.files["skills/demo/tests/validate.test.cjs"] = (
            b"const {spawnSync} = require('node:child_process');\n"
            b"const result = spawnSync('node', ['--version']);\n"
        )
        _, _ = self._make_package()
        result = audit_local_package("source-demo", root=self.root, record=self.row)
        self.assertTrue(result["integrity_ok"])
        self.assertEqual(result["security_status"], "no_obvious_static_flags_not_approved")
        self.assertEqual(result["actionable_finding_count"], 0)
        self.assertGreaterEqual(result["informational_finding_count"], 1)
        self.assertFalse(result["installation_allowed"])
        self.assertFalse(result["execution_allowed"])

    def test_changed_skill_body_cannot_be_hidden_by_rewriting_cached_sha256(self):
        folder, source = self._make_package()
        main = folder / "SKILL.md"
        main.write_text("# altered to another instruction\n")
        metadata = json.loads(source.read_text())
        for item in metadata["files"]:
            if item["source_path"] == "skills/demo/SKILL.md":
                item["sha256"] = hashlib.sha256(main.read_bytes()).hexdigest()
                item["size_bytes"] = main.stat().st_size
        source.write_text(json.dumps(metadata))
        result = audit_local_package("source-demo", root=self.root, record=self.row)
        self.assertFalse(result["pinned_skill_blob_ok"])
        self.assertFalse(result["integrity_ok"])
        self.assertEqual(result["security_status"], "integrity_failed")
        self.assertEqual(json.loads(source.read_text())["security_status"], "integrity_failed")

    def test_unsafe_manifest_path_is_never_read(self):
        _, source = self._make_package()
        secret = self.root / "private/secret.txt"
        secret.write_text("confidential test data")
        metadata = json.loads(source.read_text())
        metadata["files"].append({
            "source_path": "arbitrary", "local_path": "private/secret.txt",
            "size_bytes": secret.stat().st_size,
            "sha256": hashlib.sha256(secret.read_bytes()).hexdigest(),
        })
        source.write_text(json.dumps(metadata))
        report = scan_package(source, root=self.root)
        self.assertFalse(report["integrity_ok"])
        self.assertEqual(report["security_status"], "integrity_failed")
        self.assertTrue(any(x["status"] == "unsafe_missing_or_nonregular_path" for x in report["integrity"]))
        self.assertNotIn("confidential test data", json.dumps(report))

    def test_unlisted_file_prevents_clean_scan(self):
        folder, source = self._make_package()
        (folder / "unexpected.py").write_text("print('not inventoried')")
        report = scan_package(source, root=self.root)
        self.assertFalse(report["integrity_ok"])
        self.assertTrue(any(x["status"] == "unlisted_package_file" for x in report["integrity"]))

    def test_symlink_to_file_outside_package_is_rejected(self):
        self.files["skills/demo/scripts/handler.py"] = b"# harmless python\n"
        folder, source = self._make_package()
        external = self.root / "private/no_read.py"
        external.write_text("PRIVATE_MAGIC_SHOULD_NOT_BE_READ")
        target = folder / "scripts/handler.py"
        target.unlink()
        target.symlink_to(external)
        report = scan_package(source, root=self.root)
        self.assertFalse(report["integrity_ok"])
        self.assertTrue(any(x["status"] == "unsafe_missing_or_nonregular_path" for x in report["integrity"]))
        self.assertNotIn("PRIVATE_MAGIC_SHOULD_NOT_BE_READ", json.dumps(report))

    def test_legacy_package_missing_blob_metadata_is_verified_then_upgraded(self):
        _, source = self._make_package()
        metadata = json.loads(source.read_text())
        metadata.pop("skill_md_blob_sha", None)
        source.write_text(json.dumps(metadata))
        result = audit_local_package("source-demo", root=self.root, record=self.row)
        self.assertTrue(result["pinned_skill_blob_ok"])
        self.assertTrue(result["integrity_ok"])
        self.assertEqual(json.loads(source.read_text())["skill_md_blob_sha"],
                         self.row["skill_md_blob_sha"])

    def test_valid_legacy_checkpoint_sidecar_does_not_taint_verified_skill(self):
        folder, source = self._make_package()
        meta = json.loads(source.read_text())
        checkpoint = {
            "repository": meta["repository"],
            "commit_sha": meta["commit_sha"],
            "source_skill_path": meta["source_skill_path"],
            "files": {item["source_path"]: item for item in meta["files"]},
            "updated_at": "2026-11-20T12:00:00+00:00",
        }
        (folder / ".gasl-download-checkpoint.json").write_text(json.dumps(checkpoint))
        result = audit_local_package("source-demo", root=self.root, record=self.row)
        self.assertEqual(result["recognized_legacy_internal_checkpoints"], 1)
        self.assertTrue(result["integrity_ok"])

    def test_tampered_checkpoint_is_still_unlisted_and_blocks_integrity(self):
        folder, source = self._make_package()
        meta = json.loads(source.read_text())
        checkpoint = {
            "repository": meta["repository"],
            "commit_sha": meta["commit_sha"],
            "source_skill_path": meta["source_skill_path"],
            "files": {item["source_path"]: dict(item) for item in meta["files"]},
            "updated_at": "2026-11-20T12:00:00+00:00",
        }
        first = next(iter(checkpoint["files"].values()))
        first["sha256"] = "0" * 64
        (folder / ".gasl-download-checkpoint.json").write_text(json.dumps(checkpoint))
        result = audit_local_package("source-demo", root=self.root, record=self.row)
        self.assertFalse(result["integrity_ok"])
        self.assertEqual(result["security_status"], "integrity_failed")
        self.assertEqual(result["recognized_legacy_internal_checkpoints"], 0)

    def test_unique_older_package_folder_can_be_audited_without_moving_it(self):
        folder, _ = self._make_package()
        legacy = folder.parent / ("demo@" + self.row["commit_sha"][:12])
        folder.rename(legacy)
        source = legacy / "source.json"
        metadata = json.loads(source.read_text())
        for item in metadata["files"]:
            item["local_path"] = item["local_path"].replace(folder.name, legacy.name)
        metadata.pop("skill_md_blob_sha", None)
        source.write_text(json.dumps(metadata))
        result = audit_local_package("source-demo", root=self.root, record=self.row)
        self.assertEqual(result["local_package_path"], legacy.relative_to(self.root).as_posix())
        self.assertTrue(result["integrity_ok"])
        self.assertEqual(json.loads(source.read_text())["skill_md_blob_sha"],
                         self.row["skill_md_blob_sha"])

    def test_wrong_source_identity_rejected(self):
        _, source = self._make_package()
        metadata = json.loads(source.read_text())
        metadata["commit_sha"] = "f" * 40
        source.write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError, "identity/integrity"):
            audit_local_package("source-demo", root=self.root, record=self.row)

    def test_audit_requires_previously_downloaded_package(self):
        with self.assertRaisesRegex(FileNotFoundError, "Download this pinned Skill first"):
            audit_local_package("source-demo", root=self.root, record=self.row)
        self.assertFalse((self.root / "catalog").exists())

    def test_symlinked_source_file_is_rejected_before_parsing(self):
        folder, source = self._make_package()
        external = self.root / "private/external.json"
        external.write_text('{"files":[]}')
        source.unlink()
        source.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            scan_package(source, root=self.root)

    def test_truncated_or_size_mismatched_file_is_not_scanned_as_clean(self):
        folder, source = self._make_package()
        (folder / "SKILL.md").write_bytes(b"# small")
        result = scan_package(source, root=self.root)
        self.assertEqual(result["security_status"], "integrity_failed")
        self.assertTrue(any(x["status"] == "size_mismatch_or_scan_limit_exceeded" for x in result["integrity"]))


if __name__ == "__main__":
    unittest.main()
