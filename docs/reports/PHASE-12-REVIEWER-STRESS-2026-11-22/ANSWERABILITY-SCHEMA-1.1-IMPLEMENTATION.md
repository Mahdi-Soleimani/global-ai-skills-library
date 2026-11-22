# Answerability-aware benchmark schema 1.1.0

**Status:** Implemented and unit-tested; not yet connected to a calibrated router abstention predictor.

## Why this exists

The legacy benchmark schema `1.0.0` requires every query to have a non-empty `relevant` dictionary. It therefore cannot distinguish:

- an answerable query with relevant Skills;
- an adjudicated unanswerable query that should produce no recommendation;
- a query whose answerability is still uncertain.

Schema `1.1.0` adds explicit answerability labels and optional system decisions without changing the legacy `1.0.0` dataset contract.

## Query fields

Every `1.1.0` query contains:

- `answerability.label`: `answerable`, `unanswerable`, or `uncertain`.
- `relevant`: graded Source ID judgments. It must be non-empty for `answerable`, empty for `unanswerable`, and may be empty for `uncertain`.
- `answerability.adjudication`: required for final `answerable` and `unanswerable` labels.
- `prediction.decision`: optional explicit system decision: `recommend`, `abstain`, or `undetermined`.
- `prediction.confidence`: optional number from 0 to 1.

## Gold-label safeguards

For `answerable` and `unanswerable`, the loader requires:

- `adjudication.status = final`;
- `adjudication.reviewer_type = independent_human`;
- at least two distinct `reviewer_ids`.

For `unanswerable`, it additionally requires:

- `full_catalog_review = true`;
- `out_of_pool_review = true`;
- at least two distinct `search_formulations`;
- a non-empty `search_method`.

Model-simulated personas cannot satisfy the independent-human gate. The 10-persona Phase 12 review is not accepted as gold no-answer evidence.

## Illustrative unanswerable record

This is a schema illustration only; the reviewer IDs and search evidence must be replaced by real, independently verified review records before use as gold data.

```json
{
  "id": "example-no-answer",
  "query": "Native Android BroadcastReceiver banking SMS ingestion",
  "answerability": {
    "label": "unanswerable",
    "adjudication": {
      "status": "final",
      "reviewer_type": "independent_human",
      "reviewer_ids": ["human-reviewer-a", "human-reviewer-b"],
      "full_catalog_review": true,
      "out_of_pool_review": true,
      "search_formulations": [
        "Android BroadcastReceiver bank SMS",
        "SMS_RECEIVED Kotlin banking message parser"
      ],
      "search_method": "Document the actual catalog, metadata and pinned-body search procedure here."
    }
  },
  "relevant": {},
  "prediction": {
    "decision": "abstain",
    "confidence": 0.82
  }
}
```

## Metrics

The evaluator reports answerability separately from ranking metrics:

- `no_answer_precision`;
- `no_answer_recall`;
- `false_abstention_rate` on answerable queries;
- `answerable_query_coverage`;
- `false_recommendation_rate_on_unanswerable`;
- `decision_coverage` and the count of `undetermined` decisions.

`uncertain` gold labels are excluded from binary answerability metrics. Missing system predictions are represented as `undetermined`, not silently treated as `recommend` or `abstain`.

Ranking metrics (Precision@K, Recall@K, MRR, NDCG) are calculated only for answerable queries. They are skipped for adjudicated unanswerable and uncertain queries.

## Important implementation boundary

The runner consumes an explicit `prediction.decision`; it does not infer abstention from an empty result list, a low lexical score, or an arbitrary threshold. `tools/skill_router.py` still does not produce a calibrated abstention decision. No production abstention behavior was added in this step.

## Compatibility and validation

- Dataset schema `1.0.0` remains supported without changes.
- Dataset schema `1.1.0` supports answerable, unanswerable and uncertain labels.
- Empty qrels are accepted only for an adjudicated unanswerable query that passes all human-review and search-evidence checks.
- The existing 26-query / 148-judgment v1.0 benchmark was run successfully after the change.
- A synthetic in-memory smoke fixture exercised answerable, unanswerable and uncertain paths. Its placeholder reviewer IDs and perfect sample metrics are test data only, not actual human judgments or system-quality results.
