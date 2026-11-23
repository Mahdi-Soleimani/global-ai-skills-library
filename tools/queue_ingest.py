#!/usr/bin/env python3
"""Plan and ingest exact discovery queue revisions; never execute downloaded files."""
import argparse
try:
    import fcntl
except ImportError:
    fcntl = None  # pinned-package inspection remains importable on Windows
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import quote

from collector import safe_name, is_excluded_path, now
from discover import github_json, require_sha, REPO, ORDINARY_MODES
from path_rules import is_test_fixture_path
from reconcile import write_json

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def safe_path(path):
    if (not isinstance(path, str) or not path or path.startswith("/") or "\\" in path or
        any(p in {"", ".", ".."} for p in path.split("/")) or
        any(ord(c) < 32 or ord(c) == 127 for c in path)):
        raise ValueError("Unsafe path")
    return path


def collision_key(path):
    return unicodedata.normalize("NFD", path).casefold()


def no_symlink(root, path):
    relative = path.relative_to(root)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError("Symlink or junction in local destination")
    return path


def checked_file(root, path, item):
    no_symlink(root, path)
    if not path.is_file() or path.stat().st_size != item["size"]:
        return False
    return git_blob(path.read_bytes()) == item["sha"]


def make_plan(row, tree, policy):
    skill = safe_path(row["skill_path"])
    if is_test_fixture_path(skill) or not skill.endswith("/SKILL.md"):
        raise ValueError("Fixture, root-level or noncanonical SKILL.md requires explicit review")
    if tree.get("sha") != row["tree_sha"] or tree.get("truncated") is not False:
        raise ValueError("Pinned tree mismatch or incomplete response")
    entries = tree["tree"]
    folder = skill.rsplit("/", 1)[0]
    nested = {e["path"].rsplit("/",1)[0] for e in entries
              if e["path"].startswith(folder + "/") and e["path"].endswith("/SKILL.md") and e["path"] != skill}
    result, blocked, seen, spelling = [], [], set(), {}
    def add_entry(e, relative):
        path = e["path"]
        safe_path(path)
        key = collision_key(relative)
        if key in seen:
            raise ValueError("Case/Unicode collision in package")
        seen.add(key)
        parts = relative.split("/")
        for i in range(1, len(parts) + 1):
            prefix = "/".join(parts[:i])
            folded = collision_key(prefix)
            if folded in spelling and spelling[folded] != prefix:
                raise ValueError("Case/Unicode directory collision")
            spelling[folded] = prefix
        if (e.get("type") != "blob" or e.get("mode") not in ORDINARY_MODES or
            is_excluded_path(path) or any(part.casefold() in {"source.json", "source.json.tmp", ".gasl-download-checkpoint.json"} for part in relative.split("/")) or
            not isinstance(e.get("size"), int) or e["size"] < 0 or e["size"] > policy["max_file_size_bytes"]):
            blocked.append(path)
            return
        result.append({"path": path, "relative": relative, "size": e["size"], "sha": require_sha(e.get("sha"))})

    for e in entries:
        path = e["path"]
        if not path.startswith(folder + "/") or any(path.startswith(n + "/") for n in nested):
            continue
        if e.get("type") == "tree":
            continue
        add_entry(e, path[len(folder) + 1:])

    # Preserve the closest applicable upstream LICENSE/COPYING/NOTICE files
    # so the package can carry its original redistribution terms and notices.
    ancestors = {""}
    parts = folder.split("/")
    ancestors.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
    license_evidence = []
    for e in entries:
        path = e["path"]
        basename = path.rsplit("/", 1)[-1].casefold()
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        is_license = (basename.startswith(("license", "licence", "copying", "notice")) or basename == "copyright")
        in_package = path.startswith(folder + "/") and not any(path.startswith(n + "/") for n in nested)
        if (not in_package and parent not in ancestors) or not is_license or e.get("type") == "tree":
            continue
        if in_package:
            relative = path[len(folder) + 1:]
            if not any(item["path"] == path for item in result):
                add_entry(e, relative)
        else:
            tag = hashlib.sha256(path.encode("utf-8")).hexdigest()[:10]
            relative = "__upstream_licenses__/" + tag + "-" + basename
            add_entry(e, relative)
        if e.get("type") == "blob" and e.get("mode") in ORDINARY_MODES and isinstance(e.get("size"), int):
            if e["size"] <= policy["max_file_size_bytes"]:
                license_evidence.append({"source_path": path, "package_path": relative, "blob_sha": require_sha(e.get("sha"))})
    main = [e for e in result if e["path"] == skill]
    if len(main) != 1 or main[0]["sha"] != row["skill_md_blob_sha"]:
        raise ValueError("SKILL.md missing or blob mismatch")
    # Detect file/directory collisions, including case-insensitive filesystems.
    for key in seen:
        parts = key.split("/")
        if any("/".join(parts[:i]) in seen for i in range(1, len(parts))):
            raise ValueError("File and directory collision")
    size = sum(e["size"] for e in result)
    if blocked or size > policy["max_skill_size_bytes"]:
        raise ValueError("Package has blocked entries or exceeds size cap: " + str(len(blocked)))
    license_evidence = sorted({(x["source_path"], x["package_path"], x["blob_sha"]): x
                               for x in license_evidence}.values(), key=lambda x: x["source_path"])
    return {**row, "files": sorted(result,key=lambda e:e["relative"]), "bytes": size,
            "nested_skill_dirs_excluded": sorted(nested), "license_evidence": license_evidence}


