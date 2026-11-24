#!/usr/bin/env python3
"""Phase 50: deterministic *private* GASL MVP release draft and publication gate.

No public GitHub Release, package registry upload, or license grant is made.
Only a strict tracked-file allowlist enters an ignored local ZIP.
"""
import hashlib
import io
import json
import os
import re
import subprocess
import stat
import zipfile
from pathlib import Path

from skill_search import ROOT
from transaction_file_lock import is_redirected, require_windows_filename_safety

SCHEMA = "gasl-private-release-draft-v1"
CANONICAL_ENCODING = "zip-stored-fixed-metadata-v1"
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
MAX_MANIFEST_BYTES = 256 * 1024
MAX_ARCHIVE_BYTES = MAX_TOTAL_BYTES + 2 * 1024 * 1024
ZIP_STAMP = (1980, 1, 1, 0, 0, 0)
SHA = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            + "\n").encode("utf-8")


def _git(root, *args):
    return subprocess.check_output(["git", "--no-replace-objects", "-C", str(root), *args])


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


def _safe_path(root, path, *, directory=False):
    """Reject redirected path components without following arbitrary links."""
    relative = path.relative_to(root)
    current = root
    for part in relative.parts:
        current = current / part
        if is_redirected(current):
            raise ValueError("Symlink or redirected release path is unsafe")
    if os.name == "nt":
        from windows_user_profile import assert_no_reparse_components
        assert_no_reparse_components(path)
    if directory and path.exists() and not path.is_dir():
        raise ValueError("Unsafe local private release path")


def _regular_bytes(root, path, maximum):
    _safe_path(root, path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > maximum:
        raise ValueError("Unsafe or oversized release record")
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("Oversized release record")
    return data


def _unique_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate release JSON key")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs)


def _licenses(items):
    # Author-provided files only; presence is not a legal determination.
    return [name for name in ("LICENSE", "LICENSE.md", "COPYING")
            if any(item["path"] == name and 0 < item["bytes"] <= 100000
                   for item in items)]


def _inputs(root):
    root = Path(root).resolve(strict=True)
    if not (root/".git").exists() or is_redirected(root/".git"):
        raise ValueError("An existing Git project root is required")
    commit = _git(root, "rev-parse", "HEAD").decode().strip()
    if not GIT_SHA.fullmatch(commit):
        raise ValueError("Current Git commit is not a complete SHA")
    # Read the immutable tree, not bytes from a possibly filtered, modified
    # or assume-unchanged worktree. Git index remains an independent allowlist.
    tree = {}
    for raw in _git(root, "ls-tree", "-r", "-l", "-z", "--full-tree", commit).split(b"\x00"):
        if not raw:
            continue
        header, raw_name = raw.split(b"\t", 1)
        name = raw_name.decode("utf-8")
        if not _included(name):
            continue
        mode, kind, oid, size = header.decode("ascii").split()
        if (mode not in ("100644", "100755") or kind != "blob"
                or not GIT_SHA.fullmatch(oid) or not size.isdigit()):
            raise ValueError("Symlink or non-regular committed release entry")
        require_windows_filename_safety(name, portable=True)
        if name in tree:
            raise ValueError("Duplicate release tree path")
        tree[name] = (oid, int(size))
    files = sorted(tree)
    if not STATIC_FILES.issubset(files):
        raise ValueError("Required runtime/review files not tracked: " +
                         ", ".join(sorted(STATIC_FILES-set(files))))
    if set(files) != {name for name in _tracked(root) if _included(name)}:
        raise ValueError("Release index differs from committed source tree")
    if not 1 <= len(files) <= MAX_FILES or sum(size for _, size in tree.values()) > MAX_TOTAL_BYTES:
        raise ValueError("Release draft exceeds source limits")
    result = []
    for name in files:
        file = root/name
        _safe_path(root, file)
        if not file.is_file():
            raise ValueError("Missing or unsafe tracked release file")
        oid, size = tree[name]
        data = _git(root, "cat-file", "blob", oid)
        if (len(data) != size or hashlib.sha1(b"blob " + str(size).encode("ascii") + b"\0" + data).hexdigest() != oid):
            raise ValueError("Committed release blob identity mismatch")
        result.append({"path": name, "bytes": size,
                       "sha256": hashlib.sha256(data).hexdigest()})
    return root, files, result, commit


def inspect_release(root=ROOT):
    """Read-only readiness report; does not grant a license or build artifacts."""
    root, files, items, commit = _inputs(root)
    licenses = _licenses(items)
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
        "content_bound_to_commit_tree": True,
        "third_party_skill_executed": False,
        "host_paths_modified": False,
    }


