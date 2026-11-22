#!/usr/bin/env python3
"""Prepare a private, deterministic, verified Skill ZIP for human review only.

No Host paths are written, no downloaded code is executed, and no bundle is
published to GitHub. Packaging is NOT security or installation approval.
"""
import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path

from host_adapters import HOST_LAYOUTS
from install_lifecycle import plan_install
from queue_ingest import collision_key, git_blob, no_symlink, package_location, safe_path
from skill_search import ROOT, get_skill_by_id

SCHEMA = 'gasl-private-install-bundle-v1'
MAX_FILES = 300
MAX_BYTES = 20 * 1024 * 1024
MAX_ONE_FILE = 10 * 1024 * 1024


def _json_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def _slug(source_path, source_record_id):
    segment = Path(source_path).parent.name.lower()
    slug = re.sub(r'[^a-z0-9-]+', '-', segment).strip('-')[:45].strip('-')
    return slug if slug else 'gasl-skill-' + hashlib.sha256(source_record_id.encode()).hexdigest()[:10]


def _verified_files(root, record):
    """Verify original pinned inventory again before bundling, never trust labels alone."""
    root = Path(root).resolve()
    folder = no_symlink(root, package_location(root, {**record, 'skill_path': record['source_path']}))
    manifest_path = no_symlink(root, folder / 'source.json')
    meta = json.loads(manifest_path.read_text(encoding='utf-8'))
    if (meta.get('repository', '').casefold() != record['repository'].casefold()
            or meta.get('source_skill_path') != record['source_path']
            or meta.get('commit_sha') != record['commit_sha']
            or meta.get('skill_md_blob_sha') not in (None, record['skill_md_blob_sha'])
            or meta.get('package_complete') is not True):
        raise ValueError('Pinned source metadata and download manifest mismatch')
    entries = meta.get('files')
    if not isinstance(entries, list) or not (1 <= len(entries) <= MAX_FILES):
        raise ValueError('Invalid or oversized pinned package inventory')
    result = []
    total = 0
    seen = set()
    prefixes = set()
    has_main = False
    legacy_blob_evidence_missing = 0
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError('Invalid package entry')
        local_name = safe_path(item.get('local_path'))
        local = no_symlink(root, root / local_name)
        if not local.is_relative_to(folder):
            raise ValueError('Manifest entry points outside its pinned package')
        rel = safe_path(local.relative_to(folder).as_posix())
        declared_rel = item.get('package_relative_path')
        if declared_rel is not None and safe_path(declared_rel) != rel:
            raise ValueError('Package-relative manifest path mismatch')
        if collision_key(rel) in seen or rel.casefold() == 'source.json':
            raise ValueError('Duplicate/colliding package path')
        seen.add(collision_key(rel))
        for i in range(1, len(rel.split('/'))):
            prefixes.add(collision_key('/'.join(rel.split('/')[:i])))
        if (local.relative_to(root).as_posix() != item.get('local_path')
                or not local.is_file() or local.is_symlink()):
            raise ValueError('Manifest path is missing, unsafe or inconsistent')
        size = item.get('size_bytes')
        if (not isinstance(size, int) or isinstance(size, bool) or
                size < 0 or size > MAX_ONE_FILE or local.stat().st_size != size):
            raise ValueError('File size is invalid or changed')
        total += size
        if total > MAX_BYTES:
            raise ValueError('Total selected package bytes exceed allowed limit')
        data = local.read_bytes()
        expected_blob = item.get('git_blob_sha')
        if (hashlib.sha256(data).hexdigest() != item.get('sha256')
                or (expected_blob is not None and git_blob(data) != expected_blob)):
            raise ValueError('Downloaded package content no longer matches recorded hash')
        if expected_blob is None:
            legacy_blob_evidence_missing += 1
        if rel == 'SKILL.md':
            if git_blob(data) != record['skill_md_blob_sha']:
                raise ValueError('Main SKILL.md Git Blob differs from pinned record')
            has_main = True
        result.append((rel, data, item['sha256']))
    if not has_main or any(p in seen for p in prefixes):
        raise ValueError('Package lacks exact pinned SKILL.md or has file/directory collisions')
    actual = set()
    for candidate in folder.rglob('*'):
        no_symlink(root, candidate)
        if candidate.is_file():
            actual.add(candidate.relative_to(folder).as_posix())
        elif not candidate.is_dir():
            raise ValueError('Non-regular file found in downloaded package')
    if actual != {name for name, _, _ in result} | {'source.json'}:
        raise ValueError('Unexpected or missing files in the package directory')
    return sorted(result), total, legacy_blob_evidence_missing


def _archive_entries(record, files):
    slug = _slug(record['source_path'], record['source_record_id'])
    return [(slug + '/' + rel, data, sha) for rel, data, sha in files]


def _assert_zip_contents(path, items):
    with zipfile.ZipFile(path, 'r') as zf:
        info = zf.infolist()
        if len(info) != len(items) or [i.filename for i in info] != [entry[0] for entry in items]:
            raise ValueError('Bundle archive manifest mismatch')
        for z, (name, _, sha) in zip(info, items):
            if (z.is_dir() or z.file_size > MAX_ONE_FILE
                    or hashlib.sha256(zf.read(name)).hexdigest() != sha):
                raise ValueError('Bundle archive content hash or type mismatch')