def public_mirror_rejection(row, plan, policy):
    allowed = set(policy.get("public_mirror_spdx_allowlist", []))
    if row.get("license_spdx") not in allowed:
        return "Private collection is allowed; public mirror is blocked by the configured license allowlist"
    if not plan.get("license_evidence"):
        return "No applicable upstream LICENSE/COPYING/NOTICE file was bundled"
    return None


def fetch_tree(row):
    repo = row["repository"]
    if not REPO.fullmatch(repo) or any(p in {".", ".."} for p in repo.split("/")):
        raise ValueError("Invalid repository")
    commit_sha, tree_sha = require_sha(row["commit_sha"]), require_sha(row["tree_sha"])
    commit = github_json("/repos/" + repo + "/git/commits/" + commit_sha)
    if commit.get("sha") != commit_sha or commit.get("tree",{}).get("sha") != tree_sha:
        raise ValueError("Commit/tree relationship mismatch")
    return github_json("/repos/" + repo + "/git/trees/" + tree_sha + "?recursive=1")


def fetch_blob(plan, item):
    url = "https://raw.githubusercontent.com/" + plan["repository"] + "/" + plan["commit_sha"] + "/" + quote(item["path"], safe="/")
    r = subprocess.run(["curl","--fail","--silent","--show-error","--connect-timeout","5",
                        "--max-time","20","--max-filesize",str(max(1,item["size"])),
                        "--retry","1",url],capture_output=True,check=False)
    if r.returncode:
        raise RuntimeError(r.stderr.decode("utf-8","replace").strip()[:250])
    return r.stdout


def package_location(root, plan):
    repo = "__".join(safe_name(p) for p in plan["repository"].split("/"))
    leaf = safe_name(plan["skill_path"].split("/")[-2])
    tag = hashlib.sha256(plan["skill_path"].encode()).hexdigest()[:8]
    return root / "catalog" / repo / (leaf+"__"+tag+"@"+plan["commit_sha"][:12])


def validate_inventory(root, folder, plan, metadata=False):
    expected = {e["relative"] for e in plan["files"]}
    if metadata:
        expected.add("source.json")
    actual = set()
    for path in folder.rglob("*"):
        no_symlink(root,path)
        if path.is_file():
            actual.add(path.relative_to(folder).as_posix())
        elif not path.is_dir():
            raise ValueError("Nonregular local entry")
    if expected != actual:
        raise ValueError("Unexpected or missing package files")
    for e in plan["files"]:
        if not checked_file(root, folder/e["relative"], e):
            raise ValueError("Package integrity failure")


