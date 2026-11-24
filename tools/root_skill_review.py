"""Explicit read-only inventory review for root-level pinned Skills.

Repository root is not automatically a Skill package. No blob retrieval,
download approval, cache writes, or execution is performed.
"""
import hashlib
import json
from pathlib import Path

from canonical_index import _selected, _read_raw, ROOT
from canonical_lineage import _get, _repo_identity, _sha
from canonical_package import checked_tree, MAX_ENTRIES, MAX_DEPTH
from collector import is_excluded_path
from queue_ingest import safe_path, collision_key
from transaction_file_lock import require_windows_filename_safety

MAX_FILES = 300
MAX_BYTES = 50 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024


def verify_recursive_tree(data, expected, *, max_entries=MAX_ENTRIES, max_depth=MAX_DEPTH):
    """Reconstruct every tree bottom-up from complete recursive metadata."""
    if (not isinstance(data, dict) or data.get("sha") != expected
            or data.get("truncated") is not False or not isinstance(data.get("tree"), list)
            or len(data["tree"]) > max_entries):
        raise ValueError("Incomplete or oversized recursive tree")
    entries, directories = {}, {"": []}
    for item in data["tree"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid recursive tree entry")
        path = safe_path(item.get("path"))
        if len(path.split("/")) > max_depth or path in entries:
            raise ValueError("Duplicate or excessively deep tree path")
        entries[path] = item
        if item.get("type") == "tree":
            directories[path] = []
    for path, item in entries.items():
        parent, _, name = path.rpartition("/")
        if parent not in directories:
            raise ValueError("Missing parent tree")
        directories[parent].append(dict(item, path=name))
    for path, children in directories.items():
        pin = expected if not path else _sha(entries[path].get("sha"))
        checked_tree({"sha":pin,"truncated":False,"tree":children},pin)
    return entries


def inspect_inventory(row, data):
    if row.get("source_path") != "SKILL.md":
        raise ValueError("Only an exact repository-root SKILL.md may be reviewed")
    entries = verify_recursive_tree(data, _sha(row.get("tree_sha")))
    main = entries.get("SKILL.md")
    if (not main or main.get("type") != "blob"
            or main.get("mode") not in ("100644","100755")
            or main.get("sha") != _sha(row.get("skill_md_blob_sha"))):
        raise ValueError("Root SKILL.md pin mismatch")
    nested = sorted(p.rpartition("/")[0] for p,e in entries.items()
                    if p.endswith("/SKILL.md") and e.get("type") == "blob")
    # Never infer ownership of the entire root. Only report scope candidates.
    files, excluded, blocked = [], [], []
    spellings = {}
    total = 0
    for path, entry in sorted(entries.items()):
        if any(path == n or path.startswith(n+"/") for n in nested):
            if entry["type"] != "tree":
                excluded.append({"path":path,"reason":"nested_skill_scope"})
            continue
        reason = None
        try:
            require_windows_filename_safety(path, portable=True)
        except ValueError:
            reason = "nonportable_path"
        key = collision_key(path)
        if key in spellings and spellings[key] != path:
            reason = "case_or_unicode_collision"
        spellings[key] = path
        if reason:
            blocked.append({"path":path,"reason":reason})
            continue
        if entry["type"] == "tree":
            continue
        if is_excluded_path(path) or any(x.casefold() in
                {"source.json","source.json.tmp",".gasl-download-checkpoint.json"} for x in path.split("/")):
            excluded.append({"path":path,"reason":"collector_exclusion_or_reserved_metadata"})
            continue
        size = entry.get("size")
        if entry["mode"] not in ("100644","100755"):
            reason = "nonregular_entry"
        elif type(size) is not int or not 0 <= size <= MAX_FILE_BYTES:
            reason = "invalid_or_oversized_blob"
        if reason:
            blocked.append({"path":path,"reason":reason})
            continue
        total += size
        files.append({"path":path,"mode":entry["mode"],"git_blob_sha":entry["sha"],"bytes":size})
    if len(files)>MAX_FILES or total>MAX_BYTES:
        blocked.append({"path":".","reason":"candidate_inventory_budget_exceeded"})
    # Bind the review to all proposed and omitted paths, not just main file.
    inventory = {"source_record_id":row["source_record_id"],"repository":row["repository"],
                 "commit_sha":row["commit_sha"],"tree_sha":row["tree_sha"],
                 "candidate_files":files,"excluded_entries":excluded,"blocked_entries":blocked,
                 "nested_skill_directories":nested}
    digest = hashlib.sha256(json.dumps(inventory,sort_keys=True,ensure_ascii=False,
                                      separators=(",",":")).encode()).hexdigest()
    return {**inventory,"review_sha256":digest,"candidate_file_count":len(files),
            "candidate_bytes":total,"status":"blocked_inventory" if blocked else "scope_review_required",
            "tree_object_hashes_verified":True,"blob_contents_downloaded":False,
            "package_scope_confirmed":False,"complete_install_package_verified":False,
            "download_approved":False,"installation_or_execution_approved":False}


def inspect_root_skill(source_id, *, root=ROOT):
    rows, _, catalog_digest = _selected(root,[source_id])
    row = rows[0]
    if row.get("source_path") != "SKILL.md" or row.get("snapshot_status") != "verified_commit_pinned":
        raise ValueError("Exact verified root-level Skill required")
    repo = row["repository"].casefold()
    pin, tree = _sha(row.get("commit_sha")), _sha(row.get("tree_sha"))
    _sha(row.get("skill_md_blob_sha"))
    evidence = []
    def fetch(path):
        data, receipt = _get(path)
        evidence.append(receipt)
        return data
    _repo_identity(fetch("/repos/"+repo),repo)
    commit = fetch("/repos/"+repo+"/git/commits/"+pin)
    if commit.get("sha") != pin or not isinstance(commit.get("tree"),dict) or commit["tree"].get("sha") != tree:
        raise ValueError("Pinned commit/tree relationship mismatch")
    report = inspect_inventory(row,fetch("/repos/"+repo+"/git/trees/"+tree+"?recursive=1"))
    if _read_raw(root)[1] != catalog_digest:
        raise ValueError("Catalog changed during root scope review")
    return {"schema":"gasl-root-skill-review-v1","catalog_sha256":catalog_digest,
            "evidence":evidence,**report,
            "limitations":["Candidate root scope only; repository infrastructure or external dependencies may be unrelated.",
                           "Excluded paths are reported, not silently considered complete.",
                           "No blob bytes or legal applicability independently verified."]}
