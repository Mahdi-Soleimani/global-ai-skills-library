#!/usr/bin/env python3
"""Reversible Codex namespace migration rehearsal, self-authored fixtures ONLY.

No user-selected project, arbitrary bundle, vendor process or migration CLI.
The active Skill is never renamed or modified. This deliberately narrow
single-Skill rehearsal is not an implementation of production migration.
"""
import hashlib
import json
import os
import stat

import codex_migration_audit as audit
import codex_project_install as legacy
import host_project_install as native
from fixture_explicit_consent import _verify_private_fixture_path
from fixture_transaction_v2 import _sync_directory
from host_adapters import _checked_fixture, _path_within_fixture
from host_transaction_fixture import _new_root
from transaction_file_lock import exclusive_lock_file, is_redirected

SLUG = 'gasl-migration-inert'
SCHEMA = 'gasl-codex-disposable-migration-v1'
MARKER = '.gasl-migration-inert-fixture'
JOURNAL = '.gasl-codex-migration-pending'
LOCK = '.gasl-migration.lock'
PROJECT = 'workspace'
ORIGINAL = 'migration-original'
STAGED = 'migration-staged'
CHECKPOINTS = ('journal_written', 'candidate_staged', 'original_archived',
               'candidate_published', 'candidate_validated')


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _bytes(version):
    return ('---\nname: ' + SLUG + '\n---\n# GASL inert migration version '
            + str(version) + '\nNo code or commands.\n').encode()


def _expected(count, project=None):
    if type(count) is not int or count not in (0, 2, 3, 4, 5):
        raise ValueError('Unsupported self-authored fixture history')
    if count in (4, 5):
        if project is None:
            raise ValueError('Path-bound archive fixture requires exact project')
        return _expected_archive(count, project)
    source, destination = {}, {}
    prefix, previous = [], None
    for version in range(1, count + 2):
        ident = format(version, '032x')
        if previous is not None:
            rel = 'backups/' + SLUG + '/' + ident
            data = _bytes(version - 1)
            source[rel + '/SKILL.md'] = data
            destination['hosts/codex/' + rel + '/SKILL.md'] = data
            manifest = {
                'schema': legacy.SCHEMA, 'kind': 'pre_replace_backup',
                'slug': SLUG, 'backup_id': ident, 'transaction': ident,
                'previous_receipt': previous, 'files': previous['files'],
            }
            legacy._checked_backup(manifest, SLUG, ident)
            source[rel + '.json'] = legacy._serialized(manifest)
            mapped = {
                'schema': native.SCHEMA, 'host': 'codex', 'scope': 'project',
                'slug': SLUG, 'backup_id': ident, 'files': previous['files'],
                'previous_receipt': audit._candidate_receipt(previous, SLUG, prefix),
            }
            native._manifest_valid(mapped, 'codex', SLUG, ident)
            destination['hosts/codex/' + rel + '.json'] = legacy._serialized(mapped)
            prefix.append(ident)
        previous = {
            'schema': legacy.SCHEMA, 'action': 'replace_install' if prefix else 'fresh_install',
            'slug': SLUG, 'transaction': ident, 'plan_id': _hash(_bytes(version)),
            'binding': _hash(('inert fixture ' + ident).encode()),
            'files': [{'path': 'SKILL.md', 'sha256': _hash(_bytes(version))}],
            'backup_ids': list(prefix),
        }
    active_bytes = _bytes(count + 1)
    manifests = [json.loads(destination['hosts/codex/backups/' + SLUG + '/' + ident + '.json'])
                 for ident in prefix]
    if count == 3:
        # The third archive preserves v3 while restoring the exact v1 bytes.
        selected = manifests[0]
        active_bytes = _bytes(1)
        previous.update(action='restore_backup', source_kind='pinned',
                        restored_backup_id=prefix[0],
                        plan_id=selected['previous_receipt']['plan_id'],
                        files=selected['files'])
    candidate = audit._candidate_receipt(previous, SLUG, prefix,
                                         prior_manifests={m['backup_id']: m for m in manifests})
    source['receipts/' + SLUG + '.json'] = legacy._serialized(previous)
    destination['hosts/codex/receipts/' + SLUG + '.json'] = legacy._serialized(candidate)
    return source, destination, {'SKILL.md': active_bytes}, candidate, manifests