def merge_manifest(root, plan, dest, manifest_path=None):
    path = manifest_path if manifest_path is not None else root / "registry/download-manifest.json"
    manifest = read_json(path) if path.exists() else {"schema_version": "0.1.0", "downloads": []}
    entry = next((e for e in manifest["downloads"] if e["repository"].casefold()==plan["repository"].casefold() and e["commit_sha"]==plan["commit_sha"]),None)
    if entry is None:
        entry = {"repository":plan["repository"], "commit_sha":plan["commit_sha"], "downloaded_at":now(), "skill_packages":[]}
        manifest["downloads"].append(entry)
    item = {"skill_path":plan["skill_path"], "package_path":str(dest.relative_to(root)),
            "file_count":len(plan["files"]), "bytes":plan["bytes"]}
    existing = next((e for e in entry["skill_packages"] if e["skill_path"]==plan["skill_path"]),None)
    if existing is not None:
        if existing.get("package_path") != item["package_path"]:
            raise ValueError("Existing manifest package path conflicts for the same immutable source identity")
        # A later complete package plan may include upstream LICENSE/NOTICE files
        # that an older pilot omitted. Refresh its measured inventory after the
        # new package has passed full hash and directory validation.
        existing.update(item)
        write_json(path,manifest)
        return
    entry["skill_packages"].append(item)
    write_json(path,manifest)


