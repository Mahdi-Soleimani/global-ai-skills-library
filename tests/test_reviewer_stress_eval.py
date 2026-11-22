import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from reviewer_stress_eval import REVIEWERS, SUITE_VERSION, suite_hash


class ReviewerStressSuiteTests(unittest.TestCase):
    def test_suite_has_ten_distinct_domain_personas(self):
        self.assertEqual(SUITE_VERSION, "1.2.0")
        self.assertEqual(len(REVIEWERS), 10)
        self.assertEqual(len({x["id"] for x in REVIEWERS}), 10)
        self.assertEqual(len({x["domain"] for x in REVIEWERS}), 10)

    def test_each_persona_has_five_scenarios_and_a_persian_case(self):
        all_ids = []
        for reviewer in REVIEWERS:
            self.assertEqual(len(reviewer["scenarios"]), 5)
            self.assertEqual(sum(x.get("language") == "fa" for x in reviewer["scenarios"]), 1)
            all_ids.extend(x["id"] for x in reviewer["scenarios"])
        self.assertEqual(len(all_ids), 50)
        self.assertEqual(len(set(all_ids)), 50)

    def test_suite_contains_coverage_probes_and_explicit_negative_constraints(self):
        scenarios = [x for reviewer in REVIEWERS for x in reviewer["scenarios"]]
        self.assertEqual(sum(x["kind"] == "coverage_probe" for x in scenarios), 10)
        self.assertEqual(sum(x["kind"] == "known_coverage_gap" for x in scenarios), 2)
        self.assertEqual(sum(x["kind"] == "negative_constraint" for x in scenarios), 3)
        self.assertTrue(all(x["difficulty"] in ("high", "very-high", "extreme") for x in scenarios))

    def test_expected_families_cover_positive_and_negative_constraint_cases(self):
        scenarios = [x for reviewer in REVIEWERS for x in reviewer["scenarios"]]
        expected = [x for x in scenarios if x.get("expected")]
        positives = [x for x in expected if x["kind"] == "positive"]
        negative = [x for x in expected if x["kind"] == "negative_constraint"]
        self.assertEqual(len(expected), 38)
        self.assertEqual(len(positives), 35)
        self.assertEqual(len(negative), 3)
        des04 = next(x for x in scenarios if x["id"] == "DES-04")
        self.assertIn("accessibility-and-inclusive-visualization", des04["expected"])
        self.assertIn("design-qa", des04["expected"])

    def test_suite_fingerprint_is_stable(self):
        self.assertEqual(suite_hash(), suite_hash())


if __name__ == "__main__":
    unittest.main()
