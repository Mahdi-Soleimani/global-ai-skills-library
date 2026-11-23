#!/usr/bin/env python3
"""Compare 2–3 explicit GASL Skill source records with evidence, not quality claims."""
import json
import re
from skill_search import ROOT
from gasl_service import skill_details

ID_PATTERN = re.compile(r"GASL-SRC-[A-Za-z0-9_-]{1,100}\Z")


def compare_skills(source_ids, *, root=ROOT):
    """Read-only comparison; no upstream network calls or Skill code execution."""
    if not isinstance(source_ids, list) or not 2 <= len(source_ids) <= 3:
        raise ValueError("ids must be a list of 2 or 3 source record IDs.")
    if any(not isinstance(item, str) or not ID_PATTERN.fullmatch(item) for item in source_ids):
        raise ValueError("Each source ID must match the exact GASL-SRC format.")
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("Choose distinct source records.")

    entries = []
    for source_id in source_ids:
        record = skill_details(source_id, root=root)
        entries.append({
            "source_record_id": source_id,
            "skill_name": record.get("skill_name"),
            "description": record.get("description"),
            "repository": record.get("repository"),
            "source_path": record.get("source_path"),
            "source_url": record.get("source_url"),
            "commit_sha": record.get("commit_sha"),
            "license_spdx": record.get("license_spdx"),
            "license_assessment": record.get("license_assessment"),
            "security_status": record.get("security_status"),
            "content_status": record.get("content_status"),
            "compatibility": record.get("compatibility"),
            "inferred_domains": record.get("inferred_domains"),
            "metadata_completeness_score": record.get("metadata_completeness_score"),
            "provenance_score": record.get("provenance_score"),
            "behavioral_evaluation": record.get("behavioral_evaluation"),
            "installation_allowed": False,
            "execution_allowed": False,
        })
    dimensions = (
        "license_spdx", "license_assessment", "security_status", "content_status",
        "compatibility", "repository", "commit_sha"
    )
    differences = [
        key for key in dimensions
        if len({json.dumps(item.get(key), sort_keys=True, ensure_ascii=False)
                for item in entries}) > 1
    ]
    return {
        "schema_version": "gasl-skill-compare-v1",
        "source_record_ids": list(source_ids),
        "count": len(entries),
        "items": entries,
        "different_fields": differences,
        "winner_selected": False,
        "quality_scoring_performed": False,
        "source_authenticity_independently_verified": False,
        "installation_performed": False,
        "execution_performed": False,
        "note": (
            "These fields are locally recorded evidence, not verified source trust. "
            "No security, quality or installation approval is implied. "
            "Review the source and Skill instructions independently before using it."
        ),
    }
