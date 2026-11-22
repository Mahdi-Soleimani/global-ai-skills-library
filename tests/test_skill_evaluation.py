import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from skill_evaluation import build_evaluations, evaluate_record


def sample_record(**overrides):
    record = {
        "source_record_id": "GASL-SRC-test",
        "skill_name": "security-audit",
        "description": "Audit cloud configuration for security issues.",
        "compatibility": "Codex",
        "repository": "example/security-skills",
        "repository_owner": "example",
        "repository_url": "https://github.com/example/security-skills",
        "source_path": "skills/security-audit/SKILL.md",
        "source_url": "https://github.com/example/security-skills/blob/" + "a" * 40 + "/skills/security-audit/SKILL.md",
        "commit_sha": "a" * 40,
        "skill_md_blob_sha": "b" * 40,
        "license_spdx": "MIT",
        "license_evidence_path": "LICENSE",
        "license_assessment": "repository_license_metadata_only",
        "content_status": "not_downloaded_reference_record",
        "security_status": "not_scanned",
        "install_status": "not_installed",
        "snapshot_status": "verified_commit_pinned",
        "research_leads": ["EN-675"],
        "ownership": "third_party",
        "gasl_claims_exclusive_ownership": False,
    }
    record.update(overrides)
    return record


class SkillEvaluationTests(unittest.TestCase):
    def test_metadata_and_provenance_scores_are_separate_from_quality(self):
        result = evaluate_record(sample_record())
        self.assertEqual(result["metadata_completeness_score"], 100)
        self.assertEqual(result["provenance_score"], 100)
        self.assertIsNone(result["overall_quality_score"])
        self.assertEqual(result["behavioral_evaluation"], "not_evaluated")
        self.assertIn("behavioral_benchmark_not_run", result["risk_flags"])

    def test_missing_evidence_reduces_metadata_score_not_provenance_claims(self):
        record = sample_record(description=None, license_spdx=None, skill_md_blob_sha=None)
        result = evaluate_record(record)
        self.assertLess(result["metadata_completeness_score"], 100)
        self.assertLess(result["provenance_score"], 100)
        self.assertEqual(result["license_assessment"], "unknown_license_review_required")
        self.assertIn("license_unknown", result["risk_flags"])

    def test_public_mirror_gate_requires_bundled_license_evidence(self):
        record = sample_record()
        public = {"license_evidence": [{"source_path": "LICENSE", "blob_sha": "c" * 40}]}
        result = evaluate_record(record, public)
        self.assertEqual(result["license_assessment"], "public_mirror_allowlist_and_evidence_gate_passed")
        self.assertTrue(result["license_evidence_bundled"])

    def test_build_uses_public_package_description_for_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "registry").mkdir()
            (root / "public-catalog").mkdir()
            record = sample_record(description=None)
            (root / "registry" / "source-catalog.json").write_text(
                json.dumps({"records": [record]}), encoding="utf-8")
            package = {
                "repository": record["repository"],
                "source_skill_path": record["source_path"],
                "commit_sha": record["commit_sha"],
                "description": "A short public skill description.",
                "license_spdx": "MIT",
                "license_evidence": [{"source_path": "LICENSE", "blob_sha": "c" * 40}],
            }
            (root / "public-catalog" / "index.json").write_text(
                json.dumps({"packages": {"p1": package}}), encoding="utf-8")
            build_evaluations(root)
            result = json.loads((root / "registry" / "skill-evaluations.json").read_text())
            self.assertEqual(result["records"][0]["metadata_completeness_score"], 100)
            self.assertEqual(result["records"][0]["license_assessment"],
                             "public_mirror_allowlist_and_evidence_gate_passed")

    def test_static_clean_is_not_security_approval(self):
        result = evaluate_record(sample_record(security_status="no_obvious_static_flags_not_approved"))
        self.assertEqual(result["security_assessment"], "static_screen_no_obvious_flags_not_approval")
        self.assertIn("static_scan_is_not_security_approval", result["risk_flags"])
        self.assertIsNone(result["overall_quality_score"])

    def test_manual_review_and_integrity_failure_are_distinct(self):
        manual = evaluate_record(sample_record(security_status="manual_review_required"))
        blocked = evaluate_record(sample_record(security_status="integrity_failed"))
        self.assertEqual(manual["recommendation_state"], "manual_security_review_required")
        self.assertEqual(blocked["recommendation_state"], "blocked_integrity_failure")

    def test_build_writes_assessments_without_mutating_source_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "registry").mkdir()
            (root / "public-catalog").mkdir()
            source = {"records": [sample_record()]}
            source_path = root / "registry" / "source-catalog.json"
            original = json.dumps(source, ensure_ascii=False)
            source_path.write_text(original, encoding="utf-8")
            (root / "public-catalog" / "index.json").write_text('{"packages":{}}', encoding="utf-8")
            summary = build_evaluations(root)
            output = json.loads((root / "registry" / "skill-evaluations.json").read_text())
            self.assertEqual(summary["source_record_count"], 1)
            self.assertEqual(output["records"][0]["source_record_id"], "GASL-SRC-test")
            self.assertEqual(source_path.read_text(encoding="utf-8"), original)
            self.assertEqual(summary["behaviorally_evaluated_count"], 0)
            self.assertEqual(summary["overall_quality_scores_assigned"], 0)


if __name__ == "__main__":
    unittest.main()
