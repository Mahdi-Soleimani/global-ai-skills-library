import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_source_catalog import build


class SourceCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "registry").mkdir()
        (self.root / "registry/discovery-state.json").write_text(json.dumps({
            "repositories": {
                "org/repo": {
                    "repository": "Org/Repo", "repository_url": "https://github.com/Org/Repo",
                    "publisher_account": "Org", "default_branch": "main",
                    "commit_sha": "a" * 40, "tree_sha": "b" * 40, "checked_at": "now",
                    "license_spdx": "MIT", "license_name": "MIT License",
                    "license_files": [{"path": "LICENSE", "blob_sha": "c" * 40}],
                    "source_reports": ["EN-675"],
                    "paths": [{"path": "skills/demo/SKILL.md", "blob_sha": "d" * 40,
                               "classification": "skill_path_candidate"}],
                    "skill_paths": ["skills/demo/SKILL.md"]
                },
                "org/old": {
                    "repository": "Org/Old", "repository_url": "https://github.com/Org/Old",
                    "default_branch": "main", "commit_sha": None, "tree_sha": None,
                    "checked_at": "yesterday", "license_spdx": None, "skill_paths": ["skills/old/SKILL.md"]
                }
            }
        }))
        (self.root / "registry/source-verification.json").write_text(json.dumps({"repositories": {}}))
        (self.root / "registry/skills.json").write_text(json.dumps({"records": []}))

    def test_includes_all_paths_with_source_links_and_non_ownership_attribution(self):
        summary = build(self.root)
        data = json.loads((self.root / "registry/source-catalog.json").read_text())
        records = data["records"]
        self.assertEqual(summary["source_repository_count"], 2)
        self.assertEqual(summary["source_record_count"], 2)
        fresh = next(x for x in records if x["repository"] == "Org/Repo")
        self.assertIn("a" * 40, fresh["source_url"])
        self.assertEqual(fresh["license_spdx"], "MIT")
        self.assertEqual(fresh["license_evidence_path"], "LICENSE")
        self.assertEqual(fresh["ownership"], "third_party")
        self.assertIsNone(fresh["original_author"])
        self.assertFalse(fresh["gasl_claims_exclusive_ownership"])
        old = next(x for x in records if x["repository"] == "Org/Old")
        self.assertEqual(old["snapshot_status"], "legacy_snapshot_unpinned")
        self.assertIn("/main/", old["source_url"])
        self.assertEqual(old["public_mirror_status"], "reference_only_no_redistribution_permission_assumed")
        self.assertTrue((self.root / "registry/source-catalog.csv").exists())

    def test_downloaded_immutable_version_is_kept_separately(self):
        records = [{
            "repository": "Org/Repo", "canonical_repository": "Org/Repo",
            "source_skill_path": "skills/demo/SKILL.md", "commit_sha": "e" * 40,
            "tree_sha": "f" * 40, "license_spdx": "MIT", "package_path": "catalog/demo",
            "package_complete": True, "skill_name": "demo", "downloaded_at": "today"
        }]
        (self.root / "catalog/demo").mkdir(parents=True)
        (self.root / "catalog/demo/source.json").write_text("{}")
        (self.root / "registry/skills.json").write_text(json.dumps({"records": records}))
        summary = build(self.root)
        data = json.loads((self.root / "registry/source-catalog.json").read_text())
        versions = [x for x in data["records"] if x["repository"] == "Org/Repo"]
        self.assertEqual(len(versions), 2)
        self.assertEqual(summary["immutable_revision_count"], 2)
        self.assertIn("e" * 40, {x["commit_sha"] for x in versions})


if __name__ == "__main__":
    unittest.main()
