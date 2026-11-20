#!/usr/bin/env python3
"""Safe, pinned collector for Agent Skills. Downloads files only; never executes them."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from path_rules import is_test_fixture_path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry"
POLICY_PATH = ROOT / "config" / "policy.json"
VERIFY_PATH = REGISTRY / "source-verification.json"
API = "https://api.github.com"
UA = "GASL-Collector/0.1 (local research library)"
EXCLUDED_DIRS = {".git", "node_modules", ".venv", "venv", "vendor", "dist", "build",
                 "__pycache__", ".next", ".turbo", ".cache", "coverage", "playwright-report",
                 "test-results", "tmp", "temp"}


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def curl_bytes(url, output=None, expected_size=None):
    cmd = ["curl", "--fail", "--silent", "--show-error", "--location",
           "--retry", "6", "--retry-all-errors", "--retry-delay", "2",
           "--connect-timeout", "20", "--max-time", "180",
           "--user-agent", UA]
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith(API):
        cmd.extend(["-H", "Authorization: Bearer " + token,
                    "-H", "X-GitHub-Api-Version: 2022-11-28"])
    if output is None:
        result = subprocess.run(cmd + [url], capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", "replace").strip() or "curl failed")
        return result.stdout

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and expected_size is not None:
        current_size = output.stat().st_size
        if current_size == expected_size:
            return output.read_bytes()
        if current_size > expected_size:
            output.unlink()
        elif current_size > 0:
            cmd.extend(["--continue-at", "-"])
    cmd.extend(["--output", str(output), url])
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip() or "curl failed"
        raise RuntimeError(detail + "; partial file retained for resume: " + str(output))
    data = output.read_bytes()
    if expected_size is not None and len(data) != expected_size:
        raise RuntimeError("size mismatch for {}: expected {}, received {}; file retained for resume".format(
            output, expected_size, len(data)))
    return data


def curl_json(url):
    return json.loads(curl_bytes(url).decode("utf-8"))


def safe_name(value):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "unnamed"


def skill_dirs(paths):
    return sorted(set(p.rsplit("/", 1)[0] if "/" in p else "" for p in paths), key=lambda x: (x.count("/"), x))


def belongs_to_nested_skill(path, current_dir, all_dirs):
    for other in all_dirs:
        if other and other != current_dir:
            prefix = current_dir + "/" if current_dir else ""
            if other.startswith(prefix) and other != current_dir:
                if path.startswith(other + "/"):
                    return True
    return False


def is_excluded_path(path):
    return any(part in EXCLUDED_DIRS for part in path.split("/"))


def collect(repo_name, execute=False, selected_paths=None, include_test_fixtures=False):
    policy = load(POLICY_PATH, {})
    state = load(VERIFY_PATH, {"repositories": {}})
    repo = state.get("repositories", {}).get(repo_name.lower())
    if not repo or repo.get("status") != "verified":
        raise SystemExit("STOP: repository must be live-verified first.")
    if repo.get("archived") or repo.get("private"):
        raise SystemExit("STOP: archived/private repository requires manual review.")
    if repo.get("tree_truncated"):
        raise SystemExit("STOP: repository tree was truncated; do not bulk-download.")
    if not repo.get("skill_paths"):
        raise SystemExit("STOP: no SKILL.md paths recorded for this repository.")

    owner, name = repo["repo_full_name"].split("/", 1)
    branch = repo.get("default_branch") or "main"
    commit = curl_json(API + "/repos/" + repo["repo_full_name"] + "/commits/" + urllib.parse.quote(branch, safe=""))
    commit_sha = commit["sha"]
    tree = curl_json(API + "/repos/" + repo["repo_full_name"] + "/git/trees/" + commit_sha + "?recursive=1")
    if tree.get("truncated"):
        raise SystemExit("STOP: fresh tree is truncated; collection aborted.")
    entries = tree.get("tree", [])
    all_skill_paths = [x["path"] for x in entries if x.get("type") == "blob" and x.get("path", "").split("/")[-1].lower() == "skill.md"]
    fixture_paths = {path for path in all_skill_paths if is_test_fixture_path(path)}
    paths = all_skill_paths if include_test_fixtures else [path for path in all_skill_paths if path not in fixture_paths]
    if not paths:
        raise SystemExit("STOP: no production Skill candidates found in current commit.")
    if selected_paths:
        requested = set(selected_paths)
        missing = sorted(requested - set(all_skill_paths))
        if missing:
            raise SystemExit("STOP: requested SKILL.md path(s) not found in current tree: " + ", ".join(missing))
        blocked_fixtures = sorted(requested & fixture_paths) if not include_test_fixtures else []
        if blocked_fixtures:
            raise SystemExit("STOP: test fixture path(s) require --include-test-fixtures: " + ", ".join(blocked_fixtures))
        paths = [path for path in paths if path in requested]
    dirs = skill_dirs(paths)

    max_file = int(policy.get("max_file_size_bytes", 10 * 1024 * 1024))
    max_skill = int(policy.get("max_skill_size_bytes", 50 * 1024 * 1024))
    plan = []
    for skill_path in paths:
        skill_dir = skill_path.rsplit("/", 1)[0] if "/" in skill_path else ""
        if skill_dir:
            candidates = [x for x in entries if x.get("type") == "blob" and
                          (x["path"] == skill_dir or x["path"].startswith(skill_dir + "/")) and
                          not belongs_to_nested_skill(x["path"], skill_dir, dirs) and
                          not is_excluded_path(x["path"])]
        else:
            allow = ("SKILL.md", "README.md", "LICENSE", "LICENSE.md", "SPEC.md")
            candidates = [x for x in entries if x.get("type") == "blob" and
                          (x["path"] in allow or x["path"].startswith(
                              ("scripts/", "references/", "assets/", "examples/", "evals/"))) and
                          not is_excluded_path(x["path"])]
        total = sum(int(x.get("size") or 0) for x in candidates
                    if x.get("mode") != "120000" and int(x.get("size") or 0) <= max_file)
        plan.append({"skill_path": skill_path, "skill_dir": skill_dir,
                     "candidate_files": len(candidates), "estimated_bytes": total})
    total_paths = sum(x["candidate_files"] for x in plan)
    total_bytes = sum(x["estimated_bytes"] for x in plan)
    print("Repository:", repo["repo_full_name"])
    print("Pinned commit:", commit_sha)
    print("SKILL.md files:", len(paths))
    print("Candidate files:", total_paths)
    print("Estimated bytes:", total_bytes)
    if not execute:
        print("DRY RUN only. No files downloaded.")
        return
    if total_bytes > int(policy.get("max_repository_download_bytes", 500 * 1024 * 1024)):
        raise SystemExit("STOP: repository exceeds configured download size cap.")

    downloaded = []
    for item in plan:
        skill_path = item["skill_path"]
        skill_dir = item["skill_dir"]
        skill_leaf = skill_dir.rsplit("/", 1)[-1] if skill_dir else "root"
        dest = ROOT / "catalog" / (safe_name(owner) + "__" + safe_name(name)) / (
            safe_name(skill_leaf) + "__" + hashlib.sha256(skill_path.encode("utf-8")).hexdigest()[:8] +
            "@" + commit_sha[:12])
        if dest.exists() and (dest / "source.json").exists():
            old = load(dest / "source.json", {})
            downloaded.append({"skill_path": skill_path, "package_path": str(dest.relative_to(ROOT)),
                               "file_count": len(old.get("files", [])),
                               "bytes": sum(x.get("size_bytes", 0) for x in old.get("files", []))})
            print("SKIP existing pinned package:", dest.relative_to(ROOT))
            continue

        if skill_dir:
            candidates = [x for x in entries if x.get("type") == "blob" and
                          (x["path"] == skill_dir or x["path"].startswith(skill_dir + "/")) and
                          not belongs_to_nested_skill(x["path"], skill_dir, dirs) and
                          not is_excluded_path(x["path"])]
        else:
            allow = ("SKILL.md", "README.md", "LICENSE", "LICENSE.md", "SPEC.md")
            candidates = [x for x in entries if x.get("type") == "blob" and
                          (x["path"] in allow or x["path"].startswith(
                              ("scripts/", "references/", "assets/", "examples/", "evals/"))) and
                          not is_excluded_path(x["path"])]

        dest.mkdir(parents=True, exist_ok=True)
        checkpoint_path = dest / ".gasl-download-checkpoint.json"
        checkpoint = load(checkpoint_path, {
            "repository": repo["repo_full_name"], "commit_sha": commit_sha,
            "source_skill_path": skill_path, "files": {}
        })
        if checkpoint.get("commit_sha") != commit_sha or checkpoint.get("source_skill_path") != skill_path:
            checkpoint = {"repository": repo["repo_full_name"], "commit_sha": commit_sha,
                          "source_skill_path": skill_path, "files": {}}
        checkpoint.setdefault("files", {})

        package_files = []
        skipped_files = []
        total = 0
        for item_file in candidates:
            source_path = item_file["path"]
            size = int(item_file.get("size") or 0)
            if item_file.get("mode") == "120000":
                print("SKIP symlink:", source_path)
                skipped_files.append({"source_path": source_path, "reason": "symlink"})
                continue
            if size > max_file or total + size > max_skill:
                print("SKIP size limit:", source_path, size)
                skipped_files.append({"source_path": source_path, "reason": "size_limit", "size_bytes": size})
                continue
            if source_path.startswith("/") or ".." in source_path.split("/") or "\\" in source_path:
                print("SKIP unsafe path:", source_path)
                skipped_files.append({"source_path": source_path, "reason": "unsafe_path"})
                continue

            relative = source_path[len(skill_dir) + 1:] if skill_dir else source_path
            target = dest / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            prior = checkpoint["files"].get(source_path)
            if target.exists() and target.stat().st_size == size:
                existing = target.read_bytes()
                existing_sha256 = hashlib.sha256(existing).hexdigest()
                git_blob_sha = hashlib.sha1(b"blob " + str(len(existing)).encode("ascii") + b"\0" + existing).hexdigest()
                if git_blob_sha == item_file.get("sha"):
                    record = prior or {
                        "source_path": source_path,
                        "local_path": str(target.relative_to(ROOT)),
                        "size_bytes": len(existing),
                        "sha256": existing_sha256,
                        "git_blob_sha": git_blob_sha
                    }
                    record["sha256"] = existing_sha256
                    record["git_blob_sha"] = git_blob_sha
                    package_files.append(record)
                    total += len(existing)
                    checkpoint["files"][source_path] = record
                    continue
                target.unlink()

            raw_url = "https://raw.githubusercontent.com/{}/{}/{}/{}".format(
                owner, name, commit_sha, urllib.parse.quote(source_path, safe="/"))
            content = curl_bytes(raw_url, target, expected_size=size)
            digest = hashlib.sha256(content).hexdigest()
            git_blob_sha = hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()
            if item_file.get("sha") and git_blob_sha != item_file.get("sha"):
                raise RuntimeError("Git blob SHA mismatch for {}; partial package retained for investigation".format(source_path))
            record = {
                "source_path": source_path,
                "local_path": str(target.relative_to(ROOT)),
                "size_bytes": len(content),
                "sha256": digest,
                "git_blob_sha": git_blob_sha
            }
            package_files.append(record)
            total += len(content)
            checkpoint["files"][source_path] = record
            checkpoint["updated_at"] = now()
            save(checkpoint_path, checkpoint)

        skill_md = dest / "SKILL.md"
        skill_text = skill_md.read_text(encoding="utf-8", errors="replace") if skill_md.exists() else ""
        if not skill_text:
            raise RuntimeError("SKILL.md was not successfully collected for " + skill_path)
        match = re.search(r"(?m)^name:\s*([^\r\n]+)", skill_text)
        skill_name = match.group(1).strip().strip(chr(34)).strip(chr(39)) if match else skill_leaf
        metadata = {
            "collector_version": "0.3.1",
            "package_type": "test_fixture" if is_test_fixture_path(skill_path) else "skill_candidate",
            "skill_name": skill_name,
            "repository": repo["repo_full_name"],
            "source_repo_name": repo.get("source_repo_name", repo["repo_full_name"]),
            "canonical_repository": repo.get("canonical_repo_name", repo["repo_full_name"]),
            "source_reports": repo.get("source_reports", []),
            "repository_url": repo.get("html_url") or repo.get("repository_url"),
            "source_skill_path": skill_path,
            "default_branch_at_download": branch,
            "commit_sha": commit_sha,
            "tree_sha": tree.get("sha"),
            "license_spdx": repo.get("license_spdx"),
            "license_status": "known" if repo.get("license_spdx") else "unknown_review_required",
            "downloaded_at": now(),
            "execution_performed": False,
            "package_complete": len(skipped_files) == 0,
            "skipped_files": skipped_files,
            "security_status": "not_scanned",
            "files": package_files
        }
        save(dest / "source.json", metadata)
        downloaded.append({"skill_path": skill_path, "package_path": str(dest.relative_to(ROOT)),
                           "file_count": len(package_files), "bytes": total})
        print("DOWNLOADED:", skill_name, "files=", len(package_files), "bytes=", total)

    manifest_path = REGISTRY / "download-manifest.json"
    manifest = load(manifest_path, {"schema_version": "0.1.0", "downloads": []})
    entry = {
        "repository": repo["repo_full_name"],
        "commit_sha": commit_sha,
        "downloaded_at": now(),
        "skill_packages": downloaded
    }
    existing = next((x for x in manifest["downloads"]
                     if x.get("repository") == repo["repo_full_name"] and x.get("commit_sha") == commit_sha), None)
    if existing:
        previous = {x["skill_path"]: x for x in existing.get("skill_packages", [])}
        previous.update({x["skill_path"]: x for x in downloaded})
        existing["skill_packages"] = list(previous.values())
    else:
        manifest["downloads"].append(entry)
    save(manifest_path, manifest)
    print("Finished. Packages downloaded:", len(downloaded))
    print("Downloaded code was not executed.")


def main():
    p = argparse.ArgumentParser(prog="gasl-collect")
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("download", help="Download skill folders from a verified repository")
    d.add_argument("--repo", required=True, help="owner/repo")
    d.add_argument("--execute", action="store_true", help="Perform download; default is dry-run")
    d.add_argument("--skill-path", action="append", help="Exact SKILL.md path to collect; repeat to select multiple")
    d.add_argument("--include-test-fixtures", action="store_true",
                   help="Include SKILL.md files under evals/tests fixture directories (not installable Skills)")
    d.set_defaults(func=lambda a: collect(a.repo, a.execute, a.skill_path, a.include_test_fixtures))
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
