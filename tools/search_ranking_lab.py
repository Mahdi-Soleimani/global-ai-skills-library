#!/usr/bin/env python3
"""Phase 48 development-only ranking ablations over an identical top-10 candidate pool.

DO NOT ship the best-looking candidate from this provisional dataset: results are
not independently judged, include unjudged-as-zero bias and lack no-answer gold.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from benchmark_reconcile import reconcile, sha256_file
from search_benchmark import ROOT, metrics_for_results, source_ids
from skill_search import (
    search_skills, query_term_group_specs, query_tokens,
    normalize_text, NEGATION_ENTITY_TERMS, _relevance_details,
)

EXPERIMENT_SCHEMA = "gasl-provisional-ranking-ablation-v1"
VARIANTS = ("production", "score_first", "core_evidence_first", "named_entity_first")


def _core_relevance(query, item, specs):
    return _relevance_details(query, {
        "skill_name": item.get("skill_name") or "",
        "description": item.get("description") or "",
        "source_path": item.get("source_path") or "",
        "repository": item.get("repository") or "",
        "domains_text": "",
        "research_leads": "",
        "search_text": "",
        "feature_terms": [],
    }, term_group_specs=specs)


def rank_same_pool(results, query, root=ROOT, variant="production"):
    if variant not in VARIANTS:
        raise ValueError("Unknown experimental ranker")
    if variant == "production":
        return list(results)  # Preserve actual current production retrieval.
    terms = query_term_group_specs(query, root)
    named = set(query_tokens(query)) & NEGATION_ENTITY_TERMS
    scored = []
    for i, item in enumerate(results):
        common = (-float(item.get("query_coverage") or 0),
                  -float(item.get("relevance_score") or 0),
                  float(item.get("fts_rank") or 0),
                  str(item.get("skill_name") or "").casefold(),
                  str(item.get("source_record_id") or ""), i)
        if variant == "score_first":
            key = (common[1], common[0], *common[2:])
        elif variant == "core_evidence_first":
            core = _core_relevance(query, item, terms)
            key = (common[0], -float(core["score"]), common[1], *common[2:])
        else:
            fields = normalize_text(" ".join(str(item.get(key) or "") for key in (
                "skill_name", "description", "source_path", "repository"
            )))
            words = set(query_tokens(fields))
            coverage = len(named & words) / len(named) if named else 0.0
            key = (-coverage, *common) if named else common
        scored.append((key, item))
    scored.sort(key=lambda x: x[0])
    return [item for _, item in scored]


def run_ablation(dataset, source_mapping, current_catalog, root=ROOT, k=5):
    """Paired report only: no changes to GASL production scoring or source labels."""
    root = Path(root)
    derived, provenance = reconcile(dataset, source_mapping, current_catalog)
    metric_fields = ("precision_at_k", "recall_at_k", "mrr_at_k", "ndcg_at_k")
    rows = []
    for query in derived["queries"]:
        candidates = search_skills(query["query"], limit=10, root=root)
        original = {field: metrics_for_results(
            candidates, query["relevant"], k=k, mrr_k=10)[field]
            for field in metric_fields}
        graded = {}
        variant_top_ids = {}
        for variant in VARIANTS:
            ranked = rank_same_pool(candidates, query["query"], root=root, variant=variant)
            graded[variant] = metrics_for_results(ranked, query["relevant"], k=k, mrr_k=10)
            variant_top_ids[variant] = [
                item.get("source_record_id") for item in ranked[:k]]
        assert {key: graded["production"][key] for key in metric_fields} == original
        judged = set(query["relevant"])
        judged_top = sum(bool(set(source_ids(result)) & judged)
                         for result in candidates[:k])
        relevant = {sid for sid, grade in query["relevant"].items() if grade >= 2}
        found = set(sid for result in candidates for sid in source_ids(result)) & relevant
        rows.append({
            "id": query["id"],
            "language": query.get("language", "unknown"),
            "candidate_count": len(candidates),
            "relevant_source_count_in_candidate_pool": len(found),
            "relevant_source_count_in_labels": len(relevant),
            "retrieval_pool_recall_at_10": round(len(found) / len(relevant), 4) if relevant else None,
            "judged_result_fraction_at_5": round(judged_top / k, 4),
            "metrics": graded,
            "top_k_source_ids": variant_top_ids,
        })
    totals = {}
    languages = {}
    for variant in VARIANTS:
        totals[variant] = {
            metric: round(sum(row["metrics"][variant][metric] for row in rows) / len(rows), 4)
            for metric in metric_fields
        }
        languages[variant] = {}
        for language in sorted({row["language"] for row in rows}):
            selected = [row for row in rows if row["language"] == language]
            languages[variant][language] = {
                metric: round(sum(row["metrics"][variant][metric] for row in selected)/len(selected), 4)
                for metric in metric_fields
            }
    changes = {}
    for variant in VARIANTS[1:]:
        comparisons = Counter()
        for row in rows:
            before = row["metrics"]["production"]["ndcg_at_k"]
            after = row["metrics"][variant]["ndcg_at_k"]
            comparisons["improved" if after > before else "regressed" if after < before else "unchanged"] += 1
        changes[variant] = dict(comparisons)
    return {
        "schema": EXPERIMENT_SCHEMA,
        "status": "provisional_development_only_not_independent_evaluation",
        "query_count": len(rows),
        "judgment_count": provenance["total_judgments"],
        "crosswalk_source_id_changes": provenance["remapped_source_id_count"],
        "source_catalog_sha256": sha256_file(root/"registry"/"source-catalog.json"),
        "production_ranker_changed": False,
        "ranker_winner_selected": False,
        "no_answer_gold_available": False,
        "independent_human_gold_available": False,
        "common_candidate_pool_limit": 10,
        "metrics": totals,
        "language_metrics": languages,
        "paired_ndcg_query_outcomes": changes,
        "mean_top5_judged_fraction": round(
            sum(row["judged_result_fraction_at_5"] for row in rows)/len(rows), 4),
        "mean_candidate_pool_recall_at_10": round(
            sum(row["retrieval_pool_recall_at_10"] for row in rows)/len(rows), 4),
        "queries": rows,
        "limitations": [
            "Ablations reorder only the SAME top-10 candidates returned by the existing ranker.",
            "Higher scores on these already-seen provisional labels are NOT evidence of real-world quality gains.",
            "Unjudged results are treated as zero; metric differences are biased by incomplete labels.",
            "No independent human adjudication, no unseen holdout, and no validated answerability labels exist.",
            "No variant is promoted to production, no Skill is installed or executed.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--dataset", type=Path, default=ROOT/"benchmarks"/"search-gold-v1.json")
    parser.add_argument("--map", type=Path, default=ROOT/"benchmarks"/"search-gold-v1-crosswalk.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    from search_benchmark import load_dataset
    data = load_dataset(args.dataset)
    mapping = json.loads(args.map.read_text(encoding="utf-8"))
    current = json.loads((args.root/"registry"/"source-catalog.json").read_text(encoding="utf-8"))
    result = run_ablation(data, mapping, current, root=args.root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temp = args.output.with_suffix(args.output.suffix+".tmp")
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        temp.replace(args.output)
    print(json.dumps({
        "status": result["status"], "query_count": result["query_count"],
        "mean_top5_judged_fraction": result["mean_top5_judged_fraction"],
        "metrics": result["metrics"],
        "paired_ndcg_query_outcomes": result["paired_ndcg_query_outcomes"],
        "production_ranker_changed": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
