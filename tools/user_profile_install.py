#!/usr/bin/env python3
"""Phase 54: isolated cross-platform current-user profile Skill transactions.

The verified ZIP reader / host format / target preflight are shared with the
Codex engine. All mutable GASL records are host-isolated. Third-party Skills
are never executed. Only the explicitly selected current OS account HOME may be modified after
exact local TTY approval. POSIX validates UID/passwd/mode; Windows validates
the process-token SID, GetUserProfileDirectoryW, non-elevated token and native
owner/DACL ACEs before any profile write.
"""
import contextlib
import hashlib
import os
import re
import secrets
import sys
from pathlib import Path

try:
    import pwd
except ImportError:
    pwd = None  # Windows uses its process token and native profile APIs.

from codex_project_install import (
    _serialized, _sync, _new, _load, _mkdir_checked, _stage,
    _inventory_from_rows, _confirm, fcntl,
)
from fixture_bundle_install import _inventory, _read_bundle, _remove_verified_dir, _check_list
from host_format_review import review_host_format
from host_target_preflight import _explicit_root, _target_path, inspect_selected_target, verify_target_unchanged
from skill_search import ROOT
from transaction_file_lock import is_redirected, exclusive_lock_file, supported_platform

HOSTS = ("codex", "cursor", "claude-code")
SCHEMA = "gasl-profile-multihost-v1"
HEX64 = re.compile(r"^[a-f0-9]{64}$")
TXID = re.compile(r"^[a-f0-9]{32}$")
SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def _root(selected):
    """A User-scope write may select only the current OS user's real HOME."""
    if os.name == "nt":
        if os.environ.get("GASL_ENABLE_WINDOWS_USER_PROFILE_CI") != "1":
            raise ValueError("Windows User Profile is disabled pending native SID/ACL CI acceptance")
        from windows_user_profile import (
            current_profile, verify_owned_path, assert_no_reparse_components,
        )
        assert_no_reparse_components(Path(selected))
        home = _explicit_root(selected)
        current = current_profile()
        if os.path.normcase(str(home)) != os.path.normcase(str(current["profile"])):
            raise ValueError("Selected profile must equal the current Windows token profile")
        if current["elevated"]:
            raise ValueError("Refusing elevated Windows token for User Profile installation")
        verify_owned_path(home, current["sid"], directory=True)
        return home
    if os.name != "posix" or fcntl is None or pwd is None:
        raise ValueError("User profile installer requires a supported OS account and filesystem lock")
    if os.getuid() == 0 or os.geteuid() != os.getuid():
        raise ValueError("Refusing root/elevated account installation")
    home = _explicit_root(selected)
    actual = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve(strict=True)
    exported = Path.home().resolve(strict=True)
    if home != actual or home != exported:
        raise ValueError("Selected profile must equal current OS account HOME")
    info = home.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o002:
        raise ValueError("Selected user profile ownership/permissions unsafe")
    return home


def _profile_identity(profile):
    profile = Path(profile).resolve(strict=True)
    if os.name == "nt":
        from windows_user_profile import profile_identity
        return profile_identity(profile)
    info = profile.stat()
    return hashlib.sha256(_serialized({
        "uid": os.getuid(), "dev": info.st_dev, "inode": info.st_ino,
        "home": str(profile), "scope": "user",
    })).hexdigest()


def _windows_sid():
    if os.name != "nt":
        return None
    from windows_user_profile import _token_identity
    return _token_identity()["sid"]


def _verify_windows_path(path, *, directory=None, sid=None):
    if os.name == "nt":
        from windows_user_profile import verify_owned_path
        return verify_owned_path(path, sid or _windows_sid(), directory=directory)
    return None


def _verify_windows_tree(path):
    if os.name == "nt":
        from windows_user_profile import verify_owned_tree
        return verify_owned_tree(path, _windows_sid())
    return None


