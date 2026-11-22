#!/usr/bin/env python3
"""Build a compact attributed vocabulary index from verified upstream metadata.

Only terms from the maintained taxonomy are stored, never original descriptions,
instructions, embeddings, or the Skill body. License class does not filter
source eligibility. Fetching is bounded, incremental and does not execute Skills.
"""
import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import urllib.request

from enrich_skill_metadata import parse_search_metadata, round_robin_by_repository
from gasl_service import MAX_SKILL_BYTES, USER_AGENT, _pinned_raw_url, verify_skill_blob
from safe_http import open_pinned_url
from skill_search import ROOT, query_tokens

SCHEMA = "1.1.0"
SHA = re.compile(r"^[0-9a-f]{40}$")
RELATIVE_PATH = "registry/search-features.json"
PERMANENT_FAILURE_TYPES = {"FeatureSizeLimitError"}


class FeatureSizeLimitError(ValueError):
    """A policy-based size exclusion that should remain recorded, not retried."""


def vocabulary(root):
    taxonomy = json.loads((Path(root) / "config/taxonomy.json").read_text(encoding="utf-8"))
    terms = set()
    for rule in taxonomy.get("query_expansions", []):
        for phrase in rule.get("terms", []) + rule.get("expand", []):
            terms.update(t for t in query_tokens(phrase) if t.isascii())
    for domain in taxonomy.get("domains", []):
        for phrase in domain.get("keywords", []):
            terms.update(t for t in query_tokens(phrase) if t.isascii())
    return terms


def vocabulary_hash(terms):
    return hashlib.sha256("\n".join(sorted(terms)).encode("utf-8")).hexdigest()


def feature_terms(metadata, terms):
    text = " ".join(str(metadata.get(k) or "") for k in
                    ("skill_name", "description", "compatibility", "tags"))
    return sorted(set(query_tokens(text)) & terms)


def fetch_feature(record, terms, timeout=12):
    request = urllib.request.Request(_pinned_raw_url(record), headers={
        "User-Agent": USER_AGENT, "Accept": "text/plain"})
    with open_pinned_url(request, timeout=timeout) as response:
        raw = response.read(MAX_SKILL_BYTES + 1)
    if len(raw) > MAX_SKILL_BYTES:
        raise FeatureSizeLimitError("SKILL.md exceeds byte limit")
    blob = verify_skill_blob(raw, record)
    metadata = parse_search_metadata(raw.decode("utf-8-sig"), record,
                                     hashlib.sha256(raw).hexdigest(), "pinned_upstream_fetch")
    return {"repository": record["repository"], "source_path": record["source_path"],
            "commit_sha": record["commit_sha"], "verified_at_commit": record["commit_sha"], "git_blob_sha": blob,
            "terms": feature_terms(metadata, terms)}


def matches_record(feature, record, terms):
    vals = feature.get("terms")
    return (isinstance(vals, list) and all(isinstance(t, str) and t in terms for t in vals)
            and feature.get("repository") == record.get("repository")
            and feature.get("source_path") == record.get("source_path")
            and feature.get("commit_sha") == record.get("commit_sha")
            and feature.get("git_blob_sha") == record.get("skill_md_blob_sha")
            and bool(SHA.fullmatch(str(record.get("skill_md_blob_sha") or "")))
            and bool(SHA.fullmatch(str(feature.get("verified_at_commit") or "")))
            and record.get("snapshot_status") == "verified_commit_pinned")


def _read_feature_rows(root, terms):
    path = Path(root) / RELATIVE_PATH
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema_version") != SCHEMA or data.get("vocabulary_sha256") != vocabulary_hash(terms):
            return {}
        rows = data["records"]
        return rows if isinstance(rows, dict) else {}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def load_features(root, records):
    """Ignore stale or incompatible derived indexes, including unknown tokens."""
    path = Path(root) / RELATIVE_PATH
    if not path.is_file():
        return {}
    terms = vocabulary(root)
    rows = _read_feature_rows(root, terms)
    return {r["source_record_id"]: rows[r["source_record_id"]] for r in records
            if isinstance(rows.get(r.get("source_record_id")), dict)
            and matches_record(rows[r["source_record_id"]], r, terms)}


def reuse_unchanged_blobs(root, eligible, valid, terms):
    """A different repository commit need not trigger a fetch of identical bytes."""
    previous = {}
    for row in _read_feature_rows(root, terms).values():
        if not isinstance(row, dict):
            continue
        key = (row.get("repository"), row.get("source_path"), row.get("git_blob_sha"))
        if all(isinstance(v, str) for v in key) and SHA.fullmatch(str(row.get("commit_sha") or "")):
            previous[key] = row
    reused = 0
    for record in eligible:
        sid = record["source_record_id"]
        if sid in valid:
            continue
        old = previous.get((record["repository"], record["source_path"], record["skill_md_blob_sha"]))
        if old:
            candidate = {**old, "commit_sha": record["commit_sha"]}
            if matches_record(candidate, record, terms):
                valid[sid] = candidate
                reused += 1
    return reused


