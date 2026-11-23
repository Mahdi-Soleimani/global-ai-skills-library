#!/usr/bin/env python3
"""Phase 50: deterministic *private* GASL MVP release draft and publication gate.

No public GitHub Release, package registry upload, or license grant is made.
Only a strict tracked-file allowlist enters an ignored local ZIP.
"""
import hashlib
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path

from skill_search import ROOT

SCHEMA = "gasl-private-release-draft-v1"
STATIC_FILES = frozenset({
    "gasl", "README.md", "ATTRIBUTION.md", "THIRD_PARTY_NOTICES.md",
    "docs/ATTRIBUTION-AND-REDISTRIBUTION-POLICY.md",
    "docs/ROADMAP.md", "web/index.html",
    "registry/source-catalog.json", "registry/search-features.json",
    "registry/skill-evaluations.json", "registry/source-catalog-summary.json",
    "public-catalog/index.json",
})
MAX_FILES = 160
MAX_TOTAL_BYTES = 55 * 1024 * 1024
ZIP_STAMP = (1980, 1, 1, 0, 0, 0)
SHA = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            + "\n").encode("utf-8")


def _git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def _tracked(root):
    raw = _git(root, "ls-files", "-z")
    paths = [s.decode("utf-8") for s in raw.split(b"\x00") if s]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate Git index entries")
    return paths


def _included(path):
    return (path in STATIC_FILES
            or path in ("LICENSE", "LICENSE.md", "COPYING")
            or (path.startswith("tools/") and path.endswith(".py") and
                len(Path(path).parts) == 2)
            or (path.startswith("config/") and path.endswith(".json") and
                len(Path(path).parts) == 2))


def _clean(root):
    if _git(root, "status", "--porcelain", "--untracked-files=no").strip():
        raise ValueError("Refuse to package a Git tree with uncommitted tracked changes")


def _license(root, tracked):
    # A present license is only an explicit author-supplied publication signal,
    # never a legal/compliance determination or grant for third-party Skills.
    candidates = ("LICENSE", "LICENSE.md", "COPYING")
    files = [root / name for name in candidates if name in tracked]
    return [path.name for path in files if path.is_file() and not path.is_symlink()
            and 0 < path.stat().st_size <= 100000]


def _inputs(root):
    root = Path(root).resolve(strict=True)
    if not (root/".git").exists():
        raise ValueError("An existing Git project root is required")
    files = sorted(x for x in _tracked(root) if _included(x))
    if not STATIC_FILES.issubset(files):
        missing = sorted(STATIC_FILES-set(files))
        raise ValueError("Required runtime/review files not tracked: " + ", ".join(missing))
    if not 1 <= len(files) <= MAX_FILES:
        raise ValueError("Unexpected release file count")
    total = 0
    result = []
    for name in files:
        file = root/name
        if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(root):
            raise ValueError("Symlink, missing or escaping release file: " + name)
        data = file.read_bytes()
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Release draft exceeds maximum uncompressed bytes")
        result.append({"path": name, "bytes": len(data),
                       "sha256": hashlib.sha256(data).hexdigest()})
    commit = _git(root, "rev-parse", "HEAD").decode().strip()
    if not GIT_SHA.fullmatch(commit):
        raise ValueError("Current Git commit is not a complete SHA")
    return root, files, result, commit


def inspect_release(root=ROOT):
    """Read-only readiness report; does not grant a license or build artifacts."""
    root, files, items, commit = _inputs(root)
    licenses = _license(root, set(_tracked(root)))
    return {
        "schema": SCHEMA,
        "status": "local_release_readiness_only",
        "source_commit": commit,
        "tracked_package_files": len(files),
        "tracked_package_uncompressed_bytes": sum(x["bytes"] for x in items),
        "project_license_files": licenses,
        "project_license_declared": bool(licenses),
        "public_release_allowed": False,
        "public_release_blockers": (
            ["project_license_not_selected",
             "host_scope_other_than_codex_project_unverified",
             "public_redistribution_requires_independent_review"]
            if not licenses else
            ["host_scope_other_than_codex_project_unverified",
             "public_redistribution_requires_independent_review"]
        ),
        "private_artifact_only": True,
        "all_files_from_git_index": True,
        "third_party_skill_executed": False,
        "host_paths_modified": False,
    }