def _write_record(path, data):
    _new(path, data)
    _verify_windows_path(path, directory=False)


def _host(host):
    if host not in HOSTS:
        raise ValueError("Only Codex, Cursor and Claude Code user Skills are supported")
    return host


def _paths(profile, host, slug):
    _host(host)
    if not SLUG.fullmatch(str(slug)):
        raise ValueError("Unsafe profile Skill folder")
    profile = _root(profile)
    target, relative = _target_path(profile, host, "user", slug)
    state = profile/".gasl-managed"/"user"/"hosts"/host
    sid = _windows_sid() if os.name == "nt" else None
    if sid is not None:
        _verify_windows_path(profile, directory=True, sid=sid)
    checks = [
        profile/".gasl-managed", profile/".gasl-managed"/"user",
        profile/".gasl-managed"/"user"/"hosts",
        state, state/"receipts", state/"journals", state/"stage",
        state/"backups", state/"backups"/slug, state/"uninstalled",
    ]
    for path in checks:
        if is_redirected(path) or (path.exists() and not path.is_dir()):
            raise ValueError("Unsafe GASL user-profile state directory")
        if path.exists():
            if os.name == "nt":
                _verify_windows_path(path, directory=True)
            else:
                info = path.stat()
                if info.st_uid != os.getuid() or info.st_mode & 0o002:
                    raise ValueError("User-profile state has unsafe owner/permissions")
    # Host-level ancestors are not under GASL's exclusive control; require
    # current-account ownership and safe Windows ACLs before modifying them.
    for candidate in (target.parent.parent, target.parent):
        if candidate.exists():
            if os.name == "nt":
                _verify_windows_path(candidate, directory=True)
            else:
                info = candidate.stat()
                if info.st_uid != os.getuid() or info.st_mode & 0o002:
                    raise ValueError("Agent user Skill directory has unsafe owner/permissions")
    # State records and backup contents are also owned data, not merely paths.
    if os.name == "nt" and state.is_dir():
        for entry in state.rglob("*"):
            if is_redirected(entry) or not (entry.is_file() or entry.is_dir()):
                raise ValueError("Unsafe Windows user-profile state entry")
            _verify_windows_path(entry, directory=entry.is_dir(), sid=sid)
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
            or data.get("host") != host or data.get("scope") != "user"
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
    if not HEX64.fullmatch(str(data.get("profile_identity"))):
        raise ValueError("Missing user profile owner binding")
    return data


def _manifest_valid(data, host, slug, backup_id):
    if (not isinstance(data, dict) or data.get("schema") != SCHEMA
            or data.get("host") != host or data.get("scope") != "user"
            or data.get("slug") != slug or data.get("backup_id") != backup_id):
        raise ValueError("Invalid host-scoped backup manifest")
    previous = _receipt_valid(data.get("previous_receipt"), host, slug)
    if data.get("profile_identity") != previous["profile_identity"]:
        raise ValueError("Backup manifest is owned by a different profile")
    _inventory_valid(data.get("files"))
    if previous["files"] != data["files"]:
        raise ValueError("Backup file inventory does not match previous receipt")
    return data


def _history(state, host, slug, backup_ids, pending_backup_id=None):
    for index, backup_id in enumerate(backup_ids):
        manifest = _manifest_valid(_load(_manifest(state, slug, backup_id)),
                                   host, slug, backup_id)
        if manifest["previous_receipt"]["profile_identity"]!=_profile_identity(state.parents[3]):
            raise ValueError("Archived Skill belongs to a different OS profile")
        if manifest["previous_receipt"]["backup_ids"] != backup_ids[:index]:
            raise ValueError("Broken backup lineage")
        if _inventory(_backup(state, slug, backup_id)) != manifest["files"]:
            raise ValueError("Backup was modified or is incomplete")
        _verify_windows_tree(_backup(state, slug, backup_id))
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
            or data.get("host") != host or data.get("scope") != "user"
            or data.get("slug") != slug or data.get("status") != "uninstalled_archive"
            or not TXID.fullmatch(str(data.get("archive_id")))):
        raise ValueError("Invalid uninstalled ownership marker")
    if data.get("profile_identity")!=_profile_identity(state.parents[3]):
        raise ValueError("Uninstall marker has wrong profile identity")
    last = _receipt_valid(data.get("last_receipt"), host, slug)
    if last["profile_identity"]!=data["profile_identity"]:
        raise ValueError("Uninstall history has different profile identity")
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


