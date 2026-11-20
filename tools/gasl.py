#!/usr/bin/env python3
"""GASL Phase-1 CLI. Python 3.9+, standard library only. No downloaded code is executed."""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "source-repositories.json"
REGISTRY = ROOT / "registry"
API = "https://api.github.com"
UA = "GASL-Collector/0.1 (local research library)"


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def get_json(url):
    cmd = ["curl", "--fail", "--silent", "--show-error", "--location",
           "--retry", "3", "--retry-delay", "1", "--max-time", "45",
           "--user-agent", UA,
           "-H", "Accept: application/vnd.github+json",
           "-H", "X-GitHub-Api-Version: 2022-11-28"]
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        cmd.extend(["-H", "Authorization: Bearer " + token])
    result = subprocess.run(cmd + [url], capture_output=True, check=False)
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError("GitHub request failed: " + (detail or str(result.returncode)))
    return json.loads(result.stdout.decode("utf-8"))


def all_repos(cfg):
    by_name = {}
    for report_id, report in cfg["reports"].items():
        for repo in report["explicit_github_repositories"]:
            key = repo.lower()
            if key not in by_name:
                by_name[key] = {"repo_full_name": repo, "source_reports": []}
            if report_id not in by_name[key]["source_reports"]:
                by_name[key]["source_reports"].append(report_id)
    return sorted(by_name.values(), key=lambda x: x["repo_full_name"].lower())


def cmd_summary(args):
    cfg = load(CONFIG, {})
    print("GASL source inventory")
    for report_id, report in cfg.get("reports", {}).items():
        count = report.get("record_count_claimed", report.get("reported_unique_skills"))
        print("{} [{}]: record_count_claimed={}, sample_rows={}, explicit GitHub repos={}".format(
            report_id, report.get("dataset_role", "unspecified"), count,
            report.get("embedded_csv_sample_rows", "not embedded"),
            len(report.get("explicit_github_repositories", []))))
    repos = all_repos(cfg)
    overlap = sum(1 for r in repos if len(r["source_reports"]) > 1)
    verified = load(REGISTRY / "source-verification.json", {"repositories": {}}).get("repositories", {})
    canonical = {str(x.get("canonical_repo_name", x.get("repo_full_name", k))).lower()
                 for k, x in verified.items() if x.get("status") == "verified"}
    print("Repository mentions: {}".format(sum(len(x["explicit_github_repositories"]) for x in cfg["reports"].values())))
    print("Distinct source repository references: {}".format(len(repos)))
    print("Cross-referenced repository references: {}".format(overlap))
    print("Live-verified source references: {}".format(sum(x.get("status") == "verified" for x in verified.values())))
    print("Canonical GitHub repositories: {}".format(len(canonical)))
    print("No skills downloaded or installed by summary.")


