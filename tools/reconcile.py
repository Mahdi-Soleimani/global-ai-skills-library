#!/usr/bin/env python3
"""Derive repository/path crosswalks without modifying source reports or packages."""
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from path_rules import is_test_fixture_path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def repository_crosswalk(manifests, verification):
    rows = []
    seen_ids = set()
    paths_by_repo = {}
    for report_id, manifest in sorted(manifests.items()):
        for source in manifest["repositories"]:
            source_id = source["source_id"]
            if source_id in seen_ids or source["report_id"] != report_id:
                raise ValueError("Duplicate or mismatched source ID: " + source_id)
            seen_ids.add(source_id)
            name = source["repo_full_name"]
            item = verification.get(name.casefold(), {})
            verified = item.get("status") == "verified"
            canonical = (item.get("canonical_repo_name") or item.get("repo_full_name") or name) if verified else None
            key = canonical.casefold() if canonical else None
            if key:
                target = verification.get(key, {})
                if target.get("status") != "verified" or target.get("redirected_alias"):
                    raise ValueError("Missing verified canonical target: " + key)
                paths_by_repo[key] = target
            rows.append({
                "source_id": source_id, "report_id": report_id,
                "source_repository": name, "canonical_repository": canonical or "",
                "relationship": ("redirected_repository_alias" if key and key != name.casefold()
                                 else "verified_repository_reference" if verified else "unverified_reference"),
                "verification_date": item.get("checked_at") or item.get("verified_at") or "",
                "scope": "repository_reference_only",
            })
    return rows, paths_by_repo


def path_crosswalk(rows, repos):
    linked = defaultdict(list)
    for row in rows:
        if row["canonical_repository"]:
            linked[row["canonical_repository"].casefold()].append(row["source_id"])
    paths = []
    for key, item in sorted(repos.items()):
        observed = item.get("skill_paths", [])
        if len(observed) != item.get("skill_file_count") or len(set(observed)) != len(observed):
            raise ValueError("Path count mismatch or duplicates: " + key)
        for path in sorted(observed):
            if path.rsplit("/", 1)[-1].casefold() != "skill.md":
                raise ValueError("Unexpected path: " + path)
            paths.append({
                "canonical_repository": item.get("canonical_repo_name") or item["repo_full_name"],
                "publisher_account": item.get("owner_login") or "",
                "skill_path": path,
                "package_type": "test_fixture" if is_test_fixture_path(path) else "skill_path_candidate",
                "commit_sha": item.get("commit_sha") or "",
                "reported_tree_sha": item.get("tree_sha") or "",
                "snapshot_status": "commit_recorded" if item.get("commit_sha") else
                    "tree_ref_recorded_commit_unverified" if item.get("tree_sha") else "branch_observation_only",
                "tree_truncated": item.get("tree_truncated"),
                "source_reference_ids": ";".join(sorted(linked[key])),
                "scope": "repository_reference_only_not_source_skill_record",
            })
    return paths


def downloaded_crosswalk(records, paths):
    observed = {(r["canonical_repository"].casefold(), r["skill_path"]): r for r in paths}
    rows = []
    for r in sorted(records, key=lambda x: x["skill_id"]):
        repository = r.get("canonical_repository") or r.get("repository")
        path = r.get("source_skill_path")
        match = observed.get((str(repository).casefold(), path))
        snapshot_commit = match.get("commit_sha") if match else None
        commit = r.get("commit_sha") or ""
        rows.append({
            "skill_id": r["skill_id"],
            "canonical_repository": repository,
            "skill_path": path,
            "downloaded_commit_sha": commit,
            "snapshot_match": ("not_observed" if not match else
                               "same_recorded_commit" if snapshot_commit and commit == snapshot_commit else
                               "different_recorded_commit" if snapshot_commit and commit else
                               "path_match_only_commit_unconfirmed"),
            "source_reference_ids": match["source_reference_ids"] if match else "",
            "scope": "repository_reference_only_not_source_skill_record",
        })
    return rows


def duplicate_candidates(records):
    groups = defaultdict(list)
    for record in records:
        for field, kind in (("skill_md_sha256_raw", "exact_skill_md_digest"),
                            ("skill_md_sha256_normalized", "normalized_skill_md_digest"),
                            ("skill_name", "same_name")):
            value = record.get(field)
            if value:
                groups[(kind, str(value).casefold())].append(record)
    versions = defaultdict(list)
    for record in records:
        repository = record.get("canonical_repository") or record.get("repository")
        path = record.get("source_skill_path")
        if repository and path and record.get("commit_sha"):
            versions[(repository.casefold(), path)].append(record)
    relations = []
    for (repository, path), members in sorted(versions.items()):
        if len({m["commit_sha"] for m in members}) > 1:
            relations.append({
                "relationship": "same_path_different_commits",
                "evidence": repository + ":" + path,
                "skill_ids": sorted(m["skill_id"] for m in members),
                "decision": "candidate_only_no_merge",
                "limitation": "Different revisions are retained; ancestry and supersession not established",
            })
    for (kind, value), members in sorted(groups.items()):
        if len(members) < 2:
            continue
        if kind == "same_name" and len({m.get("skill_md_sha256_normalized") for m in members}) < 2:
            continue
        relations.append({
            "relationship": kind,
            "evidence": value,
            "skill_ids": sorted(m["skill_id"] for m in members),
            "decision": "candidate_only_no_merge",
            "limitation": "SKILL.md comparison only; no full-package, fork or mirror equivalence established",
        })
    return relations


