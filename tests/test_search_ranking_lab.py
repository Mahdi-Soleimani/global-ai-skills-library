"""Phase 48: test same-pool ranking experiments without promoting a winner."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from search_ranking_lab import VARIANTS, rank_same_pool, run_ablation
from tests.test_benchmark_reconcile import dataset, current, historical, OLD_COMMIT
from benchmark_reconcile import build_mapping

def candidate(sid, coverage, score, title):
    return {
        "source_record_id": sid, "source_record_ids": [sid],
        "skill_name": title, "description": "API research and tools",
        "repository": "example/repo", "source_path": "skills/"+title+"/SKILL.md",
        "fts_rank": -3.0, "query_coverage": coverage, "relevance_score": score,
    }


class RankingLabTests(unittest.TestCase):
    def test_production_order_is_untouched_and_input_not_modified(self):
        values = [candidate("a", 0.9, 4, "api"), candidate("b", 0.9, 9, "security")]
        original = copy.deepcopy(values)
        output = rank_same_pool(values, "API security", variant="production")
        self.assertEqual(output, values)
        self.assertIsNot(output, values)
        self.assertEqual(values, original)

    def test_score_first_is_different_and_preserves_all_candidates(self):
        values = [candidate("a", 1.0, 4, "api"), candidate("b", 0.8, 9, "security")]
        ranked = rank_same_pool(values, "API security", variant="score_first")
        self.assertEqual([item["source_record_id"] for item in ranked], ["b", "a"])
        self.assertEqual(len(ranked), len(values))

    def test_named_entity_variant_only_applies_when_named_term_present(self):
        values = [
            candidate("a", 1.0, 8, "generic"),
            candidate("b", 0.8, 6, "fastapi"),
        ]
        named = rank_same_pool(values, "FastAPI security", variant="named_entity_first")
        self.assertEqual(named[0]["source_record_id"], "b")
        generic = rank_same_pool(values, "review code", variant="named_entity_first")
        self.assertEqual(generic[0]["source_record_id"], "a")

    def test_unknown_variant_refused(self):
        with self.assertRaisesRegex(ValueError, "Unknown"):
            rank_same_pool([], "query", variant="pretend-best")

    def test_paired_ablation_report_keeps_production_and_avoids_quality_claim(self):
        ds=dataset()
        mapping=build_mapping(ds,historical(),OLD_COMMIT,"e"*64)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"registry").mkdir()
            (root/"registry"/"source-catalog.json").write_text(json.dumps(current()))
            (root/"config").mkdir()
            (root/"config"/"taxonomy.json").write_text('{"query_expansions":[]}')
            rows=[candidate("GASL-SRC-new",1.0,5,"alpha"),
                  candidate("GASL-SRC-keep",0.8,8,"beta")]
            with patch("search_ranking_lab.search_skills",return_value=rows) as search:
                result=run_ablation(ds,mapping,current(),root=root)
            self.assertEqual(search.call_count,2)
            self.assertEqual(result["query_count"],2)
            self.assertEqual(result["judgment_count"],4)
            self.assertEqual(set(result["metrics"]),set(VARIANTS))
            self.assertEqual(result["mean_top5_judged_fraction"],0.4)
            self.assertFalse(result["production_ranker_changed"])
            self.assertFalse(result["ranker_winner_selected"])
            self.assertFalse(result["independent_human_gold_available"])
            self.assertFalse(result["no_answer_gold_available"])
            self.assertIn("incomplete labels"," ".join(result["limitations"]))

    def test_real_26_query_report_is_provisional_and_not_promoted(self):
        report=json.loads((ROOT/"docs/reports"/
            "PHASE-48-PROVISIONAL-RANKING-ABLATION-2026-11-23.json").read_text())
        self.assertEqual(report["query_count"],26)
        self.assertEqual(report["judgment_count"],148)
        self.assertEqual(set(report["metrics"]),set(VARIANTS))
        self.assertFalse(report["production_ranker_changed"])
        self.assertFalse(report["ranker_winner_selected"])
        self.assertLess(report["mean_top5_judged_fraction"],0.75)


if __name__ == "__main__":
    unittest.main()
