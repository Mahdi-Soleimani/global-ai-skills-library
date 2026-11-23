#!/usr/bin/env python3
"""Phase 40: explicit Codex project Skill installation, no implicit overwrite.

Only an existing selected Git project root may be modified. Full source/ZIP
integrity, an exact read-only target binding and local interactive consent
are required. No downloaded Skill instructions or dependencies are executed.
"""
import contextlib
import hashlib
import json
import os
import re
import secrets
import stat
from pathlib import Path

from fixture_bundle_install import _inventory, _read_bundle, _remove_verified_dir, _check_list
from host_format_review import review_host_format
from host_target_preflight import _explicit_root, _target_path, inspect_selected_target, verify_target_unchanged
from skill_search import ROOT

try:
    import fcntl
except ImportError:
    fcntl = None

SCHEMA = 'gasl-codex-project-install-v1'
RESTORE_PREFLIGHT = 'gasl-codex-project-restore-preflight-v1'
STATE = '.gasl-managed'
HEX64 = re.compile(r'^[a-f0-9]{64}$')
SLUG = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$')


def _serialized(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)+'\n').encode()


def _sync(path):
    if os.name == 'posix':
        fd = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _root(selected):
    root = _explicit_root(selected)
    if root == Path.home().resolve():
        raise ValueError('Refusing user HOME: Phase 40 supports selected project scope only')
    git = root/'.git'
    if git.is_symlink() or not (git.is_dir() or git.is_file()):
        raise ValueError('A real existing Git project root must be selected')
    return root


def _paths(root, slug):
    if not SLUG.fullmatch(str(slug)):
        raise ValueError('Unsafe Skill name')
    target, relative = _target_path(root, 'codex', 'project', slug)
    state = root/STATE  # Keep staged SKILL.md outside all Host discovery directories.
    for candidate in (state, state/'receipts', state/'journals', state/'stage',
                      state/'backups', state/'backups'/slug, state/'uninstalled'):
        if candidate.is_symlink() or (candidate.exists() and not candidate.is_dir()):
            raise ValueError('Symlink or non-directory GASL state path')
    return target, relative, state


def _new(path, data):
    with path.open('xb') as f:
        f.write(_serialized(data))
        f.flush()
        os.fsync(f.fileno())
    if os.name == 'posix':
        path.chmod(0o600)
    _sync(path.parent)


