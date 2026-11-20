import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SourceManifestTests(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads((ROOT / "config" / "source-repositories.json").read_text(encoding="utf-8"))

    def test_primary_datasets_are_independent(self):
        reports = self.cfg["reports"]
        self.assertEqual(reports["EN-675"]["record_count_claimed"], 675)
        self.assertEqual(reports["FA-234"]["record_count_claimed"], 234)
        self.assertEqual(reports["EN-675"]["dataset_role"], "primary_independent_dataset")
        self.assertEqual(reports["FA-234"]["dataset_role"], "primary_independent_dataset")
        self.assertFalse(reports["EN-675"]["database_artifacts_available"])
        self.assertFalse(reports["FA-234"]["database_artifacts_available"])

    def test_supplemental_reports_are_not_primary(self):
        reports = self.cfg["reports"]
        self.assertEqual(len(reports["AUX-FA-750PLUS"]["explicit_github_repositories"]), 40)
        self.assertEqual(len(reports["AUX-FA-438"]["explicit_github_repositories"]), 32)
        self.assertNotEqual(reports["AUX-FA-750PLUS"]["dataset_role"], "primary_independent_dataset")
        self.assertNotEqual(reports["AUX-FA-438"]["dataset_role"], "primary_independent_dataset")

    def test_all_four_archives_are_recorded_as_hash_verified(self):
        for source_id, report in self.cfg["reports"].items():
            self.assertEqual(report.get("local_archive_status"), "sha256_verified", source_id)
            self.assertTrue(report.get("local_archive_verified_at"), source_id)

    def test_public_manifests_do_not_expose_account_scoped_file_ids(self):
        for source_id, report in self.cfg["reports"].items():
            self.assertNotIn("source_library_file_id", report, source_id)
            manifest = json.loads((ROOT / "research" / source_id / "source-manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn("source_library_file_id", manifest, source_id)
        for item in self.cfg.get("related_report_exports", []):
            self.assertNotIn("file_id", item)

    def test_primary_repository_cross_reference_only(self):
        reports = self.cfg["reports"]
        a = {x.lower() for x in reports["EN-675"]["explicit_github_repositories"]}
        b = {x.lower() for x in reports["FA-234"]["explicit_github_repositories"]}
        self.assertEqual(len(a), 12)
        self.assertEqual(len(b), 3)
        self.assertEqual(len(a & b), 3)
        self.assertEqual(len(a | b), 12)

    def test_all_report_repository_refs(self):
        reports = self.cfg["reports"]
        mentions = sum(len(x["explicit_github_repositories"]) for x in reports.values())
        distinct = {r.lower() for x in reports.values() for r in x["explicit_github_repositories"]}
        self.assertEqual(mentions, 87)
        self.assertEqual(len(distinct), 56)


if __name__ == "__main__":
    unittest.main()