def prepare_private_bundle(source_record_id, agent, scope, acknowledgement, *, root=ROOT, lookup=None):
    """Produce an offline artifact under ignored private/ only; never install it."""
    if agent not in HOST_LAYOUTS or HOST_LAYOUTS[agent]['kind'] not in (
            'filesystem_skill_directory', 'manual_account_zip_upload'):
        raise ValueError('No supported manual Skill ZIP handoff for this Host')
    root = Path(root).resolve()
    record = (lookup(source_record_id, root=root) if lookup is not None
              else get_skill_by_id(source_record_id, root=root))
    if record is None:
        raise KeyError('Unknown source record')
    record = {**record, 'source_record_id': source_record_id}
    plan = plan_install(source_record_id, agent, scope, root=root, lookup=lambda _, root: record)
    if acknowledgement != plan['plan_id']:
        raise ValueError('Explicit exact plan ID acknowledgement required for private ZIP creation')
    if not plan['simulation_apply_eligible']:
        raise ValueError('Package missing, tampered or statically flagged; cannot build a review ZIP')
    files, bytes_total, legacy_missing_blobs = _verified_files(root, record)
    archive_items = _archive_entries(record, files)
    storage = no_symlink(root, root / 'private' / 'install-bundles')
    storage.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == 'posix':
        storage.chmod(0o700)
    stem = plan['plan_id']
    target = no_symlink(root, storage / (stem + '.zip'))
    sidecar = no_symlink(root, storage / (stem + '.json'))
    if target.exists() or sidecar.exists():
        raise ValueError('Private bundle already exists; refusing overwrite (review existing artifact separately)')
    fd, temporary = tempfile.mkstemp(prefix='.gasl-bundle-', suffix='.zip', dir=storage)
    os.close(fd)
    tmp_path = Path(temporary)
    created = False
    sidecar_created = False
    try:
        with zipfile.ZipFile(tmp_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data, _ in archive_items:
                z = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                z.compress_type = zipfile.ZIP_DEFLATED
                z.external_attr = (0o100644 << 16)
                archive.writestr(z, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        _assert_zip_contents(tmp_path, archive_items)
        digest = hashlib.sha256(tmp_path.read_bytes()).hexdigest()
        metadata = {
            'schema_version': SCHEMA, 'plan_id': plan['plan_id'],
            'source_record_id': source_record_id, 'agent': agent, 'scope': scope,
            'source_repository': record['repository'], 'source_path': record['source_path'],
            'source_commit_sha': record['commit_sha'], 'pinned_skill_md_blob_sha': record['skill_md_blob_sha'],
            'license_spdx': plan['license_spdx'],
            'license_review_required': 'license_terms_require_review' in plan['warnings'],
            'warnings': plan['warnings'],
            'legacy_manifest_entries_without_git_blob_sha': legacy_missing_blobs,
            'non_main_file_upstream_blob_evidence_complete': legacy_missing_blobs == 0,
            'file_count': len(archive_items), 'uncompressed_bytes': bytes_total,
            'archive_sha256': digest,
            'entries': [{'archive_path': name, 'sha256': sha} for name, _, sha in archive_items],
            'manual_review_required': True, 'host_installation_approved': False,
            'real_host_files_modified': False, 'third_party_skill_executed': False,
            'production_installation_enabled': False,
        }
        with sidecar.open('xb') as out:
            sidecar_created = True
            out.write(_json_bytes(metadata))
            out.flush()
            os.fsync(out.fileno())
        if os.name == 'posix':
            sidecar.chmod(0o600)
        # Same-filesystem hard link gives exclusive creation semantics:
        # unlike replace(), an unexpected concurrent target is never overwritten.
        os.link(tmp_path, target)
        created = True
        return {'status': 'private_review_bundle_created', 'plan_id': plan['plan_id'],
                'archive_path': str(target), 'metadata_path': str(sidecar),
                'archive_sha256': digest, 'file_count': len(archive_items),
                'legacy_manifest_entries_without_git_blob_sha': legacy_missing_blobs,
                'manual_review_required': True, 'license_review_required': metadata['license_review_required'],
                'real_host_files_modified': False, 'production_installation_enabled': False,
                'third_party_skill_executed': False}
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
        # Do not remove a concurrently created sidecar that we do not own.
        if not created and sidecar_created and sidecar.exists():
            sidecar.unlink()


def verify_private_bundle(plan_id, *, root=ROOT):
    """Read back the private ZIP + sidecar; no extraction and no Skill execution."""
    if not re.fullmatch(r'[0-9a-f]{64}', str(plan_id)):
        raise ValueError('Invalid plan ID')
    root = Path(root).resolve()
    storage = no_symlink(root, root / 'private' / 'install-bundles')
    path = no_symlink(root, storage / (plan_id + '.zip'))
    meta_path = no_symlink(root, storage / (plan_id + '.json'))
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    if meta.get('schema_version') != SCHEMA or meta.get('plan_id') != plan_id:
        raise ValueError('Private bundle metadata mismatch')
    if hashlib.sha256(path.read_bytes()).hexdigest() != meta['archive_sha256']:
        raise ValueError('Private bundle archive hash mismatch')
    expected = meta.get('entries', [])
    if not expected or len(expected) != meta.get('file_count') or len(expected) > MAX_FILES:
        raise ValueError('Private bundle manifest invalid')
    with zipfile.ZipFile(path, 'r') as archive:
        if [i.filename for i in archive.infolist()] != [e['archive_path'] for e in expected]:
            raise ValueError('Bundle archive entry list differs')
        for item in expected:
            name = safe_path(item['archive_path'])
            if hashlib.sha256(archive.read(name)).hexdigest() != item['sha256']:
                raise ValueError('Bundle entry hash differs')
    return {'status': 'private_bundle_integrity_verified', 'plan_id': plan_id,
            'archive_sha256': meta['archive_sha256'], 'file_count': len(expected),
            'real_host_files_modified': False, 'third_party_skill_executed': False,
            'installation_approved': False}