def _read_state(profile, host, slug):
    target, relative, state = _paths(profile, host, slug)
    receipt_path, journal_path, marker_path = (_receipt(state,slug),
                                               _journal(state,slug), _marker(state,slug))
    for path in (receipt_path, journal_path, marker_path):
        if is_redirected(path):
            raise ValueError("Symlinked host transaction record")
    receipt = (_receipt_valid(_load(receipt_path),host,slug)
               if receipt_path.exists() else None)
    marker = (_marker_valid(_load(marker_path),state,host,slug)
              if marker_path.exists() else None)
    identity=_profile_identity(profile)
    if receipt is not None and receipt["profile_identity"]!=identity:
        raise ValueError("Active Skill owned by a different user profile")
    if marker is not None and marker["profile_identity"]!=identity:
        raise ValueError("Archived Skill owned by a different user profile")
    if receipt is not None and marker is not None:
        raise ValueError("Active ownership and uninstall marker cannot coexist")
    if receipt is not None:
        _history(state,host,slug,receipt["backup_ids"])
        if not target.is_dir() or is_redirected(target) or _inventory(target)!=receipt["files"]:
            raise ValueError("Managed Skill contents changed; refuse to modify")
        _verify_windows_tree(target)
    elif marker is None:
        parent=state/"backups"/slug
        if parent.is_dir() and any(parent.iterdir()):
            raise ValueError("Unowned backup history requires separate human reconciliation")
    if journal_path.exists():
        raise ValueError("Interrupted transaction requires explicit recover first")
    return target, relative, state, receipt, marker


def _binding(profile, host, slug, receipt=None, marker=None, backup_id=None, target_files=None):
    target, relative, state = _paths(profile,host,slug)
    if target_files is None:
        target_files = _inventory(target) if target.exists() and target.is_dir() else []
    ids=(receipt["backup_ids"] if receipt is not None else
         marker["backup_ids"] if marker is not None else [])
    manifests=[_load(_manifest(state,slug,ident)) for ident in ids]
    return hashlib.sha256(_serialized({
        "schema":SCHEMA, "host":host, "scope":"user",
        "target_sha256":hashlib.sha256(os.fsencode(str(target))).hexdigest(),
        "relative_target":relative, "target_files":target_files,
        "receipt":receipt, "uninstalled_marker":marker,
        "profile_identity":_profile_identity(profile),
        "backup_manifest_evidence":manifests,
        "selected_backup":backup_id,
    })).hexdigest()


