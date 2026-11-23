#!/usr/bin/env python3
"""Phase 51: browser-to-local-TTY handoff for Cursor and Claude Code projects.

No HTTP installation endpoint exists. Real writes require an explicit existing
Git project, pinned private ZIP, per-operation approval and host-scoped receipt.
"""
import json
import sys
from pathlib import Path

from codex_project_install import _root
from host_project_install import (
    HOSTS, _host, _paths, preview_install, preview_replace, install, replace,
)
from install_bundle import prepare_private_bundle, verify_private_bundle, _slug
from install_lifecycle import plan_install
from skill_search import ROOT, get_skill_by_id

SCHEMA = "gasl-project-host-wizard-v1"


def inspect_handoff(source_id,selected_root,host,*,root=ROOT,lookup=None):
    """Read-only, never prepares a ZIP or changes Agent directories."""
    _host(host)
    project=_root(selected_root)
    plan=plan_install(source_id,host,"project",root=root,lookup=lookup)
    local=plan["local_package"]
    return {
        "schema":SCHEMA,"status":"host_project_wizard_preview_only",
        "host":host,"scope":"project","source_record_id":source_id,
        "slug_preview":_slug(plan["source_path"],source_id),
        "plan_id":plan["plan_id"],
        "pinned_commit_sha":plan["pinned_version"]["commit_sha"],
        "package_status":local["status"],
        "package_integrity_verified":local["integrity_ok"],
        "static_security_findings":local["actionable_findings"],
        "can_prepare_zip":plan["simulation_apply_eligible"],
        "warnings":plan["warnings"],"license_spdx_recorded":plan["license_spdx"],
        "host_discovery_independently_verified":False,
        "requires_explicit_git_project":True,
        "requires_local_tty_confirmation":True,
        "project_root_valid":project.is_dir(),
        "skill_executed":False,"real_host_modified":False,
    }


def _prepare_phrase(host,plan_id):
    return "PREPARE "+host.upper()+" PRIVATE ZIP "+plan_id[:12].upper()


def _download_phrase(host,source_id,commit):
    return "DOWNLOAD "+host.upper()+" PINNED "+source_id.upper()+" "+commit[:12].upper()


def install_from_explorer(source_id,selected_root,host,*,action="install",
                          root=ROOT,lookup=None,reader=None,printer=print,
                          download_if_missing=False):
    """Explicit CLI flow. Tests inject fixture-only reader and monkeypatched TTY."""
    _host(host)
    if action not in ("install","replace"):
        raise ValueError("Only explicit install and replace actions are allowed")
    if not sys.stdin.isatty():
        raise ValueError("A local interactive TTY is required for real project changes")
    project=_root(selected_root)
    reader=reader or input
    report=inspect_handoff(source_id,project,host,root=root,lookup=lookup)
    printer(json.dumps(report,ensure_ascii=False,indent=2))
    if report["package_status"]=="not_downloaded" and download_if_missing:
        phrase=_download_phrase(host,source_id,report["pinned_commit_sha"])
        if reader("Type EXACTLY: "+phrase+"\n> ").strip()!=phrase:
            raise ValueError("Pinned download was not authorized")
        from on_demand import download_skill
        result=download_skill(source_id,root=root,execute=True)
        printer(json.dumps(result,ensure_ascii=False,indent=2))
        report=inspect_handoff(source_id,project,host,root=root,lookup=lookup)
        printer(json.dumps(report,ensure_ascii=False,indent=2))
    if not report["can_prepare_zip"]:
        raise ValueError("Pinned package missing, incomplete, modified or statically flagged")
    plan_id=report["plan_id"]
    # Refuse occupied/unmanaged targets before even preparing a new ZIP.
    record=(lookup(source_id,root=root) if lookup is not None
            else get_skill_by_id(source_id,root=root))
    slug=_slug(record["source_path"],source_id)
    target,relative,state=_paths(project,host,slug)
    if action=="install" and (target.exists() or target.is_symlink()):
        raise ValueError("Target occupied; install refuses to overwrite. Use explicit replace")
    if action=="replace" and (not target.is_dir() or target.is_symlink()):
        raise ValueError("Explicit replace requires an existing Skill directory")
    printer("Selected Host target: "+relative)
    printer("Publisher, license terms and Host compatibility require human review.")
    try:
        verified=verify_private_bundle(plan_id,root=root)
    except (FileNotFoundError,OSError):
        phrase=_prepare_phrase(host,plan_id)
        if reader("Type EXACTLY: "+phrase+"\n> ").strip()!=phrase:
            raise ValueError("Private ZIP creation was not approved")
        prepared=prepare_private_bundle(
            source_id,host,"project",plan_id,root=root,lookup=lookup)
        printer(json.dumps(prepared,ensure_ascii=False,indent=2))
        verified=verify_private_bundle(plan_id,root=root)
    if verified["plan_id"]!=plan_id:
        raise ValueError("Private ZIP Plan identity changed")
    printer(json.dumps(verified,ensure_ascii=False,indent=2))
    preview=(preview_install(plan_id,project,host,bundle_root=root,lookup=lookup)
             if action=="install" else
             preview_replace(plan_id,project,host,bundle_root=root,lookup=lookup))
    printer(json.dumps(preview,ensure_ascii=False,indent=2))
    printer("The transactional installer now requires its OWN exact local TTY phrase.")
    writer=install if action=="install" else replace
    result=writer(plan_id,project,host,preview["state_binding_id"],
                  bundle_root=root,lookup=lookup,reader=reader)
    return {
        "schema":SCHEMA,"status":"host_project_wizard_completed",
        "host":host,"scope":"project","action":action,
        "result":result,"user_profile_modified":False,
        "skill_executed":False,
        "host_discovery_independently_verified":False,
    }
