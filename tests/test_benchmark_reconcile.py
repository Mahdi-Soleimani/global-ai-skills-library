"""Phase 48: Git-blob-pinned provisional judgment reconciliation."""
import copy
import json
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from benchmark_reconcile import MAPPING_SCHEMA, build_mapping, reconcile, historical_from_git
from search_benchmark import load_dataset

OLD = "GASL-SRC-old"
NEW = "GASL-SRC-new"
KEEP = "GASL-SRC-keep"
OLD_COMMIT = "a" * 40
NEW_COMMIT = "b" * 40
BLOB = "c" * 40


def historical():
    return {"records": [
        {"source_record_id": OLD, "repository": "example/repo",
         "source_path": "skills/alpha/SKILL.md", "commit_sha": OLD_COMMIT,
         "skill_md_blob_sha": BLOB},
        {"source_record_id": KEEP, "repository": "example/repo",
         "source_path": "skills/beta/SKILL.md", "commit_sha": OLD_COMMIT,
         "skill_md_blob_sha": "d"*40},
    ]}


def current():
    return {"records": [
        {"source_record_id": NEW, "repository": "example/repo",
         "source_path": "skills/alpha/SKILL.md", "commit_sha": NEW_COMMIT,
         "skill_md_blob_sha": BLOB},
        {"source_record_id": KEEP, "repository": "example/repo",
         "source_path": "skills/beta/SKILL.md", "commit_sha": OLD_COMMIT,
         "skill_md_blob_sha": "d"*40},
    ]}


