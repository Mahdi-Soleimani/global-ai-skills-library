#!/usr/bin/env python3
"""Bounded metadata-only discovery. Never downloads or executes Skill contents."""
import argparse
import hashlib
import json
import re
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
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
    # Keep the optional Actions token out of process arguments and logs.
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "GASL-discovery/1.0"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    last_error = None
    for attempt in range(4):
        request = Request(API + endpoint, headers=headers)
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read(20_000_001)
            if len(raw) > 20_000_000:
                raise RuntimeError("GitHub API response exceeded the 20 MB safety limit")
            return json.loads(raw)
        except HTTPError as error:
            detail = error.read(1000).decode("utf-8", "replace")
            last_error = RuntimeError("GitHub API HTTP {}: {}".format(error.code, detail[:300]))
            retryable = error.code in (408, 425, 429, 500, 502, 503, 504)
            if error.code == 403 and error.headers.get("X-RateLimit-Remaining") == "0":
                retryable = True
                try:
                    delay = max(1, min(60, int(error.headers.get("X-RateLimit-Reset", "0")) - int(time.time())))
                except ValueError:
                    delay = 30
            else:
                delay = min(8, 2 ** attempt)
            if not retryable or attempt == 3:
                raise last_error from error
            time.sleep(delay)
        except (URLError, TimeoutError, OSError) as error:
            last_error = RuntimeError("GitHub API network error: " + str(getattr(error, "reason", error))[:250])
            if attempt == 3:
                raise last_error from error
            time.sleep(min(8, 2 ** attempt))
    raise last_error


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
    license_data = metadata.get("license") or {}
    license_files = []
    for item in tree["tree"]:
        basename = item["path"].rsplit("/", 1)[-1].casefold()
        if (item.get("type") == "blob" and item.get("mode") in ORDINARY_MODES and
            (basename.startswith(("license", "licence", "copying", "notice")) or basename == "copyright")):
            license_files.append({
                "path": item["path"], "blob_sha": require_sha(item.get("sha")),
                "size_bytes": item.get("size"), "mode": item.get("mode")
            })
    return {**target, "repository": canonical, "repository_id": metadata["id"],
            "publisher_account": metadata["owner"]["login"],
            "repository_url": metadata.get("html_url") or "https://github.com/" + canonical,
            "license_spdx": license_data.get("spdx_id"),
            "license_name": license_data.get("name"),
            "license_key": license_data.get("key"),
            "license_api_url": license_data.get("url"),
            "license_files": sorted(license_files, key=lambda x: x["path"]),
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
            license_files = record.get("license_files", [])
            nearest_license = None
            folder = path["path"].rsplit("/", 1)[0]
            ancestors = {""}
            parts = folder.split("/")
            ancestors.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
            nested_skill_dirs = [p["path"].rsplit("/", 1)[0] for p in record.get("paths", [])
                                 if p["path"] != path["path"] and p["path"].startswith(folder + "/")]
            def applicable_license(item):
                license_path = item["path"]
                parent = license_path.rsplit("/", 1)[0] if "/" in license_path else ""
                in_ancestor = parent in ancestors
                in_package = license_path.startswith(folder + "/") and not any(
                    license_path.startswith(n + "/") for n in nested_skill_dirs)
                return in_ancestor or in_package
            candidates = [x for x in license_files if applicable_license(x)]
            if candidates:
                nearest_license = sorted(candidates, key=lambda x: (
                    0 if (x["path"].rsplit("/", 1)[0] if "/" in x["path"] else "") in ancestors else 1,
                    -len(x["path"].rsplit("/", 1)[0]) if "/" in x["path"] else 0,
                    x["path"]))[0]
            source_url = "https://github.com/{}/blob/{}/{}".format(
                record["repository"], record["commit_sha"], quote(path["path"], safe="/"))
            license_url = None
            if nearest_license:
                license_url = "https://github.com/{}/blob/{}/{}".format(
                    record["repository"], record["commit_sha"], quote(nearest_license["path"], safe="/"))
            result.append({"repository": record["repository"], "repository_url": record.get("repository_url"),
                           "publisher_account": record.get("publisher_account"),
                           "skill_path": path["path"], "source_url": source_url,
                           "commit_sha": record["commit_sha"], "tree_sha": record["tree_sha"],
                           "skill_md_blob_sha": path["blob_sha"],
                           "license_spdx": record["license_spdx"], "license_name": record.get("license_name"),
                           "license_key": record.get("license_key"), "license_url": license_url,
                           "license_evidence_path": nearest_license["path"] if nearest_license else None,
                           "license_evidence_blob_sha": nearest_license["blob_sha"] if nearest_license else None,
                           "license_evidence_paths": sorted(x["path"] for x in candidates),
                           "research_leads": record["research_leads"],
                           "discovery_status": record.get("status", "verified_metadata_only"),
                           "snapshot_checked_at": record.get("checked_at"),
                           "status": "existing_complete_metadata" if key in existing else "pending_package_plan",
                           "install_status": "not_approved", "ownership": "third_party",
                           "original_author": None, "gasl_claims_exclusive_ownership": False})
    return result


def run(root, limit, retry_errors=False, refresh=False):
    targets = load(root / "config/discovery-targets.json")["targets"]
    out = root / "registry/discovery"
    out.mkdir(parents=True, exist_ok=True)
    records = []
    attempted = 0
    for target in targets:
        key = target["repository"].casefold()
        name = hashlib.sha256(key.encode()).hexdigest()[:20]
        state = out / (name + ".json")
        if state.exists() and not refresh:
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

    state_path = root / "registry/discovery-state.json"
    baseline_source = "tracked_discovery_state"
    if state_path.exists():
        old = load(state_path).get("repositories", {})
    elif (root / "registry/source-verification.json").exists():
        old = load(root / "registry/source-verification.json")["repositories"]
        baseline_source = "local_verification_snapshot"
    else:
        old = {}
        baseline_source = "none"

    registry_path = root / "registry/skills.json"
    local_downloaded = load(registry_path).get("records", []) if registry_path.exists() else []
    downloaded = []
    for item in local_downloaded:
        package_path = item.get("package_path")
        if package_path and (root / package_path / "source.json").is_file():
            downloaded.append(item)
    public_index_path = root / "public-catalog/index.json"
    public_index = load(public_index_path).get("packages", {}) if public_index_path.exists() else {}
    downloaded.extend({**item, "canonical_repository": item.get("repository"),
                        "source_skill_path": item.get("source_skill_path"),
                        "package_complete": True, "publicly_mirrored": True}
                       for item in public_index.values())
    queue = pending_queue(records, downloaded)
    previous_queue_path = root / "registry/download-queue.json"
    previous_queue = load(previous_queue_path) if previous_queue_path.exists() else []
    failed_by_repo = {r["repository"].casefold(): r.get("error", "refresh failed")
                      for r in records if r.get("status") == "error"}
    fresh_repos = {r["repository"].casefold() for r in records
                   if r.get("status") == "verified_metadata_only"}
    stale_rows = []
    for row in previous_queue:
        repo_key = row["repository"].casefold()
        if repo_key in failed_by_repo and repo_key not in fresh_repos:
            stale = dict(row)
            stale["discovery_status"] = "stale_fallback"
            stale["last_refresh_error"] = failed_by_repo[repo_key]
            stale_rows.append(stale)
    queue.extend(stale_rows)
    successful = [r for r in records if r.get("status") == "verified_metadata_only"]
    changes = []
    for r in successful:
        previous = old.get(r["repository"].casefold())
        earlier = set(previous.get("skill_paths", [])) if previous else set()
        current = {p["path"] for p in r["paths"]}
        changes.append({
            "repository": r["repository"], "commit_sha": r["commit_sha"],
            "tree_sha": r["tree_sha"], "checked_at": r["checked_at"],
            "prior_snapshot_present": previous is not None,
            "prior_paths": len(earlier) if previous else None,
            "observed_paths": len(current),
            "new_paths_vs_prior_snapshot": len(current-earlier) if previous else None,
            "absent_paths_vs_prior_snapshot": len(earlier-current) if previous else None,
            "license_spdx": r["license_spdx"]
        })

    # Carry forward repositories not refreshed successfully; replace only successful observations.
    next_state = dict(old)
    for r in successful:
        next_state[r["repository"].casefold()] = {
            "repository": r["repository"], "repository_id": r.get("repository_id"),
            "publisher_account": r.get("publisher_account"),
            "repository_url": r.get("repository_url"),
            "default_branch": r.get("default_branch"),
            "commit_sha": r["commit_sha"], "tree_sha": r["tree_sha"],
            "checked_at": r["checked_at"], "license_spdx": r.get("license_spdx"),
            "license_name": r.get("license_name"), "license_key": r.get("license_key"),
            "license_api_url": r.get("license_api_url"),
            "license_files": r.get("license_files", []),
            "source_reports": r.get("research_leads", []),
            "skill_paths": sorted(p["path"] for p in r["paths"]),
            "paths": r["paths"], "discovery_status": "verified_commit_pinned"
        }
    write_json(state_path, {
        "schema_version": "1.0.0", "updated_at": now(),
        "source": "commit_pinned_github_api_observations",
        "repositories": next_state
    })
    write_json(out / "download-queue.json", queue)
    # Public metadata-only queue is tracked so GitHub-hosted runners can consume it.
    write_json(root / "registry/download-queue.json", queue)
    summary = {
        "schema_version": "1.1.0", "generated_at": now(),
        "baseline_source": baseline_source, "baseline_repositories": len(old),
        "targets": len(targets), "attempted_targets": attempted,
        "processed_targets": len(records),
        "verified_targets": len(successful),
        "errors": sum(r.get("status") == "error" for r in records),
        "observed_paths": sum(len(r["paths"]) for r in successful),
        "explicit_fixture_paths": sum(p["classification"] == "excluded_test_fixture" for r in successful for p in r["paths"]),
        "excluded_non_regular_paths": sum(p["classification"] == "excluded_non_regular" for r in successful for p in r["paths"]),
        "downloaded_registry_records": len(local_downloaded),
        "locally_present_packages": len(local_downloaded) - sum(1 for item in local_downloaded
            if item.get("package_path") and not (root / item["package_path"] / "source.json").is_file()),
        "publicly_mirrored_packages": len(public_index),
        "queue_records": len(queue),
        "stale_fallback_records": len(stale_rows),
        "pending_package_plan": sum(r["status"] == "pending_package_plan" for r in queue),
        "existing_complete_metadata": sum(r["status"] == "existing_complete_metadata" for r in queue),
        "repositories": changes,
        "failed_targets": [{"repository": r["repository"], "error": r["error"]} for r in records if r.get("status") == "error"],
        "limitations": [
            "Tree metadata only; no Skill content inspected or downloaded.",
            "New paths are relative to the last tracked snapshot, not globally unique or recovered dataset rows.",
            "Queue is not authorization to install or execute.",
            "Daily automation refreshes source metadata only. Selected package downloads occur on the user machine; no private archive is required.",
            "Repositories whose refresh fails retain their prior queue entries as stale fallbacks; the downloader must not ingest stale fallbacks."
        ]
    }
    write_json(root / "reconciliation/discovery-summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100, choices=range(1, 101))
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="Re-fetch successful repository observations instead of using local checkpoints")
    args = parser.parse_args()
    print(json.dumps(run(ROOT, args.limit, args.retry_errors, args.refresh), indent=2))


if __name__ == "__main__":
    main()
