#!/usr/bin/env python3
"""Phase 51: transactional POSIX project installers for Cursor and Claude Code.

The verified ZIP reader / host format / target preflight are shared with the
Codex engine. All mutable GASL records are host-isolated. Third-party Skills
are never executed. No user-home installation is supported.
"""
import contextlib
import hashlib
import os
import re
import secrets
import sys
from pathlib import Path

from codex_project_install import (
    _root, _serialized, _sync, _new, _load, _mkdir_checked, _stage,
    _inventory_from_rows, _confirm, fcntl, _reject_other_codex_state,
)
from fixture_bundle_install import _inventory, _read_bundle, _remove_verified_dir, _check_list
from host_format_review import review_host_format
from host_target_preflight import _target_path, inspect_selected_target, verify_target_unchanged
from skill_search import ROOT
from transaction_file_lock import exclusive_lock_file, supported_platform, is_redirected

HOSTS = ("cursor", "claude-code")
SCHEMA = "gasl-project-multihost-v1"
HEX64 = re.compile(r"^[a-f0-9]{64}$")
TXID = re.compile(r"^[a-f0-9]{32}$")
SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def _host(host):
    if host not in HOSTS and not (os.name == "nt" and host == "codex"):
        raise ValueError("Only Cursor and Claude Code projects (plus Windows Codex) are supported")
    return host


def _paths(project, host, slug):
    _host(host)
    if not SLUG.fullmatch(str(slug)):
        raise ValueError("Unsafe project Skill folder")
    project = _root(project)
    if host == "codex":
        _reject_other_codex_state(project, slug, legacy=False)
    target, relative = _target_path(project, host, "project", slug)
    state = project/".gasl-managed"/"hosts"/host
    checks = [
        project/".gasl-managed", project/".gasl-managed"/"hosts",
        state, state/"receipts", state/"journals", state/"stage",
        state/"backups", state/"backups"/slug, state/"uninstalled",
    ]
    for path in checks:
        if is_redirected(path) or (path.exists() and not path.is_dir()):
            raise ValueError("Unsafe GASL host-isolated state directory")
    return target, relative, state


def _receipt(state, slug):
    return state/"receipts"/(slug+".json")


def _journal(state, slug):
    return state/"journals"/(slug+".json")


def _marker(state, slug):
    return state/"uninstalled"/(slug+".json")


def _backup(state, slug, backup_id):
    if not TXID.fullmatch(str(backup_id)):
        raise ValueError("Unsafe backup identifier")
    return state/"backups"/slug/backup_id


def _manifest(state, slug, backup_id):
    return _backup(state, slug, backup_id).with_suffix(".json")


def _id(value):
    if not TXID.fullmatch(str(value)):
        raise ValueError("Invalid transaction/backup identifier")
    return value


def _inventory_valid(items):
    _check_list(items)
    if not items or "SKILL.md" not in {item["path"] for item in items}:
        raise ValueError("Invalid Skill inventory: missing root SKILL.md")


def _receipt_valid(data, host, slug):
    if (not isinstance(data, dict) or data.get("schema") != SCHEMA
            or data.get("host") != host or data.get("scope") != "project"
            or data.get("slug") != slug
            or data.get("action") not in ("install", "replace", "restore", "reinstall")
            or not HEX64.fullmatch(str(data.get("plan_id")))
            or not HEX64.fullmatch(str(data.get("binding")))
            or not TXID.fullmatch(str(data.get("transaction")))):
        raise ValueError("Invalid host-scoped ownership receipt")
    _inventory_valid(data.get("files"))
    backups = data.get("backup_ids")
    if (not isinstance(backups, list) or len(backups) > 1000 or
            len(set(str(x) for x in backups)) != len(backups)
            or any(not TXID.fullmatch(str(x)) for x in backups)):
        raise ValueError("Invalid ownership backup history")
    if data["action"] in ("replace", "restore", "reinstall") and not backups:
        raise ValueError("Managed replacement/restore requires preserved backups")
    if data["action"] == "restore":
        if data.get("restored_backup_id") not in backups:
            raise ValueError("Unknown restoration source backup")
    if data["action"] == "reinstall" and data.get("reinstalled_backup_id") not in backups:
        raise ValueError("Unknown archived source backup")
    return data


def _manifest_valid(data, host, slug, backup_id):
    if (not isinstance(data, dict) or data.get("schema") != SCHEMA
            or data.get("host") != host or data.get("scope") != "project"
            or data.get("slug") != slug or data.get("backup_id") != backup_id):
        raise ValueError("Invalid host-scoped backup manifest")
    previous = _receipt_valid(data.get("previous_receipt"), host, slug)
    _inventory_valid(data.get("files"))
    if previous["files"] != data["files"]:
        raise ValueError("Backup file inventory does not match previous receipt")
    return data


