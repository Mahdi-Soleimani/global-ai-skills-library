#!/usr/bin/env python3
"""Build a complete, third-party-attributed source index; this does not copy upstream content."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def nearest_license(skill_path, license_files):
    folder = skill_path.rsplit("/", 1)[0] if "/" in skill_path else ""
    ancestors = {""}
    parts = folder.split("/") if folder else []
    ancestors.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
    candidates = [item for item in license_files
                  if (item.get("path", "").rsplit("/", 1)[0] if "/" in item.get("path", "") else "") in ancestors]
    if not candidates:
        return None
    return sorted(candidates, key=lambda x: (-len(x["path"].rsplit("/", 1)[0]), x["path"]))[0]


def build(root=ROOT, public_only=False):
    state = read(root / "registry/discovery-state.json", {"repositories": {}})
    historical = {"repositories": {}} if public_only else read(root / "registry/source-verification.json", {"repositories": {}})
    local_records = [] if public_only else read(root / "registry/skills.json", {"records": []}).get("records", [])
    downloaded = [{**item, "local_content_present": bool(
        item.get("package_path") and (root / item["package_path"] / "source.json").is_file())}
        for item in local_records]
    public_index = read(root / "public-catalog/index.json", {"packages": {}}).get("packages", {})
    public_records = [{**item, "publicly_mirrored": True, "package_complete": True,
                       "canonical_repository": item.get("repository"),
                       "source_skill_path": item.get("source_skill_path")}
                      for item in public_index.values()]
    downloaded.extend(public_records)
    historical_repos = historical.get("repositories", {})
    by_repo = {}
    for key, item in historical_repos.items():
        canonical = (item.get("canonical_repo_name") or item.get("repo_full_name") or key).casefold()
        current = by_repo.setdefault(canonical, {})
        if item.get("redirected_alias") is False or not current:
            current.update(item)
        current["skill_paths"] = sorted(set(current.get("skill_paths", [])) | set(item.get("skill_paths", [])))
        current["source_reports"] = sorted(set(current.get("source_reports", [])) | set(item.get("source_reports", [])))

    state_repos = state.get("repositories", {})
    repo_keys = set(by_repo) | set(state_repos)
    downloaded_by_key = {}
    for item in downloaded:
        key = (str(item.get("canonical_repository") or item.get("repository") or "").casefold(),
               item.get("source_skill_path"), item.get("commit_sha"))
        downloaded_by_key[key] = item

    records, seen = [], set()
    for repo_key in sorted(repo_keys):
        hist = by_repo.get(repo_key, {})
        current = state_repos.get(repo_key, {})
        repo = current.get("repository") or hist.get("canonical_repo_name") or hist.get("repo_full_name") or repo_key
        commit = current.get("commit_sha")
        tree = current.get("tree_sha")
        branch = current.get("default_branch") or hist.get("default_branch") or "main"
        pinned_paths = current.get("paths") or []
        if pinned_paths:
            current_paths = {item.get("path") for item in pinned_paths}
            legacy_paths = sorted(set(hist.get("skill_paths", [])) - current_paths)
            path_items = list(pinned_paths) + [
                {"path": p, "classification": "skill_path_candidate", "blob_sha": None,
                 "size_bytes": None, "legacy_unpinned": True} for p in legacy_paths
            ]
        else:
            path_items = [{"path": p, "classification": "skill_path_candidate",
                           "blob_sha": None, "size_bytes": None, "legacy_unpinned": True}
                          for p in sorted(set(current.get("skill_paths", [])) | set(hist.get("skill_paths", [])))]
        license_files = current.get("license_files") or []
        license_spdx = current.get("license_spdx") or hist.get("license_spdx")
        license_name = current.get("license_name") or hist.get("license_name")
        publisher = current.get("publisher_account") or hist.get("owner_login") or repo.split("/", 1)[0]
        repo_url = current.get("repository_url") or hist.get("repository_url") or hist.get("html_url") or "https://github.com/" + repo
        research_leads = sorted(set(current.get("source_reports", [])) | set(hist.get("source_reports", [])))
        for path_item in path_items:
            path = path_item.get("path")
            if not path or path_item.get("classification", "skill_path_candidate") != "skill_path_candidate":
                continue
            identity = (repo.casefold(), path, commit or "legacy-snapshot")
            if identity in seen:
                continue
            seen.add(identity)
            evidence = nearest_license(path, license_files)
            if path_item.get("legacy_unpinned") or not commit:
                evidence = None
            path_is_pinned = bool(commit and path_item.get("blob_sha") and not path_item.get("legacy_unpinned"))
            revision = commit if path_is_pinned else branch
            source_url = "{}/blob/{}/{}".format(repo_url.rstrip("/"), revision, quote(path, safe="/"))
            license_url = None
            if evidence and commit:
                license_url = "{}/blob/{}/{}".format(repo_url.rstrip("/"), commit, quote(evidence["path"], safe="/"))
            elif current.get("license_api_url"):
                license_url = current["license_api_url"]
            downloaded_meta = downloaded_by_key.get((repo.casefold(), path, commit)) if commit else None
            if license_spdx in (None, "", "NOASSERTION", "NONE"):
                license_status = "no_license_identified"
                mirror_status = "reference_only_no_redistribution_permission_assumed"
            else:
                license_status = "repository_license_metadata_only"
                mirror_status = "reference_only_until_file_level_rights_and_license_evidence_review"
            if downloaded_meta and downloaded_meta.get("publicly_mirrored"):
                mirror_status = "published_publicly_with_attribution"
            elif downloaded_meta and downloaded_meta.get("local_content_present"):
                mirror_status = downloaded_meta.get("public_mirror_status") or mirror_status
            if downloaded_meta and downloaded_meta.get("publicly_mirrored"):
                content_status = "mirrored_publicly_with_attribution"
                collection_status = "publicly_mirrored"
                collection_scope = "public_catalog"
            elif downloaded_meta and downloaded_meta.get("local_content_present"):
                content_status = "downloaded_and_hashed_locally"
                collection_status = downloaded_meta.get("collection_status") or "collected"
                collection_scope = downloaded_meta.get("collection_scope") or "private_local_catalog"
            elif downloaded_meta:
                content_status = "historical_package_metadata_only_content_not_present"
                collection_status = "historical_metadata_only"
                collection_scope = None
            else:
                content_status = "not_downloaded_reference_record"
                collection_status = "not_collected"
                collection_scope = None
            skill_name = path.rsplit("/", 2)[-2] if path.endswith("/SKILL.md") else path.rsplit("/", 1)[-1]
            if downloaded_meta and downloaded_meta.get("skill_name"):
                skill_name = downloaded_meta["skill_name"]
            seed = "\0".join((repo.casefold(), path, commit or "legacy-snapshot"))
            record_id = "GASL-SRC-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]
            records.append({
                "source_record_id": record_id,
                "skill_name": skill_name,
                "description": downloaded_meta.get("description") if downloaded_meta else None,
                "repository": repo,
                "repository_owner": publisher,
                "repository_url": repo_url,
                "source_path": path,
                "source_url": source_url,
                "commit_sha": commit,
                "tree_sha": tree,
                "skill_md_blob_sha": path_item.get("blob_sha"),
                "license_spdx": license_spdx,
                "license_name": license_name,
                "license_evidence_path": evidence.get("path") if evidence else None,
                "license_url": license_url,
                "license_assessment": license_status,
                "collection_license_status": downloaded_meta.get("license_status") if downloaded_meta else None,
                "public_mirror_status": mirror_status,
                "collection_status": collection_status,
                "collection_scope": collection_scope,
                "content_status": content_status,
                "content_package_path": downloaded_meta.get("package_path") if downloaded_meta else None,
                "security_status": downloaded_meta.get("security_status", "not_scanned") if downloaded_meta else "not_scanned",
                "install_status": downloaded_meta.get("install_status", "not_installed") if downloaded_meta else "not_installed",
                "snapshot_status": "verified_commit_pinned" if path_is_pinned else "legacy_snapshot_unpinned",
                "last_verified_at": current.get("checked_at") or hist.get("checked_at"),
                "research_leads": research_leads,
                "ownership": "third_party",
                "original_author": None,
                "gasl_claims_exclusive_ownership": False,
                "attribution_notice": "Third-party work. Original rights remain with the respective upstream authors/rightsholders. GASL is an attributed index and does not claim exclusive ownership.",
                "source_scope": "repository/path discovery reference; research leads are not proof of individual authorship"
            })
    # Keep every downloaded immutable package revision even if the current live source snapshot
    # is temporarily unavailable or has advanced to a different commit.
    for item in downloaded:
        repo = str(item.get("canonical_repository") or item.get("repository") or "")
        path = item.get("source_skill_path")
        commit = item.get("commit_sha")
        if not repo or not path or not commit:
            continue
        identity = (repo.casefold(), path, commit)
        if identity in seen:
            continue
        seen.add(identity)
        seed = "\0".join((repo.casefold(), path, commit))
        repo_meta = by_repo.get(repo.casefold(), {})
        records.append({
            "source_record_id": "GASL-SRC-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20],
            "skill_name": item.get("skill_name") or path.rsplit("/", 2)[-2],
            "description": item.get("description"),
            "repository": repo,
            "repository_owner": item.get("repository_owner") or repo.split("/", 1)[0],
            "repository_url": item.get("repository_url") or "https://github.com/" + repo,
            "source_path": path,
            "source_url": item.get("source_url") or "https://github.com/{}/blob/{}/{}".format(repo, commit, quote(path, safe="/")),
            "commit_sha": commit,
            "tree_sha": item.get("tree_sha"),
            "skill_md_blob_sha": item.get("skill_md_blob_sha"),
            "license_spdx": item.get("license_spdx"),
            "license_name": item.get("license_name"),
            "license_evidence_path": next((x.get("source_path") for x in item.get("license_evidence", [])), None),
            "license_url": item.get("license_url"),
            "license_assessment": "repository_license_metadata_only" if item.get("license_spdx") else "no_license_identified",
            "collection_license_status": item.get("license_status"),
            "public_mirror_status": ("published_publicly_with_attribution" if item.get("publicly_mirrored") else
                                     item.get("public_mirror_status") or "reference_only_until_file_level_rights_and_license_evidence_review"),
            "collection_status": ("publicly_mirrored" if item.get("publicly_mirrored") else
                                  item.get("collection_status") or ("collected" if item.get("local_content_present") else "historical_metadata_only")),
            "collection_scope": ("public_catalog" if item.get("publicly_mirrored") else
                                 item.get("collection_scope") or ("private_local_catalog" if item.get("local_content_present") else None)),
            "content_status": ("mirrored_publicly_with_attribution" if item.get("publicly_mirrored") else
                               "downloaded_and_hashed_locally" if item.get("local_content_present") else
                               "historical_package_metadata_only_content_not_present"),
            "content_package_path": item.get("package_path"),
            "security_status": item.get("security_status", "not_scanned"),
            "install_status": item.get("install_status", "not_installed"),
            "snapshot_status": "verified_commit_pinned",
            "last_verified_at": item.get("downloaded_at"),
            "research_leads": item.get("research_leads", repo_meta.get("source_reports", [])),
            "ownership": "third_party",
            "original_author": None,
            "gasl_claims_exclusive_ownership": False,
            "attribution_notice": "Third-party work. Original rights remain with the respective upstream authors/rightsholders. GASL is an attributed index and does not claim exclusive ownership.",
            "source_scope": "downloaded immutable package provenance; repository owner is not asserted to be the individual author"
        })
    records.sort(key=lambda x: (x["repository"].casefold(), x["source_path"], x["commit_sha"] or ""))
    counts = Counter(x["license_assessment"] for x in records)
    summary = {
        "schema_version": "1.0.0",
        "generated_at": now(),
        "source_repository_count": len(repo_keys),
        "source_record_count": len(records),
        "distinct_repository_path_count": len({(x["repository"].casefold(), x["source_path"]) for x in records}),
        "immutable_revision_count": len({(x["repository"].casefold(), x["source_path"], x["commit_sha"]) for x in records if x["commit_sha"]}),
        "commit_pinned_record_count": sum(x["snapshot_status"] == "verified_commit_pinned" for x in records),
        "legacy_unpinned_record_count": sum(x["snapshot_status"] == "legacy_snapshot_unpinned" for x in records),
        "downloaded_record_count": sum(x["content_status"] in
            ("downloaded_and_hashed_locally", "mirrored_publicly_with_attribution") for x in records),
        "private_collected_record_count": sum(x.get("collection_scope") == "private_local_catalog" for x in records),
        "collection_status_counts": dict(sorted(Counter(x.get("collection_status", "not_collected") for x in records).items())),
        "collection_license_status_counts": dict(sorted(Counter(x.get("collection_license_status") or "not_collected" for x in records).items())),
        "public_mirror_status_counts": dict(sorted(Counter(x.get("public_mirror_status", "unknown") for x in records).items())),
        "historical_package_metadata_only_count": sum(x["content_status"] == "historical_package_metadata_only_content_not_present" for x in records),
        "publicly_mirrored_record_count": sum(x["content_status"] == "mirrored_publicly_with_attribution" for x in records),
        "license_assessment_counts": dict(sorted(counts.items())),
        "third_party_attribution_preserved": True,
        "exclusive_ownership_claimed": False,
        "source_research_datasets_modified": False,
        "limitations": [
            "A repository-level GitHub license signal is not a per-file license determination.",
            "A source URL and attribution do not independently grant redistribution rights.",
            "Legacy paths without a live commit are reference-only until refreshed.",
            "Original individual author is not inferred from repository ownership."
        ]
    }
    registry = root / "registry"
    registry.mkdir(exist_ok=True)
    (registry / "source-catalog.json").write_text(
        json.dumps({"schema_version": "1.0.0", "summary": summary, "records": records},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = list(records[0]) if records else ["source_record_id", "repository", "source_path", "source_url"]
    with (registry / "source-catalog.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({**r, "research_leads": ";".join(r["research_leads"])} for r in records)
    (registry / "source-catalog-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-only", action="store_true", help="Exclude local package metadata from the public refresh")
    args = parser.parse_args()
    print(json.dumps(build(public_only=args.public_only), ensure_ascii=False, indent=2))