def _expected_archive(count, project):
    source, destination, active, last, manifests = _expected(2)
    receipt_rel = 'receipts/' + SLUG + '.json'
    marker_rel = 'uninstalled/' + SLUG + '.json'
    old = json.loads(source.pop(receipt_rel))
    destination.pop('hosts/codex/' + receipt_rel)
    ident = format(4, '032x')
    rel = 'backups/' + SLUG + '/' + ident
    source[rel + '/SKILL.md'] = active['SKILL.md']
    destination['hosts/codex/' + rel + '/SKILL.md'] = active['SKILL.md']
    source[rel + '.json'] = legacy._serialized({
        'schema': legacy.SCHEMA, 'kind': 'pre_replace_backup',
        'slug': SLUG, 'backup_id': ident, 'transaction': ident,
        'previous_receipt': old, 'files': old['files'],
    })
    manifest = {'schema': native.SCHEMA, 'host': 'codex', 'scope': 'project',
                'slug': SLUG, 'backup_id': ident, 'files': last['files'],
                'previous_receipt': last}
    native._manifest_valid(manifest, 'codex', SLUG, ident)
    manifests.append(manifest)
    destination['hosts/codex/' + rel + '.json'] = legacy._serialized(manifest)
    from codex_uninstalled_restore import MARKER_SCHEMA
    target_sha = _hash(os.fsencode(str(project.resolve() / '.agents' / 'skills' / SLUG)))
    marker = {
        'schema': MARKER_SCHEMA, 'kind': 'uninstalled_codex_project_skill',
        'slug': SLUG, 'target_sha256': target_sha,
        'uninstall_event_id': ident, 'archived_current_backup_id': ident,
        'last_receipt': old, 'backup_ids': old['backup_ids'] + [ident],
    }
    marker_bytes = legacy._serialized(marker)
    source[marker_rel] = marker_bytes
    restored = None
    active = {}
    if count == 5:
        selected = manifests[0]
        restored = dict(old, action='reinstall_backup', transaction=format(5, '032x'),
                        plan_id=selected['previous_receipt']['plan_id'],
                        files=selected['files'], backup_ids=marker['backup_ids'],
                        source_kind='pinned', restored_backup_id=selected['backup_id'],
                        uninstall_event_id=ident)
        source[receipt_rel] = legacy._serialized(restored)
        active = {'SKILL.md': _bytes(1)}
    model = audit._archive_candidate(marker, _hash(marker_bytes), restored, manifests,
                                     target_sha=target_sha)
    if model['receipt'] is not None:
        destination['hosts/codex/' + receipt_rel] = legacy._serialized(model['receipt'])
    else:
        destination['hosts/codex/' + marker_rel] = legacy._serialized(model['marker'])
    destination['hosts/codex/historical-evidence/' + SLUG + '.json'] = legacy._serialized(
        model['historical_evidence'])
    # The fixture stores exact original marker bytes separately from the
    # native lifecycle records; the full old namespace also remains archived.
    destination['hosts/codex/historical-evidence/' + SLUG + '.legacy-marker'] = marker_bytes
    return source, destination, active, model['receipt'], manifests


def _safe_dir(path):
    if is_redirected(path) or not path.is_dir():
        raise ValueError('Unsafe migration fixture directory')
    audit._directory(path)


