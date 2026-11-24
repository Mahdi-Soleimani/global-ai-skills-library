"""Retrieve an explicitly selected pinned package; never install or execute it."""
import shutil
from pathlib import Path

from skill_search import ROOT, get_skill_by_id


def download_skill(source_record_id, root=ROOT, execute=False):
    # Import the portable collector only for explicit selected retrieval.
    from queue_ingest import (fetch_tree, make_plan, ingest, package_location,
                              no_symlink, read_json, ingestion_lock)

    root = Path(root).resolve()
    record = get_skill_by_id(source_record_id, root=root)
    if record is None:
        raise KeyError("Skill source record not found: " + source_record_id)
    if record.get("snapshot_status") != "verified_commit_pinned":
        raise ValueError("A verified commit-pinned source record is required.")
    if "/" not in record["source_path"]:
        raise ValueError("Root-level Skill requires root-skill-scope review")
    row = {**record, "skill_path": record["source_path"],
           "research_leads": record.get("research_leads") or []}
    policy = read_json(root / "config/policy.json")
    # No license filter. The source, commit, tree and exact SKILL.md blob
    # must agree before any package is written.
    plan = make_plan(row, fetch_tree(row), policy)
    destination = package_location(root, plan)
    result = {
        "source_record_id": source_record_id,
        "repository": record["repository"],
        "source_url": record.get("source_url"),
        "commit_sha": record["commit_sha"],
        "license_spdx": record.get("license_spdx"),
        "license_evidence": plan["license_evidence"],
        "filesystem_path": str(destination.relative_to(root)),
        "file_count": len(plan["files"]),
        "bytes": plan["bytes"],
        "status": "planned",
        "installed": False,
        "executed": False,
        "installation_allowed": False,
        "execution_allowed": False,
        "security_status": "not_scanned",
        "security_scan_performed": False,
        "manual_review_required": True,
        "untrusted_content": True,
    }
    if not execute:
        return result
    if shutil.disk_usage(root).free < plan["bytes"] + 1024 * 1024 * 1024:
        raise RuntimeError("Insufficient free disk for selected package.")
    private_dir = no_symlink(root, root / "private")
    private_dir.mkdir(exist_ok=True)
    manifest = no_symlink(root, private_dir / "on-demand-manifest.json")
    with ingestion_lock(root):
        result.update(ingest(root, plan, manifest_path=manifest))
        # This is a local, non-executing scan. Never convert static evidence into
        # installation or execution approval.
        from security_gate import audit_local_package
        result.update(audit_local_package(source_record_id, root=root, record=record))
        if result["integrity_ok"] is False:
            result["status"] = "blocked_integrity_failure"
    return result