def _zip_entry(name, data, mode=0o100644):
    info = zipfile.ZipInfo("gasl-mvp/" + name, date_time=ZIP_STAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = mode << 16
    info.create_system = 3
    return info, data


def build_release_draft(root=ROOT):
    """Create a local ignored ZIP only; block dirty/unsafe/untracked input."""
    root, files, items, commit = _inputs(root)
    _clean(root)
    result = inspect_release(root)
    release = root/"private"/"release-drafts"
    for parent in (root/"private", release):
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ValueError("Unsafe local private release path")
    if not (root/"private").exists():
        (root/"private").mkdir(mode=0o700)
    if not release.exists():
        release.mkdir(mode=0o700)
    filename = "gasl-mvp-" + commit[:12] + ".zip"
    target = release/filename
    sidecar = release/(filename+".json")
    if target.exists() or target.is_symlink() or sidecar.exists() or sidecar.is_symlink():
        raise ValueError("Draft already exists; refusing overwrite")
    manifest = {
        "schema": SCHEMA,
        "source_commit": commit,
        "files": items,
        "artifact": "private_draft_not_public_release",
        "public_release_allowed": False,
        "project_license_files": result["project_license_files"],
        "warnings": result["public_release_blockers"],
        "third_party_code_executed": False,
    }
    completed = False
    try:
        with target.open("xb") as stream:
            with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_DEFLATED,
                                 compresslevel=8) as archive:
                for entry in items:
                    path = root/entry["path"]
                    data = path.read_bytes()
                    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                        raise ValueError("Release source changed after manifest inspection")
                    mode = 0o100755 if entry["path"] == "gasl" else 0o100644
                    info, raw = _zip_entry(entry["path"], data, mode)
                    archive.writestr(info, raw)
                info, raw = _zip_entry("RELEASE-MANIFEST.json", _json_bytes(manifest))
                archive.writestr(info, raw)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        with sidecar.open("xb") as stream:
            stream.write(_json_bytes({"schema": SCHEMA, "filename": filename,
                                      "sha256": digest,
                                      "source_commit": commit,
                                      "public_release_allowed": False}))
        completed = True
    finally:
        if not completed:
            if target.exists(): target.unlink()
            if sidecar.exists(): sidecar.unlink()
    return {
        "status": "private_mvp_draft_created",
        "relative_archive": target.relative_to(root).as_posix(),
        "archive_sha256": digest, "source_commit": commit,
        "included_tracked_files": len(items),
        "public_release_allowed": False,
        "license_missing": not result["project_license_declared"],
        "host_paths_modified": False,
        "third_party_skill_executed": False,
    }


def verify_release_draft(root=ROOT):
    """Verify only the known local draft for the current HEAD; do not unzip."""
    root, _, _, commit = _inputs(root)
    filename = "gasl-mvp-" + commit[:12] + ".zip"
    release = root/"private"/"release-drafts"
    path = release/filename
    meta_path = release/(filename+".json")
    if any(p.is_symlink() for p in (release, path, meta_path)):
        raise ValueError("Symlinked draft path is unsafe")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if (meta.get("schema") != SCHEMA or meta.get("filename") != filename
            or meta.get("source_commit") != commit
            or meta.get("public_release_allowed") is not False):
        raise ValueError("Draft metadata is invalid")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != meta.get("sha256") or not SHA.fullmatch(digest):
        raise ValueError("Private draft ZIP SHA-256 mismatch")
    with zipfile.ZipFile(path, "r") as archive:
        names = [x.filename for x in archive.infolist()]
        if len(names) != len(set(names)) or not names or len(names) > MAX_FILES + 1:
            raise ValueError("Unexpected draft archive entries")
        manifest_name = "gasl-mvp/RELEASE-MANIFEST.json"
        if names[-1] != manifest_name or any(not n.startswith("gasl-mvp/") for n in names):
            raise ValueError("Invalid release ZIP layout")
        manifest = json.loads(archive.read(manifest_name))
        if (manifest.get("schema") != SCHEMA or manifest.get("source_commit") != commit
                or manifest.get("public_release_allowed") is not False):
            raise ValueError("Untrusted draft manifest")
        items = manifest.get("files")
        if not isinstance(items, list) or not items or len(items) != len(names)-1:
            raise ValueError("Draft inventory missing")
        if names[:-1] != ["gasl-mvp/" + x["path"] for x in items]:
            raise ValueError("Draft paths disagree with manifest")
        total = 0
        for item in items:
            actual = archive.read("gasl-mvp/"+item["path"])
            total += len(actual)
            if total > MAX_TOTAL_BYTES or len(actual) != item["bytes"] or \
                    hashlib.sha256(actual).hexdigest() != item["sha256"]:
                raise ValueError("Draft content/inventory altered")
    return {
        "status": "private_mvp_draft_verified",
        "archive_sha256": digest,
        "source_commit": commit,
        "verified_file_count": len(items),
        "public_release_allowed": False,
        "files_extracted": False,
        "third_party_skill_executed": False,
    }