def cmd_bootstrap(args):
    cfg = load(CONFIG, {})
    for report_id, report in cfg["reports"].items():
        records = []
        for i, repo in enumerate(report["explicit_github_repositories"], 1):
            records.append({
                "source_id": "{}-SRC-{:04d}".format(report_id, i),
                "report_id": report_id,
                "repo_full_name": repo,
                "repository_url": "https://github.com/" + repo,
                "verification_status": "not_yet_verified_live"
            })
        manifest = {
            "manifest_version": "0.2.0",
            "report_id": report_id,
            "dataset_role": report.get("dataset_role"),
            "language": report.get("language"),
            "source_file": report["source_file"],
            "source_sha256": report["source_sha256"],
            "source_size_bytes": report.get("source_size_bytes"),
            "record_count_claimed": report.get("record_count_claimed", report.get("reported_unique_skills")),
            "record_count_semantics": report.get("record_count_semantics"),
            "database_artifacts_available": report.get("database_artifacts_available"),
            "missing_artifacts": report.get("missing_artifacts", []),
            "reported_counts": {k: v for k, v in report.items() if k.startswith("reported_")},
            "embedded_skill_record_rows": report.get("embedded_csv_sample_rows"),
            "repositories": records,
            "note": "Explicit repository references extracted from this exact report only. This is not a replacement for its full skill-record database."
        }
        save(ROOT / "research" / report_id / "source-manifest.json", manifest)
        with (ROOT / "research" / report_id / "source-manifest.csv").open("w", encoding="utf-8-sig", newline="") as f:
            fields = ["source_id", "report_id", "repo_full_name", "repository_url", "verification_status"]
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(records)

    repos = all_repos(cfg)
    with (ROOT / "reconciliation" / "repository-overlap.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["repo_full_name", "source_reports", "primary_sources", "supplemental_sources", "note"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for item in repos:
            source_ids = item["source_reports"]
            primary = [x for x in source_ids if cfg["reports"][x].get("dataset_role") == "primary_independent_dataset"]
            supplemental = [x for x in source_ids if cfg["reports"][x].get("dataset_role") != "primary_independent_dataset"]
            w.writerow({
                "repo_full_name": item["repo_full_name"],
                "source_reports": ";".join(source_ids),
                "primary_sources": ";".join(primary),
                "supplemental_sources": ";".join(supplemental),
                "note": "Repository cross-reference only; no skill records merged, deduplicated, or removed."
            })
    print("Bootstrapped {} independent report manifests; {} repository names, {} cross-referenced.".format(
        len(cfg["reports"]), len(repos), sum(1 for r in repos if len(r["source_reports"]) > 1)))


def cmd_verify(args):
    cfg = load(CONFIG, {})
    targets = all_repos(cfg)
    if args.only:
        wanted = set(x.lower() for x in args.only)
        targets = [x for x in targets if x["repo_full_name"].lower() in wanted]
    if args.limit:
        targets = targets[:args.limit]
    state_path = REGISTRY / "source-verification.json"
    state = load(state_path, {"schema_version": "0.1.0", "repositories": {}})
    state.setdefault("repositories", {})
    for i, source in enumerate(targets, 1):
        name = source["repo_full_name"]
        key = name.lower()
        print("[{}/{}] {}".format(i, len(targets), name), flush=True)
        result = {
            "repo_full_name": name,
            "repository_url": "https://github.com/" + name,
            "source_reports": source["source_reports"],
            "checked_at": now()
        }
        try:
            repo = get_json(API + "/repos/" + name)
            lic = repo.get("license") or {}
            result.update({
                "status": "verified",
                "id": repo.get("id"),
                "owner_login": (repo.get("owner") or {}).get("login"),
                "default_branch": repo.get("default_branch"),
                "archived": repo.get("archived"),
                "private": repo.get("private"),
                "visibility": repo.get("visibility"),
                "size_kb": repo.get("size"),
                "stars": repo.get("stargazers_count"),
                "forks": repo.get("forks_count"),
                "updated_at": repo.get("updated_at"),
                "pushed_at": repo.get("pushed_at"),
                "license_spdx": lic.get("spdx_id"),
                "license_name": lic.get("name"),
                "html_url": repo.get("html_url")
            })
            if args.trees:
                branch = urllib.parse.quote(repo.get("default_branch", "main"), safe="")
                tree = get_json(API + "/repos/" + name + "/git/trees/" + branch + "?recursive=1")
                paths = [x.get("path") for x in tree.get("tree", [])
                         if x.get("type") == "blob" and x.get("path", "").split("/")[-1].lower() == "skill.md"]
                result["skill_paths"] = paths
                result["skill_file_count"] = len(paths)
                result["tree_truncated"] = tree.get("truncated", False)
                result["tree_status"] = "truncated" if tree.get("truncated") else "complete"
        except urllib.error.HTTPError as exc:
            result["status"] = "http_error"
            result["error"] = "HTTP {}".format(exc.code)
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)
        state["repositories"][key] = result
        state["updated_at"] = now()
        save(state_path, state)
        time.sleep(max(0.0, args.delay))

    fields = ["repo_full_name", "status", "owner_login", "default_branch", "archived",
              "visibility", "size_kb", "stars", "forks", "updated_at", "pushed_at",
              "license_spdx", "skill_file_count", "tree_status", "error", "source_reports"]
    with (REGISTRY / "source-verification.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for item in sorted(state["repositories"].values(), key=lambda x: x["repo_full_name"].lower()):
            row = dict(item)
            row["source_reports"] = ";".join(row.get("source_reports", []))
            w.writerow({k: row.get(k, "") for k in fields})
    print("Saved {} repository verification records.".format(len(state["repositories"])))


def main():
    p = argparse.ArgumentParser(prog="gasl", description="Global AI Skills Library")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("summary")
    s.set_defaults(func=cmd_summary)
    b = sub.add_parser("bootstrap")
    b.set_defaults(func=cmd_bootstrap)
    v = sub.add_parser("verify")
    v.add_argument("--limit", type=int, default=0)
    v.add_argument("--only", nargs="*")
    v.add_argument("--trees", action="store_true")
    v.add_argument("--delay", type=float, default=0.5)
    v.set_defaults(func=cmd_verify)
    r = sub.add_parser("reconcile", help="Build source crosswalks from local snapshot and registry")
    def cmd_reconcile(args):
        from reconcile import run
        print(json.dumps(run(), indent=2))
    r.set_defaults(func=cmd_reconcile)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
