#!/usr/bin/env python3
"""Phase 44: manually attested reconciliation of orphaned pre-Phase-43 backups.

Historical manifests verify bytes and version ancestry, NOT the ownership of
the original project. This is a separate, opt-in path, never an automatic claim.
"""
import hashlib
import os
import re
import secrets

from codex_project_install import (
    SCHEMA, _root, _paths, _receipt, _journal, _backup_dir, _backup_manifest,
    _checked_backup, _checked_receipt, _inventory, _load, _serialized, _lock,
    _copy_backup_stage, _new, _sync, _confirm, _remove_verified_dir,
)
from codex_uninstalled_restore import _marker_path

ID32 = re.compile(r'^[0-9a-f]{32}$')
SCHEMA_PREFLIGHT = 'gasl-legacy-backup-manual-attestation-v1'
ROOT_SKILL = 'SKILL.md'


def _check_historical_skill_name(path, slug):
    """Conservative static name check; never interpret or execute Skill content."""
    if path.is_symlink() or not path.is_file():
        raise ValueError('Legacy SKILL.md must be a regular file')
    lines = path.read_bytes().splitlines()
    if not lines or lines[0].strip() != b'---':
        raise ValueError('Legacy SKILL.md lacks simple frontmatter')
    name = None
    closed = False
    for raw in lines[1:100]:
        line = raw.strip()
        if line == b'---':
            closed = True
            break
        if line.startswith(b'name:'):
            value = line[5:].strip().strip(b'\"').strip(b"'")
            name = value.decode('utf-8', errors='replace')
    if not closed or name != slug:
        raise ValueError('Legacy SKILL.md name does not match selected Skill')
    return True


def _legacy_history(root, slug):
    """Only a complete, unambiguous, hash-verified local backup chain qualifies."""
    target, relative, state = _paths(root, slug)
    if target.exists() or target.is_symlink():
        raise ValueError('Legacy reconciliation requires an empty Skill destination')
    for record in (_receipt(state, slug), _journal(state, slug), _marker_path(state, slug)):
        if record.exists() or record.is_symlink():
            raise ValueError('Existing receipt, journal or ownership marker blocks legacy recovery')

    base = state / 'backups' / slug
    if base.is_symlink() or not base.is_dir():
        raise ValueError('No regular legacy backup directory exists')
    children = list(base.iterdir())
    if len(children) > 2000 or not children:
        raise ValueError('Legacy backup directory too large or empty')
    dirs, manifests = set(), set()
    for child in children:
        name = child.name
        if child.is_symlink():
            raise ValueError('Symlinked legacy backup entry refused')
        if child.is_dir() and ID32.fullmatch(name):
            dirs.add(name)
        elif child.is_file() and name.endswith('.json') and ID32.fullmatch(name[:-5]):
            manifests.add(name[:-5])
        else:
            raise ValueError('Unexpected entry in legacy backup storage')
    if dirs != manifests or not dirs or len(dirs) >= 1000:
        raise ValueError('Unpaired, absent, or excessive legacy backup records')
    entries = {}
    for ident in sorted(dirs):
        m = _checked_backup(_load(_backup_manifest(state, slug, ident)), slug, ident)
        if _inventory(_backup_dir(state, slug, ident)) != m['files']:
            raise ValueError('Changed legacy backup files; refuse reconciliation')
        if not any(x['path'] == ROOT_SKILL for x in m['files']):
            raise ValueError('Legacy backup missing SKILL.md')
        _check_historical_skill_name(
            _backup_dir(state, slug, ident) / ROOT_SKILL, slug)
        prior = m['previous_receipt']
        ancestors = prior.get('backup_ids', []) if prior else []
        if ident in ancestors:
            raise ValueError('Cyclic legacy backup ancestry')
        entries[ident] = {'manifest': m, 'ancestors': ancestors}

    # A complete chain is demonstrable when each manifest's previous receipt
    # references precisely the preceding version IDs in order.
    sequence = sorted(entries, key=lambda key: (len(entries[key]['ancestors']), key))
    for index, ident in enumerate(sequence):
        if entries[ident]['ancestors'] != sequence[:index]:
            raise ValueError('Ambiguous, incomplete or foreign legacy backup ancestry')
    return target, relative, state, sequence, entries


