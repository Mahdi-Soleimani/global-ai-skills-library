#!/usr/bin/env python3
"""Evidence-aware Skill candidate routing. Routing is advisory; it never installs or executes."""
import argparse
import json
from pathlib import Path

from skill_search import search_skills, normalize_text, ROOT
from answerability_policy import decide, POLICY_VERSION, POLICY_STATUS


ANSWERABILITY_POLICY_VERSION = POLICY_VERSION
ANSWERABILITY_POLICY_STATUS = POLICY_STATUS


def route_task(task, top_k=5, domain=None, license_spdx=None, agent=None,
               strict_agent=False, public_only=False, content_only=False, root=ROOT):
    top_k = max(1, min(int(top_k), 20))
    candidates = search_skills(
        task,
        limit=min(max(top_k * 20, 100), 100),
        domain=domain,
        license_spdx=license_spdx,
        public_only=public_only,
        content_only=content_only,
        root=root,
    )
    selected = []
    excluded = 0
    for item in candidates:
        if item.get("security_status") == "integrity_failed":
            excluded += 1
            continue
        compatibility = item.get("compatibility") or ""
        if not agent:
            compatibility_status = "not_requested"
        elif not compatibility:
            compatibility_status = "not_declared"
        elif normalize_text(agent) in normalize_text(compatibility):
            compatibility_status = "declared_match"
        else:
            compatibility_status = "declared_constraint_not_matching"
        if strict_agent and compatibility_status != "declared_match":
            excluded += 1
            continue

        evaluation = item.get("metadata", {}).get("evaluation", {})
        metadata_score = int(item.get("metadata_completeness_score") or 0)
        provenance_score = int(item.get("provenance_score") or 0)
        relevance_score = float(item.get("relevance_score") or 0)
        # Rank only by task relevance. Evidence completeness is displayed separately;
        # it is not a proxy for Skill quality and must not distort relevance.
        route_score = relevance_score

        security = item.get("security_status") or "not_scanned"
        if security == "manual_review_required":
            decision = "manual_security_review_required"
        elif security == "not_scanned":
            decision = "security_screen_required"
        elif security == "integrity_failed":
            decision = "blocked_integrity_failure"
        else:
            decision = "candidate_only_installation_not_approved"

        warnings = list(evaluation.get("risk_flags") or [])
        if agent and compatibility_status == "not_declared":
            warnings.append("agent_compatibility_not_declared")
        elif agent and compatibility_status == "declared_constraint_not_matching":
            warnings.append("agent_compatibility_not_confirmed")
        if item.get("content_status") == "not_downloaded_reference_record":
            warnings.append("only_source_reference_available")
        warnings.append("router_does_not_execute_or_install_skills")

        reasons = [
            "lexical_relevance={:.2f}".format(relevance_score),
            "query_coverage={:.3f}".format(item.get("query_coverage", 0.0)),
            "metadata_completeness={}".format(metadata_score),
            "provenance_completeness={}".format(provenance_score),
        ]
        if item.get("inferred_domains"):
            reasons.append("inferred_domains=" + ",".join(x["id"] for x in item["inferred_domains"]))
        if item.get("commit_sha"):
            reasons.append("commit_pinned_source")
        if item.get("is_publicly_mirrored"):
            reasons.append("public_mirror_has_attribution_and_license_evidence")

        selected.append({
            "source_record_id": item.get("source_record_id"),
            "skill_name": item.get("skill_name"),
            "description": item.get("description"),
            "repository": item.get("repository"),
            "source_path": item.get("source_path"),
            "source_url": item.get("source_url"),
            "commit_sha": item.get("commit_sha"),
            "license_spdx": item.get("license_spdx"),
            "license_assessment": evaluation.get("license_assessment"),
            "security_status": security,
            "decision": decision,
            "route_score": route_score,
            "relevance_score": relevance_score,
            "query_coverage": item.get("query_coverage", 0.0),
            "matched_query_groups": item.get("matched_query_groups", []),
            "unmatched_query_groups": item.get("unmatched_query_groups", []),
            "query_group_coverage": item.get("query_group_coverage", []),
            "metadata_completeness_score": metadata_score,
            "provenance_score": provenance_score,
            "content_status": item.get("content_status"),
            "install_status": item.get("install_status"),
            "compatibility": compatibility or None,
            "agent_compatibility_status": compatibility_status,
            "inferred_domains": item.get("inferred_domains", []),
            "selection_reasons": reasons,
            "warnings": sorted(set(warnings)),
            "installation_allowed": False,
            "execution_allowed": False,
        })

    # Preserve the search ranking after removing ineligible candidates.
    # Re-sorting by relevance alone would undo concept-coverage priority.
    results = selected[:top_k]
    heuristic = decide(task, selected)
    routing_decision = heuristic['decision']
    recommendation_status = {
        'recommend': 'provisional_candidate_to_inspect',
        'abstain': 'no_confident_candidate_in_retrieved_pool',
        'undetermined': 'candidate_discovery_only',
    }[routing_decision]
    return {
        "schema_version": "1.0.0",
        "task": task,
        "agent": agent,
        "ranking_method": "weighted query-coverage priority and lexical relevance with query-coverage penalty; provenance, license, security, and metadata are independent evidence fields",
        "candidate_pool_size": len(candidates),
        "excluded_candidate_count": excluded,
        "returned_count": len(results),
        "routing_decision": routing_decision,
        "recommendation_status": recommendation_status,
        "answerability": {
            "decision": routing_decision,
            "policy_status": ANSWERABILITY_POLICY_STATUS,
            "policy_version": ANSWERABILITY_POLICY_VERSION,
            "reason_code": heuristic['reason_code'],
            "reason": heuristic['reason'],
            "matched_technical_identifiers": heuristic['matched_technical_identifiers'],
            "unmatched_technical_identifiers": heuristic['unmatched_technical_identifiers'],
            "top_query_coverage": heuristic['top_query_coverage'],
            "prediction_basis": "provisional_deterministic_lexical_heuristic_not_independent_or_calibrated",
            "abstain_means": "insufficient_retrieved_evidence_not_proof_of_catalog_absence",
            "candidate_discovery_available": bool(results),
            "retrieved_candidate_pool_size": len(candidates),
            "eligible_candidate_count": len(selected),
            "returned_candidate_count": len(results),
            "empty_results_prove_no_relevant_skill": False,
            "human_review_required": False,
            "independent_quality_validation_available": False,
            "decision_vocabulary": ["recommend", "abstain", "undetermined"],
            "currently_emitted_decisions": ["recommend", "abstain", "undetermined"],
        },
        "results": results,
        "installation_performed": False,
        "execution_performed": False,
        "note": (
            "Ranking remains a discovery aid, not a behavioral quality score or security approval. "
            "Routing decisions are uncalibrated provisional lexical heuristics. "
            "No Skill is installed or executed. Security, license, compatibility, and host-specific "
            "installation approval remain independent gates."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Route a task to candidate Skills without installing or executing them.")
    parser.add_argument("--task", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--domain")
    parser.add_argument("--license", dest="license_spdx")
    parser.add_argument("--agent")
    parser.add_argument("--strict-agent", action="store_true")
    parser.add_argument("--public-only", action="store_true")
    parser.add_argument("--content-only", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(route_task(
        args.task, args.top_k, args.domain, args.license_spdx, args.agent,
        args.strict_agent, args.public_only, args.content_only, args.root,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
