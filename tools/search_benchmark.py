#!/usr/bin/env python3
"""Run a graded, bilingual regression benchmark against the local GASL search index."""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from skill_search import INDEX_VERSION, search_skills, file_fingerprint

ROOT = Path(__file__).resolve().parents[1]
LEGACY_DATASET_SCHEMA = "1.0.0"
ANSWERABILITY_DATASET_SCHEMA = "1.1.0"
ANSWERABILITY_LABELS = {"answerable", "unanswerable", "uncertain"}
SYSTEM_DECISIONS = {"recommend", "abstain", "undetermined"}


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_ids(result):
    ids = result.get("source_record_ids") or [result.get("source_record_id")]
    return [value for value in ids if value]


def result_grade(result, qrels):
    return max((int(qrels.get(source_id, 0)) for source_id in source_ids(result)), default=0)


def dcg(grades):
    return sum((2 ** grade - 1) / math.log2(rank + 1)
               for rank, grade in enumerate(grades, start=1))


def metrics_for_results(results, qrels, k=5, mrr_k=10, relevant_threshold=2):
    k = max(1, int(k))
    mrr_k = max(1, int(mrr_k))
    qrels = {str(key): int(value) for key, value in qrels.items()}
    relevant_ids = {key for key, value in qrels.items() if value >= relevant_threshold}
    grades = [result_grade(result, qrels) for result in results]
    top_k_grades = grades[:k]
    precision = sum(grade >= relevant_threshold for grade in top_k_grades) / k
    retrieved_relevant = {
        source_id
        for result in results[:k]
        for source_id in source_ids(result)
        if qrels.get(source_id, 0) >= relevant_threshold
    }
    recall = len(retrieved_relevant) / len(relevant_ids) if relevant_ids else 0.0
    reciprocal_rank = 0.0
    for rank, grade in enumerate(grades[:mrr_k], start=1):
        if grade >= relevant_threshold:
            reciprocal_rank = 1.0 / rank
            break
    ideal_grades = sorted(qrels.values(), reverse=True)[:k]
    ideal_dcg = dcg(ideal_grades)
    ndcg = dcg(top_k_grades) / ideal_dcg if ideal_dcg else 0.0
    return {
        "precision_at_k": round(precision, 4),
        "recall_at_k": round(recall, 4),
        "mrr_at_k": round(reciprocal_rank, 4),
        "ndcg_at_k": round(ndcg, 4),
        "relevant_judgment_count": len(relevant_ids),
        "retrieved_relevant_count": len(retrieved_relevant),
        "result_count": len(results),
    }


def answerability_metrics(rows):
    """Score explicit recommend/abstain predictions against adjudicated answerability labels.

    Uncertain gold labels are excluded. Undetermined predictions remain in the coverage
    denominator but are not silently treated as either recommend or abstain.
    """
    eligible = [row for row in rows if row.get("gold") in ("answerable", "unanswerable")]
    decisive = [row for row in eligible if row.get("prediction") in ("recommend", "abstain")]
    gold_unanswerable = [row for row in eligible if row["gold"] == "unanswerable"]
    gold_answerable = [row for row in eligible if row["gold"] == "answerable"]
    predicted_abstain = [row for row in decisive if row["prediction"] == "abstain"]
    true_abstain = [row for row in predicted_abstain if row["gold"] == "unanswerable"]
    false_abstain = [row for row in predicted_abstain if row["gold"] == "answerable"]
    false_recommend = [row for row in decisive
                       if row["gold"] == "unanswerable" and row["prediction"] == "recommend"]
    true_recommend = [row for row in decisive
                      if row["gold"] == "answerable" and row["prediction"] == "recommend"]

    def ratio(numerator, denominator):
        return round(numerator / denominator, 4) if denominator else None

    return {
        "evaluable_query_count": len(eligible),
        "decisive_prediction_count": len(decisive),
        "undetermined_prediction_count": sum(row.get("prediction") == "undetermined" for row in eligible),
        "decision_coverage": ratio(len(decisive), len(eligible)),
        "gold_unanswerable_count": len(gold_unanswerable),
        "gold_answerable_count": len(gold_answerable),
        "true_abstain_count": len(true_abstain),
        "false_abstain_count": len(false_abstain),
        "false_recommend_count": len(false_recommend),
        "true_recommend_count": len(true_recommend),
        "no_answer_precision": ratio(len(true_abstain), len(predicted_abstain)),
        "no_answer_recall": ratio(len(true_abstain), len(gold_unanswerable)),
        "false_abstention_rate": ratio(len(false_abstain), len(gold_answerable)),
        "answerable_query_coverage": ratio(len(true_recommend), len(gold_answerable)),
        "false_recommendation_rate_on_unanswerable": ratio(len(false_recommend), len(gold_unanswerable)),
    }