def _read_exact(path, data):
    if is_redirected(path):
        raise ValueError('Redirected migration fixture file')
    if os.name == 'nt':
        from windows_user_profile import assert_no_reparse_components
        assert_no_reparse_components(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != len(data):
        raise ValueError('Unexpected migration fixture file')
    with path.open('rb') as stream:
        if stream.read(len(data) + 1) != data:
            raise ValueError('Modified migration fixture file')


def _present(path):
    return path.exists() or is_redirected(path)


def _tree(path, expected, *, partial=False):
    """Validate every entry before touching it; partial means known exact subset."""
    _safe_dir(path)
    directories = {'/'.join(name.split('/')[:i]) for name in expected
                   for i in range(1, len(name.split('/')))}
    seen_files, seen_dirs = set(), set()
    def visit(folder, prefix):
        for item in folder.iterdir():
            rel = prefix + item.name
            if rel in directories:
                _safe_dir(item)
                seen_dirs.add(rel)
                visit(item, rel + '/')
            elif rel in expected:
                _read_exact(item, expected[rel])
                seen_files.add(rel)
            else:
                raise ValueError('Unexpected migration fixture entry; preserve it')
    visit(path, '')
    if not partial and (seen_files != set(expected) or seen_dirs != directories):
        raise ValueError('Incomplete migration fixture tree')
    return seen_files, seen_dirs


def _write_new(path, data):
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(path.parent)


def _create_tree(path, entries):
    path.mkdir(mode=0o700)
    _sync_directory(path.parent)
    for rel, data in sorted(entries.items()):
        target = path / rel
        # Only fixed, generated paths under the private fixture are allowed.
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_new(target, data)
    _tree(path, entries)
    _sync_directory(path)


def _remove_known_tree(path, expected):
    files, directories = _tree(path, expected, partial=True)
    for rel in sorted(files):
        target = path / rel
        _read_exact(target, expected[rel])
        target.unlink()
        _sync_directory(target.parent)
    for rel in sorted(directories, key=lambda x: (-x.count('/'), x)):
        folder = path / rel
        _safe_dir(folder)
        folder.rmdir()
    path.rmdir()
    _sync_directory(path.parent)


def new_fixture(count=2):
    temporary, root = _new_root()
    try:
        project = root / PROJECT
        source, _, active, _, _ = _expected(count, project)
        project.mkdir()
        (project / '.git').mkdir()
        target = project / '.agents' / 'skills' / SLUG
        target.parent.mkdir(parents=True)
        if active:
            _create_tree(target, active)
        _create_tree(project / legacy.STATE, source)
        _write_new(root / MARKER, str(count).encode())
        return temporary, root
    except BaseException:
        temporary.cleanup()
        raise


def _context(root):
    root = _checked_fixture(root)
    _verify_private_fixture_path(root, directory=True)
    from host_adapters import MARKER as HOST_MARKER
    if {p.name for p in root.iterdir()} - {HOST_MARKER, MARKER, LOCK, PROJECT, ORIGINAL, STAGED}:
        raise ValueError('Unexpected migration fixture root entry')
    marker = _path_within_fixture(root, MARKER)
    for count in (0, 2, 3, 4, 5):
        try:
            _read_exact(marker, str(count).encode())
            break
        except ValueError:
            continue
    else:
        raise ValueError('Not an exact GASL migration rehearsal marker')
    project = _path_within_fixture(root, PROJECT)
    _safe_dir(project)
    target = _path_within_fixture(root, PROJECT + '/.agents/skills/' + SLUG)
    source, candidate, active, receipt, manifests = _expected(count, project)
    if active:
        _tree(target, active)
    elif _present(target):
        raise ValueError('Archived migration target must remain absent')
    _safe_dir(project / '.git')
    if any((project / '.git').iterdir()):
        raise ValueError('Fixture Git marker must remain empty')
    if {p.name for p in project.iterdir()} - {'.git', '.agents', legacy.STATE, JOURNAL}:
        raise ValueError('Unexpected project entry in migration fixture')
    if ({p.name for p in (project / '.agents').iterdir()} != {'skills'}
            or {p.name for p in target.parent.iterdir()} != ({SLUG} if active else set())):
        raise ValueError('Unexpected Skill in migration fixture')
    journal = _path_within_fixture(root, PROJECT + '/' + JOURNAL)
    live = _path_within_fixture(root, PROJECT + '/' + legacy.STATE)
    staged = _path_within_fixture(root, STAGED)
    original = _path_within_fixture(root, ORIGINAL)
    payload = legacy._serialized({
        'schema': SCHEMA, 'count': count, 'slug': SLUG,
        'fixture_binding': _hash(os.fsencode(str(root.resolve()))),
        'original_sha256': audit._digest({k: _hash(v) for k, v in source.items()}),
        'candidate_sha256': audit._digest({k: _hash(v) for k, v in candidate.items()}),
    })
    return project, live, staged, original, journal, payload, source, candidate, receipt, manifests


def _native_verified(live, candidate, receipt):
    _tree(live, candidate)
    state = live / 'hosts' / 'codex'
    if receipt is not None:
        native._receipt_valid(receipt, 'codex', SLUG)
        native._history(state, 'codex', SLUG, receipt['backup_ids'])
    else:
        marker = json.loads(candidate['hosts/codex/uninstalled/' + SLUG + '.json'])
        native._marker_valid(marker, state, 'codex', SLUG)
    evidence_key = 'hosts/codex/historical-evidence/' + SLUG
    if evidence_key + '.json' in candidate:
        evidence = json.loads(candidate[evidence_key + '.json'])
        raw = candidate[evidence_key + '.legacy-marker']
        if (evidence['legacy_marker_sha256'] != _hash(raw)
                or evidence['legacy_marker'] != json.loads(raw)
                or evidence['target_sha256'] != evidence['legacy_marker']['target_sha256']
                or evidence['production_migration_enabled'] is not False):
            raise ValueError('Historical archive evidence differs from original')


def _check_candidate_audit(report, candidate, receipt, manifests):
    key = 'hosts/codex/historical-evidence/' + SLUG + '.json'
    if key in candidate:
        evidence = json.loads(candidate[key])
        marker_key = 'hosts/codex/uninstalled/' + SLUG + '.json'
        marker = json.loads(candidate[marker_key]) if marker_key in candidate else None
        model = {'receipt': receipt, 'marker': marker, 'manifests': manifests,
                 'historical_evidence': evidence}
        return (report['status'] == 'blocked'
                and report['project_bound_archive_evidence_checked'] is True
                and report['archive_rehearsal_metadata_sha256'] == audit._digest(model)
                and report['migration_write_allowed'] is False)
    return (report['status'] == 'candidate_metadata_verified_read_only'
            and report['candidate_metadata_sha256'] == audit._digest(
                {'receipt': receipt, 'manifests': manifests}))


def rehearse_migration(root, *, checkpoint=lambda name: None):
    """Stage and publish only the exact generated fixture, retaining originals."""
    root = _checked_fixture(root)
    _context(root)  # Do not create a lock in an unrelated marked fixture.
    with exclusive_lock_file(_path_within_fixture(root, LOCK), nonblocking=True):
        project, live, staged, original, journal, payload, source, candidate, receipt, manifests = _context(root)
        if any(_present(p) for p in (staged, original, journal)):
            raise ValueError('Existing migration journal or state requires recovery')
        _tree(live, source)
        report = audit.audit_legacy_migration(SLUG, project)
        if not _check_candidate_audit(report, candidate, receipt, manifests):
            raise ValueError('Migration audit disagrees with fixture candidate')
        _write_new(journal, payload)
        checkpoint('journal_written')
        _create_tree(staged, candidate)
        _native_verified(staged, candidate, receipt)
        checkpoint('candidate_staged')
        _tree(live, source)
        live.rename(original)
        _sync_directory(project)
        _sync_directory(root)
        checkpoint('original_archived')
        staged.rename(live)
        _sync_directory(project)
        _sync_directory(root)
        checkpoint('candidate_published')
        _native_verified(live, candidate, receipt)
        _tree(original, source)
        _context(root)
        checkpoint('candidate_validated')
        return {'status': 'disposable_migration_published', 'original_records_preserved': True,
                'native_inventory_verified': True, 'rollback_required': True,
                'production_migration_enabled': False, 'real_host_files_modified': False,
                'power_loss_durability_verified': False}


def recover_migration(root, *, checkpoint=lambda name: None):
    """Repeatable rollback for every verified checkpoint; ambiguity refuses writes."""
    root = _checked_fixture(root)
    _context(root)  # Do not create a lock in an unrelated marked fixture.
    with exclusive_lock_file(_path_within_fixture(root, LOCK), nonblocking=True):
        project, live, staged, original, journal, payload, source, candidate, _, _ = _context(root)
        if not _present(journal):
            if _present(staged) or _present(original):
                raise ValueError('Migration evidence without journal; preserve it')
            _tree(live, source)
            return {'status': 'already_restored', 'original_records_restored': True}
        _read_exact(journal, payload)
        # Validate all evidence BEFORE mutating anything. Partial candidate
        # creation/removal is recoverable only when all remaining bytes match.
        if _present(staged):
            _tree(staged, candidate, partial=True)
        archived = _present(original)
        if archived:
            _tree(original, source)
            if _present(live):
                _tree(live, candidate, partial=True)
        else:
            _tree(live, source)
        if archived:
            if _present(live):
                _remove_known_tree(live, candidate)
            checkpoint('candidate_removed')
            original.rename(live)
            _sync_directory(project)
            _sync_directory(root)
            checkpoint('original_restored')
        if _present(staged):
            _remove_known_tree(staged, candidate)
        checkpoint('staging_cleaned')
        _tree(live, source)
        _context(root)
        _read_exact(journal, payload)
        journal.unlink()
        _sync_directory(project)
        return {'status': 'disposable_migration_rolled_back',
                'original_records_restored': True, 'active_skill_unchanged': True,
                'production_migration_enabled': False, 'real_host_files_modified': False,
                'power_loss_durability_verified': False}
