#!/usr/bin/env python3
"""Evidence-only Skill assessment. This module does not execute or approve third-party code."""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "registry" / "source-catalog.json"
PUBLIC_INDEX_PATH = ROOT / "public-catalog" / "index.json"
OUTPUT_PATH = ROOT / "registry" / "skill-evaluations.json"
EVALUATION_VERSION = "1.0.0"


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def identity(record):
    return (
        str(record.get("repository") or "").casefold(),
        record.get("source_path") or record.get("source_skill_path"),
        record.get("commit_sha"),
    )


def _present(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return bool(value)


def evaluate_record(record, public_package=None):
    """Return conservative evidence scores; never produce a behavioral quality score."""
    public_package = public_package or {}
    has_public_evidence = bool(public_package.get("license_evidence"))
    license_spdx = record.get("license_spdx") or public_package.get("license_spdx")
    content_status = record.get("content_status") or "not_downloaded_reference_record"
    security_status = record.get("security_status") or "not_scanned"

    metadata_fields = [
        ("skill_name", 10, record.get("skill_name")),
        ("description", 20, record.get("description")),
        ("repository", 10, record.get("repository")),
        ("repository_owner", 5, record.get("repository_owner")),
        ("source_url", 10, record.get("source_url")),
        ("commit_sha", 15, record.get("commit_sha")),
        ("skill_md_blob_sha", 10, record.get("skill_md_blob_sha")),
        ("license_spdx", 5, license_spdx),
        ("license_evidence", 5, has_public_evidence or record.get("license_evidence_path")),
        ("research_leads", 5, record.get("research_leads")),
        ("compatibility", 5, record.get("compatibility")),
    ]
    metadata_score = sum(weight for _, weight, value in metadata_fields if _present(value))

    provenance_fields = [
        ("repository", 10, record.get("repository")),
        ("repository_owner", 5, record.get("repository_owner")),
        ("source_path", 10, record.get("source_path") or record.get("source_skill_path")),
        ("source_url", 15, record.get("source_url")),
        ("commit_sha", 20, record.get("commit_sha")),
        ("skill_md_blob_sha", 20, record.get("skill_md_blob_sha")),
        ("third_party_ownership", 10, record.get("ownership") == "third_party"),
        ("no_exclusive_ownership_claim", 10, record.get("gasl_claims_exclusive_ownership") is False),
    ]
    provenance_score = sum(weight for _, weight, value in provenance_fields if _present(value))

    if public_package and has_public_evidence:
        license_status = "public_mirror_allowlist_and_evidence_gate_passed"
    elif license_spdx and record.get("license_evidence_path"):
        license_status = "repository_license_signal_and_file_discovered_review_required"
    elif license_spdx:
        license_status = "repository_license_metadata_only_review_required"
    else:
        license_status = "unknown_license_review_required"

    security_map = {
        "integrity_failed": "blocked_integrity_failure",
        "manual_review_required": "manual_review_required",
        "no_obvious_static_flags_not_approved": "static_screen_no_obvious_flags_not_approval",
        "not_scanned": "not_scanned",
    }
    security_assessment = security_map.get(security_status, "unknown_security_state")

    risk_flags = []
    if not _present(record.get("description")):
        risk_flags.append("description_missing")
    if not license_spdx:
        risk_flags.append("license_unknown")
    elif not has_public_evidence:
        risk_flags.append("file_level_license_evidence_not_in_public_package")
    if security_status == "not_scanned":
        risk_flags.append("security_not_scanned")
    elif security_status == "manual_review_required":
        risk_flags.append("manual_security_review_required")
    elif security_status == "no_obvious_static_flags_not_approved":
        risk_flags.append("static_scan_is_not_security_approval")
    if content_status not in ("downloaded_and_hashed_locally", "mirrored_publicly_with_attribution"):
        risk_flags.append("skill_content_not_available_in_verified_package")
    if record.get("install_status") not in ("install_approved", "approved"):
        risk_flags.append("installation_not_approved")
    risk_flags.append("behavioral_benchmark_not_run")

    if security_status == "integrity_failed":
        recommendation_state = "blocked_integrity_failure"
    elif security_status == "manual_review_required":
        recommendation_state = "manual_security_review_required"
    elif security_status == "not_scanned":
        recommendation_state = "security_screen_required"
    else:
        recommendation_state = "reference_candidate_only_not_approved_for_installation"

    return {
        "source_record_id": record.get("source_record_id"),
        "skill_id": record.get("skill_id"),
        "identity": {
            "repository": record.get("repository"),
            "source_path": record.get("source_path") or record.get("source_skill_path"),
            "commit_sha": record.get("commit_sha"),
        },
        "metadata_completeness_score": metadata_score,
        "provenance_score": provenance_score,
        "description_available": _present(record.get("description")),
        "license_assessment": license_status,
        "license_spdx": license_spdx,
        "license_evidence_bundled": has_public_evidence,
        "security_assessment": security_assessment,
        "security_status": security_status,
        "recommendation_state": recommendation_state,
        "content_status": content_status,
        "install_status": record.get("install_status") or "not_installed",
        "behavioral_evaluation": "not_evaluated",
        "overall_quality_score": None,
        "evaluation_status": "metadata_and_static_evidence_only",
        "risk_flags": risk_flags,
        "execution_performed": False,
        "installation_performed": False,
    }


def build_evaluations(root=ROOT):
    source = read_json(root / "registry" / "source-catalog.json", {"records": []})
    public = read_json(root / "public-catalog" / "index.json", {"packages": {}})
    public_by_identity = {
        identity(item): item for item in public.get("packages", {}).values()
    }

    evaluations = []
    source_records = source.get("records", [])
    for record in source_records:
        package = public_by_identity.get(identity(record), {})
        enriched = dict(record)
        for field in ("skill_name", "description", "license_spdx", "source_url"):
            if not _present(enriched.get(field)) and _present(package.get(field)):
                enriched[field] = package[field]
        if package:
            enriched["content_status"] = "mirrored_publicly_with_attribution"
            enriched["security_status"] = package.get("security_status", enriched.get("security_status"))
            enriched["install_status"] = package.get("install_status", enriched.get("install_status"))
        evaluations.append(evaluate_record(enriched, package))

    evaluations.sort(key=lambda x: (
        str(x["identity"]["repository"] or "").casefold(),
        x["identity"]["source_path"] or "",
        x["identity"]["commit_sha"] or "",
    ))
    counts = Counter(x["recommendation_state"] for x in evaluations)
    license_counts = Counter(x["license_assessment"] for x in evaluations)
    security_counts = Counter(x["security_assessment"] for x in evaluations)
    summary = {
        "schema_version": EVALUATION_VERSION,
        "generated_at": now(),
        "source_record_count": len(evaluations),
        "description_available_count": sum(x["description_available"] for x in evaluations),
        "license_evidence_bundled_count": sum(x["license_evidence_bundled"] for x in evaluations),
        "security_screened_count": sum(x["security_assessment"] != "not_scanned" for x in evaluations),
        "content_available_count": sum(x["content_status"] in (
            "downloaded_and_hashed_locally", "mirrored_publicly_with_attribution"
        ) for x in evaluations),
        "install_approved_count": sum(x["install_status"] in ("install_approved", "approved") for x in evaluations),
        "metadata_score_range": [min((x["metadata_completeness_score"] for x in evaluations), default=0),
                                 max((x["metadata_completeness_score"] for x in evaluations), default=0)],
        "average_metadata_completeness_score": round(
            sum(x["metadata_completeness_score"] for x in evaluations) / len(evaluations), 2
        ) if evaluations else 0,
        "average_provenance_score": round(
            sum(x["provenance_score"] for x in evaluations) / len(evaluations), 2
        ) if evaluations else 0,
        "behaviorally_evaluated_count": 0,
        "overall_quality_scores_assigned": 0,
        "execution_performed": False,
        "installation_performed": False,
        "recommendation_state_counts": dict(sorted(counts.items())),
        "license_assessment_counts": dict(sorted(license_counts.items())),
        "security_assessment_counts": dict(sorted(security_counts.items())),
        "limitations": [
            "Metadata completeness and provenance are evidence coverage metrics, not Skill quality scores.",
            "No behavioral benchmark has been run; overall_quality_score intentionally remains null.",
            "Repository-level license metadata is not a per-file legal determination.",
            "A static scan with no obvious flags is not a security approval.",
            "No third-party code was installed or executed."
        ],
    }
    output = {
        "schema_version": EVALUATION_VERSION,
        "score_policy": {
            "metadata_completeness": {
                "skill_name": 10, "description": 20, "repository": 10,
                "repository_owner": 5, "source_url": 10, "commit_sha": 15,
                "skill_md_blob_sha": 10, "license_spdx": 5,
                "license_evidence": 5, "research_leads": 5, "compatibility": 5,
            },
            "provenance": {
                "repository": 10, "repository_owner": 5, "source_path": 10,
                "source_url": 15, "commit_sha": 20, "skill_md_blob_sha": 20,
                "third_party_ownership": 10, "no_exclusive_ownership_claim": 10,
            },
            "overall_quality_score": None,
        },
        "summary": summary,
        "records": evaluations,
    }
    target = root / "registry" / "skill-evaluations.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temp.replace(target)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Build conservative, evidence-only Skill assessments.")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(build_evaluations(args.root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