def _validate_human_adjudication(answerability, query_id):
    adjudication = answerability.get("adjudication")
    if not isinstance(adjudication, dict) or adjudication.get("status") != "final":
        raise ValueError("Query {} requires final answerability adjudication.".format(query_id))
    if adjudication.get("reviewer_type") != "independent_human":
        raise ValueError("Query {} requires independent human reviewers; model-simulated personas do not qualify.".format(query_id))
    reviewer_ids = adjudication.get("reviewer_ids")
    if not isinstance(reviewer_ids, list) or len({x for x in reviewer_ids if isinstance(x, str) and x.strip()}) < 2:
        raise ValueError("Query {} requires at least two distinct independent human reviewer IDs.".format(query_id))


def _validate_answerability_query(item):
    query_id = item["id"]
    answerability = item.get("answerability")
    if not isinstance(answerability, dict) or answerability.get("label") not in ANSWERABILITY_LABELS:
        raise ValueError("Query {} requires answerability.label in {}.".format(query_id, sorted(ANSWERABILITY_LABELS)))
    label = answerability["label"]
    relevant = item.get("relevant")
    if not isinstance(relevant, dict):
        raise ValueError("Query {} requires a relevant object (which may be empty only when adjudicated unanswerable).".format(query_id))

    if label == "answerable":
        if not relevant:
            raise ValueError("Answerable query {} requires at least one relevance judgment.".format(query_id))
        _validate_human_adjudication(answerability, query_id)
    elif label == "unanswerable":
        if relevant:
            raise ValueError("Unanswerable query {} must have empty qrels.".format(query_id))
        _validate_human_adjudication(answerability, query_id)
        adjudication = answerability["adjudication"]
        if adjudication.get("full_catalog_review") is not True:
            raise ValueError("Unanswerable query {} requires documented full-catalog review.".format(query_id))
        if adjudication.get("out_of_pool_review") is not True:
            raise ValueError("Unanswerable query {} requires review beyond the pooled candidates.".format(query_id))
        formulations = adjudication.get("search_formulations")
        unique_formulations = {x.strip().casefold() for x in formulations if isinstance(x, str) and x.strip()} if isinstance(formulations, list) else set()
        if len(unique_formulations) < 2:
            raise ValueError("Unanswerable query {} requires at least two distinct documented search formulations.".format(query_id))
        if not isinstance(adjudication.get("search_method"), str) or not adjudication["search_method"].strip():
            raise ValueError("Unanswerable query {} requires a documented search method.".format(query_id))
    # Uncertain labels are deliberately retained but excluded from both ranking and binary
    # answerability metrics until independent adjudication is complete.

    prediction = item.get("prediction")
    if prediction is not None:
        if not isinstance(prediction, dict) or prediction.get("decision") not in SYSTEM_DECISIONS:
            raise ValueError("Query {} prediction.decision must be one of {}.".format(query_id, sorted(SYSTEM_DECISIONS)))
        confidence = prediction.get("confidence")
        if confidence is not None and (isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1):
            raise ValueError("Query {} prediction.confidence must be a number between 0 and 1.".format(query_id))