def _snapshot(root, slug, selected_id):
    if not ID32.fullmatch(str(selected_id)):
        raise ValueError('Exact 32-hex legacy backup ID required')
    target, relative, state, sequence, entries = _legacy_history(root, slug)
    if selected_id not in entries:
        raise ValueError('Selected legacy backup not in verified local chain')
    signatures = []
    for ident in sequence:
        manifest = entries[ident]['manifest']
        signatures.append({
            'id': ident,
            'sha256': hashlib.sha256(_serialized(manifest)).hexdigest(),
            'files': manifest['files'],
        })
    snapshot = {
        'schema': SCHEMA_PREFLIGHT,
        'target_sha256': hashlib.sha256(os.fsencode(str(target))).hexdigest(),
        'skill': slug, 'selected_backup_id': selected_id,
        'ordered_history': signatures,
        'receipt_absent': True, 'ownership_marker_absent': True,
    }
    return {
        'target': target, 'relative': relative, 'state': state,
        'sequence': sequence, 'entries': entries, 'chosen': entries[selected_id]['manifest'],
        'binding': hashlib.sha256(_serialized(snapshot)).hexdigest(),
        'history_digest': hashlib.sha256(_serialized(signatures)).hexdigest(),
    }


def _portable_orphan_history(slug, selected_root):
    """Bounded, read-only orphan inventory; no attestation or write binding."""
    from codex_migration_audit import _directory, _record, _inventory_checked, _present, _nonempty
    from transaction_file_lock import require_windows_filename_safety
    from codex_project_install import SLUG
    if not isinstance(slug, str) or not SLUG.fullmatch(slug):
        raise ValueError('Exact safe Skill slug required')
    require_windows_filename_safety(slug, portable=True)
    if os.name == 'nt':
        from windows_user_profile import assert_no_reparse_components
        assert_no_reparse_components(selected_root)
    root = _root(selected_root)
    target, relative, state = _paths(root, slug)
    for folder in (state, state/'receipts', state/'journals', state/'uninstalled',
                   state/'stage', state/'backups', state/'backups'/slug):
        _directory(folder)
    if (_present(target) or any(_present(p) for p in (
            _receipt(state, slug), _journal(state, slug), _marker_path(state, slug)))
            or _nonempty(state/'stage')):
        raise ValueError('Legacy orphan audit requires empty destination and no pending ownership state')
    parent = state/'backups'/slug
    if not parent.is_dir():
        raise ValueError('No regular legacy backup directory exists')
    dirs, manifests = set(), set()
    for index, child in enumerate(parent.iterdir()):
        if index >= 2000:
            raise ValueError('Excessive legacy history')
        if ID32.fullmatch(child.name):
            _directory(child)
            if not child.is_dir():
                raise ValueError('Invalid legacy backup directory')
            dirs.add(child.name)
        elif child.name.endswith('.json') and ID32.fullmatch(child.name[:-5]):
            manifests.add(child.name[:-5])
        else:
            raise ValueError('Unexpected legacy backup entry')
    if not dirs or dirs != manifests or len(dirs) >= 1000:
        raise ValueError('Unpaired or excessive legacy backup records')
    entries = {}
    digests = {}
    for ident in sorted(dirs):
        manifest, digest = _record(_backup_manifest(state, slug, ident))
        _checked_backup(manifest, slug, ident)
        folder = _backup_dir(state, slug, ident)
        if _inventory_checked(folder) != manifest['files']:
            raise ValueError('Changed legacy backup files')
        _check_historical_skill_name(folder/ROOT_SKILL, slug)
        prior = manifest['previous_receipt']
        ancestors = prior.get('backup_ids', []) if prior else []
        entries[ident] = {'manifest': manifest, 'ancestors': ancestors}
        digests[ident] = digest
    sequence = sorted(entries, key=lambda key: (len(entries[key]['ancestors']), key))
    for index, ident in enumerate(sequence):
        if entries[ident]['ancestors'] != sequence[:index]:
            raise ValueError('Ambiguous or incomplete legacy backup ancestry')
    return relative, sequence, entries, digests