def _zip_entry(name, data, mode=0o100644):
    info = zipfile.ZipInfo("gasl-mvp/" + name, date_time=ZIP_STAMP)
    # Stored ZIP avoids platform-dependent zlib versions/compression choices.
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = mode << 16
    info.create_system = 3
    return info, data


def build_release_draft(root=ROOT):
    """Create a local ignored ZIP only; block dirty/unsafe/untracked input."""
    root, files, items, commit = _inputs(root)
    _clean(root)
    result = inspect_release(root)
    if result["source_commit"] != commit:
        raise ValueError("HEAD changed during release inspection")
    release = root/"private"/"release-drafts"
    for parent in (root/"private", release):
        _safe_path(root, parent, directory=True)
    if not (root/"private").exists():
        (root/"private").mkdir(mode=0o700)
    if not release.exists():
        release.mkdir(mode=0o700)
    filename = "gasl-mvp-" + commit[:12] + ".zip"
    target = release/filename
    sidecar = release/(filename+".json")
    if target.exists() or is_redirected(target) or sidecar.exists() or is_redirected(sidecar):
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
    created = []
    try:
        with target.open("xb") as stream:
            created.append((target, os.fstat(stream.fileno())))
            with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_STORED) as archive:
                for entry in items:
                    data = _git(root, "show", commit + ":" + entry["path"])
                    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                        raise ValueError("Release source changed after manifest inspection")
                    mode = 0o100755 if entry["path"] == "gasl" else 0o100644
                    info, raw = _zip_entry(entry["path"], data, mode)
                    archive.writestr(info, raw)
                info, raw = _zip_entry("RELEASE-MANIFEST.json", _json_bytes(manifest))
                archive.writestr(info, raw)
        if _git(root, "rev-parse", "HEAD").decode().strip() != commit:
            raise ValueError("HEAD changed during private draft build")
        _clean(root)
        digest = hashlib.sha256(_regular_bytes(root, target, MAX_ARCHIVE_BYTES)).hexdigest()
        with sidecar.open("xb") as stream:
            created.append((sidecar, os.fstat(stream.fileno())))
            stream.write(_json_bytes({"schema": SCHEMA, "filename": filename,
                                      "sha256": digest,
                                      "source_commit": commit,
                                      "public_release_allowed": False}))
        completed = True
    finally:
        if not completed:
            # Only paths this invocation exclusively created are eligible.
            for path, identity in reversed(created):
                _safe_path(root, path)
                if path.exists() and not is_redirected(path):
                    info = path.stat()
                    if info.st_nlink == 1 and stat.S_ISREG(info.st_mode) and os.path.samestat(identity, info):
                        path.unlink()
    return {
        "status": "private_mvp_draft_created",
        "relative_archive": target.relative_to(root).as_posix(),
        "archive_sha256": digest, "source_commit": commit,
        "included_tracked_files": len(items),
        "archive_encoding": CANONICAL_ENCODING,
        "public_release_allowed": False,
        "license_missing": not result["project_license_declared"],
        "host_paths_modified": False,
        "third_party_skill_executed": False,
    }


