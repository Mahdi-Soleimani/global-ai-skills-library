#!/usr/bin/env python3
"""Phase 43: project-only, explicit reinstatement of archived Codex Skills.

An uninstall archives the previously active files outside Codex discovery and
persists a project-bound ownership marker. A selected verified backup can be
reinstalled only into an empty matching project target with local TTY consent.
"""
import hashlib
import os
import re
import secrets
from pathlib import Path

from codex_project_install import (
    SCHEMA, STATE, _root, _paths, _receipt, _journal, _backup_dir,
    _backup_manifest, _checked_receipt, _checked_backup,
    _verify_backup_history, _inventory, _load, _new, _atomic_record,
    _serialized, _sync, _lock, _confirm, _copy_backup_stage,
    _remove_verified_dir,
)

MARKER_SCHEMA = 'gasl-uninstalled-codex-project-v1'
BINDING_SCHEMA = 'gasl-reinstall-archived-skill-preflight-v1'
ID32 = re.compile(r'^[0-9a-f]{32}$')


def _marker_path(state, slug):
    return state / 'uninstalled' / (slug + '.json')


def _path_sha(root, slug):
    # Canonicalize /var -> /private/var on macOS, not just on write.
    target, _, _ = _paths(_root(root), slug)
    return hashlib.sha256(os.fsencode(str(target))).hexdigest()


def make_uninstall_marker(root, slug, receipt, tx):
    _checked_receipt(receipt, slug)
    if not ID32.fullmatch(str(tx)):
        raise ValueError('Uninstall archive ID invalid')
    history = list(receipt.get('backup_ids', []))
    if tx in history or len(history) >= 1000:
        raise ValueError('Backup history at limit or duplicate archive ID')
    return {
        'schema': MARKER_SCHEMA,
        'kind': 'uninstalled_codex_project_skill',
        'slug': slug,
        'target_sha256': _path_sha(root, slug),
        'uninstall_event_id': tx,
        'archived_current_backup_id': tx,
        'last_receipt': receipt,
        'backup_ids': history + [tx],
    }


def check_uninstall_marker(value, root, slug):
    if (not isinstance(value, dict)
            or value.get('schema') != MARKER_SCHEMA
            or value.get('kind') != 'uninstalled_codex_project_skill'
            or value.get('slug') != slug
            or value.get('target_sha256') != _path_sha(root, slug)
            or not ID32.fullmatch(str(value.get('uninstall_event_id')))
            or value.get('uninstall_event_id') != value.get('archived_current_backup_id')):
        raise ValueError('Invalid project-scoped uninstalled Skill ownership marker')
    last = _checked_receipt(value.get('last_receipt'), slug)
    expected = list(last.get('backup_ids', [])) + [value['uninstall_event_id']]
    if value.get('backup_ids') != expected or len(expected) > 1000:
        raise ValueError('Uninstalled ownership marker backup history mismatch')
    return value


def _read_marker(root, slug, state):
    path = _marker_path(state, slug)
    if path.is_symlink():
        raise ValueError('Symlinked uninstalled ownership marker refused')
    return check_uninstall_marker(_load(path), root, slug) if path.exists() else None


def _history(state, slug, marker):
    receipt_for_history = {'backup_ids': marker['backup_ids']}
    ids = _verify_backup_history(state, slug, receipt_for_history)
    last_id = marker['archived_current_backup_id']
    last_manifest = _checked_backup(_load(_backup_manifest(state, slug, last_id)),
                                    slug, last_id)
    if (last_manifest['previous_receipt'] != marker['last_receipt']
            or last_manifest['files'] != marker['last_receipt']['files']):
        raise ValueError('Archived last active Skill does not match uninstall ownership')
    return ids


