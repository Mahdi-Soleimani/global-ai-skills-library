import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from skill_evaluation import build_evaluations
from skill_search import build_index
from skill_router import route_task


def record(record_id, name, description, security="not_scanned", path=None):
    path = path or "skills/" + name + "/SKILL.md"
    return {
        "source_record_id": record_id,
        "skill_name": name,
        "description": description,
        "repository": "example/" + name,
        "repository_owner": "example",
        "repository_url": "https://github.com/example/" + name,
        "source_path": path,
        "source_url": "https://github.com/example/" + name + "/blob/" + "a" * 40 + "/" + path,
        "commit_sha": "a" * 40,
        "skill_md_blob_sha": "b" * 40,
        "license_spdx": "MIT",
        "license_evidence_path": "LICENSE",
        "license_assessment": "repository_license_metadata_only",
        "content_status": "not_downloaded_reference_record",
        "security_status": security,
        "install_status": "not_installed",
        "snapshot_status": "verified_commit_pinned",
        "research_leads": ["EN-675"],
        "ownership": "third_party",
        "original_author": None,
        "gasl_claims_exclusive_ownership": False,
    }


class SkillRouterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "registry").mkdir()
        (self.root / "public-catalog").mkdir()
        (self.root / "config").mkdir()
        records = [
            record("s1", "security-audit", "Audit cloud configuration and security controls.",
                   "manual_review_required"),
            record("s2", "security-checklist", "Check cloud security posture and compliance.",
                   "no_obvious_static_flags_not_approved"),
            record("s3", "security-reference", "Security review guidance for cloud services.",
                   "not_scanned"),
            record("s4", "security-broken", "Security audit with broken package integrity.",
                   "integrity_failed"),
            record("s5", "security-fixture", "Security audit fixture.",
                   "not_scanned", "evals/fixtures/security-fixture/SKILL.md"),
        ]
        (self.root / "registry" / "source-catalog.json").write_text(
            json.dumps({"records": records}, ensure_ascii=False), encoding="utf-8")
        (self.root / "registry" / "skills.json").write_text(json.dumps({"records": [
            {"repository": "example/security-checklist", "source_skill_path": "skills/security-checklist/SKILL.md",
             "commit_sha": "a" * 40, "compatibility": "Codex", "package_type": "skill_candidate"}
        ]}), encoding="utf-8")
        (self.root / "public-catalog" / "index.json").write_text('{"packages":{}}', encoding="utf-8")
        (self.root / "config" / "taxonomy.json").write_text(json.dumps({"domains": [
            {"id": "security-compliance", "label": "Security", "keywords": ["security", "audit", "compliance"]}
        ]}), encoding="utf-8")
        build_evaluations(self.root)
        build_index(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_router_excludes_integrity_failures_and_test_fixtures(self):
        result = route_task("security audit", top_k=10, root=self.root)
        names = [x["skill_name"] for x in result["results"]]
        self.assertNotIn("security-broken", names)
        self.assertNotIn("security-fixture", names)
        self.assertGreaterEqual(result["excluded_candidate_count"], 1)

    def test_router_surfaces_security_and_license_warnings(self):
        result = route_task("security audit", top_k=10, root=self.root)
        by_name = {x["skill_name"]: x for x in result["results"]}
        self.assertEqual(by_name["security-audit"]["decision"], "manual_security_review_required")
        self.assertEqual(by_name["security-reference"]["decision"], "security_screen_required")
        self.assertIn("behavioral_benchmark_not_run", by_name["security-audit"]["warnings"])

    def test_router_never_installs_or_executes(self):
        result = route_task("security audit", top_k=3, root=self.root)
        self.assertFalse(result["installation_performed"])
        self.assertFalse(result["execution_performed"])
        self.assertTrue(all(not x["installation_allowed"] and not x["execution_allowed"]
                            for x in result["results"]))

    def test_strict_agent_requires_declared_compatibility(self):
        result = route_task("security audit", top_k=10, agent="Codex",
                            strict_agent=True, root=self.root)
        self.assertTrue(result["results"])
        self.assertTrue(all(x["agent_compatibility_status"] == "declared_match"
                            for x in result["results"]))
        self.assertEqual([x["skill_name"] for x in result["results"]], ["security-checklist"])

    def test_router_preserves_search_order_after_filtering(self):
        from unittest.mock import patch
        candidates = [
            {"source_record_id": "specific", "skill_name": "specific", "repository": "example/a",
             "query_coverage": 1.0, "relevance_score": 60.0},
            {"source_record_id": "generic", "skill_name": "generic", "repository": "example/b",
             "query_coverage": 0.75, "relevance_score": 68.0},
        ]
        with patch("skill_router.search_skills", return_value=candidates):
            result = route_task("WordPress plugin development", root=self.root)
        self.assertEqual([x["source_record_id"] for x in result["results"]], ["specific", "generic"])

    def test_router_reports_its_ranking_is_not_quality(self):
        result = route_task("security audit", root=self.root)
        self.assertIn("query-coverage penalty", result["ranking_method"])
        self.assertIn("not a behavioral quality score", result["note"])
        self.assertIn("metadata_completeness_score", result["results"][0])


    def test_router_provisional_recommendation_preserves_security_gate(self):
        result = route_task("security audit", top_k=3, root=self.root)
        self.assertEqual(result["routing_decision"], "recommend")
        self.assertEqual(result["recommendation_status"], "provisional_candidate_to_inspect")
        self.assertEqual(result["answerability"]["decision"], "recommend")
        self.assertEqual(result["answerability"]["policy_status"], "experimental_heuristic_not_calibrated")
        self.assertEqual(result["answerability"]["reason_code"], "strong_lexical_match_in_discovery_pool")
        self.assertFalse(result["answerability"]["independent_quality_validation_available"])
        self.assertFalse(result["answerability"]["human_review_required"])
        self.assertFalse(result["answerability"]["empty_results_prove_no_relevant_skill"])
        self.assertEqual(result["results"][0]["decision"], "manual_security_review_required")
        self.assertFalse(result["results"][0]["installation_allowed"])

    def test_empty_results_abstain_without_claiming_catalog_absence(self):
        from unittest.mock import patch
        with patch("skill_router.search_skills", return_value=[]):
            result = route_task("native Android banking SMS receiver", root=self.root)
        self.assertEqual(result["returned_count"], 0)
        self.assertEqual(result["routing_decision"], "abstain")
        self.assertEqual(result["answerability"]["reason_code"], "no_eligible_candidates")
        self.assertEqual(result["answerability"]["retrieved_candidate_pool_size"], 0)
        self.assertEqual(result["answerability"]["eligible_candidate_count"], 0)
        self.assertEqual(result["answerability"]["returned_candidate_count"], 0)
        self.assertEqual(result["answerability"]["currently_emitted_decisions"],
                         ["recommend", "abstain", "undetermined"])
        self.assertFalse(result["answerability"]["candidate_discovery_available"])
        self.assertFalse(result["answerability"]["empty_results_prove_no_relevant_skill"])


if __name__ == "__main__":
    unittest.main()
