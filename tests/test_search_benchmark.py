import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from search_benchmark import metrics_for_results, load_dataset, answerability_metrics, run_benchmark


class SearchBenchmarkTests(unittest.TestCase):
    def test_metrics_use_graded_relevance_and_threshold(self):
        results = [
            {"source_record_id": "unjudged"},
            {"source_record_id": "relevant-b"},
            {"source_record_id": "relevant-a"},
        ]
        qrels = {"relevant-a": 3, "relevant-b": 2, "related": 1}
        metrics = metrics_for_results(results, qrels, k=3, mrr_k=5)
        self.assertAlmostEqual(metrics["precision_at_k"], 2 / 3, places=4)
        self.assertEqual(metrics["recall_at_k"], 1.0)
        self.assertEqual(metrics["mrr_at_k"], 0.5)
        self.assertAlmostEqual(metrics["ndcg_at_k"], 0.5741, places=4)
        self.assertEqual(metrics["relevant_judgment_count"], 2)

    def test_collapsed_duplicate_result_can_recall_all_source_records_but_counts_once_for_precision(self):
        results = [{
            "source_record_id": "source-a",
            "source_record_ids": ["source-a", "source-b"],
        }]
        metrics = metrics_for_results(
            results, {"source-a": 3, "source-b": 2}, k=2, mrr_k=5
        )
        self.assertEqual(metrics["precision_at_k"], 0.5)
        self.assertEqual(metrics["recall_at_k"], 1.0)
        self.assertEqual(metrics["mrr_at_k"], 1.0)

    def test_empty_results_are_safe(self):
        metrics = metrics_for_results([], {"relevant": 3}, k=5, mrr_k=10)
        self.assertEqual(metrics["precision_at_k"], 0.0)
        self.assertEqual(metrics["recall_at_k"], 0.0)
        self.assertEqual(metrics["mrr_at_k"], 0.0)
        self.assertEqual(metrics["ndcg_at_k"], 0.0)

    def test_dataset_rejects_duplicate_query_ids(self):
        dataset = {
            "schema_version": "1.0.0",
            "queries": [
                {"id": "same", "query": "first", "relevant": {"a": 3}},
                {"id": "same", "query": "second", "relevant": {"b": 2}},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dataset.json"
            import json
            path.write_text(json.dumps(dataset), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate benchmark query id"):
                load_dataset(path)


    def _write_dataset(self, tmp, dataset):
        import json
        path = Path(tmp) / "dataset.json"
        path.write_text(json.dumps(dataset), encoding="utf-8")
        return path

    def _human_adjudication(self, **overrides):
        value = {
            "status": "final",
            "reviewer_type": "independent_human",
            "reviewer_ids": ["human-reviewer-a", "human-reviewer-b"],
        }
        value.update(overrides)
        return value

    def test_schema_1_1_accepts_empty_qrels_only_with_full_human_no_answer_adjudication(self):
        dataset = {
            "schema_version": "1.1.0",
            "queries": [{
                "id": "android-sms-gap",
                "query": "Native Android BroadcastReceiver bank SMS ingestion",
                "answerability": {"label": "unanswerable", "adjudication": self._human_adjudication(
                    full_catalog_review=True,
                    out_of_pool_review=True,
                    search_formulations=["BroadcastReceiver bank SMS", "SMS_RECEIVED Kotlin banking message parser"],
                    search_method="Full catalog search across names, metadata and pinned Skill bodies.",
                )},
                "relevant": {},
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_dataset(self._write_dataset(tmp, dataset))
        self.assertEqual(loaded["queries"][0]["relevant"], {})

    def test_schema_1_1_rejects_model_simulated_reviewers_as_gold_adjudicators(self):
        dataset = {
            "schema_version": "1.1.0",
            "queries": [{
                "id": "not-human-reviewed", "query": "No direct Skill exists",
                "answerability": {"label": "unanswerable", "adjudication": {
                    "status": "final", "reviewer_type": "model_simulated_personas",
                    "reviewer_ids": ["R01", "R02"], "full_catalog_review": True,
                    "out_of_pool_review": True,
                    "search_formulations": ["query one", "query two"],
                    "search_method": "search all catalog records",
                }},
                "relevant": {},
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "model-simulated personas do not qualify"):
                load_dataset(self._write_dataset(tmp, dataset))

    def test_schema_1_1_rejects_unanswerable_without_out_of_pool_full_catalog_evidence(self):
        dataset = {
            "schema_version": "1.1.0",
            "queries": [{
                "id": "weak-no-answer", "query": "No direct Skill exists",
                "answerability": {"label": "unanswerable", "adjudication": self._human_adjudication(
                    full_catalog_review=True, out_of_pool_review=False,
                    search_formulations=["query one", "query two"], search_method="catalog search",
                )},
                "relevant": {},
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "review beyond the pooled candidates"):
                load_dataset(self._write_dataset(tmp, dataset))

    def test_schema_1_1_answerable_requires_qrels_and_two_human_reviewers(self):
        base = {
            "schema_version": "1.1.0",
            "queries": [{
                "id": "answerable", "query": "PostgreSQL index tuning",
                "answerability": {"label": "answerable", "adjudication": self._human_adjudication()},
                "relevant": {"GASL-SRC-example": 3},
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_dataset(self._write_dataset(tmp, base))["schema_version"], "1.1.0")
            base["queries"][0]["relevant"] = {}
            with self.assertRaisesRegex(ValueError, "requires at least one relevance judgment"):
                load_dataset(self._write_dataset(tmp, base))

    def test_schema_1_1_uncertain_label_is_allowed_but_not_a_gold_no_answer(self):
        dataset = {
            "schema_version": "1.1.0",
            "queries": [{
                "id": "uncertain", "query": "Novel hardware task",
                "answerability": {"label": "uncertain"}, "relevant": {},
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_dataset(self._write_dataset(tmp, dataset))
        self.assertEqual(loaded["queries"][0]["answerability"]["label"], "uncertain")

    def test_answerability_metrics_separate_no_answer_precision_and_false_abstention(self):
        metrics = answerability_metrics([
            {"gold": "unanswerable", "prediction": "abstain"},
            {"gold": "unanswerable", "prediction": "recommend"},
            {"gold": "answerable", "prediction": "abstain"},
            {"gold": "answerable", "prediction": "recommend"},
            {"gold": "uncertain", "prediction": "abstain"},
        ])
        self.assertEqual(metrics["no_answer_precision"], 0.5)
        self.assertEqual(metrics["no_answer_recall"], 0.5)
        self.assertEqual(metrics["false_abstention_rate"], 0.5)
        self.assertEqual(metrics["answerable_query_coverage"], 0.5)
        self.assertEqual(metrics["false_recommendation_rate_on_unanswerable"], 0.5)
        self.assertEqual(metrics["evaluable_query_count"], 4)

    def test_undetermined_predictions_reduce_decision_coverage(self):
        metrics = answerability_metrics([
            {"gold": "unanswerable", "prediction": "undetermined"},
            {"gold": "answerable", "prediction": "recommend"},
        ])
        self.assertEqual(metrics["decision_coverage"], 0.5)
        self.assertEqual(metrics["undetermined_prediction_count"], 1)
        self.assertEqual(metrics["no_answer_precision"], None)

    def test_schema_1_1_rejects_invalid_prediction_decisions(self):
        dataset = {
            "schema_version": "1.1.0",
            "queries": [{
                "id": "bad-prediction", "query": "PostgreSQL index tuning",
                "answerability": {"label": "answerable", "adjudication": self._human_adjudication()},
                "relevant": {"GASL-SRC-example": 3},
                "prediction": {"decision": "maybe"},
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "prediction.decision"):
                load_dataset(self._write_dataset(tmp, dataset))



    def test_legacy_schema_1_0_remains_compatible(self):
        dataset = {
            "schema_version": "1.0.0",
            "queries": [{"id": "legacy", "query": "security audit", "relevant": {"source-a": 3}}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_dataset(self._write_dataset(tmp, dataset))
        self.assertEqual(loaded["schema_version"], "1.0.0")

    def test_unanswerable_requires_two_distinct_search_formulations(self):
        dataset = {
            "schema_version": "1.1.0",
            "queries": [{
                "id": "duplicate-formulations", "query": "No direct Skill",
                "answerability": {"label": "unanswerable", "adjudication": self._human_adjudication(
                    full_catalog_review=True, out_of_pool_review=True,
                    search_formulations=["same query", " SAME QUERY "], search_method="catalog search",
                )},
                "relevant": {},
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "two distinct documented search formulations"):
                load_dataset(self._write_dataset(tmp, dataset))

    def test_answerable_requires_at_least_one_relevant_grade(self):
        dataset = {
            "schema_version": "1.1.0", "relevant_threshold": 2,
            "queries": [{
                "id": "all-low-grades", "query": "security audit",
                "answerability": {"label": "answerable", "adjudication": self._human_adjudication()},
                "relevant": {"source-a": 1},
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "at or above relevant_threshold"):
                load_dataset(self._write_dataset(tmp, dataset))

    def test_run_benchmark_separates_unanswerable_from_ranking_metrics(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "registry").mkdir()
            (root / "config").mkdir()
            (root / "public-catalog").mkdir()
            (root / "registry" / "source-catalog.json").write_text(
                json.dumps({"records": [{"source_record_id": "source-a"}]}), encoding="utf-8")
            (root / "config" / "taxonomy.json").write_text('{"domains": [], "query_expansions": []}', encoding="utf-8")
            dataset = {
                "schema_version": "1.1.0",
                "queries": [
                    {"id": "answerable", "query": "security audit", "answerability": {
                        "label": "answerable", "adjudication": self._human_adjudication()},
                     "relevant": {"source-a": 3}, "prediction": {"decision": "recommend"}},
                    {"id": "unanswerable", "query": "native Android SMS receiver", "answerability": {
                        "label": "unanswerable", "adjudication": self._human_adjudication(
                            full_catalog_review=True, out_of_pool_review=True,
                            search_formulations=["Android BroadcastReceiver SMS", "SMS_RECEIVED Kotlin banking"],
                            search_method="full-catalog search plus pinned-body review")},
                     "relevant": {}, "prediction": {"decision": "abstain"}},
                    {"id": "uncertain", "query": "novel hardware protocol", "answerability": {"label": "uncertain"},
                     "relevant": {}},
                ],
            }
            dataset_path = self._write_dataset(tmp, dataset)
            mocked = [{"source_record_id": "source-a", "skill_name": "security-audit",
                       "repository": "example/security", "query_coverage": 1.0, "relevance_score": 50.0}]
            with patch("search_benchmark.search_skills", return_value=mocked):
                result = run_benchmark(root=root, dataset_path=dataset_path, k=5, mrr_k=10)
        self.assertEqual(result["schema_version"], "1.1.0")
        self.assertIsNotNone(result["queries"][0]["retrieval_metrics"])
        self.assertIsNone(result["queries"][1]["retrieval_metrics"])
        self.assertEqual(result["queries"][1]["ranking_metrics_skipped_reason"], "adjudicated_unanswerable")
        self.assertIsNone(result["queries"][2]["retrieval_metrics"])
        self.assertEqual(result["answerability"]["gold_label_counts"], {
            "answerable": 1, "unanswerable": 1, "uncertain": 1})
        self.assertEqual(result["answerability"]["prediction_count"], 2)
        self.assertEqual(result["answerability"]["prediction_metrics"]["no_answer_precision"], 1.0)



    def test_schema_1_1_rejects_boolean_prediction_confidence(self):
        dataset = {
            "schema_version": "1.1.0",
            "queries": [{
                "id": "boolean-confidence", "query": "security audit",
                "answerability": {"label": "answerable", "adjudication": self._human_adjudication()},
                "relevant": {"GASL-SRC-example": 3},
                "prediction": {"decision": "recommend", "confidence": True},
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "confidence must be a number"):
                load_dataset(self._write_dataset(tmp, dataset))



if __name__ == "__main__":
    unittest.main()