def ingest(root, plan, fetch=fetch_blob, manifest_path=None):
    dest = no_symlink(root,package_location(root,plan))
    if dest.exists():
        source = no_symlink(root,dest/"source.json")
        meta = read_json(source)
        if (meta.get("repository","").casefold()!=plan["repository"].casefold() or
            meta.get("commit_sha")!=plan["commit_sha"] or meta.get("source_skill_path")!=plan["skill_path"] or
            not meta.get("package_complete")):
            raise ValueError("Existing package identity conflict")
        validate_inventory(root,dest,plan,metadata=True)
        merge_manifest(root,plan,dest,manifest_path)
        return {"status":"already_verified","new_files":0,"reused_files":len(plan["files"])}
    stage = no_symlink(root, root/"quarantine"/"queue-ingest"/dest.parent.name/dest.name)
    stage.mkdir(parents=True,exist_ok=True)
    new_files = reused = 0
    for item in plan["files"]:
        target = no_symlink(root,stage/item["relative"])
        if target.exists():
            if not checked_file(root,target,item):
                raise ValueError("Corrupt checkpoint file; retained for review")
            reused += 1
            continue
        data = fetch(plan,item)
        if len(data)!=item["size"] or git_blob(data)!=item["sha"]:
            raise ValueError("Downloaded blob size/hash mismatch")
        target.parent.mkdir(parents=True,exist_ok=True)
        # Atomic visibility: partial bytes never count as verified.
        temp_dir = no_symlink(root, root/"quarantine"/"queue-ingest"/".partial")
        temp_dir.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=temp_dir,delete=False) as stream:
            temp = Path(stream.name)
            stream.write(data)
        temp.replace(target)
        new_files += 1
    # A crash after metadata generation can be resumed, but only with full verification.
    source = no_symlink(root,stage/"source.json")
    validate_inventory(root,stage,plan,metadata=source.exists())
    records = [{"source_path":e["path"],"package_relative_path":e["relative"],
                "local_path":str((dest/e["relative"]).relative_to(root)),
                "size_bytes":e["size"],"sha256":hashlib.sha256((stage/e["relative"]).read_bytes()).hexdigest(),
                "git_blob_sha":e["sha"]} for e in plan["files"]]
    spdx = plan.get("license_spdx")
    collection_policy = read_json(root/"config/policy.json")
    allowlist = set(collection_policy.get("public_mirror_spdx_allowlist", []))
    has_license_evidence = bool(plan.get("license_evidence"))
    unknown_license = spdx in (None, "", "NOASSERTION", "NONE")
    if unknown_license:
        license_status = "license_unknown_evidence_bundled" if has_license_evidence else "license_unknown_no_evidence"
    elif has_license_evidence:
        license_status = "license_evidence_bundled_pending_scan"
    else:
        license_status = "license_evidence_missing_content_collected"
    if spdx not in allowlist:
        public_mirror_status = "not_eligible_license_policy"
    elif not has_license_evidence:
        public_mirror_status = "blocked_missing_license_evidence"
    else:
        public_mirror_status = "eligible_pending_static_scan"
    meta = {"collector_version":"0.5.0-attributed","package_type":"skill_candidate",
            "skill_name":dest.name.split("__")[0],"repository":plan["repository"],
            "canonical_repository":plan["repository"],"repository_owner":plan.get("publisher_account") or plan["repository"].split("/")[0],
            "repository_url":plan.get("repository_url") or "https://github.com/"+plan["repository"],
            "source_url":plan.get("source_url") or "https://github.com/{}/blob/{}/{}".format(plan["repository"],plan["commit_sha"],quote(plan["skill_path"],safe="/")),
            "source_skill_path":plan["skill_path"],"commit_sha":plan["commit_sha"],"tree_sha":plan["tree_sha"],
            "skill_md_blob_sha":plan.get("skill_md_blob_sha"),
            "license_spdx":spdx,"license_name":plan.get("license_name"),
            "license_url":plan.get("license_url"),"license_evidence":plan.get("license_evidence",[]),
            "license_status":license_status,"public_mirror_status":public_mirror_status,
            "collection_status":"collected","collection_scope":"private_local_catalog",
            "content_status":"downloaded_and_hashed_locally",
            "ownership":"third_party","original_author":None,"gasl_claims_exclusive_ownership":False,
            "attribution_notice":"Third-party work. Original rights remain with upstream authors/rightsholders. GASL is an attributed collection and does not claim exclusive ownership.",
            "research_leads":plan["research_leads"],"source_link_scope":"repository/path discovery reference; research leads do not establish individual authorship",
            "downloaded_at":now(),"execution_performed":False,"package_complete":True,
            "completeness_scope":"regular files in skill directory excluding nested skill folders; external dependencies unverified",
            "nested_skill_dirs_excluded":plan["nested_skill_dirs_excluded"],
            "skipped_files":[],"security_status":"not_scanned","files":records}
    write_json(source,meta)
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        raise ValueError("Destination appeared during ingest")
    stage.rename(dest)
    merge_manifest(root,plan,dest,manifest_path)
    return {"status":"downloaded","new_files":new_files,"reused_files":reused}


