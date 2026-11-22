#!/usr/bin/env python3
"""One-time, time-bound *fixture-only* consent receipt for test Skill transactions.

Receipts require a separate literal confirmation, bind the immutable package,
Host/scope/action/target state, and are consumed under the transaction lock.
Neither receipts nor programmatic tests prove human identity; this module
CANNOT authorize writes outside GASL-owned disposable fixtures.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import time
from pathlib import Path

from fixture_transaction_v2 import (
    _exclusive_fixture_lock, _sync_directory, preview_fixture_consent,
)
from host_adapters import _checked_fixture, _path_within_fixture
from fixture_bundle_install import JOURNAL

SCHEMA = 'gasl-phase30-disposable-consent-v1'
KEY_PATH = '.gasl-phase30-consent-key'
RECEIPT_PATH = '.gasl-phase30-consent-receipt.json'
ID_RE = re.compile(r'^[0-9a-f]{32}$')
HASH_RE = re.compile(r'^[0-9a-f]{64}$')
RECORD_FIELDS = {'schema', 'id', 'plan_id', 'agent', 'scope', 'action',
                 'challenge', 'source_sha256', 'state_binding_id',
                 'issued_at', 'expires_at', 'approved_at', 'consumed_at',
                 'state', 'mac'}


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':')).encode('utf-8')


def _secret(fixture, *, create=False):
    path = _path_within_fixture(fixture, KEY_PATH)
    if create:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            os.write(fd, secrets.token_bytes(32))
            os.fsync(fd)
        finally:
            os.close(fd)
        _sync_directory(fixture)
    if (not path.is_file() or path.is_symlink() or path.stat().st_size != 32
            or path.stat().st_nlink != 1):
        raise ValueError('Unsafe or invalid fixture consent signing key')
    if os.name == 'posix' and (path.stat().st_mode & 0o077):
        raise ValueError('Fixture consent key permissions are too permissive')
    return path.read_bytes()


def _signature(payload, key):
    return hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()


def _write_receipt(fixture, record, key, *, new=False):
    path = _path_within_fixture(fixture, RECEIPT_PATH)
    if path.is_symlink():
        raise ValueError('Symlinked consent receipt refused')
    if new and path.exists():
        raise ValueError('Fixture consent receipt already exists')
    value = {**record, 'mac': _signature(record, key)}
    data = _canonical(value) + b'\n'
    with tempfile.NamedTemporaryFile(prefix='.gasl-consent-write-', suffix='.tmp',
                                     dir=fixture, delete=False) as file:
        staged = Path(file.name)
        try:
            os.fchmod(file.fileno(), 0o600)
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        except BaseException:
            staged.unlink(missing_ok=True)
            raise
    try:
        if new:
            os.link(staged, path)
        else:
            if not path.is_file() or path.stat().st_nlink != 1:
                raise ValueError('Consent record replaced or hardlinked')
            staged.replace(path)
        _sync_directory(fixture)
    finally:
        staged.unlink(missing_ok=True)


def _read_receipt(fixture):
    path = _path_within_fixture(fixture, RECEIPT_PATH)
    if (not path.is_file() or path.is_symlink() or path.stat().st_size > 4000
            or path.stat().st_nlink != 1):
        raise ValueError('Fixture consent receipt missing or invalid')
    value = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(value, dict) or set(value) != RECORD_FIELDS
            or value.get('schema') != SCHEMA or not ID_RE.fullmatch(str(value.get('id')))
            or any(not HASH_RE.fullmatch(str(value.get(k))) for k in
                   ('plan_id','challenge','source_sha256','state_binding_id'))
            or value.get('agent') not in ('codex','cursor','claude-code')
            or value.get('scope') not in ('project','user')
            or value.get('action') not in ('install','replace')
            or value.get('state') not in ('pending','approved','consumed')
            or any(type(value.get(k)) is not int for k in ('issued_at','expires_at'))
            or value['expires_at'] <= value['issued_at']
            or (value['approved_at'] is not None and type(value['approved_at']) is not int)
            or (value['consumed_at'] is not None and type(value['consumed_at']) is not int)):
        raise ValueError('Malformed disposable consent receipt')
    key = _secret(fixture)
    supplied = value.pop('mac')
    if not isinstance(supplied,str) or not hmac.compare_digest(supplied,_signature(value,key)):
        raise ValueError('Fixture consent receipt signature mismatch')
    if (value['state']=='pending' and (value['approved_at'] is not None or value['consumed_at'] is not None)
            or value['state']=='approved' and (value['approved_at'] is None or value['consumed_at'] is not None)
            or value['state']=='consumed' and (value['approved_at'] is None or value['consumed_at'] is None)):
        raise ValueError('Invalid fixture consent state transition')
    return value,key


def _phrase(record):
    # This string is NOT a bearer token: it forces a human-controlled UI to
    # present the exact chosen action, Host, scope and receipt instance.
    return ('APPROVE GASL FIXTURE ' + record['action'].upper() + ' '
            + record['agent'].upper() + ' ' + record['scope'].upper() + ' '
            + record['id'][:12].upper() + ' ' + record['challenge'][:12].upper())


def request_fixture_consent(fixture, bundle_root, plan_id, agent, scope, action, *, ttl_seconds=180):
    """Creates private pending request; no install, no implicit approval."""
    fixture = _checked_fixture(fixture)
    if type(ttl_seconds) is not int or not 30 <= ttl_seconds <= 300:
        raise ValueError('Fixture consent expiration must be 30-300 seconds')
    with _exclusive_fixture_lock(fixture):
        if _path_within_fixture(fixture, JOURNAL).exists():
            raise ValueError('Cannot request consent while a fixture transaction is pending')
        if _path_within_fixture(fixture, RECEIPT_PATH).exists():
            raise ValueError('Existing fixture consent cannot be replaced or reused')
        pre = preview_fixture_consent(fixture,bundle_root,plan_id,agent,scope,action)
        now = int(time.time())
        record = {
            'schema':SCHEMA, 'id':secrets.token_hex(16), 'plan_id':plan_id,
            'agent':agent, 'scope':scope, 'action':action,
            'challenge':pre['approval_challenge'],
            'source_sha256':pre['bundle_sha256'],
            'state_binding_id':pre['state_binding_id'],
            'issued_at':now, 'expires_at':now+ttl_seconds,
            'approved_at':None, 'consumed_at':None, 'state':'pending',
        }
        key = _secret(fixture,create=True)
        _write_receipt(fixture,record,key,new=True)
        return {
            'status':'pending_explicit_fixture_confirmation',
            'request_id':record['id'], 'confirmation_phrase':_phrase(record),
            'host':agent, 'scope':scope, 'action':action,
            'plan_id':plan_id, 'source_sha256':record['source_sha256'],
            'target_state_binding_id':record['state_binding_id'],
            'expires_at_epoch':record['expires_at'],
            'human_confirmation_recorded':False,
            'production_installation_enabled':False,
            'real_host_files_modified':False,
        }


def confirm_fixture_consent(fixture,bundle_root,request_id,typed_phrase):
    """Requires deliberate exact phrase; automated unit calls simulate this gesture."""
    fixture = _checked_fixture(fixture)
    with _exclusive_fixture_lock(fixture):
        record,key=_read_receipt(fixture)
        if record['id']!=request_id or record['state']!='pending':
            raise ValueError('Fixture consent request is invalid, already confirmed or consumed')
        now=int(time.time())
        if now>record['expires_at']:
            raise ValueError('Fixture consent request has expired')
        if not isinstance(typed_phrase,str) or not hmac.compare_digest(typed_phrase,_phrase(record)):
            raise ValueError('Exact explicit fixture confirmation phrase is required')
        current=preview_fixture_consent(fixture,bundle_root,record['plan_id'],
                     record['agent'],record['scope'],record['action'])
        if (current['approval_challenge']!=record['challenge']
                or current['bundle_sha256']!=record['source_sha256']
                or current['state_binding_id']!=record['state_binding_id']):
            raise ValueError('Selected fixture target or ZIP changed before confirmation')
        record.update(state='approved',approved_at=now)
        _write_receipt(fixture,record,key)
        return {'status':'fixture_confirmation_recorded', 'request_id':request_id,
                'fixture_confirmation_entered':True,'real_user_identity_verified':False,
                'real_host_files_modified':False,'production_installation_enabled':False}


def consume_under_transaction_lock(fixture,bundle_root,request_id,plan_id,agent,scope,action,expected_challenge):
    """Called ONLY while the Phase-28 exclusive lock is already held."""
    fixture=_checked_fixture(fixture)
    record,key=_read_receipt(fixture)
    if record['id']!=request_id or record['state']!='approved':
        raise ValueError('Fixture consent already used or not approved')
    if int(time.time())>record['expires_at']:
        raise ValueError('Fixture consent expired before transaction')
    if (record['plan_id']!=plan_id or record['agent']!=agent
            or record['scope']!=scope or record['action']!=action
            or record['challenge']!=expected_challenge):
        raise ValueError('Fixture approval does not match this exact install operation')
    current=preview_fixture_consent(fixture,bundle_root,plan_id,agent,scope,action)
    if (current['approval_challenge']!=record['challenge']
            or current['bundle_sha256']!=record['source_sha256']
            or current['state_binding_id']!=record['state_binding_id']):
        raise ValueError('Fixture ZIP or target changed before receipt consumption')
    record.update(state='consumed',consumed_at=int(time.time()))
    _write_receipt(fixture,record,key)
    return {'receipt_consumed':True,'request_id':request_id}


def inspect_fixture_receipt(fixture):
    """Safe metadata read, no key/phrase/full filesystem paths returned."""
    fixture=_checked_fixture(fixture)
    with _exclusive_fixture_lock(fixture):
        record,_=_read_receipt(fixture)
        return {'status':record['state'], 'request_id':record['id'],
                'plan_id':record['plan_id'], 'host':record['agent'],
                'scope':record['scope'], 'action':record['action'],
                'expires_at_epoch':record['expires_at'],
                'real_user_identity_verified':False,
                'production_installation_enabled':False}