def load_dataset(path):
    dataset = json.loads(Path(path).read_text(encoding="utf-8"))
    schema_version = dataset.get("schema_version")
    if schema_version not in (LEGACY_DATASET_SCHEMA, ANSWERABILITY_DATASET_SCHEMA):
        raise ValueError("Unsupported search benchmark schema version.")
    queries = dataset.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError("Benchmark must contain at least one query.")
    seen = set()
    relevant_threshold = dataset.get("relevant_threshold", 2)
    if not isinstance(relevant_threshold, int) or not 1 <= relevant_threshold <= 3:
        raise ValueError("relevant_threshold must be an integer from 1 to 3.")
    for item in queries:
        if not isinstance(item, dict) or not item.get("id") or not item.get("query"):
            raise ValueError("Each benchmark query requires id and query.")
        if item["id"] in seen:
            raise ValueError("Duplicate benchmark query id: " + str(item["id"]))
        seen.add(item["id"])
        relevant = item.get("relevant")
        if schema_version == LEGACY_DATASET_SCHEMA:
            if not isinstance(relevant, dict) or not relevant:
                raise ValueError("Each benchmark query requires graded relevant judgments.")
        else:
            _validate_answerability_query(item)
        for source_id, grade in relevant.items():
            if not isinstance(source_id, str) or not isinstance(grade, int) or grade < 0 or grade > 3:
                raise ValueError("Judgments must map source IDs to integer grades from 0 to 3.")
        if schema_version == ANSWERABILITY_DATASET_SCHEMA and item["answerability"]["label"] == "answerable":
            if not any(grade >= relevant_threshold for grade in relevant.values()):
                raise ValueError("Answerable query {} requires at least one grade at or above relevant_threshold.".format(item["id"]))
    return dataset


