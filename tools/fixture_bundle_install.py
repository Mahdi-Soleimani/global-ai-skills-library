#!/usr/bin/env python3
"""Materialize a pinned private Skill ZIP only in a fresh, disposable Host fixture.

This implements REAL filesystem staging, replacement, backup and rollback on
an isolated temporary profile. It NEVER enables a real-user Host installer,
executes a Skill, connects an account, or accepts an arbitrary destination.
"""
import hashlib
import json
import os
import re
import secrets
import zipfile
from pathlib import Path

from host_adapters import SLUG, _checked_fixture, _path_within_fixture, _target_for_fixture
from host_transaction_fixture import _new_root
from install_bundle import MAX_BYTES, MAX_FILES, MAX_ONE_FILE, SCHEMA as BUNDLE_SCHEMA
from queue_ingest import collision_key, git_blob, no_symlink, safe_path
from transaction_file_lock import is_redirected, require_windows_filename_safety

SCHEMA = 'gasl-private-bundle-fixture-transaction-v1'
JOURNAL = '.gasl-bundle-fixture-transaction.json'
TRANSACTION = re.compile(r'^[0-9a-f]{32}$')
HEX = re.compile(r'^[0-9a-f]{64}$')


def _inventory(folder):
    """Full regular-file inventory; reject symlinks, empty directories, collisions."""
    if not folder.is_dir() or is_redirected(folder):
        raise ValueError('Fixture target is not a regular directory')
    entries, total, seen = [], 0, set()
    actual_dirs = set()
    for file in sorted(folder.rglob('*')):
        if is_redirected(file):
            raise ValueError('Symlink in fixture inventory')
        if file.is_dir():
            actual_dirs.add(file.relative_to(folder).as_posix())
            continue
        if not file.is_file():
            raise ValueError('Non-regular fixture entry')
        rel = safe_path(file.relative_to(folder).as_posix())
        key = collision_key(rel)
        if key in seen:
            raise ValueError('Colliding fixture paths')
        seen.add(key)
        size = file.stat().st_size
        total += size
        if size > MAX_ONE_FILE or total > MAX_BYTES or len(entries) >= MAX_FILES:
            raise ValueError('Fixture inventory exceeds limits')
        entries.append({'path': rel, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
    expected_dirs = {'/'.join(row['path'].split('/')[:i])
                     for row in entries for i in range(1, len(row['path'].split('/')))}
    if actual_dirs != expected_dirs:
        raise ValueError('Empty or untracked directory in fixture inventory')
    # WindowsPath sorts paths case-insensitively; canonical manifests require
    # a case-sensitive relative POSIX-path order on every operating system.
    return sorted(entries, key=lambda row: row['path'])


def _same_inventory(path, entries):
    if not path.is_dir() or is_redirected(path):
        return False
    try:
        return _inventory(path) == entries
    except (OSError, ValueError):
        return False


def _remove_verified_dir(path, entries):
    if not _same_inventory(path, entries):
        raise ValueError('Fixture content changed: refuse to remove user edits')
    for entry in entries:
        file = path / entry['path']
        if is_redirected(file) or hashlib.sha256(file.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('Unexpected file modification during fixture cleanup')
        file.unlink()
    for folder in sorted((x for x in path.rglob('*') if x.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if is_redirected(folder):
            raise ValueError('Unexpected symlink during fixture cleanup')
        folder.rmdir()
    path.rmdir()


def _check_list(items):
    if not isinstance(items, list) or len(items) > MAX_FILES:
        raise ValueError('Invalid fixture journal inventory')
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {'path', 'sha256'}:
            raise ValueError('Invalid fixture journal entry')
        path = safe_path(item['path'])
        if collision_key(path) in seen or not HEX.fullmatch(str(item['sha256'])):
            raise ValueError('Duplicate or invalid fixture journal entry')
        seen.add(collision_key(path))
    if items != sorted(items, key=lambda e: e['path']):
        raise ValueError('Fixture journal inventory not canonical')


def _read_bundle(bundle_root, plan_id, agent, scope):
    """Check version+host-bound sidecar and all ZIP entries before any writes."""
    if not HEX.fullmatch(str(plan_id)):
        raise ValueError('Exact SHA-256 plan ID required')
    if agent not in ('codex', 'cursor', 'claude-code') or scope not in ('project', 'user'):
        raise ValueError('Only documented filesystem Host fixtures are supported')
    root = Path(bundle_root).resolve()
    directory = no_symlink(root, root / 'private' / 'install-bundles')
    meta_path = no_symlink(root, directory / (plan_id + '.json'))
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    if (meta.get('schema_version') != BUNDLE_SCHEMA
            or meta.get('agent') != agent or meta.get('scope') != scope
            or meta.get('plan_id') != plan_id
            or meta.get('manual_review_required') is not True
            or meta.get('host_installation_approved') is not False
            or meta.get('production_installation_enabled') is not False):
        raise ValueError('Bundle is not bound to this Host, scope and non-install plan')
    archive_path = no_symlink(root, directory / (plan_id + '.zip'))
    if archive_path.stat().st_size > MAX_BYTES + (MAX_FILES * 2048):
        raise ValueError('Excessive ZIP archive size')
    if (not HEX.fullmatch(str(meta.get('archive_sha256')))
            or hashlib.sha256(archive_path.read_bytes()).hexdigest() != meta['archive_sha256']):
        raise ValueError('Private bundle ZIP digest does not match sidecar')
    expected = meta['entries']
    if not isinstance(expected, list) or not (1 <= len(expected) <= MAX_FILES):
        raise ValueError('Invalid ZIP entry manifest')
    rows = []
    total = 0
    seen = set()
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        if len(infos) != len(expected):
            raise ValueError('ZIP count differs from manifest')
        for info, item in zip(infos, expected):
            if not isinstance(item, dict) or set(item) != {'archive_path', 'sha256'}:
                raise ValueError('Invalid ZIP entry metadata')
            name = safe_path(info.filename)
            if name != item['archive_path'] or not HEX.fullmatch(str(item['sha256'])):
                raise ValueError('ZIP entry identity mismatch')
            parts = name.split('/')
            if len(parts) < 2 or not SLUG.fullmatch(parts[0]):
                raise ValueError('Unsafe ZIP Skill folder')
            rel = safe_path('/'.join(parts[1:]))
            require_windows_filename_safety(rel)
            if collision_key(rel) in seen or rel.casefold() == 'source.json':
                raise ValueError('ZIP duplicate or reserved entry')
            seen.add(collision_key(rel))
            mode = (info.external_attr >> 16) & 0o170000
            if info.is_dir() or mode not in (0, 0o100000) or info.flag_bits & 0x1:
                raise ValueError('ZIP contains link, directory, or encrypted entry')
            if info.file_size < 0 or info.file_size > MAX_ONE_FILE:
                raise ValueError('ZIP file size exceeded limit')
            total += info.file_size
            if total > MAX_BYTES:
                raise ValueError('ZIP uncompressed total exceeds limit')
            data = archive.read(info)
            if len(data) != info.file_size or hashlib.sha256(data).hexdigest() != item['sha256']:
                raise ValueError('ZIP data differs from pinned evidence')
            rows.append((parts[0], rel, data, item['sha256']))
    slug = rows[0][0]
    if any(row[0] != slug for row in rows) or not any(row[1] == 'SKILL.md' for row in rows):
        raise ValueError('ZIP must contain one Skill folder with SKILL.md')
    main = next(row for row in rows if row[1] == 'SKILL.md')
    if (not re.fullmatch(r'[0-9a-f]{40}', str(meta.get('pinned_skill_md_blob_sha')))
            or git_blob(main[2]) != meta['pinned_skill_md_blob_sha']):
        raise ValueError('ZIP main Skill Blob does not match pinned evidence')
    rel_names = {collision_key(row[1]) for row in rows}
    if any(collision_key('/'.join(row[1].split('/')[:i])) in rel_names
           for row in rows for i in range(1, len(row[1].split('/')))):
        raise ValueError('ZIP file/directory collision')
    return slug, rows


def _write_journal(root, payload):
    path = _path_within_fixture(root, JOURNAL)
    with path.open('xb') as handle:
        handle.write((json.dumps(payload, sort_keys=True, separators=(',', ':')) + '\n').encode())
        handle.flush()
        os.fsync(handle.fileno())


def _load_journal(root):
    path = _path_within_fixture(root, JOURNAL)
    if not path.is_file() or path.stat().st_size > 35000:
        raise ValueError('No valid fixture install journal')
    payload = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(payload, dict)
            or set(payload) != {'schema', 'tx', 'plan_id', 'agent', 'scope', 'slug',
                               'replaced', 'new_files', 'old_files'}
            or payload['schema'] != SCHEMA or not TRANSACTION.fullmatch(str(payload['tx']))
            or not HEX.fullmatch(str(payload['plan_id']))
            or payload['agent'] not in ('codex', 'cursor', 'claude-code')
            or payload['scope'] not in ('project', 'user')
            or not SLUG.fullmatch(str(payload['slug']))
            or not isinstance(payload['replaced'], bool)):
        raise ValueError('Invalid fixture install journal')
    _check_list(payload['new_files'])
    _check_list(payload['old_files'])
    if not payload['new_files'] or (payload['replaced'] and not payload['old_files']) or (not payload['replaced'] and payload['old_files']):
        raise ValueError('Inconsistent fixture transaction inventory')
    return payload


def stage_bundle_fixture(fixture, bundle_root, plan_id, agent, scope, acknowledgement, *, replace_existing=False):
    """Stage actual ZIP bytes under temporary fixture only; no Host execution."""
    fixture = _checked_fixture(fixture)
    if acknowledgement != plan_id:
        raise ValueError('Exact plan acknowledgement required for fixture transaction')
    if _path_within_fixture(fixture, JOURNAL).exists():
        raise ValueError('Existing fixture transaction must be rolled back first')
    slug, entries = _read_bundle(bundle_root, plan_id, agent, scope)
    target = _target_for_fixture(fixture, agent, scope, slug)
    previous = target.exists() or target.is_symlink()
    if previous and not replace_existing:
        raise ValueError('Existing Skill collision: explicit fixture replacement required')
    if not previous and replace_existing:
        raise ValueError('Cannot replace absent fixture Skill')
    old = _inventory(target) if previous else []
    if previous and not old:
        raise ValueError('Empty existing fixture target cannot be safely replaced')
    tx = secrets.token_hex(16)
    stage = _path_within_fixture(fixture, 'stage/' + tx)
    stage.mkdir(parents=True, exist_ok=False)
    for _, rel, data, _ in entries:
        dst = _path_within_fixture(fixture, 'stage/' + tx + '/' + rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        with dst.open('xb') as handle:
            handle.write(data)
    new_files = _inventory(stage)
    expected_files = sorted([{'path': row[1], 'sha256': row[3]} for row in entries], key=lambda e: e['path'])
    if new_files != expected_files:
        raise ValueError('Staging verification failed')
    payload = {'schema': SCHEMA, 'tx': tx, 'plan_id': plan_id, 'agent': agent,
               'scope': scope, 'slug': slug, 'replaced': previous,
               'new_files': new_files, 'old_files': old}
    _write_journal(fixture, payload)
    return {'status': 'fixture_bundle_staged', 'relative_target': target.relative_to(fixture).as_posix(),
            'file_count': len(new_files), 'replaced': previous, 'real_host_files_modified': False,
            'third_party_skill_executed': False, 'production_installation_enabled': False}


def activate_bundle_fixture(fixture, *, stop_after='activated'):
    """Actual fixture directory rename with a checked versioned backup."""
    fixture = _checked_fixture(fixture)
    if stop_after not in ('staged', 'backed_up', 'activated'):
        raise ValueError('Invalid fixture transaction checkpoint')
    payload = _load_journal(fixture)
    target = _target_for_fixture(fixture, payload['agent'], payload['scope'], payload['slug'])
    stage = _path_within_fixture(fixture, 'stage/' + payload['tx'])
    backup = _path_within_fixture(fixture, 'backup/' + payload['tx'])
    if not _same_inventory(stage, payload['new_files']):
        raise ValueError('Staged bundle changed before activation')
    if payload['replaced']:
        if not _same_inventory(target, payload['old_files']) or backup.exists():
            raise ValueError('Existing Skill changed or backup collision detected')
    elif target.exists() or target.is_symlink():
        raise ValueError('Unexpected target collision')
    if stop_after == 'staged':
        return {'status': 'fixture_interrupted_after_staging', 'real_host_files_modified': False}
    if payload['replaced']:
        backup.parent.mkdir(parents=True, exist_ok=True)
        target.rename(backup)
    if stop_after == 'backed_up':
        return {'status': 'fixture_interrupted_after_backup', 'real_host_files_modified': False}
    target.parent.mkdir(parents=True, exist_ok=True)
    stage.rename(target)
    return {'status': 'fixture_bundle_activated', 'real_host_files_modified': False,
            'third_party_skill_executed': False, 'production_installation_enabled': False}


def rollback_bundle_fixture(fixture):
    """Refuse to destroy changed files; restore exact prior fixture version."""
    fixture = _checked_fixture(fixture)
    payload = _load_journal(fixture)
    target = _target_for_fixture(fixture, payload['agent'], payload['scope'], payload['slug'])
    stage = _path_within_fixture(fixture, 'stage/' + payload['tx'])
    backup = _path_within_fixture(fixture, 'backup/' + payload['tx'])
    # Validate all existing trees before any destructive operations.
    if stage.exists() and not _same_inventory(stage, payload['new_files']):
        raise ValueError('Staged bundle modified; preserve fixture for manual inspection')
    if backup.exists() and not _same_inventory(backup, payload['old_files']):
        raise ValueError('Backup modified; preserve fixture for manual inspection')
    if target.is_symlink():
        raise ValueError('Fixture target symlink refused')
    if payload['replaced']:
        if backup.exists():
            if target.exists() and not _same_inventory(target, payload['new_files']):
                raise ValueError('Activated files modified; preserve backup and user changes')
        elif not _same_inventory(target, payload['old_files']):
            raise ValueError('Original Skill missing with no valid backup')
    elif target.exists() and not _same_inventory(target, payload['new_files']):
        raise ValueError('New target modified; refuse to remove user edits')
    if backup.exists():
        if target.exists():
            _remove_verified_dir(target, payload['new_files'])
        backup.rename(target)
    elif target.exists() and not payload['replaced']:
        _remove_verified_dir(target, payload['new_files'])
    if stage.exists():
        _remove_verified_dir(stage, payload['new_files'])
    _path_within_fixture(fixture, JOURNAL).unlink()
    final = _same_inventory(target, payload['old_files']) if payload['replaced'] else not target.exists()
    if not final:
        raise ValueError('Fixture rollback verification failed')
    return {'status': 'fixture_bundle_rollback_verified', 'previous_files_restored': final,
            'real_host_files_modified': False, 'third_party_skill_executed': False,
            'production_installation_enabled': False}


def rehearse_private_bundle(plan_id, agent, scope, acknowledgement, *, bundle_root, scenario='fresh', stop_after='activated'):
    """One-shot actual filesystem transaction, but only on a new disposable fixture."""
    if scenario not in ('fresh', 'upgrade', 'conflict'):
        raise ValueError('Expected fresh, upgrade or conflict fixture scenario')
    if stop_after not in ('staged', 'backed_up', 'activated'):
        raise ValueError('Invalid fixture checkpoint')
    # Validate content before creating a temporary profile or touching any files.
    slug, _ = _read_bundle(bundle_root, plan_id, agent, scope)
    directory, fixture = _new_root()
    try:
        if scenario in ('upgrade', 'conflict'):
            target = _target_for_fixture(fixture, agent, scope, slug)
            target.mkdir(parents=True)
            (target / 'SKILL.md').write_bytes(b'---\nname: old-inert-fixture\ndescription: GASL previous dummy version\n---\n')
            (target / 'user-note.txt').write_bytes(b'USER_SENTINEL_MUST_SURVIVE\n')
        if scenario == 'conflict':
            target = _target_for_fixture(fixture, agent, scope, slug)
            baseline = _inventory(target)
            try:
                stage_bundle_fixture(fixture, bundle_root, plan_id, agent, scope, acknowledgement)
            except ValueError as exc:
                if 'Existing Skill collision' not in str(exc):
                    raise
                target = _target_for_fixture(fixture, agent, scope, slug)
                return {'status': 'existing_fixture_skill_preserved',
                        'original_files_unchanged': _same_inventory(target, baseline),
                        'real_host_files_modified': False, 'third_party_skill_executed': False,
                        'production_installation_enabled': False}
            raise AssertionError('Existing target collision was not refused')
        staged = stage_bundle_fixture(fixture, bundle_root, plan_id, agent, scope, acknowledgement,
                                     replace_existing=(scenario == 'upgrade'))
        state = activate_bundle_fixture(fixture, stop_after=stop_after)
        recovered = rollback_bundle_fixture(fixture)
        return {'status': recovered['status'], 'scenario': scenario, 'checkpoint': state['status'],
                'file_count': staged['file_count'], 'previous_files_restored': True,
                'real_host_files_modified': False, 'third_party_skill_executed': False,
                'production_installation_enabled': False}
    finally:
        directory.cleanup()