def dataset():
    return {"schema_version": "1.0.0", "status": "provisional",
            "queries": [
                {"id": "en", "query": "alpha", "language": "en",
                 "relevant": {OLD: 3, KEEP: 1}},
                {"id": "fa", "query": "آلفا", "language": "fa",
                 "relevant": {OLD: 3, KEEP: 1}},
            ]}


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.original = dataset()
        self.history = historical()
        self.present = current()
        self.mapping = build_mapping(self.original, self.history, OLD_COMMIT, "e"*64)

    def test_valid_pinned_blob_transition_preserves_grades_and_original_input(self):
        before = copy.deepcopy(self.original)
        reconciled, audit = reconcile(self.original, self.mapping, self.present)
        self.assertEqual(self.original, before)
        self.assertEqual(reconciled["status"], "provisional_crosswalk_not_independent_gold")
        self.assertEqual(reconciled["queries"][0]["relevant"], {NEW: 3, KEEP: 1})
        self.assertEqual(reconciled["queries"][1]["relevant"], {NEW: 3, KEEP: 1})
        self.assertEqual(audit["distinct_judged_ids"], 2)
        self.assertEqual(audit["total_judgments"], 4)
        self.assertEqual(audit["remapped_source_id_count"], 1)
        self.assertEqual(audit["changed_commit_count"], 1)
        self.assertEqual(audit["unchanged_git_blob_count"], 2)
        self.assertFalse(audit["original_judgments_independently_adjudicated"])
        self.assertFalse(audit["git_blob_reverified_against_live_upstream"])

    def test_mapping_has_exact_history_and_no_new_grades(self):
        self.assertEqual(self.mapping["schema"], MAPPING_SCHEMA)
        self.assertEqual(len(self.mapping["identities"]), 2)
        self.assertEqual(self.mapping["historical_revision"], OLD_COMMIT)

    def test_changed_blob_requires_rejudgment(self):
        candidate = copy.deepcopy(self.present)
        candidate["records"][0]["skill_md_blob_sha"] = "f"*40
        with self.assertRaisesRegex(ValueError, "Git Blob"):
            reconcile(self.original, self.mapping, candidate)

    def test_missing_or_moved_skill_requires_rejudgment(self):
        candidate = copy.deepcopy(self.present)
        candidate["records"][0]["source_path"] = "skills/renamed/SKILL.md"
        with self.assertRaisesRegex(ValueError, "path absent"):
            reconcile(self.original, self.mapping, candidate)

    def test_duplicate_matching_variants_fails_closed(self):
        candidate = copy.deepcopy(self.present)
        duplicate = copy.deepcopy(candidate["records"][0])
        duplicate["source_record_id"] = "GASL-SRC-duplicate"
        candidate["records"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            reconcile(self.original, self.mapping, candidate)

    def test_unrelated_duplicate_path_is_allowed(self):
        candidate = copy.deepcopy(self.present)
        duplicate = copy.deepcopy(candidate["records"][0])
        duplicate["source_record_id"] = "GASL-SRC-historical-copy"
        duplicate["skill_md_blob_sha"] = "f"*40
        candidate["records"].append(duplicate)
        _, audit = reconcile(self.original, self.mapping, candidate)
        self.assertEqual(audit["remapped_source_id_count"], 1)

    def test_same_old_source_id_now_different_identity_is_rejected(self):
        candidate = copy.deepcopy(self.present)
        hijack = copy.deepcopy(candidate["records"][0])
        hijack["source_record_id"] = OLD
        hijack["source_path"] = "skills/other/SKILL.md"
        candidate["records"].append(hijack)
        with self.assertRaisesRegex(ValueError, "now points to another"):
            reconcile(self.original, self.mapping, candidate)

    def test_unknown_old_ids_fail_not_zero_graded(self):
        candidate = copy.deepcopy(self.mapping)
        candidate["identities"].pop()
        with self.assertRaisesRegex(ValueError, "exactly match"):
            reconcile(self.original, candidate, self.present)

    def test_malformed_history_map_or_missing_historical_blob_fail(self):
        candidate = copy.deepcopy(self.mapping)
        candidate["historical_revision"] = "latest"
        with self.assertRaisesRegex(ValueError, "Invalid pinned"):
            reconcile(self.original, candidate, self.present)
        historical_data = historical()
        historical_data["records"][0]["skill_md_blob_sha"] = None
        with self.assertRaisesRegex(ValueError, "not Git-blob pinned"):
            build_mapping(self.original, historical_data, OLD_COMMIT, "e"*64)

    def test_mapping_cannot_promote_gold_or_modify_schema(self):
        original = dataset()
        original["status"] = "human_gold"
        with self.assertRaisesRegex(ValueError, "Only original provisional"):
            build_mapping(original, self.history, OLD_COMMIT, "e"*64)
        original = dataset()
        original["schema_version"] = "1.1.0"
        with self.assertRaisesRegex(ValueError, "cannot promote"):
            reconcile(original, self.mapping, self.present)

    def test_snapshot_loaded_only_from_exact_local_git_ref_no_network(self):
        revision = "7e616c0f5a8b6ba906bea59a0ade3fc163d9e418"
        raw = json.dumps(self.history).encode()
        with patch("benchmark_reconcile.subprocess.check_output", return_value=raw) as show:
            records, digest = historical_from_git(ROOT, revision)
        show.assert_called_once_with(
            ["git", "-C", str(ROOT), "show", revision + ":registry/source-catalog.json"])
        self.assertEqual(records, self.history)
        self.assertEqual(len(digest), 64)
        with self.assertRaisesRegex(ValueError, "complete 40"):
            historical_from_git(ROOT, "main")

    def test_full_real_reconciliation_26_queries_148_preserved(self):
        original = load_dataset(ROOT/"benchmarks"/"search-gold-v1.json")
        mapping = json.loads((ROOT/"benchmarks"/"search-gold-v1-crosswalk.json").read_text())
        present = json.loads((ROOT/"registry"/"source-catalog.json").read_text())
        derived, audit = reconcile(original, mapping, present)
        self.assertEqual(audit["query_count"], 26)
        self.assertEqual(audit["total_judgments"], 148)
        self.assertEqual(audit["distinct_judged_ids"], 72)
        # Remap totals change when a source's pinned commit changes while its
        # repository/path/Git Blob remain identical (24 became 26 for two SEO
        # Skills). Check the current catalog, not an obsolete snapshot count.
        pinned = {row["historical_source_id"]: row for row in mapping["identities"]}
        by_id = {row["source_record_id"]: row for row in present["records"]}
        checked = {row["old_source_id"]: row for row in audit["identity_checks"]}
        self.assertEqual(set(checked), set(pinned))
        self.assertEqual(audit["unchanged_git_blob_count"], 72)
        self.assertEqual(audit["remapped_source_id_count"],
                         len(set(pinned) - set(by_id)))
        for old_id, record in checked.items():
            historic = pinned[old_id]
            current = by_id[record["current_source_id"]]
            self.assertEqual((current["repository"], current["source_path"],
                              current["skill_md_blob_sha"]),
                             (historic["repository"], historic["source_path"],
                              historic["git_blob_sha"]))
        for old_query, new_query in zip(original["queries"], derived["queries"]):
            for old_id, grade in old_query["relevant"].items():
                self.assertEqual(new_query["relevant"][checked[old_id]["current_source_id"]],
                                 grade)
        for query in derived["queries"]:
            self.assertNotIn("GASL-SRC-530827850c30c535cb40", query["relevant"])


if __name__ == "__main__":
    unittest.main()
