#!/usr/bin/env python3
"""Phase 40: explicit Codex project Skill installation, no implicit overwrite.

Only an existing selected Git project root may be modified. Full source/ZIP
integrity, an exact read-only target binding and local interactive consent
are required. No downloaded Skill instructions or dependencies are executed.
"""
import contextlib
import json
import os
import re
import secrets
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
    for candidate in (state, state/'receipts', state/'journals', state/'stage'):
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
            or data.get('action') != 'fresh_install' or data.get('slug') != slug
            or not HEX64.fullmatch(str(data.get('plan_id')))
            or not HEX64.fullmatch(str(data.get('binding')))
            or not re.fullmatch(r'[0-9a-f]{32}', str(data.get('transaction')))
            or not isinstance(data.get('files'), list) or not data['files']):
        raise ValueError('Invalid GASL ownership receipt')
    _check_list(data['files'])
    return data


def _checked_journal(data, slug):
    if (not isinstance(data, dict) or data.get('schema') != SCHEMA
            or data.get('slug') != slug or data.get('operation') not in ('install','uninstall')):
        raise ValueError('Invalid GASL transaction journal')
    _checked_receipt(data.get('receipt'), slug)
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
                 state/'receipts', state/'journals', state/'stage'):
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
    eligible = not target.exists() and not existing_receipt and not pending
    return {
        'status': 'real_project_install_preview_only', 'host': 'codex',
        'scope': 'project', 'plan_id': plan_id, 'slug': slug,
        'relative_target': relative, 'file_count': len(rows),
        'state_binding_id': preflight['state_binding_id'],
        'prior_target_state': preflight['prior_target_state'],
        'managed_receipt_exists': existing_receipt,
        'pending_transaction_exists': pending,
        'eligible_for_fresh_install': eligible,
        'existing_skill_replace_supported': False,
        'requires_human_tty_confirmation': True,
        'installation_performed': False,
        'third_party_skill_executed': False,
    }


def _stage(path, rows):
    path.mkdir(mode=0o700)
    for _, rel, data, _ in rows:
        destination = path.joinpath(*rel.split('/'))
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
    _sync(path)


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
    root = _root(selected_root)
    target, _, state = _paths(root, slug)
    receipt_path = _receipt(state, slug)
    record = _checked_receipt(_load(receipt_path), slug)
    if not target.is_dir() or target.is_symlink() or _inventory(target) != record['files']:
        raise ValueError('Installed Skill changed; refusal preserves user edits')
    _confirm(_remove_phrase(slug, record['plan_id']), reader)
    with _lock(root, slug) as state:
        if _journal(state, slug).exists():
            raise ValueError('Pending transaction requires recovery')
        record = _checked_receipt(_load(receipt_path), slug)
        if _inventory(target) != record['files']:
            raise ValueError('Installed Skill changed since approval')
        retired = state/'stage'/('retired-'+record['transaction'])
        if retired.exists() or retired.is_symlink():
            raise ValueError('Conflicting staged retirement')
        journal = _journal(state, slug)
        _new(journal, {'schema': SCHEMA, 'slug': slug,
                       'operation': 'uninstall', 'receipt': record})
        target.rename(retired)
        _sync(target.parent)
        # Keep the old bytes until receipt deletion, so recovery can restore.
        receipt_path.unlink()
        _sync(receipt_path.parent)
        _remove_verified_dir(retired, record['files'])
        journal.unlink()
        _sync(journal.parent)
    return {'status': 'codex_project_skill_uninstalled', 'slug': slug,
            'real_uninstall_performed': True, 'third_party_skill_executed': False}


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