def run(root=ROOT):
    config = load(root / "config/source-repositories.json")
    manifests = {}
    inputs = {}
    for report_id, report in sorted(config["reports"].items()):
        path = root / "research" / report_id / "source-manifest.json"
        manifest = load(path)
        if manifest["report_id"] != report_id or manifest["source_sha256"] != report["source_sha256"]:
            raise ValueError("Source identity mismatch: " + report_id)
        if [x["repo_full_name"] for x in manifest["repositories"]] != report["explicit_github_repositories"]:
            raise ValueError("Source repository mismatch: " + report_id)
        manifests[report_id] = manifest
        inputs[str(path.relative_to(root))] = digest(path)
    snapshot_path = root / "registry/source-verification.json"
    registry_path = root / "registry/skills.json"
    snapshot = load(snapshot_path)
    registry = load(registry_path)
    for path in (snapshot_path, registry_path):
        inputs[str(path.relative_to(root))] = digest(path)
    rows, repos = repository_crosswalk(manifests, snapshot["repositories"])
    paths = path_crosswalk(rows, repos)
    records = registry["records"]
    if len({r["skill_id"] for r in records}) != len(records):
        raise ValueError("Duplicate registry skill IDs")
    duplicates = duplicate_candidates(records)
    downloaded = downloaded_crosswalk(records, paths)
    outside_snapshot = sum(r["snapshot_match"] == "not_observed" for r in downloaded)
    summary = {
        "schema_version": "1.0.0",
        "snapshot_updated_at": snapshot.get("updated_at"),
        "source_manifest_count": len(manifests),
        "source_repository_mentions": len(rows),
        "distinct_source_references": len({r["source_repository"].casefold() for r in rows}),
        "canonical_repositories": len(repos),
        "redirected_source_mentions": sum(r["relationship"] == "redirected_repository_alias" for r in rows),
        "unverified_source_mentions": sum(r["relationship"] == "unverified_reference" for r in rows),
        "observed_skill_paths": len(paths),
        "explicit_test_fixture_paths": sum(r["package_type"] == "test_fixture" for r in paths),
        "commit_recorded_paths": sum(r["snapshot_status"] == "commit_recorded" for r in paths),
        "tree_ref_only_paths": sum(r["snapshot_status"] == "tree_ref_recorded_commit_unverified" for r in paths),
        "branch_only_paths": sum(r["snapshot_status"] == "branch_observation_only" for r in paths),
        "truncated_tree_repositories": sum(r.get("tree_truncated") is True for r in repos.values()),
        "downloaded_registry_records": len(records),
        "registry_records_not_in_path_snapshot": outside_snapshot,
        "registry_records_same_recorded_commit": sum(r["snapshot_match"] == "same_recorded_commit" for r in downloaded),
        "registry_records_different_recorded_commit": sum(r["snapshot_match"] == "different_recorded_commit" for r in downloaded),
        "registry_records_path_match_only": sum(r["snapshot_match"] == "path_match_only_commit_unconfirmed" for r in downloaded),
        "duplicate_candidate_groups": len(duplicates),
        "source_skill_record_matches": 0,
        "source_records_modified": False,
        "input_sha256": inputs,
        "limitations": ["Historical snapshot, not a fresh crawl.", "Publisher account is not proof of official authorship.",
                        "Paths are not globally unique skills. Tree refs are reported as stored, not independently typed.",
                        "Missing original row-level datasets prevent exact source-skill joins.",
                        "Duplicate assertions limited to the downloaded registry and SKILL.md hashes; no records removed."],
    }
    output = root / "reconciliation"
    write_csv(output / "source-crosswalk.csv", rows, list(rows[0]))
    write_csv(output / "skill-path-crosswalk.csv", paths, list(paths[0]))
    write_csv(output / "downloaded-skill-crosswalk.csv", downloaded,
              ["skill_id", "canonical_repository", "skill_path", "downloaded_commit_sha",
               "snapshot_match", "source_reference_ids", "scope"])
    write_json(output / "duplicate-candidates.json", duplicates)
    write_json(output / "crosswalk-summary.json", summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