def verify_release_draft(root=ROOT):
    """Verify only the known local draft for the current HEAD; do not unzip."""
    root, _, expected_items, commit = _inputs(root)
    filename = "gasl-mvp-" + commit[:12] + ".zip"
    release = root/"private"/"release-drafts"
    path = release/filename
    meta_path = release/(filename+".json")
    _safe_path(root, release, directory=True)
    meta = _unique_json(_regular_bytes(root, meta_path, 16384))
    if (not isinstance(meta, dict) or set(meta) != {"schema", "filename", "sha256", "source_commit", "public_release_allowed"}
            or meta.get("schema") != SCHEMA or meta.get("filename") != filename
            or meta.get("source_commit") != commit
            or meta.get("public_release_allowed") is not False):
        raise ValueError("Draft metadata is invalid")
    raw = _regular_bytes(root, path, MAX_ARCHIVE_BYTES)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != meta.get("sha256") or not SHA.fullmatch(digest):
        raise ValueError("Private draft ZIP SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
        infos = archive.infolist()
        names = [x.filename for x in infos]
        if len(names) != len(set(names)) or not names or len(names) > MAX_FILES + 1:
            raise ValueError("Unexpected draft archive entries")
        manifest_name = "gasl-mvp/RELEASE-MANIFEST.json"
        if names[-1] != manifest_name or any(not n.startswith("gasl-mvp/") for n in names):
            raise ValueError("Invalid release ZIP layout")
        if (infos[-1].file_size > MAX_MANIFEST_BYTES or
                sum(x.file_size for x in infos[:-1]) > MAX_TOTAL_BYTES or
                any(x.flag_bits & 1 or x.is_dir() for x in infos)):
            raise ValueError("Unexpected or oversized draft archive member")
        manifest = _unique_json(archive.read(manifest_name))
        if (not isinstance(manifest, dict) or set(manifest) != {"schema", "source_commit", "files", "artifact", "public_release_allowed", "project_license_files", "warnings", "third_party_code_executed"}
                or manifest.get("schema") != SCHEMA or manifest.get("source_commit") != commit
                or manifest.get("public_release_allowed") is not False
                or manifest.get("third_party_code_executed") is not False
                or manifest.get("artifact") != "private_draft_not_public_release"
                or manifest.get("project_license_files") != _licenses(expected_items)):
            raise ValueError("Untrusted draft manifest")
        items = manifest.get("files")
        if not isinstance(items, list) or not items or len(items) != len(names)-1:
            raise ValueError("Draft inventory missing")
        if items != expected_items:
            raise ValueError("Draft inventory differs from committed source tree")
        if names[:-1] != ["gasl-mvp/" + x["path"] for x in items]:
            raise ValueError("Draft paths disagree with manifest")
        if infos[-1].external_attr >> 16 != 0o100644:
            raise ValueError("Unexpected draft manifest member type")
        # Independently recreate the fixed encoding from verified member bytes.
        # Old compressed drafts can still be verified for content integrity,
        # but must not be labelled byte-reproducible in the new format.
        canonical = io.BytesIO()
        with zipfile.ZipFile(canonical, "w", compression=zipfile.ZIP_STORED) as rebuilt:
            _verify_and_encode_members(archive, rebuilt, items, infos, manifest, manifest_name)
        canonical_match = hashlib.sha256(canonical.getbuffer()).hexdigest() == digest
    if _git(root, "rev-parse", "HEAD").decode().strip() != commit:
        raise ValueError("HEAD changed during draft verification")
    return {
        "status": "private_mvp_draft_verified",
        "archive_sha256": digest,
        "source_commit": commit,
        "verified_file_count": len(items),
        "content_bound_to_commit_tree": True,
        "canonical_archive_encoding_verified": canonical_match,
        "archive_encoding": CANONICAL_ENCODING if canonical_match else "noncanonical_content_verified",
        "public_release_allowed": False,
        "files_extracted": False,
        "third_party_skill_executed": False,
    }


def _verify_and_encode_members(archive, rebuilt, items, infos, manifest, manifest_name):
    total = 0
    for item, info in zip(items, infos[:-1]):
        expected_mode = 0o100755 if item["path"] == "gasl" else 0o100644
        if info.file_size != item["bytes"] or info.external_attr >> 16 != expected_mode:
            raise ValueError("Unexpected draft member size or type")
        actual = archive.read("gasl-mvp/"+item["path"])
        total += len(actual)
        if (total > MAX_TOTAL_BYTES or len(actual) != item["bytes"]
                or hashlib.sha256(actual).hexdigest() != item["sha256"]):
            raise ValueError("Draft content/inventory altered")
        encoded, content = _zip_entry(item["path"], actual, expected_mode)
        rebuilt.writestr(encoded, content)
    info, content = _zip_entry("RELEASE-MANIFEST.json", _json_bytes(manifest))
    rebuilt.writestr(info, content)