def _ensure_uninstalled(root, slug):
    target, relative, state = _paths(root, slug)
    if target.exists() or target.is_symlink():
        raise ValueError('Reinstall requires an absent, non-symlinked Skill target')
    journal = _journal(state, slug)
    if journal.exists() or journal.is_symlink():
        raise ValueError('Pending transaction requires recovery before reinstall')
    receipt = _receipt(state, slug)
    if receipt.exists() or receipt.is_symlink():
        raise ValueError('Existing GASL receipt prevents backup reinstall')
    marker = _read_marker(root, slug, state)
    if marker is None:
        raise ValueError('No project-bound uninstall ownership marker exists')
    ids = _history(state, slug, marker)
    return target, relative, state, marker, ids


def _source_from_manifest(backup_id, manifest):
    origin = manifest['previous_receipt']
    kind = origin.get('source_kind', 'pinned') if origin else 'unmanaged'
    if origin is None:
        from codex_project_install import _unmanaged_restore_plan_id
        plan = _unmanaged_restore_plan_id(backup_id, manifest)
    else:
        plan = origin['plan_id']
    return kind, plan


def _snapshot(root, slug, backup_id):
    if not ID32.fullmatch(str(backup_id)):
        raise ValueError('Invalid selected uninstalled backup ID')
    target, relative, state, marker, ids = _ensure_uninstalled(root, slug)
    if backup_id not in ids:
        raise ValueError('Selected backup not owned by this uninstalled Skill')
    manifest = _checked_backup(_load(_backup_manifest(state, slug, backup_id)),
                               slug, backup_id)
    if not any(item['path'] == 'SKILL.md' for item in manifest['files']):
        raise ValueError('Selected archive lacks required root SKILL.md')
    kind, plan = _source_from_manifest(backup_id, manifest)
    history = []
    for value in ids:
        historical = _checked_backup(_load(_backup_manifest(state, slug, value)),
                                     slug, value)
        history.append({
            'id': value,
            'manifest_sha256': hashlib.sha256(_serialized(historical)).hexdigest(),
        })
    bound = {
        'schema': BINDING_SCHEMA,
        'target_sha256': _path_sha(root, slug),
        'marker_sha256': hashlib.sha256(_serialized(marker)).hexdigest(),
        'slug': slug, 'selected_backup_id': backup_id,
        'selected_files': manifest['files'],
        'verified_history': history,
        'receipt_absent': True, 'target_absent': True,
    }
    return {
        'target': target, 'relative': relative, 'state': state,
        'marker': marker, 'ids': ids, 'manifest': manifest,
        'source_kind': kind, 'source_plan': plan,
        'binding': hashlib.sha256(_serialized(bound)).hexdigest(),
    }


def list_uninstalled_backups(slug, selected_root):
    """Read-only, ownership-checked listing of archived versions."""
    root = _root(selected_root)
    _, relative, state, marker, ids = _ensure_uninstalled(root, slug)
    records = []
    for backup_id in ids:
        manifest = _checked_backup(_load(_backup_manifest(state, slug, backup_id)),
                                   slug, backup_id)
        kind, plan = _source_from_manifest(backup_id, manifest)
        records.append({
            'backup_id': backup_id, 'source_kind': kind,
            'upstream_plan_id': plan if kind == 'pinned' else None,
            'file_count': len(manifest['files']),
            'last_active_before_uninstall': backup_id == marker['archived_current_backup_id'],
            'backup_integrity_verified': True,
        })
    return {
        'status': 'codex_uninstalled_backups_listed_read_only',
        'host': 'codex', 'scope': 'project', 'slug': slug,
        'relative_target': relative,
        'backup_count': len(records), 'backups': records,
        'uninstall_ownership_verified': True,
        'real_host_files_modified': False,
        'third_party_skill_executed': False,
    }


def preview_reinstall(slug, selected_root, backup_id):
    """Read-only, state-bound preview; real project must already exist."""
    snap = _snapshot(_root(selected_root), slug, backup_id)
    return {
        'status': 'codex_uninstalled_backup_reinstall_preview_only',
        'host': 'codex', 'scope': 'project', 'slug': slug,
        'relative_target': snap['relative'],
        'selected_backup_id': backup_id,
        'state_binding_id': snap['binding'],
        'restored_source_kind': snap['source_kind'],
        'restored_upstream_plan_id': (
            snap['source_plan'] if snap['source_kind'] == 'pinned' else None),
        'file_count': len(snap['manifest']['files']),
        'backup_count': len(snap['ids']),
        'uninstall_ownership_verified': True,
        'requires_local_tty_confirmation': True,
        'reinstall_performed': False,
        'third_party_skill_executed': False,
    }


