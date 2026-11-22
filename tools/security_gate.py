#!/usr/bin/env python3
"""Offline-only security gate for a single, explicitly downloaded pinned Skill.

No third-party code is executed. Scans are heuristic; every local package remains
unapproved for installation and is never published automatically.
"""
import hashlib
import json
import re
from pathlib import Path

from queue_ingest import git_blob, no_symlink, package_location
from skill_search import ROOT, get_skill_by_id
from static_scan import scan_package


def _legacy_source_path(root, expected, record):
    """Locate exactly one older-format package within the same repo folder."""
    candidates = []
    for source in expected.parent.parent.glob("*/source.json"):
        try:
            no_symlink(root, source)
            if not source.is_file():
                continue
            metadata = json.loads(source.read_text(encoding="utf-8"))
            if (str(metadata.get("repository", "")).casefold() == str(record["repository"]).casefold() and
                    metadata.get("commit_sha") == record["commit_sha"] and
                    metadata.get("source_skill_path") == record["source_path"] and
                    metadata.get("package_complete") is True):
                candidates.append(source)
        except (OSError, ValueError, TypeError):
            continue
    if len(candidates) > 1:
        raise ValueError("Ambiguous legacy package locations for one pinned source identity")
    return candidates[0] if candidates else None


def audit_local_package(source_record_id, root=ROOT, record=None):
    """Verify the original pinned SKILL.md and scan its downloaded package."""
    root = Path(root).resolve()
    record = record if record is not None else get_skill_by_id(source_record_id, root=root)
    if record is None:
        raise KeyError("Skill source record not found: " + str(source_record_id))
    if record.get("snapshot_status") != "verified_commit_pinned":
        raise ValueError("Security audit requires a verified commit-pinned source record")
    row = {**record, "skill_path": record["source_path"]}
    folder = no_symlink(root, package_location(root, row))
    source_path = no_symlink(root, folder / "source.json")
    if not source_path.is_file():
        legacy = _legacy_source_path(root, source_path, record)
        if legacy is None:
            raise FileNotFoundError("Download this pinned Skill first; there is no local source.json")
        source_path = no_symlink(root, legacy)
        folder = source_path.parent
    metadata = json.loads(source_path.read_text(encoding="utf-8"))
    if (metadata.get("repository", "").casefold() != record["repository"].casefold() or
            metadata.get("commit_sha") != record["commit_sha"] or
            metadata.get("source_skill_path") != record["source_path"] or
            metadata.get("skill_md_blob_sha") not in (None, record["skill_md_blob_sha"]) or
            metadata.get("package_complete") is not True):
        raise ValueError("Local package identity/integrity does not match the selected pinned source")

    # The cached sha256 list can be edited locally; independently re-check the
    # upstream immutable Git blob for the top-level SKILL.md, not only its metadata.
    expected_skill_path = folder / "SKILL.md"
    no_symlink(root, expected_skill_path)
    if not expected_skill_path.is_file():
        raise ValueError("Local package does not contain an ordinary SKILL.md")
    pinned_blob_ok = git_blob(expected_skill_path.read_bytes()) == record["skill_md_blob_sha"]
    result = scan_package(source_path, root=root)
    result["source_record_id"] = source_record_id
    result["local_package_path"] = folder.relative_to(root).as_posix()
    result["pinned_skill_blob_ok"] = pinned_blob_ok
    result["installation_allowed"] = False
    result["execution_allowed"] = False
    result["manual_review_required"] = True
    result["sandbox_executed"] = False
    result["approval_status"] = "not_approved_static_evidence_only"
    result["license_spdx"] = record.get("license_spdx")
    result["license_evidence"] = metadata.get("license_evidence", [])
    if pinned_blob_ok and not metadata.get("skill_md_blob_sha"):
        # Old complete packages did not persist the main blob field. Upgrade
        # only after validating actual bytes against the current pinned catalog.
        verified_meta = json.loads(source_path.read_text(encoding="utf-8"))
        verified_meta["skill_md_blob_sha"] = record["skill_md_blob_sha"]
        source_path.write_text(json.dumps(verified_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not pinned_blob_ok:
        result["security_status"] = "integrity_failed"
        result["integrity_ok"] = False
        result["integrity"].append({"path": "SKILL.md", "status": "pinned_git_blob_mismatch"})
        metadata = json.loads(source_path.read_text(encoding="utf-8"))
        metadata["security_status"] = "integrity_failed"
        metadata["install_status"] = "not_approved"
        source_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Detailed evidence may include untrusted text or incidental sensitive
    # strings: store only inside ignored local reports/, never in the public repo.
    report_dir = no_symlink(root, root / "reports" / "security" / "on-demand")
    report_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((str(source_record_id) + "\n" + record["commit_sha"]).encode()).hexdigest()[:16]
    label = re.sub(r"[^a-zA-Z0-9_-]", "_", str(source_record_id))[:70]
    report_path = no_symlink(root, report_dir / (label + "-" + key + ".json"))
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "source_record_id": source_record_id,
        "local_package_path": result["local_package_path"],
        "recognized_legacy_internal_checkpoints": result["recognized_legacy_internal_checkpoints"],
        "security_status": result["security_status"],
        "integrity_ok": result["integrity_ok"],
        "pinned_skill_blob_ok": pinned_blob_ok,
        "finding_count": result["finding_count"],
        "high_confidence_signals": result["high_confidence_signals"],
        "security_report_path": report_path.relative_to(root).as_posix(),
        "installation_allowed": False,
        "execution_allowed": False,
        "manual_review_required": True,
        "sandbox_executed": False,
        "approval_status": "not_approved_static_evidence_only",
        "security_scan_performed": True,
    }
