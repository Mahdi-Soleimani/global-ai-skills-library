#!/usr/bin/env python3
"""Bounded metadata-only discovery. Never downloads or executes Skill contents."""
import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from path_rules import is_test_fixture_path
from reconcile import load, write_json

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com"
SHA = re.compile(r"^[0-9a-f]{40}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ORDINARY_MODES = {"100644", "100755"}


def now():
    return datetime.now(timezone.utc).isoformat()


def github_json(endpoint):
    # No credentials in shell arguments, no TLS verification bypass.
    result = subprocess.run(["curl", "--fail", "--silent", "--show-error",
                             "--connect-timeout", "5", "--max-time", "20",
                             "--max-filesize", "20000000",
                             "--user-agent", "GASL-discovery/1.0",
                             "-H", "Accept: application/vnd.github+json",
                             API + endpoint], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip()[:300])
    return json.loads(result.stdout)


def require_sha(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError("Missing or malformed Git SHA")
    return value


def enumerate_paths(tree, expected_tree):
    if tree.get("sha") != expected_tree or tree.get("truncated") is not False:
        raise ValueError("Tree mismatch, missing completeness flag or truncated tree")
    result = []
    seen = set()
    for item in tree["tree"]:
        path = item["path"]
        if path.rsplit("/", 1)[-1].casefold() != "skill.md":
            continue
        if (not path or path.startswith("/") or "\\" in path or
            any(part in {"", ".", ".."} for part in path.split("/")) or
            any(ord(c) < 32 or ord(c) == 127 for c in path)):
            raise ValueError("Unsafe skill path")
        if path in seen:
            raise ValueError("Duplicate skill path")
        seen.add(path)
        mode = item.get("mode")
        if item.get("type") != "blob" or mode not in ORDINARY_MODES:
            classification = "excluded_non_regular"
        elif is_test_fixture_path(path):
            classification = "excluded_test_fixture"
        else:
            classification = "skill_path_candidate"
        result.append({"path": path, "mode": mode, "blob_sha": require_sha(item.get("sha")),
                       "size_bytes": item.get("size"), "classification": classification})
    return sorted(result, key=lambda p: p["path"])


def discover_target(target, request=github_json):
    repo = target["repository"]
    if not REPO.fullmatch(repo):
        raise ValueError("Invalid repository")
    metadata = request("/repos/" + repo)
    canonical = metadata["full_name"]
    if not REPO.fullmatch(canonical) or canonical.casefold() != repo.casefold():
        raise ValueError("Repository alias requires separate verification")
    if metadata.get("private") is not False or metadata.get("archived") or metadata.get("disabled"):
        raise ValueError("Non-public, archived or disabled repository")
    branch = metadata["default_branch"]
    commit = request("/repos/" + canonical + "/commits/" + quote(branch, safe=""))
    commit_sha = require_sha(commit["sha"])
    tree_sha = require_sha(commit["commit"]["tree"]["sha"])
    tree = request("/repos/" + canonical + "/git/trees/" + tree_sha + "?recursive=1")
    paths = enumerate_paths(tree, tree_sha)
    return {**target, "repository": canonical, "repository_id": metadata["id"],
            "publisher_account": metadata["owner"]["login"],
            "license_spdx": (metadata.get("license") or {}).get("spdx_id"),
            "default_branch": branch, "commit_sha": commit_sha, "tree_sha": tree_sha,
            "checked_at": now(), "tree_truncated": False,
            "status": "verified_metadata_only", "paths": paths,
            "extraction_status": "tree_enumerated_content_not_read",
            "source_scope": "research_lead_only_not_original_skill_record"}


def pending_queue(records, downloaded):
    existing = {(str(r.get("canonical_repository") or r.get("repository")).casefold(),
                 r.get("source_skill_path"), r.get("commit_sha"))
                for r in downloaded if r.get("package_complete")}
    result = []
    for record in records:
        if record.get("status") != "verified_metadata_only":
            continue
        for path in record["paths"]:
            if path["classification"] != "skill_path_candidate":
                continue
            key = (record["repository"].casefold(), path["path"], record["commit_sha"])
            result.append({"repository": record["repository"], "skill_path": path["path"],
                           "commit_sha": record["commit_sha"], "tree_sha": record["tree_sha"],
                           "skill_md_blob_sha": path["blob_sha"],
                           "license_spdx": record["license_spdx"],
                           "research_leads": record["research_leads"],
                           "status": "existing_complete_metadata" if key in existing else "pending_package_plan",
                           "install_status": "not_approved"})
    return result


def run(root, limit, retry_errors=False):
    targets = load(root / "config/discovery-targets.json")["targets"]
    out = root / "registry/discovery"
    out.mkdir(parents=True, exist_ok=True)
    # Preserve each successful result as an immutable commit-keyed observation.
    records = []
    attempted = 0
    for target in targets:
        key = target["repository"].casefold()
        name = hashlib.sha256(key.encode()).hexdigest()[:20]
        state = out / (name + ".json")
        if state.exists():
            previous = load(state)
            if previous.get("status") == "verified_metadata_only" or not retry_errors:
                records.append(previous)
                continue
        if attempted >= limit:
            continue
        attempted += 1
        try:
            record = discover_target(target)
        except (RuntimeError, ValueError, KeyError, TypeError) as error:
            record = {**target, "status": "error", "checked_at": now(), "error": str(error)[:400]}
        if record["status"] == "verified_metadata_only":
            version = out / (name + "@" + record["commit_sha"] + ".json")
            if not version.exists():
                write_json(version, record)
        write_json(state, record)
        records.append(record)
        print(target["repository"], record["status"], len(record.get("paths", [])), flush=True)
    registry = load(root / "registry/skills.json")["records"]
    queue = pending_queue(records, registry)
    old = load(root / "registry/source-verification.json")["repositories"]
    successful = [r for r in records if r["status"] == "verified_metadata_only"]
    changes = []
    for r in successful:
        previous = old.get(r["repository"].casefold())
        earlier = set(previous.get("skill_paths", [])) if previous else set()
        current = {p["path"] for p in r["paths"]}
        changes.append({"repository": r["repository"], "commit_sha": r["commit_sha"],
                        "tree_sha": r["tree_sha"], "checked_at": r["checked_at"],
                        "prior_snapshot_present": previous is not None,
                        "prior_paths": len(earlier), "observed_paths": len(current),
                        "new_paths_vs_prior_snapshot": len(current-earlier),
                        "absent_paths_vs_prior_snapshot": len(earlier-current),
                        "license_spdx": r["license_spdx"]})
    write_json(out / "download-queue.json", queue)
    summary = {"schema_version": "1.0.0", "targets": len(targets),
               "attempted_targets": len(records), "verified_targets": len(successful),
               "errors": len(records)-len(successful),
               "observed_paths": sum(len(r["paths"]) for r in successful),
               "explicit_fixture_paths": sum(p["classification"] == "excluded_test_fixture" for r in successful for p in r["paths"]),
               "excluded_non_regular_paths": sum(p["classification"] == "excluded_non_regular" for r in successful for p in r["paths"]),
               "queue_records": len(queue),
               "pending_package_plan": sum(r["status"] == "pending_package_plan" for r in queue),
               "existing_complete_metadata": sum(r["status"] == "existing_complete_metadata" for r in queue),
               "repositories": changes,
               "failed_targets": [{"repository": r["repository"], "error": r["error"]} for r in records if r["status"] == "error"],
               "limitations": ["Tree metadata only; no Skill content inspected or downloaded.",
                               "New paths are relative to the old snapshot, not globally unique or recovered dataset rows.",
                               "Queue is not authorization to install or execute. No package size estimate yet."]}
    write_json(root / "reconciliation/discovery-summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5, choices=range(1, 11))
    parser.add_argument("--retry-errors", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(ROOT, args.limit, args.retry_errors), indent=2))


if __name__ == "__main__":
    main()