def _reinstall_phrase(slug, backup_id, event_id, binding):
    return ('REINSTALL ' + slug.upper() + ' ' + backup_id[:12].upper()
            + ' ' + event_id[:12].upper() + ' ' + binding[:12].upper()
            + ' FROM-OWNED-BACKUP')


def validate_reinstall_journal(data, slug):
    if data.get('operation') != 'reinstall':
        raise ValueError('Not a reinstall transaction')
    marker = data.get('uninstalled_marker')
    if (not isinstance(marker, dict)
            or marker.get('schema') != MARKER_SCHEMA
            or marker.get('slug') != slug
            or not ID32.fullmatch(str(data.get('transaction')))
            or not ID32.fullmatch(str(data.get('selected_backup_id')))
            or data.get('selected_backup_id') not in marker.get('backup_ids', [])
            or data['receipt']['action'] != 'reinstall_backup'
            or data['receipt']['transaction'] != data['transaction']
            or data['receipt']['restored_backup_id'] != data['selected_backup_id']
            or data['receipt']['uninstall_event_id'] != marker.get('uninstall_event_id')
            or data['receipt']['backup_ids'] != marker['backup_ids']
            or data.get('binding') != data['receipt']['binding']
            or not re.fullmatch(r'[0-9a-f]{64}', str(data.get('binding')))):
        raise ValueError('Invalid reinstall journal or uninstalled ownership chain')
    manifest = _checked_backup(data.get('selected_manifest'), slug,
                               data['selected_backup_id'])
    if manifest['files'] != data['receipt']['files']:
        raise ValueError('Reinstall journal file inventories disagree')
    kind, plan = _source_from_manifest(data['selected_backup_id'], manifest)
    if data['receipt']['source_kind'] != kind or data['receipt']['plan_id'] != plan:
        raise ValueError('Reinstall source provenance mismatch')
    if kind == 'unmanaged' and data['receipt'].get(
            'unmanaged_restore_plan_id_derived') is not True:
        raise ValueError('Reinstalled unmanaged backup identity not marked')


def validate_uninstall_journal(data, slug):
    marker = data.get('uninstalled_marker')
    if not isinstance(marker, dict):
        raise ValueError('Invalid uninstall marker journal')
    previous = data.get('previous_uninstalled_marker')
    receipt = data['receipt']
    if (marker.get('schema') != MARKER_SCHEMA
            or marker.get('slug') != slug
            or marker.get('last_receipt') != receipt
            or marker.get('backup_ids') != list(receipt.get('backup_ids', []))
               + [marker.get('uninstall_event_id')]
            or marker.get('uninstall_event_id') != data.get('archive_id')
            or not ID32.fullmatch(str(data.get('archive_id')))):
        raise ValueError('Uninstall journal lacks valid retained backup history')
    if previous is not None:
        if (previous.get('schema') != MARKER_SCHEMA
                or previous.get('slug') != slug
                or not set(previous.get('backup_ids', [])).issubset(
                    set(receipt.get('backup_ids', [])))):
            raise ValueError('Uninstall journal previous ownership cannot be reconciled')


