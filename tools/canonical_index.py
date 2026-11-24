"""Read-only evidence index of locally recorded Skill identities.

Equal recorded Git blob IDs are not independent content verification, package
equivalence, publisher identity, permission, or a basis for merging records.
"""
import copy
import hashlib
import threading
import json
import urllib.error
import urllib.request
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHA1 = re.compile(r"[0-9a-f]{40}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
MAX_CATALOG_BYTES = 64 * 1024 * 1024
MAX_RECORDS = 100_000
MAX_CACHED_CATALOG_BYTES = 16 * 1024 * 1024
_snapshot_lock = threading.Lock()
_snapshot_cache = None


def _identity(row):
    if not isinstance(row, dict):
        raise ValueError("Invalid catalog record")
    repo, path, commit, blob = (row.get(k) for k in (
        "repository", "source_path", "commit_sha", "skill_md_blob_sha"))
    if (not isinstance(repo, str) or not REPO.fullmatch(repo)
            or any(part in (".", "..") for part in repo.split("/"))):
        raise ValueError("Invalid repository identity")
    if (not isinstance(path, str) or len(path) > 4096 or "\\" in path
            or any(ord(c) < 32 for c in path)
            or any(part in ("", ".", "..") for part in path.split("/"))
            or path.split("/")[-1].casefold() != "skill.md"):
        raise ValueError("Invalid Skill path")
    if not isinstance(commit, str) or not SHA1.fullmatch(commit):
        raise ValueError("Invalid commit pin")
    if blob is not None and (not isinstance(blob, str) or not SHA1.fullmatch(blob)):
        raise ValueError("Invalid recorded Git blob")
    key = (repo.casefold(), path, commit)
    expected = "GASL-SRC-" + hashlib.sha256("\0".join(key).encode("utf-8")).hexdigest()[:20]
    if row.get("source_record_id") != expected:
        raise ValueError("Source ID does not match immutable identity")
    return key, blob, expected


def build_index(records):
    if not isinstance(records, list) or not 0 < len(records) <= MAX_RECORDS:
        raise ValueError("Invalid catalog record count")
    seen = set()
    seen_ids = set()
    by_blob, by_path = defaultdict(list), defaultdict(list)
    missing = []
    for row in records:
        key, blob, sid = _identity(row)
        if key in seen:
            raise ValueError("Duplicate immutable catalog identity")
        if sid in seen_ids:
            raise ValueError("Duplicate source record ID")
        seen.add(key)
        seen_ids.add(sid)
        member = {"source_record_id": sid, "repository": row["repository"],
                  "source_path": key[1], "commit_sha": key[2], "git_blob_sha": blob}
        by_path[key[:2]].append(member)
        if blob is None:
            missing.append(sid)
        else:
            by_blob[blob].append(member)
    groups = [{"relationship": "same_recorded_skill_md_blob",
               "git_blob_sha": blob,
               "members": sorted(members, key=lambda x: x["source_record_id"]),
               "decision": "candidate_only_no_merge"}
              for blob, members in sorted(by_blob.items()) if len(members) > 1]
    paths = []
    for (repo, path), members in sorted(by_path.items()):
        if len(members) < 2:
            continue
        blobs = {m["git_blob_sha"] for m in members}
        status = ("incomplete_blob_evidence" if None in blobs else
                  "same_recorded_blob" if len(blobs) == 1 else "different_recorded_blobs")
        paths.append({"relationship": "same_path_multiple_revisions", "repository": repo,
                      "source_path": path, "blob_comparison": status,
                      "members": sorted(members, key=lambda x: x["source_record_id"]),
                      "decision": "candidate_only_no_merge"})
    return {"schema": "gasl-canonical-evidence-v1", "source_record_count": len(records),
            "distinct_repository_paths": len(by_path),
            "records_without_blob_evidence": sorted(missing),
            "recorded_blob_group_count": len(groups),
            "recorded_blob_group_member_count": sum(len(g["members"]) for g in groups),
            "path_revision_group_count": len(paths),
            "recorded_blob_groups": groups, "path_revision_groups": paths,
            "source_records_modified": False, "source_records_merged": False,
            "independent_content_verification_performed": False,
            "package_equivalence_established": False, "ancestry_established": False,
            "installation_or_execution_approved": False,
            "limitations": ["Local recorded Git blob equality only; no content bytes fetched.",
                            "No same_as, fork_of, mirror_of, supersedes or conflicts_with asserted.",
                            "No globally unique Skill count inferred. Missing blob evidence remains unknown."]}


def _read_raw(root):
    path = Path(root) / "registry" / "source-catalog.json"
    with path.open("rb") as stream:
        raw = stream.read(MAX_CATALOG_BYTES + 1)
    if len(raw) > MAX_CATALOG_BYTES:
        raise ValueError("Catalog exceeds read limit")
    return raw, hashlib.sha256(raw).hexdigest()


def _parse_catalog(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key in catalog")
            result[key] = value
        return result
    data = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(data, dict) or data.get("schema_version") != "1.0.0":
        raise ValueError("Unsupported catalog schema")
    return data.get("records")


def _read_catalog(root):
    raw, digest = _read_raw(root)
    return _parse_catalog(raw), digest


def _snapshot(root):
    """One bounded in-memory snapshot, keyed by the exact bytes, never mtime."""
    global _snapshot_cache
    raw, digest = _read_raw(root)
    with _snapshot_lock:
        if _snapshot_cache is not None and _snapshot_cache[0] == digest:
            return _snapshot_cache[1]
        records = _parse_catalog(raw)
        index = build_index(records)
        by_id = {r["source_record_id"]: r for r in records}
        related = defaultdict(list)
        for field in ("recorded_blob_groups", "path_revision_groups"):
            for group in index[field]:
                for member in group["members"]:
                    related[member["source_record_id"]].append(group)
        result = (by_id, index, related, digest)
        _snapshot_cache = (digest, result) if len(raw) <= MAX_CACHED_CATALOG_BYTES else None
        return result


def inspect(root=ROOT):
    _, index, _, digest = _snapshot(root)
    result = copy.deepcopy(index)
    result["catalog_sha256"] = digest
    return result


def _selected(root, ids):
    by_id, index, _, digest = _snapshot(root)
    if any(sid not in by_id for sid in ids):
        raise ValueError("Unknown exact source record ID")
    return [copy.deepcopy(by_id[sid]) for sid in ids], copy.deepcopy(index), digest


def comparison_evidence(items, *, root=ROOT):
    """One exact catalog snapshot for all selected pairs, never network access."""
    by_id, _, _, digest = _snapshot(root)
    rows = []
    for item in items:
        row = by_id.get(item["source_record_id"])
        if row is None or any(row.get(k) != item.get(k) for k in
                              ("repository", "source_path", "commit_sha")):
            raise ValueError("Comparison identity does not match canonical snapshot")
        rows.append(_identity(row))
    pairs = []
    for i, (lk, lb, lid) in enumerate(rows):
        for rk, rb, rid in rows[i+1:]:
            pairs.append({"source_record_ids":[lid,rid], "same_repository_path":lk[:2]==rk[:2],
                          "blob_comparison":("incomplete_blob_evidence" if None in (lb,rb) else
                              "same_recorded_blob" if lb==rb else "different_recorded_blobs")})
    return {"status":"recorded_catalog_evidence_only", "catalog_sha256":digest,
            "pairs":pairs, "package_equivalence_established":False,
            "ancestry_established":False, "installation_or_execution_approved":False}


def lookup(source_id, *, root=ROOT):
    by_id, _, groups, digest = _snapshot(root)
    if source_id not in by_id:
        raise ValueError("Unknown exact source record ID")
    row = by_id[source_id]
    key, blob, sid = _identity(row)
    related = copy.deepcopy(groups.get(sid, []))
    return {"schema": "gasl-canonical-lookup-v1", "catalog_sha256": digest,
            "source_record_id": sid, "repository": row["repository"],
            "source_path": key[1], "commit_sha": key[2], "git_blob_sha": blob,
            "related_groups": related,
            "independent_content_verification_performed": False,
            "package_equivalence_established": False, "ancestry_established": False,
            "installation_or_execution_approved": False}


def _fetch_verified(row):
    from gasl_service import _pinned_raw_url, verify_skill_blob, MAX_SKILL_BYTES
    from safe_http import open_pinned_url
    url = _pinned_raw_url(row)
    request = urllib.request.Request(url, headers={"Accept": "text/plain", "User-Agent": "GASL/0.1"})
    try:
        with open_pinned_url(request, timeout=20) as response:
            if response.geturl() != url:
                raise ValueError("Pinned raw URL changed")
            raw = response.read(MAX_SKILL_BYTES + 1)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError("Pinned source retrieval unavailable") from exc
    if len(raw) > MAX_SKILL_BYTES:
        raise ValueError("Pinned Skill exceeds size limit")
    verify_skill_blob(raw, row)
    return raw


def compare(source_ids, *, root=ROOT, verify_online=False):
    if (not isinstance(source_ids, (list, tuple)) or len(source_ids) != 2
            or any(not isinstance(x, str) for x in source_ids)
            or source_ids[0] == source_ids[1]):
        raise ValueError("Two distinct exact source IDs required")
    rows, _, digest = _selected(root, source_ids)
    left, right = rows
    lk, lb, _ = _identity(left)
    rk, rb, _ = _identity(right)
    same_path = lk[:2] == rk[:2]
    recorded = ("incomplete_blob_evidence" if None in (lb, rb) else
                "same_recorded_blob" if lb == rb else "different_recorded_blobs")
    report = {"schema": "gasl-canonical-pair-v1", "catalog_sha256": digest,
              "source_record_ids": list(source_ids), "same_repository_path": same_path,
              "blob_comparison": recorded, "upstream_blob_verification_performed": False,
              "skill_md_bytes_equal": None, "verified_sources": [],
              "package_equivalence_established": False, "ancestry_established": False,
              "publisher_identity_independently_verified": False,
              "source_records_modified": False, "source_records_merged": False,
              "installation_or_execution_approved": False}
    if verify_online:
        if None in (lb, rb):
            raise ValueError("Both recorded Git blob pins are required for online verification")
        if not same_path and lb != rb:
            raise ValueError("Online verification requires a recorded relation candidate")
        # Fetch both independently; never save or return instruction text.
        raw_left, raw_right = _fetch_verified(left), _fetch_verified(right)
        _, current_digest = _read_catalog(root)
        if current_digest != digest:
            raise ValueError("Catalog changed during verification; repeat inspection")
        report["upstream_blob_verification_performed"] = True
        report["skill_md_bytes_equal"] = raw_left == raw_right
        report["verified_sources"] = [
            {"source_record_id": row["source_record_id"], "commit_sha": row["commit_sha"],
             "git_blob_sha": row["skill_md_blob_sha"], "sha256": hashlib.sha256(raw).hexdigest(),
             "bytes": len(raw)} for row, raw in zip(rows, (raw_left, raw_right))]
    return report