def _history(state, host, slug, backup_ids, pending_backup_id=None):
    for index, backup_id in enumerate(backup_ids):
        manifest = _manifest_valid(_load(_manifest(state, slug, backup_id)),
                                   host, slug, backup_id)
        if manifest["previous_receipt"]["backup_ids"] != backup_ids[:index]:
            raise ValueError("Broken backup lineage")
        if _inventory(_backup(state, slug, backup_id)) != manifest["files"]:
            raise ValueError("Backup was modified or is incomplete")
    # No unrecognized backup in this Skill's state folder can be silently adopted.
    parent = state/"backups"/slug
    if parent.is_dir():
        expected = set(backup_ids) | {x+".json" for x in backup_ids}
        if pending_backup_id is not None:
            expected |= {pending_backup_id,pending_backup_id+".json"}
            # The crashed transaction may be between directory rename and
            # writing the manifest. Both incomplete states are valid to audit.
            observed = {x.name for x in parent.iterdir()}
            pending = {pending_backup_id,pending_backup_id+".json"}
            if not observed <= expected or not expected.difference(pending) <= observed:
                raise ValueError("Unowned or incomplete backup entries exist")
        elif {x.name for x in parent.iterdir()} != expected:
            raise ValueError("Unowned or incomplete backup entries exist")
    return list(backup_ids)


def _marker_valid(data, state, host, slug):
    if (not isinstance(data, dict) or data.get("schema") != SCHEMA
            or data.get("host") != host or data.get("scope") != "project"
            or data.get("slug") != slug or data.get("status") != "uninstalled_archive"
            or not TXID.fullmatch(str(data.get("archive_id")))):
        raise ValueError("Invalid uninstalled ownership marker")
    last = _receipt_valid(data.get("last_receipt"), host, slug)
    ids = data.get("backup_ids")
    if (not isinstance(ids, list) or ids != last["backup_ids"] + [data["archive_id"]]
            or len(set(ids)) != len(ids)):
        raise ValueError("Uninstall backup chain is inconsistent")
    _history(state, host, slug, ids)
    manifest = _manifest_valid(
        _load(_manifest(state, slug, data["archive_id"])), host, slug, data["archive_id"])
    if manifest["previous_receipt"] != last:
        raise ValueError("Last archived version does not match ownership marker")
    return data


def _read_state(project, host, slug):
    target, relative, state = _paths(project, host, slug)
    receipt_path, journal_path, marker_path = (_receipt(state,slug),
                                               _journal(state,slug), _marker(state,slug))
    for path in (receipt_path, journal_path, marker_path):
        if is_redirected(path):
            raise ValueError("Symlinked host transaction record")
    receipt = (_receipt_valid(_load(receipt_path),host,slug)
               if receipt_path.exists() else None)
    marker = (_marker_valid(_load(marker_path),state,host,slug)
              if marker_path.exists() else None)
    if receipt is not None and marker is not None:
        raise ValueError("Active ownership and uninstall marker cannot coexist")
    if receipt is not None:
        _history(state,host,slug,receipt["backup_ids"])
        if not target.is_dir() or target.is_symlink() or _inventory(target)!=receipt["files"]:
            raise ValueError("Managed Skill contents changed; refuse to modify")
    elif marker is None:
        parent=state/"backups"/slug
        if parent.is_dir() and any(parent.iterdir()):
            raise ValueError("Unowned backup history requires separate human reconciliation")
    if journal_path.exists():
        raise ValueError("Interrupted transaction requires explicit recover first")
    return target, relative, state, receipt, marker


def _binding(project, host, slug, receipt=None, marker=None, backup_id=None, target_files=None):
    target, relative, state = _paths(project,host,slug)
    if target_files is None:
        target_files = _inventory(target) if target.exists() and target.is_dir() else []
    ids=(receipt["backup_ids"] if receipt is not None else
         marker["backup_ids"] if marker is not None else [])
    manifests=[_load(_manifest(state,slug,ident)) for ident in ids]
    return hashlib.sha256(_serialized({
        "schema":SCHEMA, "host":host, "scope":"project",
        "target_sha256":hashlib.sha256(os.fsencode(str(target))).hexdigest(),
        "relative_target":relative, "target_files":target_files,
        "receipt":receipt, "uninstalled_marker":marker,
        "backup_manifest_evidence":manifests,
        "selected_backup":backup_id,
    })).hexdigest()