def reinstall_backup(slug, selected_root, backup_id, binding, *, reader=None):
    """Real local project-only operation; never touches a personal Agent profile."""
    root = _root(selected_root)
    preview = preview_reinstall(slug, root, backup_id)
    if binding != preview['state_binding_id']:
        raise ValueError('Selected backup or uninstalled ownership changed since preview')
    snap = _snapshot(root, slug, backup_id)
    _confirm(_reinstall_phrase(slug, backup_id,
                               snap['marker']['uninstall_event_id'], binding), reader)
    with _lock(root, slug) as state:
        current = _snapshot(root, slug, backup_id)
        if current['binding'] != binding:
            raise ValueError('Target, ownership or backup changed since interactive consent')
        tx = secrets.token_hex(16)
        stage = state / 'stage' / tx
        from codex_project_install import _copy_backup_stage
        _copy_backup_stage(_backup_dir(state, slug, backup_id),
                           stage, current['manifest']['files'])
        marker = current['marker']
        receipt = {
            'schema': SCHEMA, 'action': 'reinstall_backup',
            'slug': slug, 'transaction': tx,
            'plan_id': current['source_plan'], 'binding': binding,
            'files': current['manifest']['files'],
            'backup_ids': list(marker['backup_ids']),
            'restored_backup_id': backup_id,
            'uninstall_event_id': marker['uninstall_event_id'],
            'source_kind': current['source_kind'],
        }
        if current['source_kind'] == 'unmanaged':
            receipt['unmanaged_restore_plan_id_derived'] = True
        transaction = {
            'schema': SCHEMA, 'slug': slug, 'operation': 'reinstall',
            'transaction': tx, 'selected_backup_id': backup_id,
            'selected_manifest': current['manifest'],
            'uninstalled_marker': marker, 'binding': binding,
            'receipt': receipt,
        }
        from codex_project_install import _checked_journal
        journal = _journal(state, slug)
        try:
            _checked_journal(transaction, slug)
            _new(journal, transaction)
        except Exception:
            if not journal.exists() and not journal.is_symlink():
                _remove_verified_dir(stage, receipt['files'])
            raise
        fresh_target, _, _ = _paths(root, slug)
        if fresh_target != current['target']:
            raise ValueError('Target destination changed after approval')
        if (current['target'].exists() or current['target'].is_symlink()
                or _receipt(state, slug).exists()
                or _load(_marker_path(state, slug)) != marker
                or _inventory(_backup_dir(state, slug, backup_id))
                   != current['manifest']['files']):
            raise ValueError('Reinstall target or ownership changed after journal')
        current['target'].parent.mkdir(parents=True, exist_ok=True)
        stage.rename(current['target'])
        _sync(current['target'].parent)
        if _inventory(current['target']) != receipt['files']:
            raise ValueError('Installed archive differs from original verified backup')
        _new(_receipt(state, slug), receipt)
        journal.unlink()
        _sync(journal.parent)
    return {
        'status': 'codex_uninstalled_skill_reinstalled_from_backup',
        'host': 'codex', 'scope': 'project',
        'slug': slug, 'restored_backup_id': backup_id,
        'restored_source_kind': current['source_kind'],
        'file_count': len(receipt['files']),
        'backup_history_retained': True,
        'uninstall_ownership_retained': True,
        'reinstall_performed': True,
        'third_party_skill_executed': False,
    }


def recover_reinstall(root, state, slug, transaction):
    """Recover only a verified archived reinstatement; fail closed on edits."""
    validate_reinstall_journal(transaction, slug)
    marker = check_uninstall_marker(transaction['uninstalled_marker'], root, slug)
    current_marker = _read_marker(root, slug, state)
    if current_marker != marker:
        raise ValueError('Uninstall marker changed during reinstatement')
    _history(state, slug, marker)
    target, _, _ = _paths(root, slug)
    receipt_path = _receipt(state, slug)
    if receipt_path.is_symlink():
        raise ValueError('Symlinked reinstatement receipt')
    actual_receipt = (_checked_receipt(_load(receipt_path),slug)
                      if receipt_path.exists() else None)
    if actual_receipt not in (None, transaction['receipt']):
        raise ValueError('Reinstallation receipt does not match transaction')
    expected = transaction['receipt']['files']
    backup = _backup_dir(state, slug, transaction['selected_backup_id'])
    if _inventory(backup) != expected:
        raise ValueError('Selected archived backup mutated during reinstatement')
    stage = state / 'stage' / transaction['transaction']
    if stage.exists() or stage.is_symlink():
        if stage.is_symlink() or not stage.is_dir() or _inventory(stage) != expected:
            raise ValueError('Reinstall stage changed; preserving all data')
        stage_exists = True
    else:
        stage_exists = False
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_dir() or _inventory(target) != expected:
            raise ValueError('Installed target changed during reinstatement')
        target_exists = True
    else:
        target_exists = False
    if actual_receipt is not None:
        if not target_exists:
            raise ValueError('Committed reinstall is missing its active Skill')
        outcome = 'reinstall_commit_recovered'
    else:
        if target_exists:
            _remove_verified_dir(target, expected)
        outcome = 'interrupted_reinstall_rolled_back'
    if stage_exists:
        _remove_verified_dir(stage, expected)
    journal = _journal(state, slug)
    journal.unlink()
    _sync(journal.parent)
    return outcome