def audit_portable_legacy_backups(slug, selected_root):
    first = _portable_orphan_history(slug, selected_root)
    if first != _portable_orphan_history(slug, selected_root):
        raise ValueError('Legacy audit state changed during inspection')
    relative, sequence, entries, _ = first
    return {
        'status': 'legacy_backups_audited_read_only', 'host': 'codex',
        'scope': 'project', 'slug': slug, 'relative_target': relative,
        'backup_count': len(sequence),
        'backups': [{
            'backup_id': ident, 'file_count': len(entries[ident]['manifest']['files']),
            'historical_receipt_present': entries[ident]['manifest']['previous_receipt'] is not None,
            'upstream_plan_id_in_historical_receipt': (
                entries[ident]['manifest']['previous_receipt']['plan_id']
                if entries[ident]['manifest']['previous_receipt'] else None),
            'backup_integrity_verified': True,
            'historical_project_ownership_verified': False,
        } for ident in sequence],
        'ancestry_complete': True, 'historical_project_ownership_verified': False,
        'manual_ownership_attestation_required': True,
        'reconciliation_write_enabled': False, 'approval_granted': False,
        'real_host_files_modified': False, 'third_party_skill_executed': False,
    }


def audit_legacy_backups(slug, selected_root):
    """Read-only discovery; does not infer project ownership."""
    if os.name == "nt":
        return audit_portable_legacy_backups(slug, selected_root)
    root = _root(selected_root)
    target, relative, state, sequence, entries = _legacy_history(root, slug)
    rows = []
    for ident in sequence:
        manifest = entries[ident]['manifest']
        prior = manifest['previous_receipt']
        rows.append({
            'backup_id': ident,
            'file_count': len(manifest['files']),
            'historical_receipt_present': prior is not None,
            'upstream_plan_id_in_historical_receipt': prior['plan_id'] if prior else None,
            'backup_integrity_verified': True,
            'historical_project_ownership_verified': False,
        })
    return {
        'status': 'legacy_backups_audited_read_only',
        'host': 'codex', 'scope': 'project', 'slug': slug,
        'relative_target': relative,
        'backup_count': len(rows), 'backups': rows,
        'ancestry_complete': True,
        'historical_project_ownership_verified': False,
        'manual_ownership_attestation_required': True,
        'real_host_files_modified': False,
        'third_party_skill_executed': False,
    }


def preview_legacy_reinstall(slug, selected_root, backup_id):
    if os.name == "nt":
        raise ValueError("Legacy ownership reconciliation is not enabled on Windows")
    root = _root(selected_root)
    s = _snapshot(root, slug, backup_id)
    return {
        'status': 'legacy_backup_reinstall_preview_only',
        'host': 'codex', 'scope': 'project', 'slug': slug,
        'relative_target': s['relative'],
        'selected_backup_id': backup_id,
        'state_binding_id': s['binding'],
        'file_count': len(s['chosen']['files']),
        'historical_backups_retained': len(s['sequence']),
        'history_integrity_verified': True,
        'historical_project_ownership_verified': False,
        'manual_ownership_attestation_required': True,
        'will_not_claim_upstream_pin': True,
        'requires_local_tty_confirmation': True,
        'reinstall_performed': False,
        'third_party_skill_executed': False,
    }


def _phrase(slug, backup_id, binding):
    return ('ATTEST-LEGACY-OWNERSHIP ' + slug.upper() + ' '
            + backup_id[:12].upper() + ' ' + binding[:12].upper()
            + ' REINSTALL-ONLY-IN-THIS-PROJECT')


def _local_plan(selected_id, manifest):
    return hashlib.sha256(
        b'gasl-legacy-user-attested-local-v1\x00'
        + _serialized({'id': selected_id, 'files': manifest['files']})
    ).hexdigest()