def _preview_bundle(plan_id, project, host, *, bundle_root=ROOT, lookup=None,
                    replace=False):
    _host(host)
    if not HEX64.fullmatch(str(plan_id)):
        raise ValueError("Exact Plan ID required")
    project = _root(project)
    review = review_host_format(plan_id, host, "project", root=bundle_root,lookup=lookup)
    if review["format_status"] != "simple_frontmatter_shape_detected":
        raise ValueError("Skill format requires review")
    slug, rows = _read_bundle(bundle_root,plan_id,host,"project")
    if slug != review["skill_name"]:
        raise ValueError("Pinned bundle slug does not match reviewed Skill name")
    target, relative, state, receipt, marker = _read_state(project,host,slug)
    preflight = inspect_selected_target(plan_id,host,"project",project,bundle_root=bundle_root)
    if marker is not None:
        raise ValueError("Archived uninstalled Skill must be explicitly reinstated first")
    if replace:
        if receipt is None or not target.is_dir() or target.is_symlink():
            raise ValueError("Replacement requires an unmodified GASL-owned Skill")
        if receipt["plan_id"] == plan_id:
            raise ValueError("Pinned Skill version is already active")
        eligible=True
    else:
        if (receipt is not None or target.exists() or is_redirected(target)):
            raise ValueError("Fresh install requires an unoccupied target; no overwrite")
        eligible=True
    return {
        "schema":SCHEMA, "status":"host_project_replace_preview" if replace
                            else "host_project_install_preview",
        "host":host, "scope":"project", "slug":slug, "plan_id":plan_id,
        "relative_target":relative, "file_count":len(rows),
        "state_binding_id":preflight["state_binding_id"],
        "backup_ids":receipt["backup_ids"] if receipt else [],
        "requires_human_tty":True, "eligible":eligible,
        "real_host_modified":False, "skill_executed":False,
    }


def preview_install(plan_id, project, host, *, bundle_root=ROOT, lookup=None):
    return _preview_bundle(plan_id,project,host,bundle_root=bundle_root,lookup=lookup)


def preview_replace(plan_id, project, host, *, bundle_root=ROOT, lookup=None):
    return _preview_bundle(plan_id,project,host,bundle_root=bundle_root,
                           lookup=lookup,replace=True)


@contextlib.contextmanager
def _lock(project, host, slug):
    if not supported_platform():
        raise ValueError("This installer needs Windows or POSIX filesystem locks")
    target, _, state = _paths(project,host,slug)
    for path in (target.parent.parent,target.parent,project/".gasl-managed",
                 project/".gasl-managed"/"hosts",state,state/"receipts",state/"journals",
                 state/"stage",state/"backups",state/"backups"/slug,state/"uninstalled"):
        if is_redirected(path):
            raise ValueError("Junction or symlink in project transaction paths")
        _mkdir_checked(path)
    lock=state/".lock"
    with contextlib.ExitStack() as stack:
        if host == "codex":
            # Use the old engine's coordination path as well as our own.
            # This is a cooperating local-process lock, not a distributed
            # cross-OS filesystem locking guarantee.
            stack.enter_context(exclusive_lock_file(state.parent.parent/".lock"))
            _reject_other_codex_state(_root(project), slug, legacy=False)
        stack.enter_context(exclusive_lock_file(lock))
        yield state


def _consent(text, reader=None):
    # Reader injection is for synthetic tests only. Production CLI always uses
    # standard local input and cannot approve writes through a non-TTY pipe.
    if not sys.stdin.isatty():
        raise ValueError("A local interactive TTY is required")
    _confirm(text,reader=reader)


def _phrase(action, host, slug, token, binding):
    return (action.upper()+" "+host.upper()+" "+slug.upper()+" "+
            str(token)[:12].upper()+" "+binding[:12].upper())


def _snapshot(state,host,slug,receipt,archive_id):
    return {
        "schema":SCHEMA,"host":host,"scope":"project","slug":slug,
        "backup_id":archive_id,"files":receipt["files"],
        "previous_receipt":receipt,
    }


def _write_journal(state,host,slug,operation,tx,new_receipt,previous_receipt,
                   *,backup_id=None,old_files=None,new_files=None,
                   selected_id=None,marker=None):
    data={"schema":SCHEMA,"host":host,"scope":"project","slug":slug,
          "operation":operation,"transaction":tx,"new_receipt":new_receipt,
          "previous_receipt":previous_receipt,"backup_id":backup_id,
          "old_files":old_files or [],"new_files":new_files or [],
          "selected_backup_id":selected_id,"marker":marker}
    _new(_journal(state,slug),data)
    return data


def _store_receipt(state,slug,record):
    _new(_receipt(state,slug),record)


def _finish_journal(state,slug):
    _journal(state,slug).unlink()
    _sync(state/"journals")


def _new_receipt(host,slug,operation,tx,plan_id,binding,files,ids,**extra):
    return {"schema":SCHEMA,"host":host,"scope":"project","slug":slug,
            "action":operation,"transaction":tx,"plan_id":plan_id,
            "binding":binding,"files":files,"backup_ids":ids,**extra}


def install(plan_id, project, host, binding, *, bundle_root=ROOT,lookup=None,reader=None):
    return _apply_bundle(plan_id,project,host,binding,bundle_root=bundle_root,
                         lookup=lookup,reader=reader,replace=False)


