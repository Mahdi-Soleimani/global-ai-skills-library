#!/usr/bin/env python3
"""Phase 52: terminal-only current-user-profile Skill handoff for Codex, Cursor and Claude Code.

No HTTP installation endpoint exists. Real writes require the exact current
OS account HOME, pinned private ZIP and independent local TTY approvals.
"""
import json
import sys
from pathlib import Path

from user_profile_install import _root
from user_profile_install import (
    HOSTS, _host, _paths, preview_install, preview_replace, install, replace,
)
from install_bundle import prepare_private_bundle, verify_private_bundle, _slug
from install_lifecycle import plan_install
from skill_search import ROOT, get_skill_by_id

SCHEMA = "gasl-user-profile-wizard-v1"


def inspect_handoff(source_id,selected_root,host,*,root=ROOT,lookup=None):
    """Read-only, never prepares a ZIP or changes Agent directories."""
    _host(host)
    profile=_root(selected_root)
    plan=plan_install(source_id,host,"user",root=root,lookup=lookup)
    local=plan["local_package"]
    return {
        "schema":SCHEMA,"status":"host_user_wizard_preview_only",
        "host":host,"scope":"user","source_record_id":source_id,
        "slug_preview":_slug(plan["source_path"],source_id),
        "plan_id":plan["plan_id"],
        "pinned_commit_sha":plan["pinned_version"]["commit_sha"],
        "package_status":local["status"],
        "package_integrity_verified":local["integrity_ok"],
        "static_security_findings":local["actionable_findings"],
        "can_prepare_zip":plan["simulation_apply_eligible"],
        "warnings":plan["warnings"],"license_spdx_recorded":plan["license_spdx"],
        "host_discovery_independently_verified":False,
        "user_scope_affects_all_local_projects":True,
        "cursor_may_sync_to_cloud_agents":host=="cursor",
        "other_hosts_may_discover_user_skills":host in ("codex","claude-code"),
        "requires_current_os_home":True,
        "requires_local_tty_confirmation":True,
        "current_os_home_verified":profile.is_dir(),
        "skill_executed":False,"real_host_modified":False,
    }


def _prepare_phrase(host,plan_id):
    return "PREPARE USER-WIDE "+host.upper()+" PRIVATE ZIP "+plan_id[:12].upper()


def _download_phrase(host,source_id,commit):
    return "DOWNLOAD USER-WIDE "+host.upper()+" PINNED "+source_id.upper()+" "+commit[:12].upper()


def install_from_explorer(source_id,selected_root,host,*,action="install",
                          root=ROOT,lookup=None,reader=None,printer=print,
                          download_if_missing=False):
    """Explicit CLI flow. Tests inject fixture-only reader and monkeypatched TTY."""
    _host(host)
    if action not in ("install","replace"):
        raise ValueError("Only explicit install and replace actions are allowed")
    if not sys.stdin.isatty():
        raise ValueError("A local interactive TTY is required for real profile changes")
    profile=_root(selected_root)
    reader=reader or input
    report=inspect_handoff(source_id,profile,host,root=root,lookup=lookup)
    printer(json.dumps(report,ensure_ascii=False,indent=2))
    if report["package_status"]=="not_downloaded" and download_if_missing:
        phrase=_download_phrase(host,source_id,report["pinned_commit_sha"])
        if reader("Type EXACTLY: "+phrase+"\n> ").strip()!=phrase:
            raise ValueError("Pinned download was not authorized")
        from on_demand import download_skill
        result=download_skill(source_id,root=root,execute=True)
        printer(json.dumps(result,ensure_ascii=False,indent=2))
        report=inspect_handoff(source_id,profile,host,root=root,lookup=lookup)
        printer(json.dumps(report,ensure_ascii=False,indent=2))
    if not report["can_prepare_zip"]:
        raise ValueError("Pinned package missing, incomplete, modified or statically flagged")
    plan_id=report["plan_id"]
    # Refuse occupied/unmanaged targets before even preparing a new ZIP.
    record=(lookup(source_id,root=root) if lookup is not None
            else get_skill_by_id(source_id,root=root))
    slug=_slug(record["source_path"],source_id)
    target,relative,state=_paths(profile,host,slug)
    if action=="install" and (target.exists() or target.is_symlink()):
        raise ValueError("Target occupied; install refuses to overwrite. Use explicit replace")
    if action=="replace" and (not target.is_dir() or target.is_symlink()):
        raise ValueError("Explicit replace requires an existing Skill directory")
    printer("Selected Host target: "+relative)
    printer("GLOBAL USER PROFILE: this Skill may affect ALL local Agent projects.")
    if host=="cursor":
        printer("CURSOR WARNING: user Skills may sync to Cloud Agents when Sync Skills is enabled.")
    if host in ("codex","claude-code"):
        printer("DISCOVERY WARNING: Cursor may also discover Skills in other Host directories.")
    printer("Publisher, license terms and Host compatibility require human review.")
    try:
        verified=verify_private_bundle(plan_id,root=root)
    except (FileNotFoundError,OSError):
        phrase=_prepare_phrase(host,plan_id)
        if reader("Type EXACTLY: "+phrase+"\n> ").strip()!=phrase:
            raise ValueError("Private ZIP creation was not approved")
        prepared=prepare_private_bundle(
            source_id,host,"user",plan_id,root=root,lookup=lookup)
        printer(json.dumps(prepared,ensure_ascii=False,indent=2))
        verified=verify_private_bundle(plan_id,root=root)
    if verified["plan_id"]!=plan_id:
        raise ValueError("Private ZIP Plan identity changed")
    printer(json.dumps(verified,ensure_ascii=False,indent=2))
    preview=(preview_install(plan_id,profile,host,bundle_root=root,lookup=lookup)
             if action=="install" else
             preview_replace(plan_id,profile,host,bundle_root=root,lookup=lookup))
    printer(json.dumps(preview,ensure_ascii=False,indent=2))
    printer("The transactional installer now requires its OWN exact local TTY phrase.")
    writer=install if action=="install" else replace
    result=writer(plan_id,profile,host,preview["state_binding_id"],
                  bundle_root=root,lookup=lookup,reader=reader)
    return {
        "schema":SCHEMA,"status":"host_user_wizard_completed",
        "host":host,"scope":"user","action":action,
        "result":result,"user_profile_modified":True,
        "skill_executed":False,
        "host_discovery_independently_verified":False,
        "cursor_may_sync_to_cloud_agents":host=="cursor",
        "user_scope_affects_all_local_projects":True,
    }
