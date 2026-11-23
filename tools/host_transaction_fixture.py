#!/usr/bin/env python3
"""Crash-recovery rehearsal restricted to GASL-authored inert temp fixtures.

This is deliberately NOT a production installer. It accepts neither a real
installation path nor downloaded Skill bytes, and never interacts with Agent
configurations, real home directories, network, subprocesses or Skill code.
"""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from host_adapters import (
    FIXTURE_PREFIX, MARKER, SKILL_V1, SKILL_V2,
    _checked_fixture, _path_within_fixture, _target_for_fixture,
)

_JOURNAL = '.gasl-inert-transaction.json'
_TRANSACTION = re.compile(r'^[0-9a-f]{32}$')
_NAME = 'fixture-skill'
_USER_NOTE = b'USER_MODIFICATION_SHOULD_SURVIVE\n'


def _protect_new_windows_fixture(root):
    """Restrict a newly created, empty disposable directory before any data.

    Hosted Windows runners may create a 0700 directory owned by Administrators
    with no explicit ACE for the token SID. Set a protected, inheritable DACL
    on this fresh directory only, rather than weakening the receipt checker.
    Never repair or change permissions on an existing populated fixture.
    """
    import ctypes
    from ctypes import wintypes
    from windows_user_profile import (
        _apis, _token_identity, _raise_winerror, assert_no_reparse_components,
        verify_owned_path,
    )
    root = Path(root)
    if (not root.is_absolute() or not root.name.startswith(FIXTURE_PREFIX)
            or root.parent.resolve() != Path(tempfile.gettempdir()).resolve()
            or not root.is_dir() or any(root.iterdir())):
        raise ValueError('Only a freshly created empty Windows fixture may be protected')
    assert_no_reparse_components(root)
    sid = _token_identity()['sid']
    advapi, kernel, _ = _apis()
    descriptor = ctypes.c_void_p()
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.DWORD))
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    # Only the exact token SID and LocalSystem have inheritable access.
    # D:P disables inherited ACLs from the parent temporary directory.
    sddl = 'D:P(A;OICI;FA;;;' + sid + ')(A;OICI;FA;;;SY)'
    if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, ctypes.byref(descriptor), None):
        _raise_winerror(message='Cannot construct private fixture DACL')
    try:
        present, defaulted = wintypes.BOOL(), wintypes.BOOL()
        dacl = ctypes.c_void_p()
        advapi.GetSecurityDescriptorDacl.argtypes = (
            ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL),
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.BOOL))
        advapi.GetSecurityDescriptorDacl.restype = wintypes.BOOL
        if (not advapi.GetSecurityDescriptorDacl(
                descriptor, ctypes.byref(present), ctypes.byref(dacl),
                ctypes.byref(defaulted)) or not present.value or not dacl.value):
            raise ValueError('Cannot obtain private fixture DACL')
        advapi.SetNamedSecurityInfoW.argtypes = (
            wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        advapi.SetNamedSecurityInfoW.restype = wintypes.DWORD
        status = advapi.SetNamedSecurityInfoW(
            str(root), 1, 0x80000004, None, None, dacl, None)
        if status:
            _raise_winerror(status, 'Cannot protect new disposable fixture DACL')
    finally:
        kernel.LocalFree.argtypes = (ctypes.c_void_p,)
        kernel.LocalFree.restype = ctypes.c_void_p
        kernel.LocalFree(descriptor)
    verify_owned_path(root, sid, directory=True, require_private=True)


def _new_root():
    directory = tempfile.TemporaryDirectory(prefix=FIXTURE_PREFIX)
    root = Path(directory.name)
    try:
        if os.name == 'nt':
            _protect_new_windows_fixture(root)
        (root / MARKER).write_bytes(b'INERT_HOST_FIXTURE_ONLY\n')
    except BaseException:
        directory.cleanup()
        raise
    return directory, root


def _checked_path(root, relative):
    return _path_within_fixture(root, relative)


def _bytes_equal(path, data):
    return path.is_file() and not path.is_symlink() and path.read_bytes() == data


def _expected_new_only(path):
    return (path.is_dir() and not path.is_symlink()
            and {p.name for p in path.iterdir()} == {'SKILL.md'}
            and _bytes_equal(path / 'SKILL.md', SKILL_V2))


def _expected_previous(path):
    return (path.is_dir() and not path.is_symlink()
            and {p.name for p in path.iterdir()} == {'SKILL.md', 'user-note.txt'}
            and _bytes_equal(path / 'SKILL.md', SKILL_V1)
            and _bytes_equal(path / 'user-note.txt', _USER_NOTE))


def _remove_new_only(path):
    if not _expected_new_only(path):
        raise ValueError('Fixture target modified or not owned; recovery refuses overwrite')
    (path / 'SKILL.md').unlink()
    path.rmdir()


def _write_journal(root, payload):
    temporary = _checked_path(root, _JOURNAL + '.tmp')
    final = _checked_path(root, _JOURNAL)
    if temporary.exists() or final.is_symlink():
        raise ValueError('Unexpected journal collision or symlink')
    data = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8') + b'\n'
    with temporary.open('xb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(final)


def _load_journal(root):
    p = _checked_path(root, _JOURNAL)
    if not p.is_file() or p.is_symlink() or p.stat().st_size > 4096:
        raise ValueError('Fixture transaction journal missing or unsafe')
    try:
        value = json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError):
        raise ValueError('Fixture transaction journal is corrupt')
    if (not isinstance(value, dict) or set(value) != {'schema', 'transaction', 'agent', 'scope', 'old_exists', 'new_sha256'}
            or value['schema'] != 'gasl-inert-fixture-transaction-v1'
            or not isinstance(value['transaction'], str) or not _TRANSACTION.fullmatch(value['transaction'])
            or value['old_exists'] not in (True, False) or not isinstance(value['old_exists'], bool)
            or value['new_sha256'] != hashlib.sha256(SKILL_V2).hexdigest()):
        raise ValueError('Fixture transaction journal failed integrity validation')
    target = _target_for_fixture(root, value['agent'], value['scope'], _NAME)
    if target is None:
        raise ValueError('Only filesystem-style fixture hosts support this transaction')
    return value, target


def prepare_transaction(root, agent, scope, *, upgrade=True):
    root = _checked_fixture(root)
    target = _target_for_fixture(root, agent, scope, _NAME)
    if target is None:
        raise ValueError('Account-upload and generic MCP hosts cannot install filesystem fixtures')
    if _checked_path(root, _JOURNAL).exists():
        raise ValueError('Unfinished inert fixture transaction must be recovered first')
    if target.exists() or target.is_symlink():
        raise ValueError('Existing target collision: never overwrite without verified fixture backup')
    target.parent.mkdir(parents=True, exist_ok=True)
    if upgrade:
        target.mkdir()
        (target / 'SKILL.md').write_bytes(SKILL_V1)
        (target / 'user-note.txt').write_bytes(_USER_NOTE)
    transaction = hashlib.sha256(os.urandom(24)).hexdigest()[:32]
    stage = _checked_path(root, 'stage/' + transaction)
    stage.parent.mkdir(parents=True, exist_ok=True)
    stage.mkdir()
    (stage / 'SKILL.md').write_bytes(SKILL_V2)
    payload = {
        'schema': 'gasl-inert-fixture-transaction-v1',
        'transaction': transaction, 'agent': agent, 'scope': scope,
        'old_exists': upgrade,
        'new_sha256': hashlib.sha256(SKILL_V2).hexdigest(),
    }
    _write_journal(root, payload)
    return payload


def advance_transaction(root, *, stop_after):
    root = _checked_fixture(root)
    if stop_after not in ('prepared', 'old_backed_up', 'new_activated'):
        raise ValueError('Unknown inert transaction checkpoint')
    payload, target = _load_journal(root)
    stage = _checked_path(root, 'stage/' + payload['transaction'])
    backup = _checked_path(root, 'backup/' + payload['transaction'])
    if not _expected_new_only(stage):
        raise ValueError('Inert staging bytes changed; cannot advance')
    if stop_after == 'prepared':
        return {'state': 'interrupted_prepared', 'inert_only': True}
    if payload['old_exists']:
        if not _expected_previous(target) or backup.exists():
            raise ValueError('Original inert fixture changed before backup')
        backup.parent.mkdir(parents=True, exist_ok=True)
        target.rename(backup)
    elif target.exists():
        raise ValueError('Fresh fixture target unexpectedly exists')
    if stop_after == 'old_backed_up':
        return {'state': 'interrupted_after_backup', 'inert_only': True}
    stage.rename(target)
    return {'state': 'interrupted_after_activation', 'inert_only': True}


def recover_transaction(root):
    """Recover only owned inert bytes; preserve conflicts and refuse data loss."""
    root = _checked_fixture(root)
    payload, target = _load_journal(root)
    stage = _checked_path(root, 'stage/' + payload['transaction'])
    backup = _checked_path(root, 'backup/' + payload['transaction'])
    # Validate every existing path before ANY modification. Even temporary data
    # may have been changed by another process after the crash.
    if stage.exists() and not _expected_new_only(stage):
        raise ValueError('Unknown or modified staged files; cannot recover safely')
    if backup.exists() and not _expected_previous(backup):
        raise ValueError('Unknown or modified backup; recovery refuses overwrite')
    if target.is_symlink():
        raise ValueError('Symlink at target; recovery refuses overwrite')
    if payload['old_exists']:
        if backup.exists():
            if target.exists() and not _expected_new_only(target):
                raise ValueError('Target was modified after activation; keep backup for manual recovery')
        elif not _expected_previous(target):
            raise ValueError('Original fixture missing without valid backup')
    elif target.exists() and not _expected_new_only(target):
        raise ValueError('New target was edited; refuse to delete user changes')

    if target.exists() and _expected_new_only(target):
        _remove_new_only(target)
    if backup.exists():
        backup.rename(target)
    if stage.exists():
        _remove_new_only(stage)
    (root / _JOURNAL).unlink()
    restored = _expected_previous(target) if payload['old_exists'] else not target.exists()
    if not restored:
        raise ValueError('Fixture recovery could not verify original state')
    return {
        'status': 'inert_fixture_recovery_verified',
        'recovered_original_version': True,
        'user_note_preserved': payload['old_exists'],
        'real_host_files_modified': False,
        'third_party_code_executed': False,
        'real_skill_installed': False,
        'production_install_enabled': False,
    }


def rehearse_interrupted_transaction(agent, scope='project', *, upgrade=True,
                                      stop_after='new_activated'):
    """Single-request disposable test: fake interruption, then verified recovery."""
    directory, root = _new_root()
    try:
        prepare_transaction(root, agent, scope, upgrade=upgrade)
        interrupted = advance_transaction(root, stop_after=stop_after)
        recovery = recover_transaction(root)
        return {'agent': agent, 'scope': scope, 'upgrade': upgrade,
                'interruption_checkpoint': interrupted['state'], **recovery}
    finally:
        directory.cleanup()
