#!/usr/bin/env python3
"""Build a derived index for downloaded live-catalog packages; never edits source research datasets."""
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from path_rules import is_test_fixture_path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog"
REGISTRY = ROOT / "registry"


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def clean_scalar(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return value


def parse_frontmatter(text):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    if not lines or lines[0].strip() != "---":
        return {"_valid": False}
    end = next((i for i in range(1, len(lines)) if lines[i].strip() in ("---", "...")), None)
    if end is None:
        return {"_valid": False}
    header = lines[1:end]
    values = {}
    i = 0
    while i < len(header):
        line = header[i]
        if not line.strip() or line.lstrip().startswith("#") or line[0].isspace() or ":" not in line:
            i += 1
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        raw = raw.strip()
        if raw in ("|", ">", "|-", ">-", "|+", ">+"):
            block = []
            i += 1
            while i < len(header) and (not header[i].strip() or header[i][0].isspace()):
                block.append(header[i].strip())
                i += 1
            values[key] = " ".join(x for x in block if x)
            continue
        values[key] = clean_scalar(raw)
        i += 1
    values["_valid"] = bool(values.get("name") and values.get("description"))
    return values


def normalized_content_hash(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip() + "\n"
    return sha256_bytes(normalized.encode("utf-8"))


def classify_package(meta):
    path = meta.get("source_skill_path") or ""
    return "test_fixture" if is_test_fixture_path(path) else "skill_candidate"


def merge_previous_registry_records(records, previous_records, root):
    current_keys = {(str(x.get("repository") or "").casefold(), x.get("source_skill_path"), x.get("commit_sha"))
                    for x in records}
    merged = list(records)
    for previous in previous_records:
        key = (str(previous.get("repository") or "").casefold(),
               previous.get("source_skill_path"), previous.get("commit_sha"))
        if key in current_keys:
            continue
        item = dict(previous)
        package_path = item.get("package_path")
        package_present = bool(package_path and (root / package_path / "source.json").is_file())
        item["package_content_present"] = package_present
        item["historical_registry_record"] = True
        if not package_present:
            item["content_status"] = "historical_package_metadata_only_content_not_on_runner"
        merged.append(item)
        current_keys.add(key)
    return merged


def main():
    verification_path = REGISTRY / "source-verification.json"
    if verification_path.exists():
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        repos = verification.get("repositories", {})
    else:
        # GitHub-hosted runners intentionally do not receive the local-only verification snapshot.
        state_path = REGISTRY / "discovery-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        repos = state.get("repositories", {})
    previous_registry = json.loads((REGISTRY / "skills.json").read_text(encoding="utf-8")) if (REGISTRY / "skills.json").exists() else {"records": []}
    package_sources = sorted(CATALOG.glob("**/source.json"))
    records = []
    for source_path in package_sources:
        meta = json.loads(source_path.read_text(encoding="utf-8"))
        package_dir = source_path.parent
        skill_md = package_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        raw = skill_md.read_bytes()
        text = raw.decode("utf-8", "replace")
        fm = parse_frontmatter(text)
        repo_key = (meta.get("repository") or "").lower()
        repo_meta = repos.get(repo_key, {})
        source_reports = repo_meta.get("source_reports", [])
        package_type = classify_package(meta)
        is_fixture = package_type == "test_fixture"
        record_id_seed = "|".join((meta.get("repository") or "", meta.get("source_skill_path") or "", meta.get("commit_sha") or ""))
        skill_id = "GASL-" + sha256_bytes(record_id_seed.encode("utf-8"))[:20]
        record = {
            "skill_id": skill_id,
            "skill_name": fm.get("name") or package_dir.name.split("__")[0],
            "description": fm.get("description") or "",
            "license_frontmatter": fm.get("license"),
            "compatibility": fm.get("compatibility"),
            "frontmatter_valid": bool(fm.get("_valid")),
            "repository": meta.get("repository"),
            "canonical_repository": repo_meta.get("canonical_repo_name", meta.get("repository")),
            "repository_url": meta.get("repository_url"),
            "source_skill_path": meta.get("source_skill_path"),
            "package_type": package_type,
            "install_eligibility": "excluded_test_fixture" if is_fixture else "pending_security_and_license_review",
            "commit_sha": meta.get("commit_sha"),
            "tree_sha": meta.get("tree_sha"),
            "license_spdx": meta.get("license_spdx"),
            "source_reports": source_reports,
            "research_leads": meta.get("research_leads", []),
            "source_link_scope": "repository_reference_only; no join to EN-675 or FA-234 skill rows",
            "package_path": str(package_dir.relative_to(ROOT)),
            "package_complete": meta.get("package_complete"),
            "package_content_present": True,
            "historical_registry_record": False,
            "package_file_count": len(meta.get("files", [])),
            "package_bytes": sum(x.get("size_bytes", 0) for x in meta.get("files", [])),
            "skill_md_sha256_raw": sha256_bytes(raw),
            "skill_md_sha256_normalized": normalized_content_hash(text),
            "security_status": meta.get("security_status", "not_scanned"),
            "security_finding_count": meta.get("static_scan_finding_count", 0),
            "high_confidence_signals": meta.get("high_confidence_signals", 0),
            "official_status": "not_independently_verified_at_skill_level",
            "evidence_level": "Unknown",
            "quality_score": None,
            "install_status": "not_applicable_test_fixture" if is_fixture else "not_installed",
            "downloaded_at": meta.get("downloaded_at"),
            "dataset_scope": "LIVE_CATALOG_PILOT_ONLY"
        }
        records.append(record)

    records = merge_previous_registry_records(records, previous_registry.get("records", []), ROOT)

    by_hash = defaultdict(list)
    by_name = defaultdict(list)
    for record in records:
        by_hash[record["skill_md_sha256_normalized"]].append(record)
        by_name[(record["skill_name"] or "").casefold()].append(record)

    for record in records:
        group = by_hash[record["skill_md_sha256_normalized"]]
        record["dedup_status"] = "duplicate_content_match" if len(group) > 1 else "unique_in_current_download_set"
        record["duplicate_group"] = ("DUP-" + record["skill_md_sha256_normalized"][:12]) if len(group) > 1 else None
        name_group = by_name[(record["skill_name"] or "").casefold()]
        distinct_hashes = {x["skill_md_sha256_normalized"] for x in name_group}
        record["name_collision_status"] = "same_name_different_content" if len(name_group) > 1 and len(distinct_hashes) > 1 else "no_conflict_in_current_download_set"

    REGISTRY.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "0.1.0",
        "generated_at": now(),
        "dataset_scope": "LIVE_CATALOG_PILOT_ONLY",
        "source_dataset_policy": "EN-675, FA-234, AUX-FA-750PLUS, and AUX-FA-438 remain separate; no source skill rows are merged into this derived live catalog index.",
        "record_count": len(records),
        "records": records
    }
    (REGISTRY / "skills.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fields = (list(records[0].keys()) + sorted({key for item in records for key in item} - set(records[0].keys()))
              if records else ["skill_id", "skill_name", "repository"])
    with (REGISTRY / "skills.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

    duplicate_rows = []
    for digest, group in sorted(by_hash.items()):
        if len(group) > 1:
            for record in group:
                duplicate_rows.append({
                    "duplicate_group": "DUP-" + digest[:12],
                    "normalized_sha256": digest,
                    "skill_id": record["skill_id"],
                    "skill_name": record["skill_name"],
                    "repository": record["repository"],
                    "source_skill_path": record["source_skill_path"]
                })
    with (REGISTRY / "content-duplicates.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["duplicate_group", "normalized_sha256", "skill_id", "skill_name", "repository", "source_skill_path"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(duplicate_rows)

    collision_rows = []
    for name, group in sorted(by_name.items()):
        if name and len({x["skill_md_sha256_normalized"] for x in group}) > 1:
            for record in group:
                collision_rows.append({
                    "skill_name": record["skill_name"],
                    "skill_id": record["skill_id"],
                    "repository": record["repository"],
                    "source_skill_path": record["source_skill_path"],
                    "normalized_sha256": record["skill_md_sha256_normalized"]
                })
    with (REGISTRY / "name-collisions.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["skill_name", "skill_id", "repository", "source_skill_path", "normalized_sha256"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(collision_rows)

    candidate_records = [x for x in records if x["package_type"] == "skill_candidate"]
    fixture_records = [x for x in records if x["package_type"] == "test_fixture"]
    summary = {
        "schema_version": "0.2.0",
        "generated_at": now(),
        "record_count": len(records),
        "historical_metadata_only_count": sum(x.get("historical_registry_record") and not x.get("package_content_present") for x in records),
        "skill_candidate_count": len(candidate_records),
        "test_fixture_count": len(fixture_records),
        "valid_frontmatter": sum(x["frontmatter_valid"] for x in records),
        "invalid_or_incomplete_frontmatter": sum(not x["frontmatter_valid"] for x in records),
        "content_duplicate_groups": sum(1 for x in by_hash.values() if len(x) > 1),
        "content_duplicate_records": sum(len(x) for x in by_hash.values() if len(x) > 1),
        "same_name_collision_groups": sum(1 for x in by_name.values() if len({y["skill_md_sha256_normalized"] for y in x}) > 1),
        "security_manual_review": sum(x["security_status"] == "manual_review_required" for x in records),
        "security_manual_review_candidates": sum(x["security_status"] == "manual_review_required" for x in candidate_records),
        "security_manual_review_fixtures": sum(x["security_status"] == "manual_review_required" for x in fixture_records),
        "high_confidence_signals": sum(x["high_confidence_signals"] for x in records),
        "install_approved_records": sum(x["install_status"] == "install_approved" for x in records),
        "installed_records": sum(x["install_status"] == "installed" for x in records),
        "source_datasets_modified": False
    }
    (REGISTRY / "skills-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
