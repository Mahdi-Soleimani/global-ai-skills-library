#!/usr/bin/env python3
"""Phase 49: explicit Codex project install handoff from the local Explorer.

All real Agent writes remain in codex_project_install and need its own exact
interactive TTY phrase. The browser gets only a user-copyable CLI command.
"""
import json
import sys
from pathlib import Path

from codex_project_install import (
    _root, _paths, preview_install, install_fresh, preview_replace,
    replace_existing,
)
from install_bundle import prepare_private_bundle, verify_private_bundle
from install_lifecycle import plan_install
from skill_search import ROOT

PREPARE_SCHEMA = "gasl-codex-explorer-install-handoff-v1"


def inspect_handoff(source_id, selected_root, *, root=ROOT, lookup=None):
    """Read-only project validation and source readiness. No project writes."""
    project = _root(selected_root)
    plan = plan_install(source_id, "codex", "project", root=root, lookup=lookup)
    local = plan["local_package"]
    return {
        "schema": PREPARE_SCHEMA,
        "status": "codex_install_handoff_preview_only",
        "agent": "codex",
        "scope": "project",
        "source_record_id": source_id,
        "skill_name": plan["skill_name"],
        "plan_id": plan["plan_id"],
        "pinned_repository": plan["repository"],
        "pinned_commit_sha": plan["pinned_version"]["commit_sha"],
        "license_spdx_recorded": plan["license_spdx"],
        "compatibility_claim": plan["compatibility"],
        "package_status": local["status"],
        "local_package_verified": local["integrity_ok"],
        "static_security_actionable_findings": local["actionable_findings"],
        "manual_source_review_required": True,
        "warnings": plan["warnings"],
        "eligible_for_bundle_preparation": plan["simulation_apply_eligible"],
        "requires_selected_git_project": True,
        "requires_interactive_tty_for_writes": True,
        "installation_performed": False,
        "third_party_skill_executed": False,
        "real_agent_paths_modified": False,
        "selected_project_root_verified": project.is_dir(),
    }


def _prepare_phrase(plan_id):
    return "PREPARE PRIVATE CODEX ZIP " + plan_id[:12].upper()


def install_from_explorer(
    source_id, selected_root, *, action="install", root=ROOT,
    lookup=None, reader=None, printer=print, download_if_missing=False,
):
    """Interactive CLI-only handoff; never callable from HTTP.

    Tests may inject input on disposable fixtures, but the production CLI must
    always have an actual local TTY before any private ZIP preparation/write.
    """
    if action not in ("install", "replace"):
        raise ValueError("Explicit action must be install or replace")
    # Refuse automation before any mutating operation, even if reader is injected.
    if not sys.stdin.isatty():
        raise ValueError("A local interactive TTY is required for any real Skill installation")
    review = inspect_handoff(source_id, selected_root, root=root, lookup=lookup)
    printer(json.dumps(review, ensure_ascii=False, indent=2))
    reader = reader or input
    if review["package_status"] == "not_downloaded" and download_if_missing:
        # Opt-in external I/O is *not* installation approval. Revalidate pins,
        # complete package and static scan again after fetching.
        phrase = ("DOWNLOAD PINNED SKILL " + source_id.upper()
                  + " " + review["pinned_commit_sha"][:12].upper())
        if reader("Type EXACTLY: " + phrase + "\n> ").strip() != phrase:
            raise ValueError("Pinned source download was not approved")
        from on_demand import download_skill
        downloaded = download_skill(source_id, root=root, execute=True)
        printer(json.dumps(downloaded, ensure_ascii=False, indent=2))
        review = inspect_handoff(source_id, selected_root, root=root, lookup=lookup)
        printer(json.dumps(review, ensure_ascii=False, indent=2))
    if not review["eligible_for_bundle_preparation"]:
        raise ValueError(
            "Pinned Skill is unavailable, incomplete, or has static security findings. "
            "Download/review the exact pinned package separately and retry; "
            "no Agent files were modified."
        )
    plan_id = review["plan_id"]
    # Validate destination state before creating the private ZIP.
    from install_bundle import _slug
    from skill_search import get_skill_by_id
    record = (lookup(source_id, root=root) if lookup is not None else
              get_skill_by_id(source_id, root=root))
    slug = _slug(record["source_path"], source_id)
    project = _root(selected_root)
    target, relative, state = _paths(project, slug)
    if action == "install" and (target.exists() or target.is_symlink()):
        raise ValueError("Skill destination occupied; install cannot overwrite it. "
                         "Choose --action replace explicitly after review.")
    if action == "replace" and (not target.is_dir() or target.is_symlink()):
        raise ValueError("Replacement requires a regular existing Skill directory")
    printer("Selected target: " + relative)
    printer("Source is pinned, but license/compatibility/safety still require human review.")
    try:
        verified = verify_private_bundle(plan_id, root=root)
        printer(json.dumps(verified, ensure_ascii=False, indent=2))
    except (FileNotFoundError, OSError):
        phrase = _prepare_phrase(plan_id)
        if reader("Type EXACTLY: " + phrase + "\n> ").strip() != phrase:
            raise ValueError("Private ZIP creation was not approved")
        made = prepare_private_bundle(
            source_id, "codex", "project", plan_id, root=root, lookup=lookup)
        printer(json.dumps(made, ensure_ascii=False, indent=2))
        verified = verify_private_bundle(plan_id, root=root)
        printer(json.dumps(verified, ensure_ascii=False, indent=2))

    if verified["plan_id"] != plan_id:
        raise ValueError("Private ZIP does not belong to selected Plan")
    preview = (
        preview_install(plan_id, project, bundle_root=root, lookup=lookup)
        if action == "install" else
        preview_replace(plan_id, project, bundle_root=root, lookup=lookup)
    )
    printer(json.dumps(preview, ensure_ascii=False, indent=2))
    if not preview.get("eligible_for_fresh_install", False) and action == "install":
        raise ValueError("Destination is not eligible; no Skill installation attempted")
    if not preview.get("eligible_for_replace", False) and action == "replace":
        raise ValueError("Destination is not eligible for replacement")
    printer("Review the exact plan, file count, target and retained Backup policy above.")
    printer("The installer will require its own exact interactive TTY confirmation.")
    if action == "install":
        result = install_fresh(
            plan_id, project, preview["state_binding_id"],
            bundle_root=root, lookup=lookup, reader=reader)
    else:
        result = replace_existing(
            plan_id, project, preview["state_binding_id"],
            bundle_root=root, lookup=lookup, reader=reader)
    return {
        "status": "codex_explorer_handoff_completed",
        "action": action,
        "result": result,
        "installed_by_existing_transactional_installer": True,
        "third_party_skill_executed": False,
        "user_profile_modified": False,
    }
