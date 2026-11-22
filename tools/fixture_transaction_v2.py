#!/usr/bin/env python3
"""Phase 28: separate fixture-only approval, advisory lock, fsynced ZIP transaction.

There is deliberately no real-user installer in this module. Both the source
ZIP and all installation targets must belong to a disposable GASL fixture;
real user directories, account credentials, and Skill execution are excluded.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path

from fixture_bundle_install import (
    JOURNAL, _inventory, activate_bundle_fixture, rollback_bundle_fixture,
    stage_bundle_fixture,
)
from host_adapters import _checked_fixture, _path_within_fixture, _target_for_fixture
from host_target_preflight import inspect_selected_target
from host_transaction_fixture import _new_root

try:
    import fcntl
except ImportError:  # Unsupported platforms must fail closed, never omit locking.
    fcntl = None

SCHEMA = 'gasl-v28-fixture-consent-v1'
LOCK = '.gasl-phase28-transaction.lock'


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode('utf-8')).hexdigest()


def _sync_directory(folder):
    """Durability barrier for an existing fixture directory; unsupported => error."""
    flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)
    fd = os.open(folder, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _sync_tree(path):
    """fsync data before rename, then its directory metadata."""
    if path.is_symlink() or not path.is_dir():
        raise ValueError('Only a regular fixture staging directory may be synced')
    for item in sorted(path.rglob('*')):
        if item.is_symlink():
            raise ValueError('Symlink in fixture staging directory')
        if item.is_file():
            fd = os.open(item, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        elif not item.is_dir():
            raise ValueError('Non-regular fixture staging entry')
    for folder in sorted([path, *(x for x in path.rglob('*') if x.is_dir())],
                         key=lambda d: len(d.parts), reverse=True):
        _sync_directory(folder)


@contextlib.contextmanager
def _exclusive_fixture_lock(fixture):
    """Nonblocking, cooperative process lock; NEVER delete the lock inode."""
    fixture = _checked_fixture(fixture)
    if fcntl is None:
        raise RuntimeError('POSIX flock is unavailable: fixture transactions disabled')
    path = _path_within_fixture(fixture, LOCK)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags, 0o600)
    try:
        if not os.path.isfile(path) or os.stat(path).st_nlink != 1:
            raise ValueError('Fixture lock path is not a unique regular file')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Fixture transaction already locked by another process')
        _sync_directory(fixture)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _chosen_profile(fixture, scope):
    fixture = _checked_fixture(fixture)
    if scope not in ('project', 'user'):
        raise ValueError('Unknown test profile scope')
    relative = 'workspace' if scope == 'project' else 'home'
    root = _path_within_fixture(fixture, relative)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Test-only selected profile root must already exist')
    return root


def preview_fixture_consent(fixture, bundle_root, plan_id, agent, scope, action):
    """Separate, read-only challenge for exact ZIP, fixture target and action."""
    if action not in ('install', 'replace'):
        raise ValueError('Action must be install or replace')
    profile = _chosen_profile(fixture, scope)
    report = inspect_selected_target(plan_id, agent, scope, profile,
                                     bundle_root=bundle_root)
    has_prior = report['prior_target_state'] == 'existing_skill_collision'
    if has_prior != (action == 'replace'):
        raise ValueError('Requested action does not match exact prior target state')
    identity = {
        'schema': SCHEMA, 'fixture_only': True, 'plan_id': plan_id,
        'agent': agent, 'scope': scope, 'action': action,
        'state_binding_id': report['state_binding_id'],
        'bundle_sha256': report['bundle_sha256'],
        'selected_target_sha256': report['selected_target_sha256'],
    }
    return {
        'status': 'fixture_only_consent_preview',
        'approval_challenge': _digest(identity),
        'state_binding_id': report['state_binding_id'],
        'action': action, 'agent': agent, 'scope': scope,
        'plan_id': plan_id, 'bundle_sha256': report['bundle_sha256'],
        'prior_target_state': report['prior_target_state'],
        'real_user_authorization_collected': False,
        'real_host_files_modified': False,
        'production_installation_enabled': False,
        'third_party_skill_executed': False,
    }


def enact_fixture_transaction(fixture, bundle_root, plan_id, agent, scope, action,
                                exact_challenge, *, checkpoint='activated',
                                consent_request_id=None):
    """Materialize source bytes only in marked temp fixture, never a real Host."""
    if checkpoint not in ('staged', 'backed_up', 'activated'):
        raise ValueError('Unrecognized fixture checkpoint')
    fixture = _checked_fixture(fixture)
    with _exclusive_fixture_lock(fixture):
        expected = preview_fixture_consent(fixture, bundle_root, plan_id,
                                           agent, scope, action)
        if exact_challenge != expected['approval_challenge']:
            raise ValueError('Exact fixture-only consent challenge mismatch')
        if _path_within_fixture(fixture, JOURNAL).exists():
            raise ValueError('Unfinished fixture transaction must be recovered first')
        # Phase 30 opt-in: redeem one short-lived, independently confirmed
        # fixture receipt under the *same* exclusive lock as the file move.
        # On any later failure it remains consumed (conservative fail-closed).
        if consent_request_id is not None:
            from fixture_explicit_consent import consume_under_transaction_lock
            consume_under_transaction_lock(fixture, bundle_root, consent_request_id,
                plan_id, agent, scope, action, exact_challenge)
        staged = stage_bundle_fixture(
            fixture, bundle_root, plan_id, agent, scope, plan_id,
            replace_existing=(action == 'replace'))
        receipt_path = _path_within_fixture(fixture, JOURNAL)
        _sync_tree(_path_within_fixture(fixture,
                     'stage/' + json.loads(receipt_path.read_text())['tx']))
        _sync_directory(receipt_path.parent)
        # Re-read target after staging: even cooperative filesystem changes must
        # not silently change which user-approved state we are replacing.
        after_staging = preview_fixture_consent(fixture, bundle_root, plan_id,
                                                agent, scope, action)
        if after_staging['approval_challenge'] != exact_challenge:
            raise ValueError('Fixture state changed between consent and activation')
        from fixture_bundle_install import _load_journal
        from host_adapters import _target_for_fixture
        journal = _load_journal(fixture)
        target = _target_for_fixture(fixture, agent, scope, journal['slug'])
        if action == 'replace':
            _sync_tree(target)
            if preview_fixture_consent(fixture, bundle_root, plan_id, agent,
                                       scope, action)['approval_challenge'] != exact_challenge:
                raise ValueError('Existing fixture changed during durability preflight')
        state = activate_bundle_fixture(fixture, stop_after=checkpoint)
        for parent in (target.parent,
                       _path_within_fixture(fixture, 'stage'),
                       _path_within_fixture(fixture, 'backup')):
            if parent.is_dir():
                _sync_directory(parent)
        if checkpoint == 'activated' and target.is_dir():
            _sync_directory(target)
        for name in ('workspace', 'home', 'stage', 'backup'):
            item = _path_within_fixture(fixture, name)
            if item.is_dir():
                _sync_directory(item)
        _sync_directory(fixture)
        return {'status': state['status'], 'checkpoint': checkpoint,
                'file_count': staged['file_count'], 'plan_id': plan_id,
                'agent': agent, 'scope': scope, 'action': action,
                'fixture_only_consent_matched': True,
                'one_time_fixture_receipt_consumed': consent_request_id is not None,
                'real_user_authorization_collected': False,
                'real_host_files_modified': False,
                'third_party_skill_executed': False,
                'production_installation_enabled': False}


def recover_fixture_transaction(fixture):
    """Can be called from a NEW process after any intentional interruption."""
    fixture = _checked_fixture(fixture)
    with _exclusive_fixture_lock(fixture):
        from fixture_bundle_install import _load_journal
        from host_adapters import _target_for_fixture
        journal = _load_journal(fixture)
        target = _target_for_fixture(fixture, journal['agent'],
                                     journal['scope'], journal['slug'])
        result = rollback_bundle_fixture(fixture)
        for parent in (target.parent,
                       _path_within_fixture(fixture, 'stage'),
                       _path_within_fixture(fixture, 'backup')):
            if parent.is_dir():
                _sync_directory(parent)
        if target.is_dir():
            _sync_tree(target)
        for name in ('workspace', 'home', 'stage', 'backup'):
            path = _path_within_fixture(fixture, name)
            if path.is_dir():
                _sync_directory(path)
        _sync_directory(fixture)
        return {**result, 'recovery_revalidated_under_lock': True,
                'real_user_authorization_collected': False}


def rehearse_locked_transaction(plan_id, agent, scope, acknowledgement,
                                 *, bundle_root, action='replace', checkpoint='activated'):
    """One-shot convenient test; all private ZIP writes are disposed afterward."""
    if acknowledgement != plan_id:
        raise ValueError('Exact package Plan ID acknowledgement required')
    if action not in ('install', 'replace'):
        raise ValueError('Invalid fixture action')
    directory, fixture = _new_root()
    try:
        profile = _path_within_fixture(fixture, 'workspace' if scope == 'project' else 'home')
        profile.mkdir()
        if action == 'replace':
            from fixture_bundle_install import _read_bundle
            slug, _ = _read_bundle(bundle_root, plan_id, agent, scope)
            target = _target_for_fixture(fixture, agent, scope, slug)
            target.mkdir(parents=True)
            (target / 'SKILL.md').write_bytes(
                b'---\nname: gasl-old-fixture\ndescription: Temporary test version\n---\n')
            (target / 'user-note.txt').write_bytes(b'USER_NOTE_MUST_SURVIVE\n')
        preview = preview_fixture_consent(fixture, bundle_root, plan_id, agent, scope, action)
        applied = enact_fixture_transaction(fixture, bundle_root, plan_id,
                     agent, scope, action, preview['approval_challenge'], checkpoint=checkpoint)
        recovered = recover_fixture_transaction(fixture)
        return {'status': 'fixture_locked_transaction_rollback_verified',
                'checkpoint': applied['status'], 'action': action,
                'file_count': applied['file_count'],
                'previous_files_restored': recovered['previous_files_restored'],
                'approval_bound_to_fixture_state': True,
                'real_host_files_modified': False,
                'third_party_skill_executed': False,
                'production_installation_enabled': False}
    finally:
        directory.cleanup()