def _preview_bundle(plan_id, profile, host, *, bundle_root=ROOT, lookup=None,
                    replace=False):
    _host(host)
    if not HEX64.fullmatch(str(plan_id)):
        raise ValueError("Exact Plan ID required")
    profile = _root(profile)
    review = review_host_format(plan_id, host, "user", root=bundle_root,lookup=lookup)
    if review["format_status"] != "simple_frontmatter_shape_detected":
        raise ValueError("Skill format requires review")
    slug, rows = _read_bundle(bundle_root,plan_id,host,"user")
    if slug != review["skill_name"]:
        raise ValueError("Pinned bundle slug does not match reviewed Skill name")
    target, relative, state, receipt, marker = _read_state(profile,host,slug)
    preflight = inspect_selected_target(plan_id,host,"user",profile,bundle_root=bundle_root)
    if marker is not None:
        raise ValueError("Archived uninstalled Skill must be explicitly reinstated first")
    if replace:
        if receipt is None or not target.is_dir() or is_redirected(target):
            raise ValueError("Replacement requires an unmodified GASL-owned Skill")
        if receipt["plan_id"] == plan_id:
            raise ValueError("Pinned Skill version is already active")
        eligible=True
    else:
        if (receipt is not None or target.exists() or is_redirected(target)):
            raise ValueError("Fresh install requires an unoccupied target; no overwrite")
        eligible=True
    return {
        "schema":SCHEMA, "status":"host_user_replace_preview" if replace
                            else "host_user_install_preview",
        "host":host, "scope":"user", "slug":slug, "plan_id":plan_id,
        "relative_target":relative, "file_count":len(rows),
        "state_binding_id":preflight["state_binding_id"],
        "backup_ids":receipt["backup_ids"] if receipt else [],
        "requires_human_tty":True, "eligible":eligible,
        "user_scope_affects_all_local_projects":True,
        "cursor_may_sync_to_cloud_agents":host=="cursor",
        "other_hosts_may_discover_user_skills":host in ("codex","claude-code"),
        "real_host_modified":False, "skill_executed":False,
    }


def preview_install(plan_id, profile, host, *, bundle_root=ROOT, lookup=None):
    return _preview_bundle(plan_id,profile,host,bundle_root=bundle_root,lookup=lookup)


def preview_replace(plan_id, profile, host, *, bundle_root=ROOT, lookup=None):
    return _preview_bundle(plan_id,profile,host,bundle_root=bundle_root,
                           lookup=lookup,replace=True)


@contextlib.contextmanager
def _lock(profile, host, slug):
    if not supported_platform():
        raise ValueError("User Profile transactions require POSIX or Windows file locking")
    target, _, state = _paths(profile, host, slug)
    for path in (target.parent.parent, target.parent, profile/".gasl-managed",
                 profile/".gasl-managed"/"user",
                 profile/".gasl-managed"/"user"/"hosts", state, state/"receipts",
                 state/"journals", state/"stage", state/"backups",
                 state/"backups"/slug, state/"uninstalled"):
        _mkdir_checked(path)
        _verify_windows_path(path, directory=True)
    lock = state/".lock"
    with exclusive_lock_file(lock):
        _verify_windows_path(lock, directory=False)
        yield state


def _consent(text, reader=None):
    # Reader injection is for synthetic tests only. Production CLI always uses
    # standard local input and cannot approve writes through a non-TTY pipe.
    if not sys.stdin.isatty():
        raise ValueError("A local interactive TTY is required")
    _confirm(text,reader=reader)


def _phrase(action, host, slug, token, binding):
    caution=(" CURSOR-SYNC-RISK" if host=="cursor" else "")
    return (action.upper()+" USER PROFILE ALL PROJECTS "+host.upper()+
            caution+" "+slug.upper()+" "+
            str(token)[:12].upper()+" "+binding[:12].upper())


def _snapshot(state,host,slug,receipt,archive_id):
    return {
        "schema":SCHEMA,"host":host,"scope":"user","slug":slug,
        "backup_id":archive_id,"files":receipt["files"],
        "profile_identity":receipt["profile_identity"],
        "previous_receipt":receipt,
    }


def _write_journal(state,host,slug,operation,tx,new_receipt,previous_receipt,
                   *,backup_id=None,old_files=None,new_files=None,
                   selected_id=None,marker=None):
    data={"schema":SCHEMA,"host":host,"scope":"user","slug":slug,
          "operation":operation,"transaction":tx,"new_receipt":new_receipt,
          "previous_receipt":previous_receipt,"backup_id":backup_id,
          "old_files":old_files or [],"new_files":new_files or [],
          "selected_backup_id":selected_id,"marker":marker,
          "profile_identity":_profile_identity(state.parents[3])}
    _write_record(_journal(state,slug),data)
    return data