def _journal_valid(data, slug):
    if (not isinstance(data, dict)
            or data.get('schema') != SCHEMA
            or data.get('operation') != 'legacy_reinstall'
            or data.get('slug') != slug
            or not ID32.fullmatch(str(data.get('transaction')))
            or not ID32.fullmatch(str(data.get('selected_backup_id')))
            or not re.fullmatch(r'[a-f0-9]{64}', str(data.get('binding')))):
        raise ValueError('Invalid legacy reinstall journal')
    receipt = _checked_receipt(data.get('receipt'), slug)
    if (receipt['action'] != 'legacy_reconcile_install'
            or receipt['transaction'] != data['transaction']
            or receipt['binding'] != data['binding']
            or receipt['legacy_selected_backup_id'] != data['selected_backup_id']
            or receipt.get('historical_project_ownership_verified') is not False
            or receipt.get('manual_ownership_attested') is not True
            or receipt.get('source_kind') != 'unmanaged'
            or receipt.get('legacy_identity_derived') is not True):
        raise ValueError('Legacy reinstall journal origin incorrectly claimed')
    if (receipt['backup_ids'] != data.get('history_ids')
            or not re.fullmatch(r'[a-f0-9]{64}', str(data.get('history_digest')))):
        raise ValueError('Legacy reinstall journal history mismatch')
    manifest = _checked_backup(data.get('selected_manifest'), slug,
                               data['selected_backup_id'])
    if (receipt['files'] != manifest['files']
            or receipt['plan_id'] != _local_plan(data['selected_backup_id'], manifest)):
        raise ValueError('Legacy reinstall journal inventory or identity mismatch')
    return data


def reinstall_legacy_backup(slug, selected_root, backup_id, binding, *, reader=None):
    root = _root(selected_root)
    preview = preview_legacy_reinstall(slug, root, backup_id)
    if binding != preview['state_binding_id']:
        raise ValueError('Legacy backup or selected project changed since preview')
    _confirm(_phrase(slug, backup_id, binding), reader)
    with _lock(root, slug) as state:
        snap = _snapshot(root, slug, backup_id)
        if snap['binding'] != binding:
            raise ValueError('Legacy backups changed after manual attestation')
        tx = secrets.token_hex(16)
        stage = state / 'stage' / tx
        selected = snap['chosen']
        _copy_backup_stage(_backup_dir(state, slug, backup_id), stage,
                           selected['files'])
        receipt = {
            'schema': SCHEMA, 'action': 'legacy_reconcile_install', 'slug': slug,
            'transaction': tx, 'plan_id': _local_plan(backup_id, selected),
            'binding': binding, 'files': selected['files'],
            'backup_ids': list(snap['sequence']),
            'source_kind': 'unmanaged', 'legacy_identity_derived': True,
            'legacy_selected_backup_id': backup_id,
            'historical_project_ownership_verified': False,
            'manual_ownership_attested': True,
        }
        transaction = {
            'schema': SCHEMA, 'operation': 'legacy_reinstall',
            'slug': slug, 'transaction': tx,
            'binding': binding, 'selected_backup_id': backup_id,
            'selected_manifest': selected, 'history_ids': list(snap['sequence']),
            'history_digest': snap['history_digest'], 'receipt': receipt,
        }
        _journal_valid(transaction, slug)
        journal = _journal(state, slug)
        try:
            _new(journal, transaction)
        except Exception:
            if not journal.exists() and not journal.is_symlink():
                _remove_verified_dir(stage, receipt['files'])
            raise
        # The original files and metadata are never overwritten.
        if (_receipt(state, slug).exists()
                or _marker_path(state, slug).exists()
                or snap['target'].exists() or snap['target'].is_symlink()
                or _legacy_history_for_recovery(
                    root, slug, snap['sequence'], snap['history_digest']) is not True):
            raise ValueError('Legacy destination or backup history changed after journal')
        stage.rename(snap['target'])
        _sync(snap['target'].parent)
        if _inventory(snap['target']) != receipt['files']:
            raise ValueError('Activated legacy backup bytes changed')
        _new(_receipt(state, slug), receipt)
        journal.unlink()
        _sync(journal.parent)
    return {
        'status': 'legacy_skill_reinstalled_with_manual_ownership_attestation',
        'slug': slug, 'restored_backup_id': backup_id,
        'file_count': len(receipt['files']),
        'backup_history_retained': True,
        'historical_project_ownership_verified': False,
        'manual_ownership_attested': True,
        'real_project_skill_installed': True,
        'third_party_skill_executed': False,
    }