def _load(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 100_000:
        raise ValueError('Missing or unsafe GASL state record')
    return json.loads(path.read_text(encoding='utf-8'))


def _receipt(state, slug):
    return state/'receipts'/(slug+'.json')


def _journal(state, slug):
    return state/'journals'/(slug+'.json')


def _inventory_from_rows(rows):
    return sorted(({'path': rel, 'sha256': sha} for _, rel, _, sha in rows),
                  key=lambda item: item['path'])


def _checked_receipt(data, slug):
    if (not isinstance(data, dict) or data.get('schema') != SCHEMA
            or data.get('action') not in ('fresh_install', 'replace_install', 'restore_backup',
                                           'reinstall_backup')
            or data.get('slug') != slug
            or not HEX64.fullmatch(str(data.get('plan_id')))
            or not HEX64.fullmatch(str(data.get('binding')))
            or not re.fullmatch(r'[0-9a-f]{32}', str(data.get('transaction')))
            or not isinstance(data.get('files'), list) or not data['files']):
        raise ValueError('Invalid GASL ownership receipt')
    _check_list(data['files'])
    backup_ids = data.get('backup_ids', [])
    if (not isinstance(backup_ids, list) or len(backup_ids) > 1000
            or any(not isinstance(item, str) or not re.fullmatch(r'[0-9a-f]{32}', item)
                   for item in backup_ids)
            or len(set(backup_ids)) != len(backup_ids)):
        raise ValueError('Invalid GASL backup history')
    if data.get('action') == 'replace_install' and not backup_ids:
        raise ValueError('Replacement receipt has no retained backup')
    if data.get('action') == 'reinstall_backup':
        if (data.get('source_kind') not in ('pinned', 'unmanaged')
                or not re.fullmatch(r'[0-9a-f]{32}', str(data.get('restored_backup_id')))
                or data['restored_backup_id'] not in backup_ids
                or not re.fullmatch(r'[0-9a-f]{32}', str(data.get('uninstall_event_id')))
                or (data['source_kind'] == 'unmanaged'
                    and data.get('unmanaged_restore_plan_id_derived') is not True)):
            raise ValueError('Invalid reinstalled Skill provenance or backup history')
    if data.get('action') == 'restore_backup':
        if (data.get('source_kind') not in ('pinned', 'unmanaged')
                or not re.fullmatch(r'[0-9a-f]{32}', str(data.get('restored_backup_id')))
                or data['restored_backup_id'] not in backup_ids
                or data.get('transaction') != backup_ids[-1]
                or data.get('source_kind') == 'unmanaged'
                and data.get('unmanaged_restore_plan_id_derived') is not True):
            raise ValueError('Invalid restored Skill provenance or retained backup history')
    return data


def _checked_journal(data, slug):
    if (not isinstance(data, dict) or data.get('schema') != SCHEMA
            or data.get('slug') != slug
            or data.get('operation') not in (
                'install', 'uninstall', 'uninstall_archive', 'replace', 'restore', 'reinstall')):
        raise ValueError('Invalid GASL transaction journal')
    _checked_receipt(data.get('receipt'), slug)
    if data['operation'] == 'reinstall':
        from codex_uninstalled_restore import validate_reinstall_journal
        validate_reinstall_journal(data, slug)
    if data['operation'] == 'uninstall_archive':
        from codex_uninstalled_restore import validate_uninstall_journal
        validate_uninstall_journal(data, slug)
    if data['operation'] == 'replace':
        previous = data.get('previous_receipt')
        if previous is not None:
            _checked_receipt(previous, slug)
        if (not re.fullmatch(r'[0-9a-f]{32}', str(data.get('backup_id')))
                or not re.fullmatch(r'[0-9a-f]{32}', str(data.get('transaction')))
                or data['receipt'].get('action') != 'replace_install'
                or data['backup_id'] != data['transaction']
                or data['receipt'].get('transaction') != data['transaction']
                or not data['receipt'].get('backup_ids')
                or data['receipt']['backup_ids'][-1] != data['backup_id']):
            raise ValueError('Invalid replacement transaction identity')
        expected_history = (list(previous.get('backup_ids', [])) if previous else []) + [data['backup_id']]
        if data['receipt']['backup_ids'] != expected_history:
            raise ValueError('Replacement receipt backup history does not extend prior state')
        _check_list(data.get('old_files'))
        _check_list(data.get('new_files'))
        if not data['old_files'] or not data['new_files']:
            raise ValueError('Replacement transaction requires both file inventories')
        if previous is not None and previous['files'] != data['old_files']:
            raise ValueError('Replacement old inventory differs from previous receipt')
        if data['receipt']['files'] != data['new_files']:
            raise ValueError('Replacement receipt differs from new file inventory')
    if data['operation'] == 'restore':
        previous = _checked_receipt(data.get('previous_receipt'), slug)
        selected_id, saved_id = data.get('selected_backup_id'), data.get('current_backup_id')
        if (not re.fullmatch(r'[0-9a-f]{32}', str(selected_id))
                or not re.fullmatch(r'[0-9a-f]{32}', str(saved_id))
                or saved_id != data.get('transaction')
                or saved_id in previous.get('backup_ids', [])
                or selected_id not in previous.get('backup_ids', [])
                or data['receipt']['action'] != 'restore_backup'
                or data['receipt']['transaction'] != saved_id
                or data['receipt'].get('restored_backup_id') != selected_id
                or data['receipt']['backup_ids'] != list(previous['backup_ids']) + [saved_id]):
            raise ValueError('Invalid restoration transaction identity')
        _check_list(data.get('current_files'))
        _check_list(data.get('restored_files'))
        if (not data['restored_files'] or not data['current_files']
                or data['current_files'] != previous['files']
                or data['receipt']['files'] != data['restored_files']
                or data['current_files'] == data['restored_files']):
            raise ValueError('Restore journal inventories are invalid')
        selected_manifest = _checked_backup(data.get('selected_manifest'), slug, selected_id)
        if selected_manifest['files'] != data['restored_files']:
            raise ValueError('Selected backup inventory differs from restore journal')
        source_record = selected_manifest.get('previous_receipt')
        if (data['receipt']['source_kind'] != (
                source_record.get('source_kind', 'pinned') if source_record else 'unmanaged')):
            raise ValueError('Restoration provenance disagrees with selected backup')
        if source_record and data['receipt']['plan_id'] != source_record['plan_id']:
            raise ValueError('Restored source Plan ID mismatch')
        if not source_record and data['receipt']['plan_id'] != _unmanaged_restore_plan_id(
                selected_id, selected_manifest):
            raise ValueError('Unmanaged restore synthetic identity mismatch')
        if data.get('binding') != data['receipt']['binding'] or not HEX64.fullmatch(str(data.get('binding'))):
            raise ValueError('Restore journal binding mismatch')
    return data


def _mkdir_checked(path):
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise ValueError('Unsafe path')
    if not path.exists():
        path.mkdir(mode=0o700)


@contextlib.contextmanager
def _lock(root, slug):
    if fcntl is None:
        raise ValueError('This installer currently requires a POSIX Host (macOS/Linux)')
    target, _, state = _paths(root, slug)
    # _target_path rejects symlink/non-directory segments.
    for path in (target.parent.parent, target.parent, state,
                 state/'receipts', state/'journals', state/'stage',
                 state/'backups', state/'backups'/slug, state/'uninstalled'):
        _mkdir_checked(path)
    lock = state/'.lock'
    if lock.is_symlink():
        raise ValueError('Unsafe lock')
    fd = os.open(str(lock), os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'a+b', closefd=True) as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield state
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _confirm(phrase, reader=None):
    if reader is None:
        import sys
        if not sys.stdin.isatty():
            raise ValueError('A local interactive TTY is required')
        reader = input
    response = reader('Type EXACTLY: '+phrase+'\n> ')
    if response.strip() != phrase:
        raise ValueError('Interactive approval phrase did not match')


def _install_phrase(slug, plan_id, binding):
    return 'INSTALL '+slug.upper()+' '+plan_id[:12].upper()+' '+binding[:12].upper()


def _remove_phrase(slug, plan_id):
    return 'UNINSTALL '+slug.upper()+' '+plan_id[:12].upper()


def preview_install(plan_id, selected_root, *, bundle_root=ROOT, lookup=None):
    """Pure read-only approval preview; never creates any Host paths."""
    if not HEX64.fullmatch(str(plan_id)):
        raise ValueError('Invalid exact Plan ID')
    root = _root(selected_root)
    review = review_host_format(plan_id, 'codex', 'project', root=bundle_root, lookup=lookup)
    if review['format_status'] != 'simple_frontmatter_shape_detected':
        raise ValueError('Unreviewed complex/missing Skill metadata')
    slug, rows = _read_bundle(bundle_root, plan_id, 'codex', 'project')
    if slug != review['skill_name']:
        raise ValueError('Pinned ZIP Skill name mismatch')
    target, relative, state = _paths(root, slug)
    preflight = inspect_selected_target(plan_id, 'codex', 'project', root,
                                        bundle_root=bundle_root)
    existing_receipt = _receipt(state, slug).exists()
    pending = _journal(state, slug).exists()
    marker = state/'uninstalled'/(slug+'.json')
    if marker.is_symlink():
        raise ValueError('Symlinked uninstalled ownership marker refused')
    retained_history = marker.exists()
    eligible = (not target.exists() and not existing_receipt and not pending
                and not retained_history)
    return {
        'status': 'real_project_install_preview_only', 'host': 'codex',
        'scope': 'project', 'plan_id': plan_id, 'slug': slug,
        'relative_target': relative, 'file_count': len(rows),
        'state_binding_id': preflight['state_binding_id'],
        'prior_target_state': preflight['prior_target_state'],
        'managed_receipt_exists': existing_receipt,
        'pending_transaction_exists': pending,
        'retained_uninstall_ownership_exists': retained_history,
        'eligible_for_fresh_install': eligible,
        'existing_skill_replace_supported': False,
        'requires_human_tty_confirmation': True,
        'installation_performed': False,
        'third_party_skill_executed': False,
    }


def _stage(path, rows):
    path.mkdir(mode=0o700)
    try:
        for _, rel, data, _ in rows:
            destination = path.joinpath(*rel.split('/'))
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
        _sync(path)
    except Exception:
        _remove_partial_stage(path)
        raise


def install_fresh(plan_id, selected_root, binding, *, bundle_root=ROOT, lookup=None, reader=None):
    root = _root(selected_root)
    plan = preview_install(plan_id, root, bundle_root=bundle_root, lookup=lookup)
    if not plan['eligible_for_fresh_install'] or binding != plan['state_binding_id']:
        raise ValueError('Destination occupied, pending transaction, or stale preflight')
    _confirm(_install_phrase(plan['slug'], plan_id, binding), reader)
    slug = plan['slug']
    with _lock(root, slug) as state:
        now = preview_install(plan_id, root, bundle_root=bundle_root, lookup=lookup)
        if not now['eligible_for_fresh_install'] or now['state_binding_id'] != binding:
            raise ValueError('Destination changed since interactive consent')
        verify_target_unchanged(plan_id, 'codex', 'project', root, binding,
                                bundle_root=bundle_root)
        target, _, _ = _paths(root, slug)
        _, rows = _read_bundle(bundle_root, plan_id, 'codex', 'project')
        tx = secrets.token_hex(16)
        stage = state/'stage'/tx
        if stage.exists() or stage.is_symlink():
            raise ValueError('Staging identifier collision')
        inventory = _inventory_from_rows(rows)
        _stage(stage, rows)
        if _inventory(stage) != inventory:
            raise ValueError('Staged bundle did not match ZIP')
        verify_target_unchanged(plan_id, 'codex', 'project', root, binding,
                                bundle_root=bundle_root)
        record = {'schema': SCHEMA, 'action': 'fresh_install',
                  'slug': slug, 'transaction': tx, 'plan_id': plan_id,
                  'binding': binding, 'files': inventory}
        pending = _journal(state, slug)
        _new(pending, {'schema': SCHEMA, 'slug': slug,
                       'operation': 'install', 'receipt': record})
        # From this point recover() can undo a partial operation.
        if target.exists() or target.is_symlink():
            raise ValueError('Target unexpectedly created before activation')
        stage.rename(target)
        _sync(target.parent)
        if _inventory(target) != inventory:
            raise ValueError('Installed contents differ from immutable manifest')
        _new(_receipt(state, slug), record)
        pending.unlink()
        _sync(pending.parent)
    return {'status': 'codex_project_skill_installed', 'slug': slug,
            'plan_id': plan_id, 'file_count': len(inventory),
            'receipt_written': True, 'real_installation_performed': True,
            'discovery_not_yet_verified': True, 'third_party_skill_executed': False}


def uninstall(slug, selected_root, *, reader=None):
    """Archive a removed Codex project Skill for explicit future reinstallation."""
    from codex_uninstalled_restore import (
        _read_marker, _marker_path, make_uninstall_marker,
    )
    root = _root(selected_root)
    target, _, state = _paths(root, slug)
    receipt_path = _receipt(state, slug)
    record = _checked_receipt(_load(receipt_path), slug)
    retained_backups = _verify_backup_history(state, slug, record)
    if not target.is_dir() or target.is_symlink() or _inventory(target) != record['files']:
        raise ValueError('Installed Skill changed; refusal preserves user edits')
    existing = _read_marker(root, slug, state)
    if existing is not None and (
            retained_backups[:len(existing['backup_ids'])] != existing['backup_ids']):
        raise ValueError('Uninstall ownership history does not match active receipt')
    if len(retained_backups) >= 1000:
        raise ValueError('Backup history at limit; no files removed')
    _confirm(_remove_phrase(slug, record['plan_id']), reader)
    with _lock(root, slug) as state:
        journal = _journal(state, slug)
        if journal.exists() or journal.is_symlink():
            raise ValueError('Pending transaction requires recovery')
        record = _checked_receipt(_load(receipt_path), slug)
        retained_backups = _verify_backup_history(state, slug, record)
        if _inventory(target) != record['files']:
            raise ValueError('Installed Skill changed since approval')
        previous = _read_marker(root, slug, state)
        if previous is not None and (
                retained_backups[:len(previous['backup_ids'])] != previous['backup_ids']):
            raise ValueError('Previous uninstall marker history not inherited')
        tx = secrets.token_hex(16)
        archived = _backup_dir(state, slug, tx)
        manifest_path = _backup_manifest(state, slug, tx)
        if (archived.exists() or archived.is_symlink()
                or manifest_path.exists() or manifest_path.is_symlink()):
            raise ValueError('Uninstall backup identifier collision')
        marker = make_uninstall_marker(root, slug, record, tx)
        manifest = {
            'schema': SCHEMA, 'kind': 'pre_replace_backup', 'slug': slug,
            'backup_id': tx, 'transaction': tx,
            'previous_receipt': record, 'files': record['files'],
        }
        transaction = {
            'schema': SCHEMA, 'slug': slug, 'operation': 'uninstall_archive',
            'archive_id': tx, 'receipt': record,
            'previous_uninstalled_marker': previous,
            'uninstalled_marker': marker,
        }
        _checked_journal(transaction, slug)
        _new(journal, transaction)
        if _inventory(target) != record['files']:
            raise ValueError('Skill changed after durable uninstall journal')
        target.rename(archived)
        _sync(target.parent)
        _sync(archived.parent)
        if _inventory(archived) != record['files']:
            raise ValueError('Archived Skill changed during rename')
        _new(manifest_path, manifest)
        marker_path = _marker_path(state, slug)
        if previous is None:
            _new(marker_path, marker)
        else:
            _atomic_record(marker_path, marker, previous)
        receipt_path.unlink()
        _sync(receipt_path.parent)
        journal.unlink()
        _sync(journal.parent)
    return {
        'status': 'codex_project_skill_uninstalled',
        'slug': slug,
        'retained_backup_ids': marker['backup_ids'],
        'backups_retained': True,
        'uninstall_ownership_marker_recorded': True,
        'archived_last_active_backup_id': tx,
        'real_uninstall_performed': True,
        'third_party_skill_executed': False,
    }


def _backup_dir(state, slug, backup_id):
    if not re.fullmatch(r'[0-9a-f]{32}', str(backup_id)):
        raise ValueError('Invalid backup identifier')
    return state/'backups'/slug/backup_id


def _backup_manifest(state, slug, backup_id):
    if not re.fullmatch(r'[0-9a-f]{32}', str(backup_id)):
        raise ValueError('Invalid backup identifier')
    return state/'backups'/slug/(backup_id+'.json')


def _checked_backup(data, slug, backup_id):
    if (not isinstance(data, dict) or data.get('schema') != SCHEMA
            or data.get('kind') != 'pre_replace_backup'
            or data.get('slug') != slug or data.get('backup_id') != backup_id
            or not re.fullmatch(r'[0-9a-f]{32}', str(data.get('transaction')))
            or data.get('transaction') != backup_id):
        raise ValueError('Invalid GASL backup manifest')
    _check_list(data.get('files'))
    if not data['files']:
        raise ValueError('Empty backup inventory is not restorable')
    previous = data.get('previous_receipt')
    if previous is not None:
        _checked_receipt(previous, slug)
        if previous['files'] != data['files']:
            raise ValueError('Backup manifest and previous receipt disagree')
    return data


def _atomic_record(path, data, expected_previous):
    """Atomically replace a receipt only if its exact prior value still matches."""
    if path.is_symlink():
        raise ValueError('Refusing symlinked GASL receipt')
    current = _load(path) if path.exists() else None
    if current != expected_previous:
        raise ValueError('GASL receipt changed during replacement')
    temporary = path.parent/('.'+path.name+'.'+secrets.token_hex(8)+'.tmp')
    try:
        _new(temporary, data)
        os.replace(temporary, path)
        _sync(path.parent)
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()
            _sync(path.parent)


def _remove_partial_stage(path):
    """Remove only a private GASL stage tree containing regular files/directories."""
    if path.is_symlink() or not path.is_dir():
        raise ValueError('Unsafe partial staging path')
    entries = list(path.rglob('*'))
    if any(item.is_symlink() or not (item.is_file() or item.is_dir()) for item in entries):
        raise ValueError('Unexpected entry in partial staging tree')
    for item in sorted((x for x in entries if x.is_file()), key=lambda x: len(x.parts), reverse=True):
        item.unlink()
    for item in sorted((x for x in entries if x.is_dir()), key=lambda x: len(x.parts), reverse=True):
        item.rmdir()
    path.rmdir()


def _replace_phrase(slug, plan_id, binding):
    return 'REPLACE '+slug.upper()+' '+plan_id[:12].upper()+' '+binding[:12].upper()+' KEEP-BACKUP'



def _verify_backup_history(state, slug, receipt):
    for backup_id in receipt.get('backup_ids', []):
        backup_path = _backup_dir(state, slug, backup_id)
        manifest_path = _backup_manifest(state, slug, backup_id)
        if (backup_path.is_symlink() or not backup_path.is_dir()
                or manifest_path.is_symlink() or not manifest_path.is_file()):
            raise ValueError('Managed backup history is incomplete')
        manifest = _checked_backup(_load(manifest_path), slug, backup_id)
        if _inventory(backup_path) != manifest['files']:
            raise ValueError('Managed backup changed')
    return list(receipt.get('backup_ids', []))


def preview_replace(plan_id, selected_root, *, bundle_root=ROOT, lookup=None):
    """Read-only preflight for replacing an existing, regular Skill directory."""
    if not HEX64.fullmatch(str(plan_id)):
        raise ValueError('Invalid exact Plan ID')
    root = _root(selected_root)
    review = review_host_format(plan_id, 'codex', 'project', root=bundle_root, lookup=lookup)
    if review['format_status'] != 'simple_frontmatter_shape_detected':
        raise ValueError('Skill metadata requires manual format review')
    slug, rows = _read_bundle(bundle_root, plan_id, 'codex', 'project')
    if slug != review['skill_name']:
        raise ValueError('Pinned ZIP Skill name mismatch')
    target, relative, state = _paths(root, slug)
    if not target.is_dir() or target.is_symlink():
        raise ValueError('Replacement requires an existing regular Skill directory')
    main = target/'SKILL.md'
    if main.is_symlink() or not main.is_file():
        raise ValueError('Existing Skill must contain a regular root SKILL.md')
    old_files = _inventory(target)
    if not old_files or not any(item['path'] == 'SKILL.md' for item in old_files):
        raise ValueError('Existing Skill inventory is empty or missing SKILL.md')
    receipt_path = _receipt(state, slug)
    if receipt_path.is_symlink():
        raise ValueError('Symlinked GASL receipt refused')
    previous_receipt = _checked_receipt(_load(receipt_path), slug) if receipt_path.exists() else None
    if previous_receipt is not None:
        if previous_receipt['files'] != old_files:
            raise ValueError('Managed Skill changed since installation; preserve user edits')
        if previous_receipt['plan_id'] == plan_id:
            raise ValueError('The selected pinned Skill version is already installed')
        _verify_backup_history(state, slug, previous_receipt)
    journal_path = _journal(state, slug)
    if journal_path.is_symlink():
        raise ValueError('Symlinked GASL journal refused')
    pending = journal_path.exists()
    if pending:
        raise ValueError('Pending GASL transaction must be recovered first')
    preflight = inspect_selected_target(plan_id, 'codex', 'project', root,
                                        bundle_root=bundle_root)
    return {
        'status': 'codex_project_replace_preview_only',
        'host': 'codex', 'scope': 'project', 'slug': slug,
        'plan_id': plan_id, 'relative_target': relative,
        'new_file_count': len(rows), 'existing_file_count': len(old_files),
        'existing_inventory_sha256': preflight['existing_file_inventory_sha256'],
        'state_binding_id': preflight['state_binding_id'],
        'existing_install_managed_by_gasl': previous_receipt is not None,
        'existing_plan_id': previous_receipt['plan_id'] if previous_receipt else None,
        'eligible_for_replace': True,
        'backup_required_and_retained': True,
        'requires_interactive_confirmation': True,
        'replacement_performed': False,
        'third_party_skill_executed': False,
    }


def replace_existing(plan_id, selected_root, binding, *,
                     bundle_root=ROOT, lookup=None, reader=None):
    """Replace an existing project Skill, retaining a verified full backup."""
    root = _root(selected_root)
    plan = preview_replace(plan_id, root, bundle_root=bundle_root, lookup=lookup)
    if binding != plan['state_binding_id']:
        raise ValueError('Destination changed or stale replacement preflight')
    _confirm(_replace_phrase(plan['slug'], plan_id, binding), reader)
    slug = plan['slug']
    with _lock(root, slug) as state:
        current = preview_replace(plan_id, root, bundle_root=bundle_root, lookup=lookup)
        if current['state_binding_id'] != binding:
            raise ValueError('Existing Skill changed since interactive consent')
        verify_target_unchanged(plan_id, 'codex', 'project', root, binding,
                                bundle_root=bundle_root)
        target, _, _ = _paths(root, slug)
        old_files = _inventory(target)
        receipt_path = _receipt(state, slug)
        previous_receipt = _checked_receipt(_load(receipt_path), slug) if receipt_path.exists() else None
        if previous_receipt is not None and previous_receipt['files'] != old_files:
            raise ValueError('Managed Skill changed before replacement')
        _, rows = _read_bundle(bundle_root, plan_id, 'codex', 'project')
        tx = secrets.token_hex(16)
        backup_id = tx
        stage = state/'stage'/tx
        backup_parent = state/'backups'/slug
        _mkdir_checked(backup_parent)
        backup = _backup_dir(state, slug, backup_id)
        manifest_path = _backup_manifest(state, slug, backup_id)
        journal = _journal(state, slug)
        if backup.exists() or backup.is_symlink() or manifest_path.exists() or manifest_path.is_symlink():
            raise ValueError('Backup identifier collision')
        if journal.exists() or journal.is_symlink():
            raise ValueError('Pending transaction must be recovered first')
        new_files = _inventory_from_rows(rows)
        if stage.exists() or stage.is_symlink():
            raise ValueError('Staging identifier collision')
        _stage(stage, rows)
        if _inventory(stage) != new_files:
            raise ValueError('Staged replacement differs from pinned ZIP')
        inherited_backups = list(previous_receipt.get('backup_ids', [])) if previous_receipt else []
        new_receipt = {
            'schema': SCHEMA, 'action': 'replace_install', 'slug': slug,
            'transaction': tx, 'plan_id': plan_id, 'binding': binding,
            'files': new_files, 'backup_ids': inherited_backups+[backup_id],
        }
        transaction = {
            'schema': SCHEMA, 'slug': slug, 'operation': 'replace',
            'transaction': tx, 'backup_id': backup_id,
            'previous_receipt': previous_receipt,
            'old_files': old_files, 'new_files': new_files,
            'receipt': new_receipt,
        }
        _new(journal, transaction)
        # Recheck immediately before the atomic rename; the advisory lock
        # coordinates GASL processes, not arbitrary editors or other tools.
        if _inventory(target) != old_files:
            raise ValueError('Existing Skill changed immediately before backup')
        # Atomic same-filesystem directory rename preserves every old file,
        # including user notes and files not present in the new ZIP.
        target.rename(backup)
        _sync(target.parent)
        _sync(backup.parent)
        if _inventory(backup) != old_files:
            raise ValueError('Previous Skill changed during backup rename')
        manifest = {
            'schema': SCHEMA, 'kind': 'pre_replace_backup', 'slug': slug,
            'backup_id': backup_id, 'transaction': tx,
            'previous_receipt': previous_receipt, 'files': old_files,
        }
        _new(manifest_path, manifest)
        if target.exists() or target.is_symlink():
            raise ValueError('Target reappeared before replacement activation')
        stage.rename(target)
        _sync(target.parent)
        if _inventory(target) != new_files:
            raise ValueError('Activated replacement differs from pinned ZIP')
        _atomic_record(receipt_path, new_receipt, previous_receipt)
        journal.unlink()
        _sync(journal.parent)
    return {
        'status': 'codex_project_skill_replaced',
        'slug': slug, 'plan_id': plan_id, 'file_count': len(new_files),
        'backup_id': backup_id,
        'backup_relative_path': (Path(STATE)/'backups'/slug/backup_id).as_posix(),
        'backup_manifest_recorded': True,
        'previous_skill_restorable': True,
        'real_replacement_performed': True,
        'third_party_skill_executed': False,
    }



def _restore_phrase(slug, selected_backup_id, current_plan_id, binding):
    return ('RESTORE '+slug.upper()+' '+selected_backup_id[:12].upper()
            +' '+current_plan_id[:12].upper()+' '+binding[:12].upper()
            +' KEEP-CURRENT-BACKUP')


def _unmanaged_restore_plan_id(backup_id, manifest):
    """A local synthetic identity, never presented as a pinned upstream Plan."""
    return hashlib.sha256(
        b'gasl-unmanaged-restore-v1\x00'
        + _serialized({'backup_id': backup_id, 'files': manifest['files']})
    ).hexdigest()


def _restore_snapshot(slug, root, selected_backup_id):
    """Read-only, path-bound snapshot of current files and all backups."""
    target, relative, state = _paths(root, slug)
    if not re.fullmatch(r'[0-9a-f]{32}', str(selected_backup_id)):
        raise ValueError('Invalid selected backup identifier')
    if not target.is_dir() or target.is_symlink():
        raise ValueError('Restore requires an installed regular Skill directory')
    main = target/'SKILL.md'
    if main.is_symlink() or not main.is_file():
        raise ValueError('Installed Skill must contain a regular root SKILL.md')
    journal = _journal(state, slug)
    if journal.exists() or journal.is_symlink():
        raise ValueError('Pending transaction requires recovery before restore')
    receipt_path = _receipt(state, slug)
    if receipt_path.is_symlink():
        raise ValueError('Symlinked GASL ownership receipt refused')
    active = _checked_receipt(_load(receipt_path), slug)
    current_files = _inventory(target)
    if current_files != active['files']:
        raise ValueError('Installed Skill changed; preserving user edits')
    ids = _verify_backup_history(state, slug, active)
    if len(ids) >= 1000:
        raise ValueError('Managed backup history limit reached; preserving all backups')
    if selected_backup_id not in ids:
        raise ValueError('Selected backup is not owned by the current Skill history')
    selected = _checked_backup(
        _load(_backup_manifest(state, slug, selected_backup_id)), slug, selected_backup_id)
    if selected['files'] == current_files:
        raise ValueError('Selected backup is byte-identical to installed Skill')
    if not any(item['path'] == 'SKILL.md' for item in selected['files']):
        raise ValueError('Selected backup does not contain a root SKILL.md')
    origin = selected['previous_receipt']
    source_kind = origin.get('source_kind', 'pinned') if origin else 'unmanaged'
    # Include the path hash and *every* backup manifest in the binding, without
    # leaking any local absolute path or existing file contents in the output.
    history = []
    for item in ids:
        backup_manifest = _checked_backup(_load(_backup_manifest(state,slug,item)),slug,item)
        history.append({'id': item,
                        'sha256': hashlib.sha256(_serialized(backup_manifest)).hexdigest()})
    snapshot = {
        'schema': RESTORE_PREFLIGHT,
        'target_sha256': hashlib.sha256(os.fsencode(str(target))).hexdigest(),
        'slug': slug, 'selected_backup_id': selected_backup_id,
        'current_receipt_sha256': hashlib.sha256(_serialized(active)).hexdigest(),
        'current_files': current_files,
        'restored_files': selected['files'],
        'history': history,
    }
    binding = hashlib.sha256(_serialized(snapshot)).hexdigest()
    return {
        'target': target, 'relative': relative, 'state': state,
        'active': active, 'selected': selected, 'binding': binding,
        'source_kind': source_kind, 'current_files': current_files,
        'restored_files': selected['files'], 'history_count': len(ids),
    }



def list_backups(slug, selected_root):
    """Read-only, privacy-preserving inventory of retained project backups."""
    root = _root(selected_root)
    target, relative, state = _paths(root, slug)
    if not target.is_dir() or target.is_symlink():
        raise ValueError('Listing backups requires an installed Skill directory')
    journal = _journal(state, slug)
    if journal.exists() or journal.is_symlink():
        raise ValueError('Pending transaction requires recovery before listing backups')
    receipt_path = _receipt(state, slug)
    if receipt_path.is_symlink():
        raise ValueError('Symlinked GASL ownership receipt refused')
    receipt = _checked_receipt(_load(receipt_path), slug)
    active_files = _inventory(target)
    if active_files != receipt['files']:
        raise ValueError('Installed Skill changed; preserve local edits')
    backup_ids = _verify_backup_history(state, slug, receipt)
    records = []
    for backup_id in backup_ids:
        manifest = _checked_backup(
            _load(_backup_manifest(state, slug, backup_id)), slug, backup_id)
        origin = manifest['previous_receipt']
        source_kind = origin.get('source_kind','pinned') if origin else 'unmanaged'
        records.append({
            'backup_id': backup_id,
            'source_kind': source_kind,
            'upstream_plan_id': (
                origin['plan_id'] if origin and source_kind == 'pinned' else None),
            'file_count': len(manifest['files']),
            'eligible_for_restore': manifest['files'] != active_files,
            'backup_integrity_verified': True,
        })
    return {
        'status': 'codex_project_backups_listed_read_only',
        'host': 'codex', 'scope': 'project', 'slug': slug,
        'relative_target': relative, 'current_plan_id': receipt['plan_id'],
        'backup_count': len(records), 'backups': records,
        'real_host_files_modified': False, 'third_party_skill_executed': False,
    }



def preview_restore(slug, selected_root, backup_id):
    """No writes, no installation, no Host execution or automatic approval."""
    root = _root(selected_root)
    snapshot = _restore_snapshot(slug, root, backup_id)
    selected = snapshot['selected']
    origin = selected['previous_receipt']
    return {
        'status': 'codex_project_backup_restore_preview_only',
        'host': 'codex', 'scope': 'project', 'slug': slug,
        'selected_backup_id': backup_id,
        'relative_target': snapshot['relative'],
        'state_binding_id': snapshot['binding'],
        'current_plan_id': snapshot['active']['plan_id'],
        'restored_source_kind': snapshot['source_kind'],
        'restored_upstream_plan_id': (
            origin['plan_id'] if origin and snapshot['source_kind']=='pinned' else None),
        'current_file_count': len(snapshot['current_files']),
        'restored_file_count': len(snapshot['restored_files']),
        'retained_backup_count': snapshot['history_count'],
        'current_version_will_be_backed_up': True,
        'selected_backup_preserved_without_modification': True,
        'requires_local_tty_confirmation': True,
        'eligible_for_restore': True,
        'restore_performed': False,
        'third_party_skill_executed': False,
    }


def _copy_backup_stage(source, stage, expected_files):
    """Copy verified local backup bytes into a distinct, private staging tree."""
    if source.is_symlink() or not source.is_dir():
        raise ValueError('Unsafe original backup')
    if stage.exists() or stage.is_symlink():
        raise ValueError('Unexpected restore staging collision')
    _check_list(expected_files)
    stage.mkdir(mode=0o700)
    try:
        for item in expected_files:
            source_file = source.joinpath(*item['path'].split('/'))
            destination = stage.joinpath(*item['path'].split('/'))
            destination.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
            fd = os.open(str(source_file), flags)
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise ValueError('Nonregular backup file during restore')
                h = hashlib.sha256()
                with os.fdopen(fd, 'rb', closefd=False) as stream, destination.open('xb') as output:
                    while True:
                        chunk = stream.read(1024*1024)
                        if not chunk:
                            break
                        h.update(chunk)
                        output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                if h.hexdigest() != item['sha256']:
                    raise ValueError('Backup bytes changed while copying')
            finally:
                os.close(fd)
        if _inventory(stage) != expected_files:
            raise ValueError('Restored staging inventory differs from selected backup')
        _sync(stage)
    except Exception:
        _remove_partial_stage(stage)
        raise


def restore_backup(slug, selected_root, backup_id, binding, *, reader=None):
    """Restore exact historical backup and retain the current active version."""
    root = _root(selected_root)
    plan = preview_restore(slug, root, backup_id)
    if binding != plan['state_binding_id']:
        raise ValueError('Selected backup or current files changed since preview')
    _confirm(_restore_phrase(slug, backup_id, plan['current_plan_id'], binding), reader)
    with _lock(root, slug) as state:
        snapshot = _restore_snapshot(slug, root, backup_id)
        if snapshot['binding'] != binding:
            raise ValueError('Backup or installed files changed after interactive consent')
        active = snapshot['active']
        selected = snapshot['selected']
        current_files, restored_files = snapshot['current_files'], snapshot['restored_files']
        source_kind = snapshot['source_kind']
        target = snapshot['target']
        selected_dir = _backup_dir(state, slug, backup_id)
        tx = secrets.token_hex(16)
        stage = state/'stage'/tx
        current_backup = _backup_dir(state, slug, tx)
        current_manifest_path = _backup_manifest(state, slug, tx)
        journal = _journal(state, slug)
        if (current_backup.exists() or current_backup.is_symlink()
                or current_manifest_path.exists() or current_manifest_path.is_symlink()
                or journal.exists() or journal.is_symlink()
                or stage.exists() or stage.is_symlink()):
            raise ValueError('Restore transaction identifier/path collision')
        _copy_backup_stage(selected_dir, stage, restored_files)
        origin = selected['previous_receipt']
        restored_plan = (origin['plan_id'] if origin else
                         _unmanaged_restore_plan_id(backup_id, selected))
        receipt = {
            'schema': SCHEMA, 'action': 'restore_backup', 'slug': slug,
            'transaction': tx, 'plan_id': restored_plan, 'binding': binding,
            'files': restored_files,
            'backup_ids': list(active['backup_ids'])+[tx],
            'restored_backup_id': backup_id, 'source_kind': source_kind,
        }
        if source_kind == 'unmanaged':
            receipt['unmanaged_restore_plan_id_derived'] = True
        transaction = {
            'schema': SCHEMA, 'slug': slug, 'operation': 'restore',
            'transaction': tx, 'current_backup_id': tx,
            'selected_backup_id': backup_id, 'selected_manifest': selected,
            'previous_receipt': active, 'receipt': receipt,
            'current_files': current_files, 'restored_files': restored_files,
            'binding': binding,
        }
        _checked_journal(transaction, slug)
        _new(journal, transaction)
        if (_inventory(target) != current_files
                or _inventory(selected_dir) != restored_files
                or _load(_backup_manifest(state, slug, backup_id)) != selected):
            raise ValueError('Installed Skill or selected backup changed before activation')
        # Same-filesystem rename safeguards the version being replaced.
        target.rename(current_backup)
        _sync(target.parent)
        _sync(current_backup.parent)
        if _inventory(current_backup) != current_files:
            raise ValueError('Current Skill changed during backup rename')
        current_manifest = {
            'schema': SCHEMA, 'kind': 'pre_replace_backup', 'slug': slug,
            'backup_id': tx, 'transaction': tx,
            'previous_receipt': active, 'files': current_files,
        }
        _new(current_manifest_path, current_manifest)
        if target.exists() or target.is_symlink():
            raise ValueError('Skill target reappeared during restore')
        stage.rename(target)
        _sync(target.parent)
        if _inventory(target) != restored_files:
            raise ValueError('Restored version differs from verified backup')
        _atomic_record(_receipt(state, slug), receipt, active)
        journal.unlink()
        _sync(journal.parent)
    return {
        'status': 'codex_project_skill_backup_restored',
        'slug': slug, 'restored_backup_id': backup_id,
        'restored_source_kind': source_kind,
        'restored_file_count': len(restored_files),
        'saved_current_backup_id': tx,
        'saved_current_backup_relative_path': (
            Path(STATE)/'backups'/slug/tx).as_posix(),
        'selected_backup_preserved': True,
        'current_version_backed_up': True,
        'restoration_performed': True,
        'third_party_skill_executed': False,
    }


def _recover_restore(root, state, slug, data):
    """Resolve only exact, evidenced restore states; never discard edits."""
    target, _, _ = _paths(root, slug)
    old_receipt = data['previous_receipt']
    new_receipt = data['receipt']
    old_files, restored_files = data['current_files'], data['restored_files']
    selected_id, saved_id = data['selected_backup_id'], data['current_backup_id']
    selected_dir = _backup_dir(state, slug, selected_id)
    selected_manifest = _backup_manifest(state, slug, selected_id)
    saved_dir = _backup_dir(state, slug, saved_id)
    saved_manifest = _backup_manifest(state, slug, saved_id)
    stage = state/'stage'/saved_id
    receipt_path = _receipt(state, slug)
    journal = _journal(state, slug)
    if receipt_path.is_symlink():
        raise ValueError('Symlinked receipt during restore recovery')
    current_receipt = _checked_receipt(_load(receipt_path), slug)
    if current_receipt not in (old_receipt, new_receipt):
        raise ValueError('Restore receipt neither matches old nor new transaction')
    _verify_backup_history(state, slug, old_receipt)
    if _load(selected_manifest) != data['selected_manifest']:
        raise ValueError('Historical backup manifest changed during restore')
    if _inventory(selected_dir) != restored_files:
        raise ValueError('Historical backup bytes changed during restore')

    saved_exists = saved_dir.exists() or saved_dir.is_symlink()
    manifest_exists = saved_manifest.exists() or saved_manifest.is_symlink()
    stage_exists = stage.exists() or stage.is_symlink()
    target_exists = target.exists() or target.is_symlink()
    if saved_exists:
        if saved_dir.is_symlink() or not saved_dir.is_dir() or _inventory(saved_dir) != old_files:
            raise ValueError('Saved current-version backup changed; preserve data')
    expected_manifest = {
        'schema': SCHEMA, 'kind': 'pre_replace_backup', 'slug': slug,
        'backup_id': saved_id, 'transaction': saved_id,
        'previous_receipt': old_receipt, 'files': old_files,
    }
    if manifest_exists:
        if saved_manifest.is_symlink() or _checked_backup(
                _load(saved_manifest),slug,saved_id) != expected_manifest:
            raise ValueError('Saved current-version backup manifest changed')
        if not saved_exists:
            raise ValueError('Saved current backup manifest exists without backup')
    if stage_exists:
        if stage.is_symlink() or not stage.is_dir() or _inventory(stage) != restored_files:
            raise ValueError('Restore staging changed; preserve data')
    target_files = None
    if target_exists:
        if target.is_symlink() or not target.is_dir():
            raise ValueError('Restored Skill target replaced with non-directory')
        target_files = _inventory(target)

    if current_receipt == new_receipt:
        if target_files != restored_files or not saved_exists:
            raise ValueError('Committed restoration or saved current version changed')
        if not manifest_exists:
            _new(saved_manifest, expected_manifest)
        if stage_exists:
            _remove_verified_dir(stage, restored_files)
        journal.unlink()
        _sync(journal.parent)
        return 'restore_commit_recovered'

    # Pre-commit states must be unambiguous.
    if target_files == old_files and saved_exists:
        raise ValueError('Ambiguous original version and backup duplication')
    if target_files == restored_files and not saved_exists:
        raise ValueError('Restored target exists but the current backup is missing')
    if target_files is None and not saved_exists:
        raise ValueError('Both original target and new backup are missing')
    if target_files not in (None, old_files, restored_files):
        raise ValueError('Restored target changed; preserving user edits')
    if target_files == restored_files:
        _remove_verified_dir(target, restored_files)
    if saved_exists:
        if target.exists() or target.is_symlink():
            raise ValueError('Cannot recover over an occupied target')
        saved_dir.rename(target)
        _sync(target.parent)
    if stage_exists:
        _remove_verified_dir(stage, restored_files)
    if manifest_exists:
        saved_manifest.unlink()
        _sync(saved_manifest.parent)
    journal.unlink()
    _sync(journal.parent)
    if _inventory(target) != old_files:
        raise ValueError('Restore rollback did not preserve previous Skill version')
    return 'interrupted_restore_rolled_back'

def _recover_replace(root, state, slug, data):
    target, _, _ = _paths(root, slug)
    receipt_path = _receipt(state, slug)
    record = data['receipt']
    previous = data.get('previous_receipt')
    old_files, new_files = data['old_files'], data['new_files']
    backup_id, tx = data['backup_id'], data['transaction']
    backup = _backup_dir(state, slug, backup_id)
    manifest_path = _backup_manifest(state, slug, backup_id)
    stage = state/'stage'/tx

    if receipt_path.is_symlink():
        raise ValueError('Symlinked GASL receipt refused during recovery')
    current_receipt = _checked_receipt(_load(receipt_path), slug) if receipt_path.exists() else None
    backup_exists = backup.exists() or backup.is_symlink()
    stage_exists = stage.exists() or stage.is_symlink()
    manifest_exists = manifest_path.exists() or manifest_path.is_symlink()
    target_exists = target.exists() or target.is_symlink()

    # Validate every tree and metadata file BEFORE deleting or moving anything.
    if backup_exists:
        if backup.is_symlink() or not backup.is_dir() or _inventory(backup) != old_files:
            raise ValueError('Previous Skill backup changed; manual recovery required')
    if stage_exists:
        if stage.is_symlink() or not stage.is_dir() or _inventory(stage) != new_files:
            raise ValueError('Staged replacement changed; manual recovery required')
    expected_manifest = {
        'schema': SCHEMA, 'kind': 'pre_replace_backup', 'slug': slug,
        'backup_id': backup_id, 'transaction': tx,
        'previous_receipt': previous, 'files': old_files,
    }
    if manifest_exists:
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise ValueError('Unsafe backup manifest path')
        if _checked_backup(_load(manifest_path), slug, backup_id) != expected_manifest:
            raise ValueError('Backup manifest changed; manual recovery required')
    target_inventory = None
    if target_exists:
        if target.is_symlink() or not target.is_dir():
            raise ValueError('Replacement target changed to a non-directory')
        target_inventory = _inventory(target)

    # Receipt replacement is the commit point. A valid receipt + both exact
    # directories means finish commit, not rollback.
    if current_receipt == record:
        if target_inventory != new_files or not backup_exists:
            raise ValueError('Committed replacement or backup changed; manual review required')
        if not manifest_exists:
            _new(manifest_path, expected_manifest)
        if stage_exists:
            _remove_verified_dir(stage, new_files)
        _journal(state, slug).unlink()
        _sync(_journal(state, slug).parent)
        return 'replacement_commit_recovered'

    if current_receipt != previous:
        raise ValueError('Receipt is neither the old nor new transaction state')
    # Only these three pre-commit layouts are possible with atomic directory
    # renames. Anything else is ambiguous and must be preserved for inspection.
    if target_inventory == new_files and not backup_exists:
        raise ValueError('New Skill exists but its previous-version backup is missing')
    if target_inventory == old_files and backup_exists:
        raise ValueError('Both old target and backup exist; refusing ambiguous recovery')
    if target_inventory is None and not backup_exists:
        raise ValueError('Original Skill and verified backup are both missing')
    if target_inventory not in (None, old_files, new_files):
        raise ValueError('Replacement target changed; preserve files and backup')

    if target_inventory == new_files:
        _remove_verified_dir(target, new_files)
    if backup_exists:
        if target.exists():
            raise ValueError('Cannot restore backup over an existing target')
        backup.rename(target)
        _sync(target.parent)
    if stage_exists:
        _remove_verified_dir(stage, new_files)
    if manifest_exists:
        manifest_path.unlink()
        _sync(manifest_path.parent)
    _journal(state, slug).unlink()
    _sync(_journal(state, slug).parent)
    return 'interrupted_replacement_rolled_back'


def recover(slug, selected_root):
    """Repair an interrupted install or uninstall after verifying exact ownership."""
    root = _root(selected_root)
    with _lock(root, slug) as state:
        journal = _journal(state, slug)
        data = _checked_journal(_load(journal), slug)
        record = data['receipt']
        target, _, _ = _paths(root, slug)
        receipt_path = _receipt(state, slug)
        staged = state/'stage'/record['transaction']
        retired = state/'stage'/('retired-'+record['transaction'])
        if data['operation'] == 'reinstall':
            from codex_uninstalled_restore import recover_reinstall
            outcome = recover_reinstall(root, state, slug, data)
            return {'status': outcome, 'slug': slug, 'recovery_performed': True,
                    'backup_retained': True, 'third_party_skill_executed': False}
        if data['operation'] == 'uninstall_archive':
            from codex_uninstalled_restore import recover_uninstall_archive
            outcome = recover_uninstall_archive(root, state, slug, data)
            return {'status': outcome, 'slug': slug, 'recovery_performed': True,
                    'archived_backup_retained':
                        outcome == 'archived_uninstall_commit_recovered',
                    'third_party_skill_executed': False}
        if data['operation'] == 'restore':
            outcome = _recover_restore(root, state, slug, data)
            return {'status': outcome, 'slug': slug, 'recovery_performed': True,
                    'previous_skill_restored': outcome == 'interrupted_restore_rolled_back',
                    'backup_retained': outcome == 'restore_commit_recovered',
                    'third_party_skill_executed': False}
        if data['operation'] == 'replace':
            outcome = _recover_replace(root, state, slug, data)
            return {'status': outcome, 'slug': slug, 'recovery_performed': True,
                    'previous_skill_restored': outcome == 'interrupted_replacement_rolled_back',
                    'backup_retained': outcome == 'replacement_commit_recovered',
                    'third_party_skill_executed': False}
        if data['operation'] == 'install':
            if receipt_path.exists():
                owned = _checked_receipt(_load(receipt_path), slug)
                if owned != record or _inventory(target) != record['files']:
                    raise ValueError('Changed installed Skill; manual recovery required')
                outcome = 'installed_receipt_committed'
            else:
                if target.exists():
                    _remove_verified_dir(target, record['files'])
                if staged.exists():
                    _remove_verified_dir(staged, record['files'])
                outcome = 'partial_install_rolled_back'
        else:
            if retired.exists():
                if target.exists() or target.is_symlink() or _inventory(retired) != record['files']:
                    raise ValueError('Cannot safely restore changed retire state')
                retired.rename(target)
                if not receipt_path.exists():
                    _new(receipt_path, record)
                outcome = 'interrupted_uninstall_restored'
            elif target.exists() and _inventory(target) == record['files']:
                if not receipt_path.exists():
                    _new(receipt_path, record)
                outcome = 'original_install_still_present'
            elif not target.exists() and not receipt_path.exists():
                outcome = 'uninstall_already_finished'
            else:
                raise ValueError('Ambiguous interrupted uninstall: manual review required')
        journal.unlink()
        _sync(journal.parent)
    return {'status': outcome, 'recovery_performed': True,
            'third_party_skill_executed': False}