def _store_receipt(state,slug,record):
    _write_record(_receipt(state,slug),record)


def _finish_journal(state,slug):
    _journal(state,slug).unlink()
    _sync(state/"journals")


def _new_receipt(host,slug,operation,tx,plan_id,binding,files,ids,
                 *,profile_identity,**extra):
    if not HEX64.fullmatch(str(profile_identity)):
        raise ValueError("New user receipt requires an exact account binding")
    return {"schema":SCHEMA,"host":host,"scope":"user","slug":slug,
            "action":operation,"transaction":tx,"plan_id":plan_id,
            "binding":binding,"files":files,"backup_ids":ids,
            "profile_identity":profile_identity,**extra}


def install(plan_id, profile, host, binding, *, bundle_root=ROOT,lookup=None,reader=None):
    return _apply_bundle(plan_id,profile,host,binding,bundle_root=bundle_root,
                         lookup=lookup,reader=reader,replace=False)


def replace(plan_id, profile, host, binding, *, bundle_root=ROOT,lookup=None,reader=None):
    return _apply_bundle(plan_id,profile,host,binding,bundle_root=bundle_root,
                         lookup=lookup,reader=reader,replace=True)


def _apply_bundle(plan_id,profile,host,binding,*,bundle_root,lookup,reader,replace):
    profile=_root(profile)
    preview=(_preview_bundle(plan_id,profile,host,bundle_root=bundle_root,
                             lookup=lookup,replace=replace))
    if binding!=preview["state_binding_id"]:
        raise ValueError("Stale target/ZIP binding")
    operation="replace" if replace else "install"
    _consent(_phrase(operation,host,preview["slug"],plan_id,binding),reader)
    slug=preview["slug"]
    with _lock(profile,host,slug) as state:
        refreshed=_preview_bundle(plan_id,profile,host,bundle_root=bundle_root,
                                  lookup=lookup,replace=replace)
        if refreshed["state_binding_id"]!=binding:
            raise ValueError("Target/ZIP changed after consent")
        verify_target_unchanged(plan_id,host,"user",profile,binding,
                                bundle_root=bundle_root)
        target, _, state,previous,_=_read_state(profile,host,slug)
        _,rows=_read_bundle(bundle_root,plan_id,host,"user")
        inventory=_inventory_from_rows(rows)
        _inventory_valid(inventory)
        tx=secrets.token_hex(16)
        stage=state/"stage"/tx
        backup_id=tx if replace else None
        for path in (stage,_backup(state,slug,tx),_manifest(state,slug,tx)):
            if path.exists() or is_redirected(path):
                raise ValueError("Transaction identifier collision")
        _stage(stage,rows)
        if _inventory(stage)!=inventory:
            raise ValueError("Staged pinned ZIP changed")
        _verify_windows_tree(stage)
        if replace and _inventory(target)!=previous["files"]:
            raise ValueError("Managed Skill changed before replacement")
        ids=(previous["backup_ids"]+[tx]) if replace else []
        new=_new_receipt(host,slug,operation,tx,plan_id,binding,inventory,ids,
                         profile_identity=_profile_identity(profile))
        _write_journal(state,host,slug,operation,tx,new,previous,
                       backup_id=backup_id,old_files=previous["files"] if previous else [],
                       new_files=inventory)
        if replace:
            target.rename(_backup(state,slug,tx))
            _sync(target.parent)
            if _inventory(_backup(state,slug,tx))!=previous["files"]:
                raise ValueError("Previous Skill changed during archiving")
            _verify_windows_tree(_backup(state,slug,tx))
            _write_record(_manifest(state,slug,tx),_snapshot(state,host,slug,previous,tx))
        if target.exists() or is_redirected(target):
            raise ValueError("Target occupied before activation")
        stage.rename(target)
        _sync(target.parent)
        if _inventory(target)!=inventory:
            raise ValueError("Installed files differ from verified ZIP")
        _verify_windows_tree(target)
        if replace:
            # Remove only the previously checked ownership receipt.
            existing=_receipt_valid(_load(_receipt(state,slug)),host,slug)
            if existing!=previous:
                raise ValueError("Ownership receipt changed during replacement")
            _receipt(state,slug).unlink()
        _store_receipt(state,slug,new)
        _finish_journal(state,slug)
    return {
        "status":"host_user_skill_replaced" if replace else "host_user_skill_installed",
        "host":host,"scope":"user","slug":slug,"plan_id":plan_id,
        "backup_id":backup_id,"file_count":len(inventory),
        "receipt_written":True,"real_user_profile_files_modified":True,
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


def list_backups(host,profile,slug):
    _host(host)
    profile=_root(profile)
    _,_,state,receipt,marker=_read_state(profile,host,slug)
    active=receipt is not None
    if receipt is None and marker is None:
        raise ValueError("Skill has no managed history")
    ids=receipt["backup_ids"] if active else marker["backup_ids"]
    return {
        "schema":SCHEMA,"status":"host_user_backup_inventory",
        "host":host,"scope":"user","slug":slug,
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


def _preview_state(host,profile,slug,action,selected_id=None):
    _host(host)
    profile=_root(profile)
    target,relative,state,receipt,marker=_read_state(profile,host,slug)
    if action=="restore":
        if receipt is None:
            raise ValueError("Restore requires active, unmodified GASL-owned Skill")
        if not TXID.fullmatch(str(selected_id)) or selected_id not in receipt["backup_ids"]:
            raise ValueError("Restore requires an existing owned backup identifier")
        chosen=_manifest_valid(_load(_manifest(state,slug,selected_id)),
                               host,slug,selected_id)
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
    binding=_binding(profile,host,slug,receipt,marker,selected_id)
    return {
        "schema":SCHEMA,"status":"host_user_"+action+"_preview",
        "host":host,"scope":"user","slug":slug,"relative_target":relative,
        "plan_id":selected_plan,"selected_backup_id":selected_id,
        "state_binding_id":binding,"backup_ids":(
            receipt["backup_ids"] if receipt else marker["backup_ids"]),
        "requires_human_tty":True,"real_host_modified":False,"skill_executed":False,
        "user_scope_affects_all_local_projects":True,
        "cursor_may_sync_to_cloud_agents":host=="cursor",
    }


def preview_restore(host,profile,slug,backup_id):
    return _preview_state(host,profile,slug,"restore",backup_id)


def preview_uninstall(host,profile,slug):
    return _preview_state(host,profile,slug,"uninstall")


def preview_reinstall(host,profile,slug,backup_id):
    return _preview_state(host,profile,slug,"reinstall",backup_id)


def _same_preview(host,profile,slug,action,selected_id,binding):
    preview=_preview_state(host,profile,slug,action,selected_id)
    if preview["state_binding_id"]!=binding:
        raise ValueError("Target/backup history changed since preflight")
    return preview


def restore(host,profile,slug,backup_id,binding,*,reader=None):
    profile=_root(profile)
    preview=_same_preview(host,profile,slug,"restore",backup_id,binding)
    _consent(_phrase("restore",host,slug,backup_id,binding),reader)
    with _lock(profile,host,slug) as state:
        _same_preview(host,profile,slug,"restore",backup_id,binding)
        target,_,state,previous,_=_read_state(profile,host,slug)
        selected,rows=_backup_copy_rows(state,host,slug,backup_id)
        tx=secrets.token_hex(16)
        saved=_backup(state,slug,tx)
        if any(x.exists() or is_redirected(x) for x in
               (saved,_manifest(state,slug,tx),state/"stage"/tx)):
            raise ValueError("Transaction ID collision")
        stage=state/"stage"/tx
        _stage(stage,rows)
        if _inventory(stage)!=selected["files"]:
            raise ValueError("Selected restored version staging mismatch")
        _verify_windows_tree(stage)
        new=_new_receipt(host,slug,"restore",tx,
                         selected["previous_receipt"]["plan_id"],binding,
                         selected["files"],previous["backup_ids"]+[tx],
                         profile_identity=_profile_identity(profile),
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
        _verify_windows_tree(saved)
        _write_record(_manifest(state,slug,tx),_snapshot(state,host,slug,previous,tx))
        if target.exists() or is_redirected(target):
            raise ValueError("Destination unexpectedly occupied during restoration")
        stage.rename(target)
        _sync(target.parent)
        if _inventory(target)!=selected["files"]:
            raise ValueError("Restored version differs from verified backup")
        _verify_windows_tree(target)
        if _load(_receipt(state,slug))!=previous:
            raise ValueError("Active receipt changed during restore")
        _receipt(state,slug).unlink()
        _store_receipt(state,slug,new)
        _finish_journal(state,slug)
    return {
        "status":"host_user_backup_restored",
        "host":host,"scope":"user","slug":slug,
        "selected_backup_id":backup_id,"preserved_previous_backup_id":tx,
        "retained_backup_ids":new["backup_ids"],
        "real_user_profile_files_modified":True,"skill_executed":False,
    }


def uninstall(host,profile,slug,binding,*,reader=None):
    profile=_root(profile)
    preview=_same_preview(host,profile,slug,"uninstall",None,binding)
    _consent(_phrase("uninstall",host,slug,preview["plan_id"],binding),reader)
    with _lock(profile,host,slug) as state:
        _same_preview(host,profile,slug,"uninstall",None,binding)
        target,_,state,previous,_=_read_state(profile,host,slug)
        tx=secrets.token_hex(16)
        archived=_backup(state,slug,tx)
        if any(x.exists() or is_redirected(x) for x in
               (archived,_manifest(state,slug,tx))):
            raise ValueError("Backup ID collision")
        marker={
            "schema":SCHEMA,"host":host,"scope":"user","slug":slug,
            "status":"uninstalled_archive","archive_id":tx,
            "backup_ids":previous["backup_ids"]+[tx],
            "last_receipt":previous,
            "profile_identity":_profile_identity(profile),
        }
        _write_journal(state,host,slug,"uninstall",tx,None,previous,
                       backup_id=tx,old_files=previous["files"],marker=marker)
        if _inventory(target)!=previous["files"]:
            raise ValueError("Managed Skill changed immediately before archive")
        _verify_windows_tree(target)
        target.rename(archived)
        _sync(target.parent)
        if _inventory(archived)!=previous["files"]:
            raise ValueError("Uninstall archive differs from previous files")
        _verify_windows_tree(archived)
        _write_record(_manifest(state,slug,tx),_snapshot(state,host,slug,previous,tx))
        _write_record(_marker(state,slug),marker)
        if _load(_receipt(state,slug))!=previous:
            raise ValueError("Active ownership changed before uninstall commit")
        _receipt(state,slug).unlink()
        _sync(state/"receipts")
        _finish_journal(state,slug)
    return {
        "status":"host_user_skill_uninstalled_archived",
        "host":host,"scope":"user","slug":slug,
        "archived_backup_id":tx,"retained_backup_ids":marker["backup_ids"],
        "real_user_profile_files_modified":True,"skill_executed":False,
    }


def reinstall(host,profile,slug,backup_id,binding,*,reader=None):
    profile=_root(profile)
    _same_preview(host,profile,slug,"reinstall",backup_id,binding)
    _consent(_phrase("reinstall",host,slug,backup_id,binding),reader)
    with _lock(profile,host,slug) as state:
        _same_preview(host,profile,slug,"reinstall",backup_id,binding)
        target,_,state,_,marker=_read_state(profile,host,slug)
        selected,rows=_backup_copy_rows(state,host,slug,backup_id)
        tx=secrets.token_hex(16)
        if (state/"stage"/tx).exists() or is_redirected(state/"stage"/tx):
            raise ValueError("Staging collision")
        stage=state/"stage"/tx
        _stage(stage,rows)
        if _inventory(stage)!=selected["files"]:
            raise ValueError("Archived Skill staging mismatch")
        _verify_windows_tree(stage)
        new=_new_receipt(host,slug,"reinstall",tx,
                         selected["previous_receipt"]["plan_id"],binding,
                         selected["files"],marker["backup_ids"],
                         profile_identity=_profile_identity(profile),
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
        _verify_windows_tree(target)
        _store_receipt(state,slug,new)
        if _load(_marker(state,slug))!=marker:
            raise ValueError("Uninstall marker unexpectedly changed")
        _marker(state,slug).unlink()
        _sync(state/"uninstalled")
        _finish_journal(state,slug)
    return {
        "status":"host_user_skill_reinstalled_from_archive",
        "host":host,"scope":"user","slug":slug,
        "selected_backup_id":backup_id,
        "retained_backup_ids":new["backup_ids"],
        "real_user_profile_files_modified":True,"skill_executed":False,
    }



def _journal_valid(value, state, host, slug):
    """Check all encoded ownership and lineages before a recovery could mutate."""
    if (not isinstance(value,dict) or value.get("schema")!=SCHEMA
            or value.get("host")!=host or value.get("scope")!="user"
            or value.get("slug")!=slug or value.get("operation") not in
            ("install","replace","restore","uninstall","reinstall")
            or not TXID.fullmatch(str(value.get("transaction")))):
        raise ValueError("Invalid host transaction journal")
    if value.get("profile_identity")!=_profile_identity(state.parents[3]):
        raise ValueError("Recovery journal belongs to a different user profile")
    operation=value["operation"]
    tx=value["transaction"]
    before=value.get("previous_receipt")
    after=value.get("new_receipt")
    identity=_profile_identity(state.parents[3])
    if before is not None:
        before=_receipt_valid(before,host,slug)
        if before["profile_identity"]!=identity:
            raise ValueError("Previous receipt belongs to a different OS user")
    if after is not None:
        after=_receipt_valid(after,host,slug)
        if after["profile_identity"]!=identity:
            raise ValueError("Pending receipt belongs to a different OS user")
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
                or marker.get("scope")!="user" or marker.get("slug")!=slug
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


def recover(host,profile,slug):
    """Complete a committed journal or undo only exact GASL-owned staged files.

    Never overwrites unexpected files, never guesses a source or alters another
    Host's directory. Returns a refusal and retains the journal on ambiguity.
    """
    profile=_root(profile)
    _host(host)
    with _lock(profile,host,slug) as state:
        target,_,state=_paths(profile,host,slug)
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
            if is_redirected(entry):
                raise ValueError("Symlink found in interrupted profile transaction")
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
        if current_inventory is not None:
            _verify_windows_tree(target)
        if stage_inventory is not None:
            _verify_windows_tree(stage)
        if backup_inventory is not None:
            _verify_windows_tree(backup)
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
            _read_state(profile,host,slug)
            return {"status":"host_user_committed_transaction_finalized",
                    "host":host,"scope":"user","action":action,"skill_executed":False}

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
                _verify_windows_tree(target)
                if manifest_path.exists():
                    manifest_path.unlink()
                    _sync(manifest_path.parent)
            if current_path.exists():
                if _load(current_path)!=prev:
                    raise ValueError("Old ownership receipt changed before rollback")
            else:
                _write_record(current_path,prev)
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
        _read_state(profile,host,slug)
        return {"status":"host_user_incomplete_transaction_rolled_back",
                "host":host,"scope":"user","action":action,
                "original_state_preserved":True,"skill_executed":False}