def recover_uninstall_archive(root, state, slug, transaction):
    """Recover a new-style archived uninstall; retain all exact archived bytes."""
    validate_uninstall_journal(transaction, slug)
    marker = check_uninstall_marker(transaction['uninstalled_marker'], root, slug)
    prior = transaction.get('previous_uninstalled_marker')
    if prior is not None:
        check_uninstall_marker(prior, root, slug)
    current_marker = _read_marker(root, slug, state)
    if current_marker not in (prior, marker):
        raise ValueError('Uninstall ownership changed during interruption')
    receipt = transaction['receipt']
    target, _, _ = _paths(root, slug)
    rp = _receipt(state, slug)
    if rp.is_symlink():
        raise ValueError('Symlinked receipt during uninstall recovery')
    active_receipt = _checked_receipt(_load(rp), slug) if rp.exists() else None
    if active_receipt not in (None, receipt):
        raise ValueError('Uninstall receipt changed; preserve files')
    _verify_backup_history(state, slug, receipt)
    archived = _backup_dir(state, slug, transaction['archive_id'])
    archived_manifest = _backup_manifest(state, slug, transaction['archive_id'])
    expected = receipt['files']
    archive_exists = archived.exists() or archived.is_symlink()
    target_exists = target.exists() or target.is_symlink()
    if archive_exists:
        if archived.is_symlink() or not archived.is_dir() or _inventory(archived) != expected:
            raise ValueError('Uninstalled archive was changed; preserve data')
    if target_exists:
        if target.is_symlink() or not target.is_dir() or _inventory(target) != expected:
            raise ValueError('Uninstall target was changed; preserve data')
    manifest = {
        'schema': SCHEMA, 'kind': 'pre_replace_backup', 'slug': slug,
        'backup_id': transaction['archive_id'],
        'transaction': transaction['archive_id'],
        'previous_receipt': receipt, 'files': expected,
    }
    manifest_exists = archived_manifest.exists() or archived_manifest.is_symlink()
    if manifest_exists:
        if archived_manifest.is_symlink() or _checked_backup(
                _load(archived_manifest), slug,
                transaction['archive_id']) != manifest:
            raise ValueError('Uninstalled archive manifest changed')
        if not archive_exists:
            raise ValueError('Archived manifest exists without its files')
    if active_receipt is None:
        if (target_exists or not archive_exists or current_marker != marker
                or not manifest_exists):
            raise ValueError('Ambiguous completion of interrupted uninstall')
        _history(state, slug, marker)
        outcome = 'archived_uninstall_commit_recovered'
    else:
        if target_exists and archive_exists:
            raise ValueError('Both active target and uninstall archive exist')
        if not target_exists and not archive_exists:
            raise ValueError('Active Skill missing and no uninstall archive exists')
        if archive_exists:
            archived.rename(target)
            _sync(target.parent)
        if manifest_exists:
            archived_manifest.unlink()
            _sync(archived_manifest.parent)
        path = _marker_path(state, slug)
        if current_marker == marker:
            if prior is None:
                path.unlink()
                _sync(path.parent)
            else:
                _atomic_record(path, prior, marker)
        outcome = 'interrupted_archived_uninstall_rolled_back'
    journal = _journal(state, slug)
    journal.unlink()
    _sync(journal.parent)
    return outcome
