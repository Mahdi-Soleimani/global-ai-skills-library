#!/usr/bin/env python3
"""Mirror only packages with an identified redistribution license and bundled license evidence."""
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public-catalog"


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def package_id(meta):
    identity = "\0".join((meta["repository"].casefold(), meta["source_skill_path"], meta["commit_sha"]))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def safe_copy(source, target):
    if source.is_symlink() or not source.is_file():
        raise ValueError("Public catalog accepts regular files only")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def validate_public_package(folder, files):
    expected = {item["path"] for item in files} | {"ATTRIBUTION.md", "ATTRIBUTION.json"}
    actual = set()
    for path in folder.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlink found in public package")
        if path.is_file():
            actual.add(path.relative_to(folder).as_posix())
    if expected != actual:
        raise ValueError("Public package inventory mismatch")
    for item in files:
        path = folder / item["path"]
        if path.stat().st_size != item["size_bytes"] or sha256(path) != item["sha256"]:
            raise ValueError("Public package integrity mismatch")


def build(root=ROOT):
    policy = read(root / "config/policy.json")
    allowlist = set(policy.get("public_mirror_spdx_allowlist", []))
    packages = sorted((root / "catalog").glob("**/source.json"))
    public = root / "public-catalog"
    public.mkdir(parents=True, exist_ok=True)
    (public / "packages").mkdir(parents=True, exist_ok=True)
    index_path = public / "index.json"
    index = read(index_path, {"schema_version": "1.0.0", "updated_at": now(), "packages": {}})
    if index.get("schema_version") != "1.0.0" or not isinstance(index.get("packages"), dict):
        raise ValueError("Public catalog index schema mismatch")
    published, skipped = [], []
    for source_path in packages:
        meta = read(source_path)
        spdx = meta.get("license_spdx")
        evidence = meta.get("license_evidence") or []
        if spdx not in allowlist:
            skipped.append({"repository": meta.get("repository"), "skill_path": meta.get("source_skill_path"),
                            "reason": "license_not_on_public_mirror_allowlist"})
            continue
        if not evidence or meta.get("license_status") != "license_evidence_bundled_pending_scan":
            skipped.append({"repository": meta.get("repository"), "skill_path": meta.get("source_skill_path"),
                            "reason": "applicable_license_evidence_not_bundled"})
            continue
        if meta.get("execution_performed") is not False or meta.get("package_complete") is not True:
            skipped.append({"repository": meta.get("repository"), "skill_path": meta.get("source_skill_path"),
                            "reason": "package_incomplete_or_execution_flagged"})
            continue
        if not meta.get("last_static_scan_at"):
            skipped.append({"repository": meta.get("repository"), "skill_path": meta.get("source_skill_path"),
                            "reason": "static_scan_not_completed"})
            continue
        if not meta.get("commit_sha") or not meta.get("tree_sha"):
            skipped.append({"repository": meta.get("repository"), "skill_path": meta.get("source_skill_path"),
                            "reason": "source_revision_not_pinned"})
            continue
        pid = package_id(meta)
        dest = public / "packages" / pid
        files = []
        for item in meta.get("files", []):
            rel = item.get("package_relative_path")
            if not rel or rel.startswith("/") or any(x in ("", ".", "..") for x in rel.split("/")):
                raise ValueError("Unsafe package-relative path in source metadata")
            src = root / item["local_path"]
            files.append({"path": rel, "size_bytes": item["size_bytes"],
                          "sha256": item["sha256"], "git_blob_sha": item["git_blob_sha"]})
            if not src.is_file() or src.is_symlink() or src.stat().st_size != item["size_bytes"] or sha256(src) != item["sha256"]:
                raise ValueError("Local package integrity check failed before public mirror")
        files.sort(key=lambda x: x["path"])
        license_evidence_paths = {x.get("package_path") for x in evidence}
        if not license_evidence_paths.issubset({x["path"] for x in files}):
            raise ValueError("License evidence missing from package inventory")
        source_url = meta.get("source_url") or "https://github.com/{}/blob/{}/{}".format(
            meta["repository"], meta["commit_sha"], meta["source_skill_path"])
        attribution = {
            "package_id": pid,
            "skill_name": meta.get("skill_name"),
            "repository": meta["repository"],
            "repository_owner": meta.get("repository_owner") or meta["repository"].split("/")[0],
            "repository_url": meta.get("repository_url"),
            "source_skill_path": meta["source_skill_path"],
            "source_url": source_url,
            "commit_sha": meta["commit_sha"],
            "tree_sha": meta["tree_sha"],
            "skill_md_blob_sha": meta.get("skill_md_blob_sha"),
            "license_spdx": spdx,
            "license_name": meta.get("license_name"),
            "license_url": meta.get("license_url"),
            "license_evidence": evidence,
            "license_assessment": "repository-level license signal plus bundled applicable license/notice files; individual file exceptions are not independently adjudicated",
            "ownership": "third_party",
            "original_author": meta.get("original_author"),
            "gasl_claims_exclusive_ownership": False,
            "attribution_notice": meta.get("attribution_notice") or
                "Third-party work. Original rights remain with upstream authors/rightsholders. GASL does not claim exclusive ownership.",
            "execution_performed": False,
            "install_status": "not_approved",
            "files": files
        }
        attribution_json = json.dumps(attribution, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        attribution_md = (
            "# Third-party skill attribution\n\n"
            + "- Skill: " + str(meta.get("skill_name") or pid) + "\n"
            + "- Original repository: " + str(meta["repository"]) + " (" + str(meta.get("repository_url") or "https://github.com/"+meta["repository"]) + ")\n"
            + "- Original path: " + str(meta["source_skill_path"]) + "\n"
            + "- Exact source revision: " + str(meta["commit_sha"]) + "\n"
            + "- Source file: " + source_url + "\n"
            + "- License reported by GitHub: " + str(spdx) + " (" + str(meta.get("license_name") or "name unavailable") + ")\n"
            + "- License evidence: " + ", ".join(x.get("source_path", "") for x in evidence) + "\n"
            + "This is a third-party work collected for discovery and reference. GASL does not claim authorship or exclusive ownership. "
            + "The original rights holder and the license terms above remain authoritative. Review the upstream source and license before reuse.\n"
        )
        if dest.exists():
            validate_public_package(dest, files)
            existing = read(dest / "ATTRIBUTION.json")
            if existing != attribution or (dest / "ATTRIBUTION.md").read_text(encoding="utf-8") != attribution_md:
                raise ValueError("Existing public package attribution differs for the same immutable source revision")
        else:
            with tempfile.TemporaryDirectory(prefix="gasl-public-", dir=public / "packages") as temp:
                stage = Path(temp) / pid
                stage.mkdir()
                for item in files:
                    safe_copy(source_path.parent / item["path"], stage / item["path"])
                (stage / "ATTRIBUTION.json").write_text(attribution_json, encoding="utf-8")
                (stage / "ATTRIBUTION.md").write_text(attribution_md, encoding="utf-8")
                validate_public_package(stage, files)
                if dest.exists():
                    raise ValueError("Public package destination appeared during publication")
                stage.rename(dest)
        index["packages"][pid] = {
            "package_id": pid, "skill_name": meta.get("skill_name"),
            "repository": meta["repository"], "repository_owner": attribution["repository_owner"],
            "source_skill_path": meta["source_skill_path"],
            "source_url": source_url, "commit_sha": meta["commit_sha"],
            "license_spdx": spdx, "license_url": meta.get("license_url"),
            "license_evidence": evidence,
            "package_path": str(dest.relative_to(root)),
            "file_count": len(files), "package_bytes": sum(x["size_bytes"] for x in files),
            "security_status": meta.get("security_status", "not_scanned"),
            "ownership": "third_party", "gasl_claims_exclusive_ownership": False,
            "execution_performed": False, "install_status": "not_approved"
        }
        published.append(pid)
    index["updated_at"] = now()
    index["package_count"] = len(index["packages"])
    write(index_path, index)
    summary = {
        "schema_version": "1.0.0", "generated_at": now(),
        "public_package_count": len(index["packages"]),
        "new_or_verified_this_run": len(published),
        "local_packages_examined": len(packages),
        "skipped_count": len(skipped),
        "skipped_by_reason": {},
        "third_party_attribution_preserved": True,
        "exclusive_ownership_claimed": False,
        "execution_performed": False
    }
    for item in skipped:
        reason = item["reason"]
        summary["skipped_by_reason"][reason] = summary["skipped_by_reason"].get(reason, 0) + 1
    write(root / "registry/public-catalog-summary.json", summary)
    (public / "README.md").write_text(
        "# GASL Public Catalog\n\n"
        "This directory contains version-pinned third-party skill packages whose repository-level license signal is on the configured redistribution allowlist and whose upstream license/notice evidence is bundled. "
        "Every package includes ATTRIBUTION.md and ATTRIBUTION.json. GASL is a discovery and aggregation project; it does not claim authorship or exclusive ownership of these works. "
        "The original author/rightsholder and upstream license remain authoritative.\n\n"
        "A clean static scan is not a security approval. Packages are not installed or executed by this workflow. "
        "Sources with unknown, missing, proprietary, non-allowlisted or unverified licensing remain listed in registry/source-catalog.json with their original source links; their content is not mirrored here automatically.\n",
        encoding="utf-8")
    return summary


if __name__ == "__main__":
    import json
    print(json.dumps(build(), ensure_ascii=False, indent=2))
