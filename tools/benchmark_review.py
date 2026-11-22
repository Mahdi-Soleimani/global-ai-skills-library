#!/usr/bin/env python3
"""Preflight and validate independent human GASL benchmark review packets.

This module never creates relevance labels. It checks packet integrity, reviewer
attestations, source pins, completed annotations and answerability evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import csv
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = ROOT / "private" / "benchmark-review"
DEFAULT_CATALOG = ROOT / "registry" / "source-catalog.json"

CANDIDATE_COLUMNS = [
    "pair_id", "target_domain", "query_en_id", "query_en", "query_fa_id", "query_fa",
    "source_record_id", "skill_name", "repository", "source_path", "commit_sha",
    "skill_md_blob_sha", "description", "license_spdx", "relevance_grade", "rationale",
    "content_checked", "language_specific_exception",
]
ANSWERABILITY_COLUMNS = [
    "pair_id", "target_domain", "query_en_id", "query_en", "query_fa_id", "query_fa",
    "candidate_count", "answerability_status", "direct_match_source_ids",
    "partial_match_source_ids", "additional_source_ids_found", "full_catalog_reviewed",
    "out_of_pool_reviewed", "search_formulations", "search_method", "rationale",
    "language_specific_exception",
]
ATTESTATION_COLUMNS = [
    "reviewer_id", "reviewer_type", "completed_at_utc", "independence_confirmed",
    "saw_other_reviewer_material", "saw_private_manifest_or_audit",
    "used_model_generated_judgments", "conflict_of_interest", "attestation",
]
ANSWERABILITY_STATUSES = {
    "direct_match_found", "partial_match_only", "no_relevant_skill_found", "uncertain"
}
YES_NO = {"yes", "no"}


def read_csv(path: Path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames or [], list(reader)


def write_csv(path: Path, columns, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_source_index(path=DEFAULT_CATALOG):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    records = data.get("records", [])
    index = {}
    for record in records:
        source_id = record.get("source_record_id")
        if source_id:
            index[source_id] = record
    return index


def split_ids(value):
    return [part.strip() for part in re.split(r"[;,\n]+", value or "") if part.strip()]


def split_formulations(value):
    return [part.strip() for part in re.split(r"[;\n]+", value or "") if part.strip()]


def _check_columns(path, actual, required, errors):
    missing = [column for column in required if column not in actual]
    if missing:
        errors.append("{} missing required columns: {}".format(path, ", ".join(missing)))


def _check_source_pin(row, source_index, location, errors):
    source_id = (row.get("source_record_id") or "").strip()
    record = source_index.get(source_id)
    if not source_id:
        errors.append("{} has an empty source_record_id".format(location))
        return
    if record is None:
        errors.append("{} references unknown source ID {}".format(location, source_id))
        return
    for field in ("repository", "source_path", "commit_sha", "skill_md_blob_sha"):
        expected = str(record.get(field) or "").strip()
        actual = str(row.get(field) or "").strip()
        if expected != actual:
            errors.append("{} source pin mismatch for {} ({})".format(location, source_id, field))


def validate_candidate_sheet(path, source_index, require_complete=False):
    errors, incomplete, warnings = [], [], []
    columns, rows = read_csv(path)
    _check_columns(path, columns, CANDIDATE_COLUMNS, errors)
    seen = set()
    for number, row in enumerate(rows, start=2):
        location = "{}:{}".format(path, number)
        pair_id = (row.get("pair_id") or "").strip()
        source_id = (row.get("source_record_id") or "").strip()
        if not pair_id:
            errors.append(location + " has an empty pair_id")
        key = (pair_id, source_id)
        if key in seen:
            errors.append("{} duplicates pair/source key {}".format(location, key))
        seen.add(key)
        for field in ("query_en_id", "query_en", "query_fa_id", "query_fa"):
            if not (row.get(field) or "").strip():
                errors.append("{} has an empty {}".format(location, field))
        _check_source_pin(row, source_index, location, errors)

        grade = (row.get("relevance_grade") or "").strip()
        if not grade:
            incomplete.append("{} missing relevance_grade".format(location))
        elif grade not in {"0", "1", "2", "3"}:
            errors.append("{} relevance_grade must be 0, 1, 2 or 3".format(location))
        else:
            if grade in {"1", "2", "3"} and not (row.get("rationale") or "").strip():
                errors.append("{} grades 1-3 require a rationale".format(location))
            checked = (row.get("content_checked") or "").strip().casefold()
            if checked not in YES_NO:
                errors.append("{} content_checked must be yes or no".format(location))
        if not grade and ((row.get("rationale") or "").strip() or (row.get("content_checked") or "").strip()):
            warnings.append("{} has review metadata but no grade".format(location))

    return {
        "path": str(path), "row_count": len(rows), "rows": rows, "columns": columns,
        "keys": seen, "errors": errors, "incomplete": incomplete, "warnings": warnings,
    }


def validate_answerability_sheet(path, source_index, candidate_rows, require_complete=False):
    errors, incomplete, warnings = [], [], []
    columns, rows = read_csv(path)
    _check_columns(path, columns, ANSWERABILITY_COLUMNS, errors)
    seen_pairs = set()
    candidate_by_pair = {}
    for candidate in candidate_rows:
        candidate_by_pair.setdefault(candidate.get("pair_id", ""), {})[candidate.get("source_record_id", "")] = candidate

    for number, row in enumerate(rows, start=2):
        location = "{}:{}".format(path, number)
        pair_id = (row.get("pair_id") or "").strip()
        if not pair_id:
            errors.append(location + " has an empty pair_id")
        if pair_id in seen_pairs:
            errors.append("{} duplicates pair_id {}".format(location, pair_id))
        seen_pairs.add(pair_id)
        for field in ("query_en_id", "query_en", "query_fa_id", "query_fa"):
            if not (row.get(field) or "").strip():
                errors.append("{} has an empty {}".format(location, field))
        expected_count = len(candidate_by_pair.get(pair_id, {}))
        try:
            supplied_count = int((row.get("candidate_count") or "").strip())
            if supplied_count != expected_count:
                errors.append("{} candidate_count={} but candidate sheet has {}".format(
                    location, supplied_count, expected_count))
        except ValueError:
            errors.append("{} candidate_count must be an integer".format(location))

        status = (row.get("answerability_status") or "").strip()
        if not status:
            incomplete.append("{} missing answerability_status".format(location))
            continue
        if status not in ANSWERABILITY_STATUSES:
            errors.append("{} has invalid answerability_status {!r}".format(location, status))
            continue

        direct_ids = split_ids(row.get("direct_match_source_ids"))
        partial_ids = split_ids(row.get("partial_match_source_ids"))
        additional_ids = split_ids(row.get("additional_source_ids_found"))
        pair_candidates = candidate_by_pair.get(pair_id, {})
        for values, label in ((direct_ids, "direct"), (partial_ids, "partial"), (additional_ids, "additional")):
            if len(values) != len(set(values)):
                errors.append("{} contains duplicate {} Source IDs".format(location, label))
        if set(direct_ids) & set(partial_ids):
            errors.append("{} direct and partial Source ID lists must not overlap".format(location))
        for source_id in direct_ids + partial_ids + additional_ids:
            if source_id not in source_index:
                errors.append("{} references unknown answerability Source ID {}".format(location, source_id))
            if source_id not in pair_candidates:
                errors.append("{} Source ID {} must also appear in the candidate sheet".format(location, source_id))

        full_catalog = (row.get("full_catalog_reviewed") or "").strip().casefold()
        out_of_pool = (row.get("out_of_pool_reviewed") or "").strip().casefold()
        if full_catalog not in YES_NO:
            errors.append("{} full_catalog_reviewed must be yes or no".format(location))
        if out_of_pool not in YES_NO:
            errors.append("{} out_of_pool_reviewed must be yes or no".format(location))

        formulations = split_formulations(row.get("search_formulations"))
        unique_formulations = {value.casefold() for value in formulations}
        search_method = (row.get("search_method") or "").strip()
        rationale = (row.get("rationale") or "").strip()
        grade_by_id = {
            source_id: (candidate.get("relevance_grade") or "").strip()
            for source_id, candidate in pair_candidates.items()
        }
        if not rationale:
            errors.append("{} requires a rationale for answerability_status {}".format(location, status))
        if status == "direct_match_found":
            if not direct_ids:
                errors.append("{} direct_match_found requires direct_match_source_ids".format(location))
            if any(grade_by_id.get(source_id) != "3" for source_id in direct_ids):
                errors.append("{} every direct match ID must have grade 3".format(location))
        elif status == "partial_match_only":
            if direct_ids:
                errors.append("{} partial_match_only cannot list direct-match IDs".format(location))
            if any(grade == "3" for grade in grade_by_id.values()):
                errors.append("{} partial_match_only conflicts with a grade-3 direct candidate".format(location))
            if not partial_ids:
                errors.append("{} partial_match_only requires partial_match_source_ids".format(location))
            if any(grade_by_id.get(source_id) != "2" for source_id in partial_ids):
                errors.append("{} every partial match ID must have grade 2".format(location))
        elif status == "no_relevant_skill_found":
            if direct_ids or partial_ids:
                errors.append("{} no_relevant_skill_found cannot list direct or partial matches".format(location))
            if any(grade in {"2", "3"} for grade in grade_by_id.values()):
                errors.append("{} no-relevant label conflicts with a grade-2/3 candidate".format(location))
            if full_catalog != "yes":
                errors.append("{} no-relevant label requires full_catalog_reviewed=yes".format(location))
            if out_of_pool != "yes":
                errors.append("{} no-relevant label requires out_of_pool_reviewed=yes".format(location))
            if len(unique_formulations) < 2:
                errors.append("{} no-relevant label requires at least two distinct search_formulations separated by semicolons/newlines".format(location))
            if not search_method:
                errors.append("{} no-relevant label requires search_method".format(location))
            if not rationale:
                errors.append("{} no-relevant label requires a rationale".format(location))

    expected_pairs = set(candidate_by_pair)
    if seen_pairs != expected_pairs:
        missing = sorted(expected_pairs - seen_pairs)
        extra = sorted(seen_pairs - expected_pairs)
        if missing:
            errors.append("{} missing answerability pairs: {}".format(path, ", ".join(missing)))
        if extra:
            errors.append("{} has unknown answerability pairs: {}".format(path, ", ".join(extra)))
    return {
        "path": str(path), "row_count": len(rows), "rows": rows, "columns": columns,
        "pair_ids": seen_pairs, "errors": errors, "incomplete": incomplete, "warnings": warnings,
    }


def validate_attestation(path):
    errors, incomplete = [], []
    columns, rows = read_csv(path)
    _check_columns(path, columns, ATTESTATION_COLUMNS, errors)
    if len(rows) != 1:
        errors.append("{} must contain exactly one attestation row".format(path))
        row = rows[0] if rows else {}
    else:
        row = rows[0]
    for field in ATTESTATION_COLUMNS:
        if not (row.get(field) or "").strip():
            incomplete.append("{} missing {}".format(path, field))
    reviewer_type = (row.get("reviewer_type") or "").strip()
    if reviewer_type and reviewer_type != "independent_human":
        errors.append("{} reviewer_type must be independent_human".format(path))
    independence = (row.get("independence_confirmed") or "").strip().casefold()
    if independence and independence != "yes":
        errors.append("{} independence_confirmed must be yes".format(path))
    for field in ("saw_other_reviewer_material", "saw_private_manifest_or_audit", "used_model_generated_judgments"):
        value = (row.get(field) or "").strip().casefold()
        if value and value != "no":
            errors.append("{} {} must be no".format(path, field))
    conflict = (row.get("conflict_of_interest") or "").strip().casefold()
    if conflict and conflict not in {"none", "no"}:
        errors.append("{} conflict_of_interest must be none/no; disclose conflicts outside this intake".format(path))
    timestamp = (row.get("completed_at_utc") or "").strip()
    if timestamp:
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
                errors.append("{} completed_at_utc must include an explicit UTC timezone".format(path))
        except ValueError:
            errors.append("{} completed_at_utc must be ISO-8601 UTC".format(path))
    return {"path": str(path), "row": row, "errors": errors, "incomplete": incomplete}


def _review_paths(workspace, reviewer):
    suffix = reviewer.upper()
    return {
        "candidate": workspace / "SEARCH-GOLD-V2-REVIEWER-{}-INTAKE-V2.csv".format(suffix),
        "answerability": workspace / "SEARCH-GOLD-V2-ANSWERABILITY-REVIEWER-{}-INTAKE-V2.csv".format(suffix),
        "attestation": workspace / "SEARCH-GOLD-V2-REVIEWER-{}-ATTESTATION-INTAKE-V2.csv".format(suffix),
    }


def audit_workspace(workspace=DEFAULT_WORKSPACE, catalog=DEFAULT_CATALOG):
    workspace, catalog = Path(workspace), Path(catalog)
    source_index = load_source_index(catalog)
    errors, warnings = [], []
    manifest_path = workspace / "SEARCH-GOLD-V2-QUERY-MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_candidate_count = int(manifest.get("candidate_count_total", 0))
    expected_pairs = int(manifest.get("pair_count", 0))
    source_universe = manifest.get("source_universe", {})
    catalog_hash = hashlib.sha256(catalog.read_bytes()).hexdigest()
    if source_universe.get("source_catalog_sha256") and source_universe["source_catalog_sha256"] != catalog_hash:
        errors.append("Source Catalog SHA-256 differs from the reviewer manifest snapshot")
    if source_universe.get("source_catalog_records") and int(source_universe["source_catalog_records"]) != len(source_index):
        errors.append("Source Catalog record count differs from the reviewer manifest snapshot")
    taxonomy_path = ROOT / "config" / "taxonomy.json"
    taxonomy_hash = hashlib.sha256(taxonomy_path.read_bytes()).hexdigest() if taxonomy_path.exists() else None
    taxonomy_manifest_hash = manifest.get("taxonomy_sha256")
    taxonomy_hash_match = (taxonomy_hash == taxonomy_manifest_hash) if taxonomy_manifest_hash and taxonomy_hash else None
    if taxonomy_hash_match is False:
        warnings.append(
            "Taxonomy drift: reviewer manifest records {}, current taxonomy is {}. "
            "Do not rewrite the manifest or rebuild the pools; source-pinned candidate rows remain the review target. "
            "The exact historical taxonomy bytes are not present in the active workspace."
            .format(taxonomy_manifest_hash, taxonomy_hash)
        )
    expected_by_pair = {str(k): int(v) for k, v in manifest.get("unique_candidates_by_pair", {}).items()}
    reviewer_results = {}
    for reviewer in ("A", "B"):
        paths = _review_paths(workspace, reviewer)
        candidate = validate_candidate_sheet(paths["candidate"], source_index)
        answerability = validate_answerability_sheet(
            paths["answerability"], source_index, candidate["rows"]
        )
        attestation_path = paths["attestation"]
        attestation = validate_attestation(attestation_path) if attestation_path.exists() else {
            "errors": [], "incomplete": ["attestation file not created yet"]
        }
        errors.extend(candidate["errors"] + answerability["errors"] + attestation["errors"])
        warnings.extend(candidate["warnings"] + answerability["warnings"])
        candidate_counts = Counter(row.get("pair_id", "") for row in candidate["rows"])
        if expected_by_pair and dict(candidate_counts) != expected_by_pair:
            errors.append("Reviewer {} candidate counts differ from manifest per-pair counts".format(reviewer))
        forbidden_columns = {"rank", "retrieval_rank", "relevance_score", "fts_rank", "pool_origin", "retrieval_score"}
        if forbidden_columns.intersection({str(column).casefold() for column in candidate["columns"]}):
            errors.append("Reviewer {} candidate sheet leaks retrieval rank/score or pool-origin metadata".format(reviewer))
        reviewer_results[reviewer] = {
            "candidate": candidate, "answerability": answerability, "attestation": attestation,
            "paths": paths,
        }

    a, b = reviewer_results["A"], reviewer_results["B"]
    keys_a, keys_b = a["candidate"]["keys"], b["candidate"]["keys"]
    if keys_a != keys_b:
        errors.append("Reviewer A/B candidate key sets differ")
    if [ (r.get("pair_id"), r.get("source_record_id")) for r in a["candidate"]["rows"] ] == [
        (r.get("pair_id"), r.get("source_record_id")) for r in b["candidate"]["rows"]
    ]:
        errors.append("Reviewer A/B candidate order is identical; independent randomization is expected")
    if len(a["candidate"]["rows"]) != expected_candidate_count or len(b["candidate"]["rows"]) != expected_candidate_count:
        errors.append("Candidate row count does not match manifest count {}".format(expected_candidate_count))
    if len(a["answerability"]["rows"]) != expected_pairs or len(b["answerability"]["rows"]) != expected_pairs:
        errors.append("Answerability row count does not match manifest pair count {}".format(expected_pairs))
    if a["answerability"]["pair_ids"] != b["answerability"]["pair_ids"]:
        errors.append("Reviewer A/B answerability pair sets differ")

    # Check identical task wording and candidate identity across the two blind sheets.
    by_key_b = {(r.get("pair_id"), r.get("source_record_id")): r for r in b["candidate"]["rows"]}
    for row in a["candidate"]["rows"]:
        other = by_key_b.get((row.get("pair_id"), row.get("source_record_id")))
        if other:
            for field in ("query_en_id", "query_en", "query_fa_id", "query_fa", "skill_name", "repository", "source_path", "commit_sha", "skill_md_blob_sha", "description", "license_spdx"):
                if row.get(field) != other.get(field):
                    errors.append("A/B mismatch for {} / {} field {}".format(row.get("pair_id"), row.get("source_record_id"), field))
                    break

    # Validate the ZIP contents are blind and contain only the assigned reviewer files.
    expected_zip_entries = {
        "A": {"SEARCH-GOLD-V2-REVIEWER-A-INTAKE-V2.csv", "SEARCH-GOLD-V2-ANSWERABILITY-REVIEWER-A-INTAKE-V2.csv", "SEARCH-GOLD-V2-REVIEWER-A-INSTRUCTIONS-INTAKE-V2.md", "SEARCH-GOLD-V2-REVIEWER-A-ATTESTATION-INTAKE-V2.csv"},
        "B": {"SEARCH-GOLD-V2-REVIEWER-B-INTAKE-V2.csv", "SEARCH-GOLD-V2-ANSWERABILITY-REVIEWER-B-INTAKE-V2.csv", "SEARCH-GOLD-V2-REVIEWER-B-INSTRUCTIONS-INTAKE-V2.md", "SEARCH-GOLD-V2-REVIEWER-B-ATTESTATION-INTAKE-V2.csv"},
    }
    zip_summaries = {}
    for reviewer in ("A", "B"):
        zip_path = workspace / "SEARCH-GOLD-V2-REVIEWER-{}-PACKET-INTAKE-V2.zip".format(reviewer)
        if not zip_path.exists():
            errors.append("Missing reviewer packet {}".format(zip_path))
            continue
        with zipfile.ZipFile(zip_path) as archive:
            entries = set(archive.namelist())
            bad_entry = archive.testzip()
            if bad_entry:
                errors.append("{} ZIP integrity failed at {}".format(zip_path, bad_entry))
            if entries != expected_zip_entries[reviewer]:
                errors.append("{} ZIP entries differ from expected set: {}".format(zip_path, sorted(entries)))
            for member in entries & expected_zip_entries[reviewer]:
                local_file = workspace / member
                if not local_file.exists() or archive.read(member) != local_file.read_bytes():
                    errors.append("{} member {} differs from the local reviewer artifact".format(zip_path, member))
            if any(token in name.casefold() for name in entries for token in ("manifest", "coverage-audit", "adjudication-template", "reviewer-b" if reviewer == "A" else "reviewer-a")):
                errors.append("{} contains material that violates reviewer blindness".format(zip_path))
            zip_summaries[reviewer] = {"entries": sorted(entries), "integrity": "PASS" if bad_entry is None else "FAIL"}

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    if "/private/" not in gitignore:
        errors.append("private/ is not explicitly excluded by .gitignore")

    return {
        "status": "PASS" if not errors else "FAIL",
        "workspace": str(workspace),
        "source_catalog_record_count": len(source_index),
        "source_catalog_sha256": catalog_hash,
        "taxonomy_manifest_sha256": taxonomy_manifest_hash,
        "taxonomy_current_sha256": taxonomy_hash,
        "taxonomy_hash_match": taxonomy_hash_match,
        "manifest_candidate_count": expected_candidate_count,
        "manifest_pair_count": expected_pairs,
        "reviewers": {
            key: {
                "candidate_rows": value["candidate"]["row_count"],
                "answerability_rows": value["answerability"]["row_count"],
                "candidate_grades_entered": sum(bool((r.get("relevance_grade") or "").strip()) for r in value["candidate"]["rows"]),
                "answerability_labels_entered": sum(bool((r.get("answerability_status") or "").strip()) for r in value["answerability"]["rows"]),
                "attestation_complete": not value["attestation"]["incomplete"] and not value["attestation"]["errors"],
            } for key, value in reviewer_results.items()
        },
        "zip_packets": zip_summaries,
        "errors": errors,
        "warnings": warnings,
        "notes": [
            "Audit checks packet structure and source pins; it does not create human labels.",
            "A passing packet audit is not evidence that reviewers have completed their work.",
        ],
    }


def validate_returned_reviews(workspace=DEFAULT_WORKSPACE, catalog=DEFAULT_CATALOG):
    workspace, catalog = Path(workspace), Path(catalog)
    source_index = load_source_index(catalog)
    results, errors, incomplete, warnings = {}, [], [], []
    for reviewer in ("A", "B"):
        paths = _review_paths(workspace, reviewer)
        candidate = validate_candidate_sheet(paths["candidate"], source_index, require_complete=True)
        answerability = validate_answerability_sheet(
            paths["answerability"], source_index, candidate["rows"], require_complete=True
        )
        attestation = validate_attestation(paths["attestation"])
        results[reviewer] = {"candidate": candidate, "answerability": answerability, "attestation": attestation}
        errors.extend(candidate["errors"] + answerability["errors"] + attestation["errors"])
        incomplete.extend(candidate["incomplete"] + answerability["incomplete"] + attestation["incomplete"])

    a, b = results["A"], results["B"]
    reviewer_ids = [
        (a["attestation"]["row"].get("reviewer_id") or "").strip(),
        (b["attestation"]["row"].get("reviewer_id") or "").strip(),
    ]
    if all(reviewer_ids) and reviewer_ids[0].casefold() == reviewer_ids[1].casefold():
        errors.append("Reviewer A and Reviewer B must have distinct reviewer_id values")

    keys_a, keys_b = a["candidate"]["keys"], b["candidate"]["keys"]
    missing_for_a, missing_for_b = keys_b - keys_a, keys_a - keys_b
    rows_b = {(r.get("pair_id"), r.get("source_record_id")): r for r in b["candidate"]["rows"]}
    for row in a["candidate"]["rows"]:
        other = rows_b.get((row.get("pair_id"), row.get("source_record_id")))
        if other:
            for field in ("query_en_id", "query_en", "query_fa_id", "query_fa", "skill_name", "repository", "source_path", "commit_sha", "skill_md_blob_sha", "description", "license_spdx"):
                if row.get(field) != other.get(field):
                    errors.append("A/B metadata mismatch for {} / {} field {}".format(row.get("pair_id"), row.get("source_record_id"), field))
                    break
    if missing_for_a:
        warnings.append("Reviewer A has not reviewed {} candidate(s) added by Reviewer B".format(len(missing_for_a)))
    if missing_for_b:
        warnings.append("Reviewer B has not reviewed {} candidate(s) added by Reviewer A".format(len(missing_for_b)))
    for reviewer in ("A", "B"):
        other = "B" if reviewer == "A" else "A"
        own_pairs = results[reviewer]["answerability"]["pair_ids"]
        other_pairs = results[other]["answerability"]["pair_ids"]
        if own_pairs != other_pairs:
            errors.append("Reviewer {} answerability pair set differs from Reviewer {}".format(reviewer, other))

    language_exceptions = sorted({
        row.get("pair_id", "")
        for reviewer_result in results.values()
        for sheet in (reviewer_result["candidate"], reviewer_result["answerability"])
        for row in sheet["rows"]
        if (row.get("language_specific_exception") or "").strip()
    })
    if language_exceptions:
        warnings.append("Language-specific exceptions require separate query-level qrels review: {}".format(", ".join(language_exceptions)))

    return {
        "status": "PASS" if not errors and not incomplete and not missing_for_a and not missing_for_b and not language_exceptions else "INCOMPLETE" if not errors else "FAIL",
        "reviewer_ids": reviewer_ids,
        "reviewers": {
            key: {
                "candidate_rows": value["candidate"]["row_count"],
                "candidate_graded": value["candidate"]["row_count"] - len(value["candidate"]["incomplete"]),
                "answerability_rows": value["answerability"]["row_count"],
                "answerability_completed": value["answerability"]["row_count"] - len(value["answerability"]["incomplete"]),
            } for key, value in results.items()
        },
        "language_exception_pairs": language_exceptions,
        "candidate_keys_missing_for_a": sorted([list(key) for key in missing_for_a]),
        "candidate_keys_missing_for_b": sorted([list(key) for key in missing_for_b]),
        "errors": errors,
        "incomplete": incomplete,
        "warnings": warnings,
    }



def create_blinded_addenda(workspace=DEFAULT_WORKSPACE, catalog=DEFAULT_CATALOG, validation=None):
    """Create reviewer-specific, grade-free addenda for out-of-pool additions.

    The reviewer who did not discover a source receives only pinned source metadata;
    the discovering reviewer's grade, rationale and identity are never copied.
    """
    workspace, catalog = Path(workspace), Path(catalog)
    source_index = load_source_index(catalog)
    candidate_rows = {}
    for reviewer in ("A", "B"):
        path = _review_paths(workspace, reviewer)["candidate"]
        _, rows = read_csv(path)
        candidate_rows[reviewer] = {(r.get("pair_id"), r.get("source_record_id")): r for r in rows}
    keys_a, keys_b = set(candidate_rows["A"]), set(candidate_rows["B"])
    missing = {"A": keys_b - keys_a, "B": keys_a - keys_b}
    outputs = {}
    existing_rounds = []
    for path in workspace.glob("SEARCH-GOLD-V2-REVIEWER-*-ADDENDUM-ROUND-*.csv"):
        match = re.search(r"ROUND-(\d+)\.csv$", path.name)
        if match:
            existing_rounds.append(int(match.group(1)))
    round_number = max(existing_rounds, default=0) + 1
    for reviewer in ("A", "B"):
        other = "B" if reviewer == "A" else "A"
        rows = []
        for key in sorted(missing[reviewer]):
            source_row = candidate_rows[other][key]
            row = {field: source_row.get(field, "") for field in CANDIDATE_COLUMNS}
            for field in ("relevance_grade", "rationale", "content_checked", "language_specific_exception"):
                row[field] = ""
            # Re-check pinned identity before exposing a candidate to the second reviewer.
            pin_errors = []
            _check_source_pin(row, source_index, "addendum {}".format(key), pin_errors)
            if pin_errors:
                raise ValueError("Cannot create blinded addendum: " + "; ".join(pin_errors))
            rows.append(row)
        if rows:
            path = workspace / "SEARCH-GOLD-V2-REVIEWER-{}-ADDENDUM-ROUND-{}.csv".format(reviewer, round_number)
            write_csv(path, CANDIDATE_COLUMNS, rows)
            instructions = workspace / "SEARCH-GOLD-V2-REVIEWER-{}-ADDENDUM-ROUND-{}-INSTRUCTIONS.md".format(reviewer, round_number)
            instructions.write_text(
                "# Independent Candidate Addendum\n\n"
                "Review these additional pinned Skill records independently using the same 0-3 rubric. "
                "Do not infer why they were added or who found them. Do not ask for or view the other reviewer's grades. "
                "Append these rows to your own `SEARCH-GOLD-V2-REVIEWER-{}-INTAKE-V2.csv`, complete "
                "relevance_grade/rationale/content_checked, and update candidate_count in your answerability sheet. "
                "If a source is a direct or useful partial match, update the appropriate Source ID list. "
                "Return the updated candidate and answerability sheets to the organizer.\n".format(reviewer),
                encoding="utf-8"
            )
            outputs[reviewer] = {"path": str(path), "instructions": str(instructions), "row_count": len(rows), "source_ids": [r["source_record_id"] for r in rows]}
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate GASL independent human benchmark review packets.")
    parser.add_argument("command", choices=("audit", "validate"))
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--create-addenda", action="store_true", help="Create blinded grade-free addenda when reviewer candidate sets differ.")
    args = parser.parse_args(argv)

    result = audit_workspace(args.workspace, args.catalog) if args.command == "audit" else validate_returned_reviews(args.workspace, args.catalog)
    if args.command == "validate" and args.create_addenda:
        result["blinded_addenda"] = create_blinded_addenda(args.workspace, args.catalog, result)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    if result["status"] == "FAIL":
        return 1
    if result["status"] == "INCOMPLETE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