def main():
    p = argparse.ArgumentParser()
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--repo",action="append")
    group.add_argument("--all-queued-repos",action="store_true")
    p.add_argument("--per-repo",type=int,default=1,choices=range(1,11))
    p.add_argument("--max-batch-bytes",type=int,default=5*1024*1024)
    p.add_argument("--max-files",type=int,default=30)
    p.add_argument("--execute",action="store_true")
    p.add_argument("--verify-existing",action="store_true",help="Select existing packages for integrity verification instead of advancing the queue")
    args = p.parse_args()
    if args.max_batch_bytes<1 or args.max_files<1:
        p.error("positive bounds required")
    policy = read_json(ROOT/"config/policy.json")
    queue_path = ROOT/"registry/discovery/download-queue.json"
    if not queue_path.exists():
        queue_path = ROOT/"registry/download-queue.json"
    queue = read_json(queue_path)
    planned, rejected, total, count = [], [], 0, 0
    # License status never filters private collection. Public mirroring is a separate
    # operation with its own allowlist/evidence checks.
    selected_repos = (list(dict.fromkeys(r["repository"].casefold() for r in queue
                                           if r.get("discovery_status", "verified_metadata_only") != "stale_fallback"
                                           and r.get("install_status") == "not_approved"
                                           and r.get("status") == "pending_package_plan"))
                      if args.all_queued_repos else list(dict.fromkeys(r.casefold() for r in args.repo)))
    if fcntl is None:
        raise ValueError("Queue ingestion is not enabled on Windows until its own lock is ported")
    with (ROOT/"registry/discovery/.ingest.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for repo in selected_repos:
            rows = [r for r in queue if r["repository"].casefold()==repo
                    and r["install_status"]=="not_approved"
                    and r.get("status")=="pending_package_plan"
                    and r.get("discovery_status", "verified_metadata_only") != "stale_fallback"]
            if not rows:
                raise ValueError("Repository missing from queue: "+repo)
            tree = fetch_tree(rows[0])
            # Preserve FIFO order within each repo; skip only blocked/over-budget choices, recording reason.
            selected = 0
            for row in rows:
                if row["commit_sha"]!=rows[0]["commit_sha"]:
                    raise ValueError("Mixed queue revisions")
                try:
                    # Every discovered skill is eligible for private collection, including
                    # unknown, proprietary, copyleft, and non-allowlisted licenses.
                    # Public redistribution remains a separate gate in build_public_catalog.py.
                    plan = make_plan(row,tree,policy)
                    dest = no_symlink(ROOT,package_location(ROOT,plan))
                    if dest.exists() and not args.verify_existing:
                        # Skip only after verifying the complete inventory against the pinned tree.
                        metadata=read_json(no_symlink(ROOT,dest/"source.json"))
                        if (metadata.get("repository","").casefold()!=row["repository"].casefold()
                            or metadata.get("commit_sha")!=row["commit_sha"]
                            or metadata.get("source_skill_path")!=row["skill_path"]
                            or not metadata.get("package_complete")):
                            raise ValueError("Existing package identity conflict")
                        validate_inventory(ROOT,dest,plan,metadata=True)
                        if args.execute:
                            merge_manifest(ROOT,plan,dest)
                        continue
                    if (total+plan["bytes"]>min(args.max_batch_bytes,policy["max_repository_download_bytes"]) or
                        count+len(plan["files"])>args.max_files):
                        raise ValueError("Batch budget exceeded")
                except ValueError as error:
                    rejected.append({"repository":row["repository"],"skill_path":row["skill_path"],"reason":str(error)})
                    continue
                planned.append(plan)
                count += len(plan["files"])
                total += plan["bytes"]
                selected += 1
                if selected>=args.per_repo:
                    break
            if not selected:
                print("No bounded package selected:",repo,flush=True)
        write_json(ROOT/"registry/discovery/ingest-plan.json",{"packages":planned,"rejected":rejected,"bytes":total,"files":count})
        print("PLAN",len(planned),"packages",count,"files",total,"bytes",flush=True)
        if not args.execute:
            return
        if not planned:
            write_json(ROOT/"registry/discovery/ingest-results.json", [])
            print("No new packages selected; queue is already satisfied or blocked.",flush=True)
            return
        if shutil.disk_usage(ROOT).free < total+1024*1024*1024:
            raise SystemExit("Insufficient free disk")
        results = []
        for plan in planned:
            try:
                result = ingest(ROOT,plan)
            except (OSError,ValueError,RuntimeError) as error:
                result = {"status":"blocked_or_failed","reason":str(error)}
            result.update({"repository":plan["repository"],"skill_path":plan["skill_path"],
                           "commit_sha":plan["commit_sha"],"bytes":plan["bytes"],"file_count":len(plan["files"])})
            results.append(result)
            write_json(ROOT/"registry/discovery/ingest-results.json",results)
            print(json.dumps(result,ensure_ascii=False),flush=True)
        if any(r["status"]=="blocked_or_failed" for r in results):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