def replace(plan_id, project, host, binding, *, bundle_root=ROOT,lookup=None,reader=None):
    return _apply_bundle(plan_id,project,host,binding,bundle_root=bundle_root,
                         lookup=lookup,reader=reader,replace=True)


def _apply_bundle(plan_id,project,host,binding,*,bundle_root,lookup,reader,replace):
    project=_root(project)
    preview=(_preview_bundle(plan_id,project,host,bundle_root=bundle_root,
                             lookup=lookup,replace=replace))
    if binding!=preview["state_binding_id"]:
        raise ValueError("Stale target/ZIP binding")
    operation="replace" if replace else "install"
    _consent(_phrase(operation,host,preview["slug"],plan_id,binding),reader)
    slug=preview["slug"]
    with _lock(project,host,slug) as state:
        refreshed=_preview_bundle(plan_id,project,host,bundle_root=bundle_root,
                                  lookup=lookup,replace=replace)
        if refreshed["state_binding_id"]!=binding:
            raise ValueError("Target/ZIP changed after consent")
        verify_target_unchanged(plan_id,host,"project",project,binding,
                                bundle_root=bundle_root)
        target, _, state,previous,_=_read_state(project,host,slug)
        _,rows=_read_bundle(bundle_root,plan_id,host,"project")
        inventory=_inventory_from_rows(rows)
        _inventory_valid(inventory)
        tx=secrets.token_hex(16)
        stage=state/"stage"/tx
        backup_id=tx if replace else None
        for path in (stage,_backup(state,slug,tx),_manifest(state,slug,tx)):
            if path.exists() or path.is_symlink():
                raise ValueError("Transaction identifier collision")
        _stage(stage,rows)
        if _inventory(stage)!=inventory:
            raise ValueError("Staged pinned ZIP changed")
        if replace and _inventory(target)!=previous["files"]:
            raise ValueError("Managed Skill changed before replacement")
        ids=(previous["backup_ids"]+[tx]) if replace else []
        new=_new_receipt(host,slug,operation,tx,plan_id,binding,inventory,ids)
        _write_journal(state,host,slug,operation,tx,new,previous,
                       backup_id=backup_id,old_files=previous["files"] if previous else [],
                       new_files=inventory)
        if replace:
            target.rename(_backup(state,slug,tx))
            _sync(target.parent)
            if _inventory(_backup(state,slug,tx))!=previous["files"]:
                raise ValueError("Previous Skill changed during archiving")
            _new(_manifest(state,slug,tx),_snapshot(state,host,slug,previous,tx))
        if target.exists() or is_redirected(target):
            raise ValueError("Target occupied before activation")
        stage.rename(target)
        _sync(target.parent)
        if _inventory(target)!=inventory:
            raise ValueError("Installed files differ from verified ZIP")
        if replace:
            # Remove only the previously checked ownership receipt.
            existing=_receipt_valid(_load(_receipt(state,slug)),host,slug)
            if existing!=previous:
                raise ValueError("Ownership receipt changed during replacement")
            _receipt(state,slug).unlink()
        _store_receipt(state,slug,new)
        _finish_journal(state,slug)
    return {
        "status":"host_project_skill_replaced" if replace else "host_project_skill_installed",
        "host":host,"scope":"project","slug":slug,"plan_id":plan_id,
        "backup_id":backup_id,"file_count":len(inventory),
        "receipt_written":True,"real_project_files_modified":True,
        "skill_executed":False,
    }



