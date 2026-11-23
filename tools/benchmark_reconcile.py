#!/usr/bin/env python3
"""Phase 48: reconcile a *provisional* benchmark with commit-pinned Skill snapshots.

Only a local, recorded repository/path/Git-blob identity can carry an old
judgment forward. This never creates human gold labels or verifies publisher
authenticity. Neither benchmark nor source catalog is edited in place.
"""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

from search_benchmark import ROOT, load_dataset, run_benchmark, sha256_file
from skill_search import file_fingerprint

SHA1 = re.compile(r"^[a-f0-9]{40}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
MAPPING_SCHEMA = "gasl-provisional-query-crosswalk-v1"


def _bytes(data):
    return (json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")) +
            "\n").encode("utf-8")


def _unique_records(records, key):
    result = {}
    for record in records:
        value = key(record)
        if not value or value in result:
            raise ValueError("Missing or duplicate catalog identity in benchmark crosswalk")
        result[value] = record
    return result


def _valid_blob(value):
    return isinstance(value, str) and SHA1.fullmatch(value) is not None


def build_mapping(dataset, historical_catalog, historical_revision, historical_sha256):
    """Generate a reviewer-auditable pin from an exact historical Git snapshot."""
    if not SHA1.fullmatch(historical_revision) or not SHA256.fullmatch(historical_sha256):
        raise ValueError("Exact historical Git revision and catalog digest required")
    if dataset.get("status") != "provisional" or dataset.get("schema_version") != "1.0.0":
        raise ValueError("Only original provisional V1 judgments may be crosswalked")
    historical = _unique_records(historical_catalog["records"],
                                 lambda record: record.get("source_record_id"))
    ids = sorted({sid for query in dataset["queries"] for sid in query["relevant"]})
    mapped = []
    for sid in ids:
        record = historical.get(sid)
        if record is None:
            raise ValueError("Missing source ID in historical catalog: " + sid)
        blob = record.get("skill_md_blob_sha")
        if (not _valid_blob(blob)
                or not SHA1.fullmatch(str(record.get("commit_sha") or ""))
                or not record.get("repository") or not record.get("source_path")):
            raise ValueError("Historical Skill is not Git-blob pinned: " + sid)
        mapped.append({
            "historical_source_id": sid,
            "repository": record["repository"],
            "source_path": record["source_path"],
            "historical_commit_sha": record["commit_sha"],
            "git_blob_sha": blob,
        })
    return {
        "schema": MAPPING_SCHEMA,
        "benchmark_status": "provisional_not_independently_adjudicated",
        "historical_revision": historical_revision,
        "historical_catalog_sha256": historical_sha256,
        "identities": mapped,
        "limitation": ("Records are linked by locally recorded repository/path and equal "
                       "Git blob SHA; this does not verify publisher identity or improve "
                       "the original human-review status."),
    }


def inspect_crosswalk(dataset, mapping, current_catalog):
    """Audit every pinned identity without transferring any blocked judgment.

    Content drift is review-required, while identity conflicts or invalid pins
    block evaluation as integrity failures. This never computes rank metrics.
    """
    if dataset.get("status") != "provisional" or dataset.get("schema_version") != "1.0.0":
        raise ValueError("Reconciliation cannot promote an unknown benchmark to gold")
    if mapping.get("schema") != MAPPING_SCHEMA or not SHA1.fullmatch(
            str(mapping.get("historical_revision") or "")) or not SHA256.fullmatch(
            str(mapping.get("historical_catalog_sha256") or "")):
        raise ValueError("Invalid pinned historical benchmark map")
    history = _unique_records(mapping["identities"], lambda x: x.get("historical_source_id"))
    current = _unique_records(current_catalog["records"], lambda x: x.get("source_record_id"))
    by_path = {}
    for row in current.values():
        key = (row.get("repository"), row.get("source_path"))
        by_path.setdefault(key, []).append(row)
    known_ids = {sid for q in dataset["queries"] for sid in q["relevant"]}
    if set(history) != known_ids:
        raise ValueError("Crosswalk IDs do not exactly match original benchmark labels")

    checks = {}
    blocked = {}
    for old_id in sorted(known_ids):
        record = history[old_id]
        if (not _valid_blob(record.get("git_blob_sha"))
                or not SHA1.fullmatch(str(record.get("historical_commit_sha") or ""))
                or not record.get("repository") or not record.get("source_path")):
            raise ValueError("Historical mapping lacks pinned Git blob: " + old_id)
        key = (record["repository"], record["source_path"])
        variants = by_path.get(key, [])
        matches = [x for x in variants if x.get("skill_md_blob_sha") == record["git_blob_sha"]]
        row = {
            "old_source_id": old_id,
            "repository": record["repository"],
            "source_path": record["source_path"],
            "historical_git_blob_sha": record["git_blob_sha"],
            "old_commit_sha": record["historical_commit_sha"],
            "current_candidates": [{
                "source_record_id": x["source_record_id"],
                "commit_sha": x.get("commit_sha"),
                "git_blob_sha": x.get("skill_md_blob_sha"),
            } for x in sorted(variants, key=lambda x: x["source_record_id"])],
        }
        status, error = None, None
        # Reused source IDs may never be reinterpreted as changed content.
        previous_id = current.get(old_id)
        if previous_id is not None and (
                (previous_id.get("repository"), previous_id.get("source_path")) != key
                or previous_id.get("skill_md_blob_sha") != record["git_blob_sha"]):
            status, error = "historical_id_conflict", "Historical source ID now points to another Skill: "
        elif not variants:
            status, error = "missing_path", "Mapped Skill path absent from current catalog: "
        elif not matches:
            if any(not _valid_blob(x.get("skill_md_blob_sha"))
                   or not SHA1.fullmatch(str(x.get("commit_sha") or "")) for x in variants):
                status = "invalid_current_pin"
            else:
                status = "changed_blob"
            error = "Git Blob missing, changed, or ambiguous; rejudgment required: "
        elif len(matches) != 1:
            status, error = "ambiguous_blob", "Git Blob missing, changed, or ambiguous; rejudgment required: "
        else:
            target = matches[0]
            if not SHA1.fullmatch(str(target.get("commit_sha") or "")):
                status, error = "invalid_current_pin", "Current Skill lacks an exact pinned Commit: "
            elif previous_id is not None and old_id != target["source_record_id"]:
                status, error = "historical_id_conflict", "Historical source ID now points to another Skill: "
        if status:
            blocked[old_id] = {**row, "status": status, "strict_error": error + old_id}
            continue
        checks[old_id] = {
            "old_source_id": old_id,
            "current_source_id": target["source_record_id"],
            "repository": record["repository"],
            "source_path": record["source_path"],
            "matching_git_blob_sha": record["git_blob_sha"],
            "old_commit_sha": record["historical_commit_sha"],
            "current_commit_sha": target["commit_sha"],
            "source_id_changed": old_id != target["source_record_id"],
            "commit_changed": record["historical_commit_sha"] != target["commit_sha"],
        }

    # A collision invalidates EVERY historical identity sharing the target.
    by_target = {}
    for old_id, check in checks.items():
        by_target.setdefault(check["current_source_id"], []).append(old_id)
    for target_id, old_ids in by_target.items():
        if len(old_ids) > 1:
            for old_id in old_ids:
                check = checks.pop(old_id)
                blocked[old_id] = {
                    **check, "status": "many_to_one",
                    "conflicting_historical_ids": sorted(old_ids),
                    "strict_error": "Ambiguous many-to-one crosswalk; rejudgment required",
                }

    queries = []
    for q in dataset["queries"]:
        pending = sorted(set(q["relevant"]) & blocked.keys())
        queries.append({
            "query_id": q["id"],
            "judgment_count": len(q["relevant"]),
            "same_blob_eligible_count": len(q["relevant"]) - len(pending),
            "blocked_judgment_count": len(pending),
            "blocked_historical_ids": pending,
        })
    review_statuses = {"missing_path", "changed_blob"}
    integrity = any(row["status"] not in review_statuses for row in blocked.values())
    status = ("integrity_blocked" if integrity else
              "rejudgment_required" if blocked else "ready_provisional")
    return {
        "schema": "gasl-provisional-crosswalk-drift-v1",
        "evaluation_status": status,
        "ranking_metrics_allowed": not blocked,
        "historical_revision": mapping["historical_revision"],
        "historical_catalog_sha256": mapping["historical_catalog_sha256"],
        "query_count": len(queries),
        "distinct_judged_ids": len(known_ids),
        "total_judgments": sum(q["judgment_count"] for q in queries),
        "same_blob_eligible_identity_count": len(checks),
        "same_blob_eligible_judgment_count": sum(q["same_blob_eligible_count"] for q in queries),
        "blocked_identity_count": len(blocked),
        "blocked_judgment_count": sum(q["blocked_judgment_count"] for q in queries),
        "affected_query_count": sum(bool(q["blocked_judgment_count"]) for q in queries),
        "identity_checks": [checks[k] for k in sorted(checks)],
        "blocked_identities": [blocked[k] for k in sorted(blocked)],
        "queries": queries,
        "new_judgments_created": False,
        "original_benchmark_edited": False,
        "current_catalog_edited": False,
        "original_judgments_independently_adjudicated": False,
        "git_blob_reverified_against_live_upstream": False,
    }


def reconcile(dataset, mapping, current_catalog):
    inspection = inspect_crosswalk(dataset, mapping, current_catalog)
    if inspection["blocked_identities"]:
        raise ValueError(inspection["blocked_identities"][0]["strict_error"])
    reasons = inspection["identity_checks"]
    resolved = {x["old_source_id"]: x["current_source_id"] for x in reasons}
    known_ids = set(resolved)
    derived = json.loads(json.dumps(dataset, ensure_ascii=False))
    derived["name"] = dataset.get("name", "GASL") + " — same-blob provisional crosswalk"
    derived["status"] = "provisional_crosswalk_not_independent_gold"
    derived["description"] = (
        "Derived without new judgments: original 26-query internal provisional labels, "
        "relabeled only when same repository/path and Git Blob SHA match. "
        "Never use as calibrated ranking-quality evidence.")
    for query in derived["queries"]:
        query["relevant"] = {resolved[sid]: grade for sid, grade in query["relevant"].items()}
    audit = {
        "schema": MAPPING_SCHEMA,
        "historical_revision": mapping["historical_revision"],
        "historical_catalog_sha256": mapping["historical_catalog_sha256"],
        "query_count": len(derived["queries"]),
        "distinct_judged_ids": len(known_ids),
        "total_judgments": sum(len(q["relevant"]) for q in derived["queries"]),
        "remapped_source_id_count": sum(x["source_id_changed"] for x in reasons),
        "changed_commit_count": sum(x["commit_changed"] for x in reasons),
        "unchanged_git_blob_count": len(reasons),
        "identity_checks": reasons,
        "original_judgments_independently_adjudicated": False,
        "git_blob_reverified_against_live_upstream": False,
        "original_benchmark_edited": False,
        "current_catalog_edited": False,
    }
    return derived, audit


def historical_from_git(root, revision):
    if not SHA1.fullmatch(revision):
        raise ValueError("Historical revision must be a complete 40-character Git SHA")
    raw = subprocess.check_output(
        ["git", "-C", str(root), "show", revision + ":registry/source-catalog.json"])
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _write(path, document):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # A unique same-directory temporary file avoids following a pre-created
    # fixed .tmp alias and supports atomic replacement on Windows/POSIX.
    destination = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            destination = Path(stream.name)
            stream.write(_bytes(document))
        destination.replace(path)
    finally:
        if destination is not None:
            destination.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--dataset", type=Path, default=ROOT/"benchmarks"/"search-gold-v1.json")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--historical-revision")
    group.add_argument("--map", type=Path)
    parser.add_argument("--write-map", type=Path,
                        help="Produce the pinned mapping after reading the old Git catalog.")
    outputs = parser.add_mutually_exclusive_group()
    outputs.add_argument("--report", type=Path, help="Write reconciled provisional benchmark report.")
    outputs.add_argument("--audit-report", type=Path,
                         help="Write read-only version-drift audit, without ranking metrics.")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    source_path = args.root/"registry"/"source-catalog.json"
    if args.audit_report:
        if args.write_map:
            parser.error("--audit-report is read-only and cannot be combined with --write-map")
        protected = [source_path, args.dataset, args.map]
        if any(args.audit_report.resolve() == p.resolve() for p in protected if p is not None):
            parser.error("Audit report must not overwrite benchmark, crosswalk or catalog")
    source_bytes = source_path.read_bytes()
    current = json.loads(source_bytes)
    dataset_bytes = args.dataset.read_bytes()
    dataset = load_dataset(args.dataset)
    if dataset != json.loads(dataset_bytes):
        raise ValueError("Benchmark dataset changed while reading; retry with a stable snapshot")
    if args.historical_revision:
        historical, digest = historical_from_git(args.root, args.historical_revision)
        mapping = build_mapping(dataset, historical, args.historical_revision, digest)
        if args.write_map:
            _write(args.write_map, mapping)
    else:
        if args.write_map:
            parser.error("--write-map requires --historical-revision")
        mapping = json.loads(args.map.read_text(encoding="utf-8"))
    if args.audit_report:
        inspection = inspect_crosswalk(dataset, mapping, current)
        inspection["current_catalog_sha256"] = hashlib.sha256(source_bytes).hexdigest()
        inspection["original_dataset_sha256"] = hashlib.sha256(dataset_bytes).hexdigest()
        inspection["crosswalk_sha256"] = hashlib.sha256(_bytes(mapping)).hexdigest()
        _write(args.audit_report, inspection)
        print(json.dumps({key: value for key, value in inspection.items()
                          if key not in ("identity_checks", "queries")},
                         ensure_ascii=False, indent=2))
        # Ordinary upstream drift is not a software error; integrity conflicts are.
        # Neither allows metrics. The original strict --report still raises.
        if inspection["evaluation_status"] == "integrity_blocked":
            raise SystemExit(2)
        return
    derived, audit = reconcile(dataset, mapping, current)
    audit["current_catalog_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    audit["original_dataset_sha256"] = hashlib.sha256(dataset_bytes).hexdigest()
    audit["crosswalk_sha256"] = hashlib.sha256(_bytes(mapping)).hexdigest()
    if args.report:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"provisional-crosswalk.json"
            path.write_bytes(_bytes(derived))
            report = run_benchmark(root=args.root, dataset_path=path, k=args.k)
        # Never pretend this is a formal gold evaluation.
        report["benchmark_status"] = derived["status"]
        report["dataset_sha256"] = audit["original_dataset_sha256"]
        report["derived_dataset_sha256"] = hashlib.sha256(_bytes(derived)).hexdigest()
        report["reconciliation"] = audit
        report["limitations"].append(
            "All judgments remain provisional. Git blob equality transfers no independent "
            "quality proof; unjudged results are treated as non-relevant for these metrics.")
        _write(args.report, report)
        print(json.dumps({
            "status": report["benchmark_status"], "query_count": report["query_count"],
            "judgment_count": report["judgment_count"], "remapped_ids": audit["remapped_source_id_count"],
            "averages": report["averages"], "report": str(args.report),
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
