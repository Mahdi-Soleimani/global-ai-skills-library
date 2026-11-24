"""Compare pinned Skill directory Git trees without downloading blob contents.

Scope is the entire containing upstream directory, including nested Skills.
External licenses, runtime dependencies and install bundles are not equivalent.
"""
import hashlib
import unicodedata
from datetime import datetime, timezone

from canonical_index import _selected, _identity, _read_catalog, ROOT
from canonical_lineage import _get, _sha, _repo_identity
from transaction_file_lock import require_windows_filename_safety

MAX_REQUESTS = 64
MAX_ENTRIES = 12000
MAX_FILES = 300
MAX_DEPTH = 20
MAX_BYTES = 20 * 1024 * 1024
MAX_ONE_FILE = 10 * 1024 * 1024
MODES = {"040000": "tree", "100644": "blob", "100755": "blob",
         "120000": "blob", "160000": "commit"}

# Names are discovery signals only. Neither scope nor legal applicability is inferred.
DEPENDENCY_NAMES = frozenset(("pyproject.toml", "setup.py", "setup.cfg", "pipfile",
    "pipfile.lock", "poetry.lock", "uv.lock", "package.json", "package-lock.json",
    "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb", "cargo.toml", "cargo.lock",
    "go.mod", "go.sum", "gemfile", "gemfile.lock", "composer.json", "composer.lock",
    "pom.xml", "build.gradle", "build.gradle.kts", "dockerfile",
    "environment.yml", "environment.yaml", "conda-lock.yml", ".gitmodules"))


def _context_kind(name):
    name = name.casefold()
    if name.startswith(("license", "licence", "copying", "notice")) or name == "copyright":
        return "license_notice_filename"
    if name in DEPENDENCY_NAMES or (name.startswith("requirements") and name.endswith(".txt")):
        return "dependency_manifest_filename"
    return None


def _context_entry(path, entry, distance):
    kind = _context_kind(path.rsplit("/", 1)[-1])
    if kind is None:
        return None
    return {"source_path": path, "ancestor_distance": distance, "kind": kind,
            "mode": entry["mode"], "git_object_sha": entry["sha"],
            "ordinary_file": entry["mode"] in ("100644", "100755")}