def run_benchmark(root=ROOT, dataset_path=None, k=5, mrr_k=10):
    root = Path(root)
    dataset_path = Path(dataset_path) if dataset_path else root / "benchmarks" / "search-gold-v1.json"
    dataset = load_dataset(dataset_path)
    source_path = root / "registry" / "source-catalog.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    available_ids = {record.get("source_record_id") for record in source.get("records", [])}
    missing = sorted({
        source_id
        for item in dataset["queries"]
        for source_id in item["relevant"]
        if source_id not in available_ids
    })
    if missing:
        raise ValueError("Benchmark references unknown source_record_id values: " + ", ".join(missing[:10]))

    threshold = int(dataset.get("relevant_threshold", 2))
    query_reports = []
    answerability_rows = []
    gold_label_counts = {label: 0 for label in sorted(ANSWERABILITY_LABELS)}
    for item in dataset["queries"]:
        results = search_skills(item["query"], limit=max(k, mrr_k), root=root)
        if dataset.get("schema_version") == ANSWERABILITY_DATASET_SCHEMA:
            label = item["answerability"]["label"]
            gold_label_counts[label] += 1
            prediction = item.get("prediction", {}).get("decision") if item.get("prediction") else None
            answerability_rows.append({"gold":label,"prediction":prediction or "undetermined"})
            metrics = (metrics_for_results(
                results, item["relevant"], k=k, mrr_k=mrr_k, relevant_threshold=threshold
            ) if label == "answerable" else None)
        else:
            label = "answerable"
            prediction = None
            metrics = metrics_for_results(
                results, item["relevant"], k=k, mrr_k=mrr_k, relevant_threshold=threshold
            )
        query_report = {
            "id": item["id"],
            "language": item.get("language", "unknown"),
            "query": item["query"],
            "answerability_label": label,
            "system_prediction": prediction,
            "retrieval_metrics": metrics,
            "ranking_metrics_skipped_reason": ("adjudicated_unanswerable" if label == "unanswerable" else "answerability_uncertain" if label == "uncertain" else None),
            "top_results": [
                {
                    "source_record_ids": source_ids(result),
                    "skill_name": result.get("skill_name"),
                    "repository": result.get("repository"),
                    "relevance_grade": result_grade(result, item["relevant"]),
                    "query_coverage": result.get("query_coverage"),
                    "relevance_score": result.get("relevance_score"),
                }
                for result in results[:k]
            ],
        }
        if metrics is not None:
            query_report.update(metrics)
        query_reports.append(query_report)

    metric_names = ("precision_at_k", "recall_at_k", "mrr_at_k", "ndcg_at_k")
    ranked_reports = [row for row in query_reports if row["retrieval_metrics"] is not None]
    averages = {
        metric: round(sum(row[metric] for row in ranked_reports) / len(ranked_reports), 4)
        for metric in metric_names
    } if ranked_reports else {metric: None for metric in metric_names}
    language_averages = {}
    for language in sorted({row["language"] for row in ranked_reports}):
        rows = [row for row in ranked_reports if row["language"] == language]
        language_averages[language] = {
            metric: round(sum(row[metric] for row in rows) / len(rows), 4)
            for metric in metric_names
        }

    judgment_count = sum(len(item.get("relevant", {})) for item in dataset["queries"])
    answerability_report = None
    if dataset.get("schema_version") == ANSWERABILITY_DATASET_SCHEMA:
        answerability_report = {
            "gold_label_counts": gold_label_counts,
            "prediction_count": sum(bool(item.get("prediction")) for item in dataset["queries"]),
            "prediction_metrics": answerability_metrics(answerability_rows) if answerability_rows else None,
            "prediction_source": "explicit dataset prediction.decision; no abstention is inferred from result count or ranking score",
        }
    return {
        "schema_version": "1.1.0" if dataset.get("schema_version") == ANSWERABILITY_DATASET_SCHEMA else "1.0.0",
        "benchmark_name": dataset.get("name", "GASL search benchmark"),
        "benchmark_status": dataset.get("status", "unspecified"),
        "generated_at": now(),
        "search_index_version": INDEX_VERSION,
        "source_record_count": len(available_ids),
        "source_catalog_sha256": sha256_file(source_path),
        "taxonomy_sha256": sha256_file(root / "config" / "taxonomy.json"),
        "dataset_sha256": sha256_file(dataset_path),
        "search_inputs_fingerprint": file_fingerprint(root),
        "ranking_code_sha256": sha256_file(Path(__file__).with_name("skill_search.py")),
        "private_metadata_cache_present": (root / "private" / "skill-metadata-cache.json").is_file(),
        "query_count": len(query_reports),
        "judgment_count": judgment_count,
        "k": int(k),
        "mrr_k": int(mrr_k),
        "relevant_threshold": threshold,
        "averages": averages,
        "language_averages": language_averages,
        "answerability": answerability_report,
        "limitations": [
            "This is a provisional internal regression set, not an independently validated quality benchmark.",
            "Unjudged results are treated as non-relevant; metrics are relative to the observed judgment set, not exhaustive ground truth.",
            "Relevance labels require independent review by domain users before public quality claims.",
            "An unanswerable label is accepted only with final independent-human adjudication, at least two reviewer IDs, full-catalog review, out-of-pool review, multiple search formulations and a documented search method.",
            "Answerability predictions must be explicit; the runner never infers abstention from an empty result set or a relevance-score threshold.",
            "Search relevance does not assess Skill safety, licensing, installation eligibility, or behavioral quality.",
        ],
        "queries": query_reports,
    }


def main():
    parser = argparse.ArgumentParser(description="Run the local bilingual GASL search regression benchmark.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--mrr-k", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_benchmark(args.root, args.dataset, args.k, args.mrr_k)
    if args.output:
        output = args.output if args.output.is_absolute() else args.root / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + ".tmp")
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(output)
    print(json.dumps({
        "benchmark_status": result["benchmark_status"],
        "query_count": result["query_count"],
        "judgment_count": result["judgment_count"],
        "k": result["k"],
        "mrr_k": result["mrr_k"],
        "averages": result["averages"],
        "language_averages": result["language_averages"],
        "answerability": result.get("answerability"),
        "output": str(args.output) if args.output else None,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