def _legacy_history_for_recovery(root, slug, expected_ids, expected_digest):
    """Inspect backups only, including while journal or restored Skill exists."""
    _, _, state = _paths(root, slug)
    base = state / 'backups' / slug
    if base.is_symlink() or not base.is_dir():
        raise ValueError('Legacy backup history disappeared')
    names = set()
    for item in base.iterdir():
        if item.is_symlink():
            raise ValueError('Symlinked historical backup')
        if item.is_dir() and ID32.fullmatch(item.name):
            names.add((item.name, 'dir'))
        elif item.is_file() and item.name.endswith('.json') and ID32.fullmatch(item.name[:-5]):
            names.add((item.name[:-5], 'manifest'))
        else:
            raise ValueError('Unexpected untracked legacy backup entry')
    expected = {(ident, part) for ident in expected_ids for part in ('dir', 'manifest')}
    if names != expected:
        raise ValueError('Legacy backup history changed')
    signatures = []
    for index, ident in enumerate(expected_ids):
        manifest = _checked_backup(_load(_backup_manifest(state, slug, ident)), slug, ident)
        prior = manifest['previous_receipt']
        if (prior.get('backup_ids', []) if prior else []) != expected_ids[:index]:
            raise ValueError('Historical ancestry changed')
        if _inventory(_backup_dir(state, slug, ident)) != manifest['files']:
            raise ValueError('Historical backup bytes changed')
        _check_historical_skill_name(
            _backup_dir(state, slug, ident) / ROOT_SKILL, slug)
        signatures.append({
            'id': ident,
            'sha256': hashlib.sha256(_serialized(manifest)).hexdigest(),
            'files': manifest['files'],
        })
    if hashlib.sha256(_serialized(signatures)).hexdigest() != expected_digest:
        raise ValueError('Historical backup manifests changed since approval')
    return True


def recover_legacy_reinstall(root, state, slug, data):
    _journal_valid(data, slug)
    receipt_path = _receipt(state, slug)
    if receipt_path.is_symlink():
        raise ValueError('Unsafe legacy receipt')
    receipt = _checked_receipt(_load(receipt_path), slug) if receipt_path.exists() else None
    if receipt not in (None, data['receipt']):
        raise ValueError('Legacy receipt changed since pending operation')
    if _marker_path(state, slug).exists() or _marker_path(state, slug).is_symlink():
        raise ValueError('Unexpected legacy marker during recovery')
    _legacy_history_for_recovery(root, slug, data['history_ids'],
                                 data['history_digest'])
    chosen = _checked_backup(
        _load(_backup_manifest(state, slug, data['selected_backup_id'])),
        slug, data['selected_backup_id'])
    if chosen != data['selected_manifest']:
        raise ValueError('Selected legacy manifest changed')
    target, _, _ = _paths(root, slug)
    stage = state / 'stage' / data['transaction']
    expected = data['receipt']['files']
    if stage.exists() or stage.is_symlink():
        if stage.is_symlink() or _inventory(stage) != expected:
            raise ValueError('Pending legacy stage changed')
        staged = True
    else:
        staged = False
    if target.exists() or target.is_symlink():
        if target.is_symlink() or _inventory(target) != expected:
            raise ValueError('Installed legacy Skill changed; preserve user edits')
        activated = True
    else:
        activated = False
    if receipt is not None:
        if not activated:
            raise ValueError('Committed legacy install missing activated Skill')
        result = 'legacy_reinstall_commit_recovered'
    else:
        if activated:
            _remove_verified_dir(target, expected)
        result = 'interrupted_legacy_reinstall_rolled_back'
    if staged:
        _remove_verified_dir(stage, expected)
    journal = _journal(state, slug)
    journal.unlink()
    _sync(journal.parent)
    return result