def checked_tree(data, expected):
    """Reconstruct the Git tree object from the complete direct child list."""
    if (not isinstance(data, dict) or data.get("sha") != expected or data.get("truncated") is not False
            or not isinstance(data.get("tree"), list)
            or len(data["tree"]) > MAX_ENTRIES):
        raise ValueError("Incomplete or mismatched Git tree")
    entries = {}
    encoded = []
    for item in data["tree"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid tree entry")
        name, mode, kind = (item.get(k) for k in ("path", "mode", "type"))
        if (not isinstance(name, str) or not name or name in (".", "..")
                or "/" in name or "\0" in name or name in entries
                or not isinstance(mode, str) or MODES.get(mode) != kind):
            raise ValueError("Invalid or duplicate Git tree entry")
        oid = _sha(item.get("sha"))
        name_bytes = name.encode("utf-8")
        encoded.append((name_bytes + (b"/" if kind == "tree" else b""),
                        mode.lstrip("0").encode("ascii") + b" " + name_bytes + b"\0" + bytes.fromhex(oid)))
        entries[name] = item
    raw = b"".join(value for _, value in sorted(encoded))
    actual = hashlib.sha1(b"tree " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    if actual != expected:
        raise ValueError("Git tree object hash mismatch")
    return entries


def compare_packages(ids, *, root=ROOT):
    if (not isinstance(ids, (list, tuple)) or len(ids) != 2
            or any(not isinstance(s, str) for s in ids) or ids[0] == ids[1]):
        raise ValueError("Two distinct exact source IDs required")
    rows, _, digest = _selected(root, ids)
    lk, lb, _ = _identity(rows[0])
    rk, rb, _ = _identity(rows[1])
    if lk[:2] != rk[:2] and (lb is None or lb != rb):
        raise ValueError("Package comparison requires recorded relation candidate")
    evidence, cache = [], {}
    total_entries = 0

    def fetch(path):
        if path not in cache:
            if len(evidence) >= MAX_REQUESTS:
                raise ValueError("Package comparison request budget exceeded")
            data, receipt = _get(path)
            cache[path] = data
            evidence.append(receipt)
        return cache[path]

    def tree(repo, oid):
        nonlocal total_entries
        entries = checked_tree(fetch("/repos/"+repo+"/git/trees/"+oid), oid)
        total_entries += len(entries)
        if total_entries > MAX_ENTRIES:
            raise ValueError("Package comparison entry budget exceeded")
        return entries

    def package(row):
        repo = row["repository"].casefold()
        _repo_identity(fetch("/repos/"+repo), repo)
        pin = row["commit_sha"]
        commit = fetch("/repos/"+repo+"/git/commits/"+pin)
        if commit.get("sha") != pin or not isinstance(commit.get("tree"), dict):
            raise ValueError("Commit pin or tree mismatch")
        root_tree = _sha(commit["tree"].get("sha"))
        if row.get("tree_sha") is not None and row["tree_sha"] != root_tree:
            raise ValueError("Catalog commit tree pin mismatch")
        parts = row["source_path"].split("/")
        if len(parts) > MAX_DEPTH or len(parts) < 2:
            raise ValueError("Root-level or excessively deep Skill package requires review")
        oid = root_tree
        ancestor_context = []
        for depth, part in enumerate(parts[:-1]):
            direct = tree(repo, oid)
            for name, item in sorted(direct.items()):
                path = "/".join(parts[:depth] + [name])
                signal = _context_entry(path, item, len(parts)-1-depth)
                if signal is not None:
                    ancestor_context.append(signal)
                    if len(ancestor_context) > MAX_FILES:
                        raise ValueError("Ancestor context entry budget exceeded")
            entry = direct.get(part)
            if not entry or entry["type"] != "tree":
                raise ValueError("Pinned Skill directory missing")
            oid = entry["sha"]
        folder_tree = oid
        files, seen = [], set()
        total = 0
        def walk(sha, prefix="", depth=0):
            nonlocal total
            if depth > MAX_DEPTH:
                raise ValueError("Package directory depth exceeded")
            for name, entry in sorted(tree(repo, sha).items()):
                path = prefix + name
                require_windows_filename_safety(path, portable=True)
                key = unicodedata.normalize("NFC", path).casefold()
                if key in seen:
                    raise ValueError("Case or Unicode package path collision")
                seen.add(key)
                if entry["type"] == "tree":
                    walk(entry["sha"], path+"/", depth+1)
                    continue
                if entry["mode"] not in ("100644", "100755"):
                    raise ValueError("Symlink or submodule in package; comparison blocked")
                size = entry.get("size")
                if type(size) is not int or not 0 <= size <= MAX_ONE_FILE:
                    raise ValueError("Invalid or oversized package blob")
                total += size
                if len(files) >= MAX_FILES or total > MAX_BYTES:
                    raise ValueError("Package exceeds inventory limits")
                files.append({"path":path, "mode":entry["mode"], "git_blob_sha":entry["sha"],"bytes":size})
        walk(folder_tree)
        main = next((f for f in files if f["path"] == parts[-1]), None)
        if main is None or (row.get("skill_md_blob_sha") is not None
                            and main["git_blob_sha"] != row["skill_md_blob_sha"]):
            raise ValueError("SKILL.md blob does not match pinned record")
        return {"source_record_id":row["source_record_id"],"commit_sha":pin,
                "root_tree_sha":root_tree,"directory_tree_sha":folder_tree,
                "catalog_skill_blob_pin_present":row.get("skill_md_blob_sha") is not None,
                "file_count":len(files),"bytes":total,"files":sorted(files,key=lambda f:f["path"]),
                "catalog_license_spdx":row.get("license_spdx"),
                "ancestor_context_candidates":ancestor_context,
                "directory_context_candidates":[signal for f in sorted(files,key=lambda f:f["path"])
                    if (signal := _context_entry(f["path"], {"mode":f["mode"],"sha":f["git_blob_sha"]},0)) is not None]}

    a,b = [package(row) for row in rows]
    left,right = ({f["path"]:f for f in p["files"]} for p in (a,b))
    same = a["directory_tree_sha"] == b["directory_tree_sha"]
    equal_inventory = left == right
    if same and not equal_inventory:
        raise ValueError("Identical tree hashes with inconsistent file metadata")
    # Context comparison is relative to the Skill directory, never absolute repository path.
    def signature(package, kind):
        return sorted((x["ancestor_distance"], x["source_path"].rsplit("/",1)[-1],
                       x["mode"], x["git_object_sha"])
                      for x in package["ancestor_context_candidates"] if x["kind"] == kind)
    context = {}
    for kind in ("license_notice_filename", "dependency_manifest_filename"):
        sa,sb = signature(a,kind),signature(b,kind)
        context[kind] = {"left_count":len(sa),"right_count":len(sb),
                         "recorded_candidates_equal":sa == sb if sa or sb else None,
                         "status":"filename_and_object_id_evidence_only" if sa or sb else "no_named_candidate_observed"}
    if _read_catalog(root)[1] != digest:
        raise ValueError("Catalog changed during package comparison")
    return {"schema":"gasl-canonical-package-tree-v1","catalog_sha256":digest,
            "observed_at":datetime.now(timezone.utc).isoformat(),"source_record_ids":list(ids),
            "scope":"entire_upstream_skill_directory_including_nested_skills",
            "directory_tree_identity_equal":same,"recorded_file_inventory_equal":equal_inventory,
            "only_left":sorted(left.keys()-right.keys()),"only_right":sorted(right.keys()-left.keys()),
            "changed_files":sorted(p for p in left.keys()&right.keys() if left[p]!=right[p]),
            "packages":[a,b],"evidence":evidence,"git_tree_object_hashes_verified":True,
            "ancestor_context_comparison":context,"license_applicability_verified":False,
            "dependency_resolution_performed":False,
            "blob_contents_downloaded":False,"commit_objects_independently_reconstructed":False,
            "full_install_bundle_equivalence_established":False,"runtime_dependencies_verified":False,
            "source_records_modified":False,"source_records_merged":False,
            "installation_or_execution_approved":False,
            "limitations":["GitHub commit-to-tree mapping is API evidence; tree objects reconstructed from metadata.",
                           "File blob IDs and modes are compared, not independently downloaded bytes.",
                           "Ancestor license/notice and dependency filenames are candidates only, not legal or dependency resolution.",
                           "Outside-directory references, transitive dependencies and install eligibility are not verified."]}
