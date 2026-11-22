import csv
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import benchmark_review as review


class BenchmarkReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "benchmark-review"
        self.workspace.mkdir()
        self.catalog_path = Path(self.tmp.name) / "source-catalog.json"
        self.records = {
            "SRC-1": {"source_record_id": "SRC-1", "repository": "example/skills", "source_path": "skills/direct/SKILL.md", "commit_sha": "a" * 40, "skill_md_blob_sha": "b" * 40, "skill_name": "direct-skill", "license_spdx": "MIT"},
            "SRC-2": {"source_record_id": "SRC-2", "repository": "example/skills", "source_path": "skills/partial/SKILL.md", "commit_sha": "c" * 40, "skill_md_blob_sha": "d" * 40, "skill_name": "partial-skill", "license_spdx": "MIT"},
        }
        self.catalog_path.write_text(json.dumps({"records": list(self.records.values())}), encoding="utf-8")
        self.candidates = [self._candidate("SRC-1", "direct-skill", "skills/direct/SKILL.md", "a", "b"),
                           self._candidate("SRC-2", "partial-skill", "skills/partial/SKILL.md", "c", "d")]

    def tearDown(self):
        self.tmp.cleanup()

    def _candidate(self, source_id, name, path, commit_char, blob_char, grade="", rationale="", checked=""):
        return {
            "pair_id": "task-one", "target_domain": "software-development",
            "query_en_id": "task-one-en", "query_en": "Build a feature with direct and partial Skills",
            "query_fa_id": "task-one-fa", "query_fa": "ساخت یک قابلیت با مهارت‌های مستقیم و جزئی",
            "source_record_id": source_id, "skill_name": name, "repository": "example/skills",
            "source_path": path, "commit_sha": commit_char * 40, "skill_md_blob_sha": blob_char * 40,
            "description": "Test Skill description", "license_spdx": "MIT",
            "relevance_grade": grade, "rationale": rationale, "content_checked": checked,
            "language_specific_exception": "",
        }

    def _answerability(self, status="", **overrides):
        row = {
            "pair_id": "task-one", "target_domain": "software-development",
            "query_en_id": "task-one-en", "query_en": "Build a feature with direct and partial Skills",
            "query_fa_id": "task-one-fa", "query_fa": "ساخت یک قابلیت با مهارت‌های مستقیم و جزئی",
            "candidate_count": "2", "answerability_status": status,
            "direct_match_source_ids": "", "partial_match_source_ids": "",
            "additional_source_ids_found": "", "full_catalog_reviewed": "no",
            "out_of_pool_reviewed": "no", "search_formulations": "", "search_method": "",
            "rationale": "", "language_specific_exception": "",
        }
        row.update(overrides)
        return row

    def _attestation(self, reviewer_id):
        return {
            "reviewer_id": reviewer_id, "reviewer_type": "independent_human",
            "completed_at_utc": "2026-11-22T12:00:00Z", "independence_confirmed": "yes",
            "saw_other_reviewer_material": "no", "saw_private_manifest_or_audit": "no",
            "used_model_generated_judgments": "no", "conflict_of_interest": "none",
            "attestation": "I confirm these are my independent human judgments.",
        }

    def _write_csv(self, path, columns, rows):
        with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

    def _write_complete_review(self, reviewer, candidate_rows=None, answer_row=None, reviewer_id=None):
        candidate_rows = candidate_rows or [
            self._candidate("SRC-1", "direct-skill", "skills/direct/SKILL.md", "a", "b", "3", "Directly implements the required feature.", "yes"),
            self._candidate("SRC-2", "partial-skill", "skills/partial/SKILL.md", "c", "d", "2", "Provides actionable support for a meaningful part.", "no"),
        ]
        answer_row = answer_row or self._answerability(
            "direct_match_found", direct_match_source_ids="SRC-1", partial_match_source_ids="SRC-2",
            rationale="A direct implementation candidate is present."
        )
        paths = review._review_paths(self.workspace, reviewer)
        self._write_csv(paths["candidate"], review.CANDIDATE_COLUMNS, candidate_rows)
        self._write_csv(paths["answerability"], review.ANSWERABILITY_COLUMNS, [answer_row])
        self._write_csv(paths["attestation"], review.ATTESTATION_COLUMNS, [self._attestation(reviewer_id or "human-" + reviewer.lower())])

    def test_audit_accepts_prepared_blind_packets_without_labels(self):
        manifest = {"candidate_count_total": 2, "pair_count": 1,
                    "taxonomy_sha256": "3c16e787ccc6ad0f481f69e3683330801d9ba745578ca9476d26c6f37116174f",
                    "source_universe": {"source_catalog_sha256": hashlib.sha256(self.catalog_path.read_bytes()).hexdigest(),
                                        "source_catalog_records": 2},
                    "unique_candidates_by_pair": {"task-one": 2}}
        (self.workspace / "SEARCH-GOLD-V2-QUERY-MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
        a_rows = [self._candidate("SRC-1", "direct-skill", "skills/direct/SKILL.md", "a", "b"), self._candidate("SRC-2", "partial-skill", "skills/partial/SKILL.md", "c", "d")]
        b_rows = list(reversed(a_rows))
        for reviewer, rows in (("A", a_rows), ("B", b_rows)):
            paths = review._review_paths(self.workspace, reviewer)
            self._write_csv(paths["candidate"], review.CANDIDATE_COLUMNS, rows)
            self._write_csv(paths["answerability"], review.ANSWERABILITY_COLUMNS, [self._answerability()])
            self._write_csv(paths["attestation"], review.ATTESTATION_COLUMNS, [{field: "" for field in review.ATTESTATION_COLUMNS}])
            packet = self.workspace / f"SEARCH-GOLD-V2-REVIEWER-{reviewer}-PACKET-INTAKE-V2.zip"
            packet_entries = sorted({
                f"SEARCH-GOLD-V2-REVIEWER-{reviewer}-INTAKE-V2.csv",
                f"SEARCH-GOLD-V2-ANSWERABILITY-REVIEWER-{reviewer}-INTAKE-V2.csv",
                f"SEARCH-GOLD-V2-REVIEWER-{reviewer}-INSTRUCTIONS-INTAKE-V2.md",
                f"SEARCH-GOLD-V2-REVIEWER-{reviewer}-ATTESTATION-INTAKE-V2.csv",
            })
            (self.workspace / packet_entries[2]).write_text("review instructions", encoding="utf-8")
            with zipfile.ZipFile(packet, "w") as archive:
                for name in packet_entries:
                    archive.write(self.workspace / name, arcname=name)
        result = review.audit_workspace(self.workspace, self.catalog_path)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["taxonomy_hash_match"])
        self.assertTrue(any("Taxonomy drift" in warning for warning in result["warnings"]))
        self.assertEqual(result["reviewers"]["A"]["candidate_grades_entered"], 0)
        self.assertFalse(result["reviewers"]["A"]["attestation_complete"])

    def test_unfilled_returned_packets_are_incomplete_not_gold(self):
        for reviewer in ("A", "B"):
            self._write_csv(review._review_paths(self.workspace, reviewer)["candidate"], review.CANDIDATE_COLUMNS, self.candidates)
            self._write_csv(review._review_paths(self.workspace, reviewer)["answerability"], review.ANSWERABILITY_COLUMNS, [self._answerability()])
            self._write_csv(review._review_paths(self.workspace, reviewer)["attestation"], review.ATTESTATION_COLUMNS, [{field: "" for field in review.ATTESTATION_COLUMNS}])
        result = review.validate_returned_reviews(self.workspace, self.catalog_path)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["errors"], [])
        self.assertGreater(len(result["incomplete"]), 0)

    def test_two_completed_independent_reviews_validate(self):
        self._write_complete_review("A", reviewer_id="human-a")
        self._write_complete_review("B", candidate_rows=list(reversed([
            self._candidate("SRC-1", "direct-skill", "skills/direct/SKILL.md", "a", "b", "3", "Direct implementation confirmed.", "yes"),
            self._candidate("SRC-2", "partial-skill", "skills/partial/SKILL.md", "c", "d", "2", "Useful partial support.", "no"),
        ])), reviewer_id="human-b")
        result = review.validate_returned_reviews(self.workspace, self.catalog_path)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["reviewer_ids"], ["human-a", "human-b"])

    def test_no_answer_requires_full_catalog_and_out_of_pool_evidence(self):
        rows = [
            self._candidate("SRC-1", "direct-skill", "skills/direct/SKILL.md", "a", "b", "0", "", "no"),
            self._candidate("SRC-2", "partial-skill", "skills/partial/SKILL.md", "c", "d", "1", "Related but insufficient.", "yes"),
        ]
        answer = self._answerability(
            "no_relevant_skill_found", full_catalog_reviewed="yes", out_of_pool_reviewed="yes",
            search_formulations="Android BroadcastReceiver bank SMS; SMS_RECEIVED Kotlin transaction parsing",
            search_method="Searched all catalog metadata, relevant pinned bodies and out-of-pool variants.",
            rationale="No candidate reaches useful/actionable grade 2 after full review."
        )
        self._write_complete_review("A", rows, answer, "human-a")
        self._write_complete_review("B", list(reversed(rows)), answer, "human-b")
        result = review.validate_returned_reviews(self.workspace, self.catalog_path)
        self.assertEqual(result["status"], "PASS")

    def test_no_answer_without_out_of_pool_review_is_rejected(self):
        rows = [
            self._candidate("SRC-1", "direct-skill", "skills/direct/SKILL.md", "a", "b", "0", "", "no"),
            self._candidate("SRC-2", "partial-skill", "skills/partial/SKILL.md", "c", "d", "1", "Related but insufficient.", "yes"),
        ]
        answer = self._answerability(
            "no_relevant_skill_found", full_catalog_reviewed="yes", out_of_pool_reviewed="no",
            search_formulations="Android SMS receiver; Kotlin SMS_RECEIVED parser",
            search_method="Full catalog metadata search.", rationale="No useful match."
        )
        self._write_complete_review("A", rows, answer, "human-a")
        self._write_complete_review("B", list(reversed(rows)), answer, "human-b")
        result = review.validate_returned_reviews(self.workspace, self.catalog_path)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("out_of_pool_reviewed=yes" in error for error in result["errors"]))

    def test_same_reviewer_id_cannot_satisfy_independent_review(self):
        self._write_complete_review("A", reviewer_id="same-human")
        self._write_complete_review("B", reviewer_id="same-human")
        result = review.validate_returned_reviews(self.workspace, self.catalog_path)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("distinct reviewer_id" in error for error in result["errors"]))

    def test_source_pin_mismatch_is_rejected(self):
        row = self._candidate("SRC-1", "direct-skill", "skills/direct/SKILL.md", "a", "b", "3", "Direct match.", "yes")
        row["commit_sha"] = "f" * 40
        path = self.workspace / "bad.csv"
        self._write_csv(path, review.CANDIDATE_COLUMNS, [row])
        result = review.validate_candidate_sheet(path, review.load_source_index(self.catalog_path), require_complete=True)
        self.assertTrue(any("source pin mismatch" in error for error in result["errors"]))

    def test_reviewer_addition_generates_blinded_addendum_without_grade_leak(self):
        a_rows = [self._candidate("SRC-1", "direct-skill", "skills/direct/SKILL.md", "a", "b", "3", "A found this direct match.", "yes")]
        b_rows = [
            self._candidate("SRC-1", "direct-skill", "skills/direct/SKILL.md", "a", "b", "3", "B found this direct match.", "yes"),
            self._candidate("SRC-2", "partial-skill", "skills/partial/SKILL.md", "c", "d", "2", "B found a useful partial match.", "yes"),
        ]
        self._write_complete_review("A", a_rows, self._answerability("direct_match_found", candidate_count="1", direct_match_source_ids="SRC-1", rationale="Direct."), "human-a")
        self._write_complete_review("B", b_rows, self._answerability("direct_match_found", direct_match_source_ids="SRC-1", partial_match_source_ids="SRC-2", rationale="Direct and partial."), "human-b")
        result = review.validate_returned_reviews(self.workspace, self.catalog_path)
        self.assertEqual(result["status"], "INCOMPLETE")
        outputs = review.create_blinded_addenda(self.workspace, self.catalog_path, result)
        self.assertEqual(outputs["A"]["row_count"], 1)
        _, addendum_rows = review.read_csv(outputs["A"]["path"])
        self.assertEqual(addendum_rows[0]["source_record_id"], "SRC-2")
        self.assertEqual(addendum_rows[0]["relevance_grade"], "")
        self.assertEqual(addendum_rows[0]["rationale"], "")


    def test_language_specific_exception_blocks_shared_qrels_pass(self):
        rows_a = [
            self._candidate("SRC-1", "direct-skill", "skills/direct/SKILL.md", "a", "b", "3", "Direct.", "yes"),
            self._candidate("SRC-2", "partial-skill", "skills/partial/SKILL.md", "c", "d", "2", "Partial.", "no"),
        ]
        rows_b = [dict(row) for row in rows_a]
        rows_a[0]["language_specific_exception"] = "Persian prompt adds a constraint absent from English."
        self._write_complete_review("A", rows_a, reviewer_id="human-a")
        self._write_complete_review("B", rows_b, reviewer_id="human-b")
        result = review.validate_returned_reviews(self.workspace, self.catalog_path)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["language_exception_pairs"], ["task-one"])



if __name__ == "__main__":
    unittest.main()