def _read_failures(root, terms, eligible):
    """Carry only failures associated with the current exact source pin."""
    try:
        data = json.loads((Path(root) / RELATIVE_PATH).read_text(encoding="utf-8"))
        if data.get("schema_version") != SCHEMA or data.get("vocabulary_sha256") != vocabulary_hash(terms):
            return {}
        previous = data.get("failures", {})
        result = {}
        for r in eligible:
            sid = r["source_record_id"]
            item = previous.get(sid)
            if (isinstance(item, dict) and item.get("commit_sha") == r["commit_sha"]
                    and item.get("git_blob_sha") == r["skill_md_blob_sha"]
                    and isinstance(item.get("attempts"), int) and item["attempts"] > 0):
                result[sid] = item
        return result
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def _save_features(root, terms, valid, failures):
    output = {"schema_version": SCHEMA, "vocabulary_sha256": vocabulary_hash(terms),
              "source_scope": "verified_pinned_frontmatter_vocabulary_only",
              "records": dict(sorted(valid.items())),
              "failures": dict(sorted(failures.items()))}
    path = root / RELATIVE_PATH
    text = json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".search-features-", delete=False) as stream:
        temp = Path(stream.name)
        stream.write(text)
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def refresh(root=ROOT, limit=100, workers=4, fetch=fetch_feature):
    root = Path(root)
    if not 1 <= workers <= 8 or not 0 <= limit <= 500:
        raise ValueError("limit must be 0..500; workers must be 1..8")
    source = json.loads((root / "registry/source-catalog.json").read_text(encoding="utf-8"))["records"]
    terms = vocabulary(root)
    valid = load_features(root, source)
    eligible = [r for r in source if r.get("snapshot_status") == "verified_commit_pinned"
                and r.get("skill_md_blob_sha")]
    reused = reuse_unchanged_blobs(root, eligible, valid, terms)
    failures = _read_failures(root, terms, eligible)
    failures = {sid: item for sid, item in failures.items() if sid not in valid}
    permanent_failure_ids = {sid for sid, item in failures.items()
                             if item.get("error_type") in PERMANENT_FAILURE_TYPES}
    # Unattempted records first, then least-attempted retryable failures.
    # Policy-based size exclusions stay in the ledger but are not fetched again.
    # Stable order within each tier preserves repository round-robin fairness.
    pending = round_robin_by_repository([
        r for r in eligible
        if r["source_record_id"] not in valid
        and r["source_record_id"] not in permanent_failure_ids
    ])
    pending.sort(key=lambda r: failures.get(r["source_record_id"], {}).get("attempts", 0))
    pending = pending[:limit]
    records_by_id = {r["source_record_id"]: r for r in pending}

    def work(record):
        try:
            result = fetch(record, terms)
            if not matches_record(result, record, terms):
                raise ValueError("Invalid feature evidence")
            return record["source_record_id"], result, None
        except (OSError, ValueError, RuntimeError) as exc:
            return record["source_record_id"], None, type(exc).__name__

    errors = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for completed, (sid, row, error) in enumerate(pool.map(work, pending), 1):
            if row is not None:
                valid[sid] = row
                failures.pop(sid, None)
            else:
                errors[sid] = error
                r = records_by_id[sid]
                failures[sid] = {
                    "commit_sha": r["commit_sha"], "git_blob_sha": r["skill_md_blob_sha"],
                    "attempts": failures.get(sid, {}).get("attempts", 0) + 1,
                    "error_type": error,
                }
            if completed % 25 == 0:
                _save_features(root, terms, valid, failures)
    _save_features(root, terms, valid, failures)
    return {"eligible": len(eligible), "attempted": len(pending),
            "new_verified": len(pending) - len(errors), "reused_unchanged_blobs": reused, "failed": len(errors),
            "verified_records": len(valid), "remaining": len(eligible) - len(valid),
            "vocabulary_terms": len(terms), "pending_failure_records": len(failures),
            "permanent_exclusions": sum(1 for item in failures.values()
                                         if item.get("error_type") in PERMANENT_FAILURE_TYPES),
            "errors": errors}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    print(json.dumps(refresh(args.root, args.limit, args.workers), indent=2))


if __name__ == "__main__":
    main()