def _backup_copy_rows(state,host,slug,backup_id):
    manifest=_manifest_valid(_load(_manifest(state,slug,backup_id)),
                             host,slug,backup_id)
    folder=_backup(state,slug,backup_id)
    if _inventory(folder)!=manifest["files"]:
        raise ValueError("Selected stored backup changed")
    rows=[]
    for item in manifest["files"]:
        data=(folder/item["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest()!=item["sha256"]:
            raise ValueError("Stored backup file differs from inventory")
        rows.append((slug,item["path"],data,item["sha256"]))
    return manifest, rows


def list_backups(host,project,slug):
    _host(host)
    project=_root(project)
    _,_,state,receipt,marker=_read_state(project,host,slug)
    active=receipt is not None
    if receipt is None and marker is None:
        raise ValueError("Skill has no managed history")
    ids=receipt["backup_ids"] if active else marker["backup_ids"]
    return {
        "schema":SCHEMA,"status":"host_project_backup_inventory",
        "host":host,"scope":"project","slug":slug,
        "active":active,"backups":[
            {"backup_id":ident,
             "plan_id":_manifest_valid(
                 _load(_manifest(state,slug,ident)),host,slug,ident
             )["previous_receipt"]["plan_id"]}
            for ident in ids
        ],
        "provenance":"local_record_only_not_independently_verified",
        "skill_executed":False,
    }


def _preview_state(host,project,slug,action,selected_id=None):
    _host(host)
    project=_root(project)
    target,relative,state,receipt,marker=_read_state(project,host,slug)
    if action=="restore":
        if receipt is None:
            raise ValueError("Restore requires active, unmodified GASL-owned Skill")
        if not TXID.fullmatch(str(selected_id)) or selected_id not in receipt["backup_ids"]:
            raise ValueError("Restore requires an existing owned backup identifier")
        chosen=_manifest_valid(_load(_manifest(state,slug,selected_id)),
                               host,slug,selected_id)
        if chosen["files"] == receipt["files"]:
            raise ValueError("Selected backup is identical to active Skill; no restore needed")
        selected_plan=chosen["previous_receipt"]["plan_id"]
    elif action=="uninstall":
        if receipt is None:
            raise ValueError("Uninstall requires an active GASL-owned Skill")
        selected_plan=receipt["plan_id"]
    elif action=="reinstall":
        if marker is None:
            raise ValueError("Reinstall requires retained GASL uninstall ownership")
        if target.exists() or is_redirected(target):
            raise ValueError("Archived reinstall target must be absent")
        if not TXID.fullmatch(str(selected_id)) or selected_id not in marker["backup_ids"]:
            raise ValueError("Reinstall requires a valid retained backup ID")
        chosen=_manifest_valid(_load(_manifest(state,slug,selected_id)),
                               host,slug,selected_id)
        selected_plan=chosen["previous_receipt"]["plan_id"]
    else:
        raise ValueError("Unknown backup lifecycle action")
    binding=_binding(project,host,slug,receipt,marker,selected_id)
    return {
        "schema":SCHEMA,"status":"host_project_"+action+"_preview",
        "host":host,"scope":"project","slug":slug,"relative_target":relative,
        "plan_id":selected_plan,"selected_backup_id":selected_id,
        "state_binding_id":binding,"backup_ids":(
            receipt["backup_ids"] if receipt else marker["backup_ids"]),
        "requires_human_tty":True,"real_host_modified":False,"skill_executed":False,
    }


def preview_restore(host,project,slug,backup_id):
    return _preview_state(host,project,slug,"restore",backup_id)


def preview_uninstall(host,project,slug):
    return _preview_state(host,project,slug,"uninstall")


def preview_reinstall(host,project,slug,backup_id):
    return _preview_state(host,project,slug,"reinstall",backup_id)


def _same_preview(host,project,slug,action,selected_id,binding):
    preview=_preview_state(host,project,slug,action,selected_id)
    if preview["state_binding_id"]!=binding:
        raise ValueError("Target/backup history changed since preflight")
    return preview


def restore(host,project,slug,backup_id,binding,*,reader=None):
    project=_root(project)
    preview=_same_preview(host,project,slug,"restore",backup_id,binding)
    _consent(_phrase("restore",host,slug,backup_id,binding),reader)
    with _lock(project,host,slug) as state:
        _same_preview(host,project,slug,"restore",backup_id,binding)
        target,_,state,previous,_=_read_state(project,host,slug)
        selected,rows=_backup_copy_rows(state,host,slug,backup_id)
        tx=secrets.token_hex(16)
        saved=_backup(state,slug,tx)
        if any(x.exists() or x.is_symlink() for x in
               (saved,_manifest(state,slug,tx),state/"stage"/tx)):
            raise ValueError("Transaction ID collision")
        stage=state/"stage"/tx
        _stage(stage,rows)
        if _inventory(stage)!=selected["files"]:
            raise ValueError("Selected restored version staging mismatch")
        new=_new_receipt(host,slug,"restore",tx,
                         selected["previous_receipt"]["plan_id"],binding,
                         selected["files"],previous["backup_ids"]+[tx],
                         restored_backup_id=backup_id)
        _write_journal(state,host,slug,"restore",tx,new,previous,
                       backup_id=tx,old_files=previous["files"],
                       new_files=selected["files"],selected_id=backup_id)
        if _inventory(target)!=previous["files"]:
            raise ValueError("Active Skill changed immediately before backup")
        target.rename(saved)
        _sync(target.parent)
        if _inventory(saved)!=previous["files"]:
            raise ValueError("Previous active version changed during backup")
        _new(_manifest(state,slug,tx),_snapshot(state,host,slug,previous,tx))
        if target.exists() or is_redirected(target):
            raise ValueError("Destination unexpectedly occupied during restoration")
        stage.rename(target)
        _sync(target.parent)
        if _inventory(target)!=selected["files"]:
            raise ValueError("Restored version differs from verified backup")
        if _load(_receipt(state,slug))!=previous:
            raise ValueError("Active receipt changed during restore")
        _receipt(state,slug).unlink()
        _store_receipt(state,slug,new)
        _finish_journal(state,slug)
    return {
        "status":"host_project_backup_restored",
        "host":host,"scope":"project","slug":slug,
        "selected_backup_id":backup_id,"preserved_previous_backup_id":tx,
        "retained_backup_ids":new["backup_ids"],
        "real_project_files_modified":True,"skill_executed":False,
    }


def uninstall(host,project,slug,binding,*,reader=None):
    project=_root(project)
    preview=_same_preview(host,project,slug,"uninstall",None,binding)
    _consent(_phrase("uninstall",host,slug,preview["plan_id"],binding),reader)
    with _lock(project,host,slug) as state:
        _same_preview(host,project,slug,"uninstall",None,binding)
        target,_,state,previous,_=_read_state(project,host,slug)
        tx=secrets.token_hex(16)
        archived=_backup(state,slug,tx)
        if any(x.exists() or x.is_symlink() for x in
               (archived,_manifest(state,slug,tx))):
            raise ValueError("Backup ID collision")
        marker={
            "schema":SCHEMA,"host":host,"scope":"project","slug":slug,
            "status":"uninstalled_archive","archive_id":tx,
            "backup_ids":previous["backup_ids"]+[tx],
            "last_receipt":previous,
        }
        _write_journal(state,host,slug,"uninstall",tx,None,previous,
                       backup_id=tx,old_files=previous["files"],marker=marker)
        if _inventory(target)!=previous["files"]:
            raise ValueError("Managed Skill changed immediately before archive")
        target.rename(archived)
        _sync(target.parent)
        if _inventory(archived)!=previous["files"]:
            raise ValueError("Uninstall archive differs from previous files")
        _new(_manifest(state,slug,tx),_snapshot(state,host,slug,previous,tx))
        _new(_marker(state,slug),marker)
        if _load(_receipt(state,slug))!=previous:
            raise ValueError("Active ownership changed before uninstall commit")
        _receipt(state,slug).unlink()
        _sync(state/"receipts")
        _finish_journal(state,slug)
    return {
        "status":"host_project_skill_uninstalled_archived",
        "host":host,"scope":"project","slug":slug,
        "archived_backup_id":tx,"retained_backup_ids":marker["backup_ids"],
        "real_project_files_modified":True,"skill_executed":False,
    }


def reinstall(host,project,slug,backup_id,binding,*,reader=None):
    project=_root(project)
    _same_preview(host,project,slug,"reinstall",backup_id,binding)
    _consent(_phrase("reinstall",host,slug,backup_id,binding),reader)
    with _lock(project,host,slug) as state:
        _same_preview(host,project,slug,"reinstall",backup_id,binding)
        target,_,state,_,marker=_read_state(project,host,slug)
        selected,rows=_backup_copy_rows(state,host,slug,backup_id)
        tx=secrets.token_hex(16)
        if (state/"stage"/tx).exists() or (state/"stage"/tx).is_symlink():
            raise ValueError("Staging collision")
        stage=state/"stage"/tx
        _stage(stage,rows)
        if _inventory(stage)!=selected["files"]:
            raise ValueError("Archived Skill staging mismatch")
        new=_new_receipt(host,slug,"reinstall",tx,
                         selected["previous_receipt"]["plan_id"],binding,
                         selected["files"],marker["backup_ids"],
                         reinstalled_backup_id=backup_id)
        _write_journal(state,host,slug,"reinstall",tx,new,None,
                       new_files=selected["files"],
                       selected_id=backup_id,marker=marker)
        if target.exists() or is_redirected(target):
            raise ValueError("Reinstall target appeared after consent")
        stage.rename(target)
        _sync(target.parent)
        if _inventory(target)!=selected["files"]:
            raise ValueError("Reinstalled backup differs from recorded inventory")
        _store_receipt(state,slug,new)
        if _load(_marker(state,slug))!=marker:
            raise ValueError("Uninstall marker unexpectedly changed")
        _marker(state,slug).unlink()
        _sync(state/"uninstalled")
        _finish_journal(state,slug)
    return {
        "status":"host_project_skill_reinstalled_from_archive",
        "host":host,"scope":"project","slug":slug,
        "selected_backup_id":backup_id,
        "retained_backup_ids":new["backup_ids"],
        "real_project_files_modified":True,"skill_executed":False,
    }



def _journal_valid(value, state, host, slug):
    """Check all encoded ownership and lineages before a recovery could mutate."""
    if (not isinstance(value,dict) or value.get("schema")!=SCHEMA
            or value.get("host")!=host or value.get("scope")!="project"
            or value.get("slug")!=slug or value.get("operation") not in
            ("install","replace","restore","uninstall","reinstall")
            or not TXID.fullmatch(str(value.get("transaction")))):
        raise ValueError("Invalid host transaction journal")
    operation=value["operation"]
    tx=value["transaction"]
    before=value.get("previous_receipt")
    after=value.get("new_receipt")
    if before is not None:
        before=_receipt_valid(before,host,slug)
    if after is not None:
        after=_receipt_valid(after,host,slug)
        if after["transaction"]!=tx or after["action"]!=operation:
            raise ValueError("Recovery receipt action/transaction mismatch")
    if value.get("old_files")!=(before["files"] if before else []):
        raise ValueError("Recovery journal old inventory mismatch")
    if value.get("new_files")!=(after["files"] if after else []):
        raise ValueError("Recovery journal new inventory mismatch")
    backup_id=value.get("backup_id")
    if operation in ("replace","restore","uninstall"):
        if before is None or backup_id!=tx:
            raise ValueError("Archiving transaction lacks prior ownership")
        _history(state,host,slug,before["backup_ids"],pending_backup_id=tx)
    elif backup_id is not None:
        raise ValueError("Unexpected archiving transaction")
    if operation=="install":
        if before is not None or after is None or after["backup_ids"] or value.get("marker") is not None:
            raise ValueError("Invalid fresh install journal")
    if operation=="replace":
        if (after is None or after["backup_ids"]!=before["backup_ids"]+[tx]
                or after["plan_id"]==before["plan_id"]):
            raise ValueError("Replacement journal does not extend ownership")
    if operation=="restore":
        selected_id=value.get("selected_backup_id")
        if (after is None or selected_id not in before["backup_ids"]
                or after["backup_ids"]!=before["backup_ids"]+[tx]
                or after.get("restored_backup_id")!=selected_id):
            raise ValueError("Restore journal has wrong backup chain")
        selected=_manifest_valid(_load(_manifest(state,slug,selected_id)),
                                 host,slug,selected_id)
        if (after["files"]!=selected["files"] or
                after["plan_id"]!=selected["previous_receipt"]["plan_id"]):
            raise ValueError("Restore journal disagrees with selected backup")
    if operation=="uninstall":
        marker=value.get("marker")
        if (after is not None or not isinstance(marker,dict)
                or marker.get("schema")!=SCHEMA or marker.get("host")!=host
                or marker.get("scope")!="project" or marker.get("slug")!=slug
                or marker.get("archive_id")!=tx
                or marker.get("status")!="uninstalled_archive"
                or marker.get("last_receipt")!=before
                or marker.get("backup_ids")!=before["backup_ids"]+[tx]):
            raise ValueError("Uninstall journal does not retain original ownership")
    if operation=="reinstall":
        marker=value.get("marker")
        if before is not None or after is None or not isinstance(marker,dict):
            raise ValueError("Reinstall journal lacks archive ownership")
        # A completed reinstall deletes the marker, but the journal retains
        # the exact original marker and verifies all its immutable backup IDs.
        _marker_valid(marker,state,host,slug)
        chosen=value.get("selected_backup_id")
        if (chosen not in marker["backup_ids"]
                or after["backup_ids"]!=marker["backup_ids"]
                or after.get("reinstalled_backup_id")!=chosen):
            raise ValueError("Reinstall journal selects an unowned backup")
        selected=_manifest_valid(_load(_manifest(state,slug,chosen)),
                                 host,slug,chosen)
        if (after["files"]!=selected["files"] or
                after["plan_id"]!=selected["previous_receipt"]["plan_id"]):
            raise ValueError("Reinstall journal differs from archived source")
    if operation!="uninstall" and value.get("marker") is not None and operation!="reinstall":
        raise ValueError("Unexpected ownership marker in journal")
    if operation not in ("restore","reinstall") and value.get("selected_backup_id") is not None:
        raise ValueError("Unexpected selected backup ID")
    return value


def recover(host,project,slug):
    """Complete a committed journal or undo only exact GASL-owned staged files.

    Never overwrites unexpected files, never guesses a source or alters another
    Host's directory. Returns a refusal and retains the journal on ambiguity.
    """
    project=_root(project)
    _host(host)
    with _lock(project,host,slug) as state:
        target,_,state=_paths(project,host,slug)
        path=_journal(state,slug)
        if is_redirected(path) or not path.is_file():
            raise ValueError("No safe pending transaction journal for recovery")
        data=_journal_valid(_load(path),state,host,slug)
        action=data["operation"]
        tx=data["transaction"]
        prev=data["previous_receipt"]
        after=data["new_receipt"]
        old=data["old_files"]
        new=data["new_files"]
        current_path=_receipt(state,slug)
        marker_path=_marker(state,slug)
        stage=state/"stage"/tx
        backup=_backup(state,slug,tx)
        manifest_path=_manifest(state,slug,tx)
        for entry in (target,stage,backup,manifest_path,current_path,marker_path):
            if entry.is_symlink():
                raise ValueError("Symlink found in interrupted project transaction")
        current=(_receipt_valid(_load(current_path),host,slug)
                 if current_path.exists() else None)
        recorded_marker=_load(marker_path) if marker_path.exists() else None
        if current not in (None,prev,after):
            raise ValueError("Another owner changed the receipt during recovery")
        if action=="reinstall":
            if recorded_marker is not None and recorded_marker!=data["marker"]:
                raise ValueError("Archived ownership marker changed")
        elif action=="uninstall":
            if recorded_marker is not None and recorded_marker!=data["marker"]:
                raise ValueError("Archived ownership marker changed")
        elif recorded_marker is not None:
            raise ValueError("Unexpected uninstall marker during recovery")

        current_inventory=_inventory(target) if target.exists() else None
        stage_inventory=_inventory(stage) if stage.exists() else None
        backup_inventory=_inventory(backup) if backup.exists() else None
        if stage_inventory is not None and stage_inventory!=new:
            raise ValueError("Interrupted staging directory was edited; refuse recovery")
        if (current_inventory is not None and
                current_inventory not in ((old if prev is not None else []),new)):
            raise ValueError("Interrupted Host target was edited; preserve it")
        if backup_inventory is not None and backup_inventory!=old:
            raise ValueError("Archived previous files were edited; preserve them")
        if manifest_path.exists():
            checked=_manifest_valid(_load(manifest_path),host,slug,tx)
            if checked!=_snapshot(state,host,slug,prev,tx):
                raise ValueError("Backup manifest changed during transaction")
        if backup_inventory is None and manifest_path.exists():
            raise ValueError("Interrupted backup manifest has no matching directory")

        # Commit recognized: never roll back already completed user-approved
        # transactions. Remove only the obsolete journal / owned marker.
        if action=="uninstall":
            committed=(current is None and current_inventory is None
                       and recorded_marker==data["marker"]
                       and backup_inventory==old and manifest_path.exists())
        else:
            committed=(after is not None and current==after
                       and current_inventory==new and stage_inventory is None
                       and (action not in ("replace","restore")
                            or (backup_inventory==old and manifest_path.exists())))
        if committed:
            if action=="reinstall" and recorded_marker is not None:
                marker_path.unlink()
                _sync(state/"uninstalled")
            _finish_journal(state,slug)
            _read_state(project,host,slug)
            return {"status":"host_project_committed_transaction_finalized",
                    "host":host,"scope":"project","action":action,"skill_executed":False}

        # All other states are treated as incomplete. Receipt cannot already
        # claim the new owner unless the full commit above checked out.
        if current==after and after is not None:
            raise ValueError("New receipt exists but committed inventory is incomplete")
        if action=="uninstall":
            if recorded_marker is not None and not manifest_path.exists():
                raise ValueError("Marker exists without a complete archived manifest")
            if current_inventory is not None and current_inventory!=old:
                raise ValueError("Uninstall target contains unowned files")
        if action in ("replace","restore","uninstall"):
            if backup_inventory is not None and current_inventory==old:
                raise ValueError("Active and archived previous Skill coexist")
            if current_inventory==new and action in ("replace","restore"):
                if backup_inventory!=old:
                    raise ValueError("Refuse to remove new target without old backup")
            if (current_inventory is None and backup_inventory is None and
                    action in ("replace","restore","uninstall")):
                raise ValueError("Both old target and archived previous Skill are missing")
            if current_inventory==new and action in ("replace","restore"):
                _remove_verified_dir(target,new)
                current_inventory=None
            if recorded_marker is not None and action=="uninstall":
                marker_path.unlink()
                _sync(state/"uninstalled")
            if backup_inventory is not None:
                if target.exists() or is_redirected(target):
                    raise ValueError("Original target path reappeared before restore")
                backup.rename(target)
                _sync(target.parent)
                _sync(backup.parent)
                if manifest_path.exists():
                    manifest_path.unlink()
                    _sync(manifest_path.parent)
            if current_path.exists():
                if _load(current_path)!=prev:
                    raise ValueError("Old ownership receipt changed before rollback")
            else:
                _new(current_path,prev)
            if _inventory(target)!=old:
                raise ValueError("Restored original Skill inventory failed check")
        elif action in ("install","reinstall"):
            if current is not None:
                raise ValueError("Unexpected ownership receipt during fresh/reinstall rollback")
            if current_inventory is not None:
                if current_inventory!=new:
                    raise ValueError("Refusing to remove user-edited activation")
                _remove_verified_dir(target,new)
        if stage.exists():
            _remove_verified_dir(stage,new)
        _finish_journal(state,slug)
        _read_state(project,host,slug)
        return {"status":"host_project_incomplete_transaction_rolled_back",
                "host":host,"scope":"project","action":action,
                "original_state_preserved":True,"skill_executed":False}
