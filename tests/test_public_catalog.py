import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_public_catalog import build, package_id


class PublicCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        (self.root / "catalog").mkdir()
        policy = {"public_mirror_spdx_allowlist": ["MIT", "Apache-2.0"]}
        (self.root / "config/policy.json").write_text(json.dumps(policy))
        self.package_dir = self.root / "catalog/demo"
        self.package_dir.mkdir()
        self.skill = b"---\nname: demo\ndescription: demo skill\n---\n"
        self.license = b"MIT License\n"
        (self.package_dir / "SKILL.md").write_bytes(self.skill)
        (self.package_dir / "__upstream_licenses__").mkdir()
        (self.package_dir / "__upstream_licenses__/LICENSE").write_bytes(self.license)
        files = []
        for rel, data in [("SKILL.md", self.skill), ("__upstream_licenses__/LICENSE", self.license)]:
            local = self.package_dir / rel
            files.append({
                "source_path": "skills/demo/" + rel,
                "package_relative_path": rel,
                "local_path": str(local.relative_to(self.root)),
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "git_blob_sha": "a" * 40
            })
        self.meta = {
            "repository": "Org/Repo", "repository_owner": "Org",
            "repository_url": "https://github.com/Org/Repo",
            "source_url": "https://github.com/Org/Repo/blob/" + "b" * 40 + "/skills/demo/SKILL.md",
            "source_skill_path": "skills/demo/SKILL.md", "commit_sha": "b" * 40,
            "tree_sha": "c" * 40, "skill_md_blob_sha": "d" * 40,
            "skill_name": "demo", "license_spdx": "MIT", "license_name": "MIT License",
            "license_url": "https://github.com/Org/Repo/blob/" + "b" * 40 + "/LICENSE",
            "license_evidence": [{"source_path": "LICENSE", "package_path": "__upstream_licenses__/LICENSE", "blob_sha": "e" * 40}],
            "license_status": "license_evidence_bundled_pending_scan",
            "ownership": "third_party", "original_author": None,
            "gasl_claims_exclusive_ownership": False, "execution_performed": False,
            "package_complete": True, "last_static_scan_at": "2026-11-20T00:00:00Z",
            "security_status": "no_obvious_static_flags_not_approved",
            "static_scan_finding_count": 0, "install_status": "not_installed",
            "files": files
        }
        (self.package_dir / "source.json").write_text(json.dumps(self.meta))

    def test_mirrors_with_attribution_and_no_ownership_claim(self):
        summary = build(self.root)
        pid = package_id(self.meta)
        dest = self.root / "public-catalog/packages" / pid
        self.assertEqual(summary["public_package_count"], 1)
        self.assertEqual((dest / "SKILL.md").read_bytes(), self.skill)
        self.assertEqual((dest / "__upstream_licenses__/LICENSE").read_bytes(), self.license)
        attribution = json.loads((dest / "ATTRIBUTION.json").read_text())
        self.assertEqual(attribution["repository"], "Org/Repo")
        self.assertFalse(attribution["gasl_claims_exclusive_ownership"])
        self.assertEqual(attribution["ownership"], "third_party")
        self.assertFalse(attribution["execution_performed"])
        again = build(self.root)
        self.assertEqual(again["public_package_count"], 1)

    def test_unknown_license_stays_in_reference_catalog_not_public_mirror(self):
        self.meta["license_spdx"] = None
        self.meta["license_status"] = "unknown_license_reference_only"
        (self.package_dir / "source.json").write_text(json.dumps(self.meta))
        summary = build(self.root)
        self.assertEqual(summary["public_package_count"], 0)
        self.assertEqual(summary["skipped_by_reason"]["license_not_on_public_mirror_allowlist"], 1)

    def test_missing_license_evidence_is_not_mirrored(self):
        self.meta["license_evidence"] = []
        self.meta["license_status"] = "license_evidence_missing_or_terms_unreviewed"
        (self.package_dir / "source.json").write_text(json.dumps(self.meta))
        summary = build(self.root)
        self.assertEqual(summary["public_package_count"], 0)
        self.assertEqual(summary["skipped_by_reason"]["applicable_license_evidence_not_bundled"], 1)

    def test_static_scan_must_be_completed_before_public_mirror(self):
        self.meta.pop("last_static_scan_at")
        (self.package_dir / "source.json").write_text(json.dumps(self.meta))
        summary = build(self.root)
        self.assertEqual(summary["public_package_count"], 0)
        self.assertEqual(summary["skipped_by_reason"]["static_scan_not_completed"], 1)

    def test_hash_mismatch_fails_closed(self):
        (self.package_dir / "SKILL.md").write_text("changed")
        with self.assertRaises(ValueError):
            build(self.root)


if __name__ == "__main__":
    unittest.main()
