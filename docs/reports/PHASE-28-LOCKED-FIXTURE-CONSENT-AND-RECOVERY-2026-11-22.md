# Phase 28 — Exact fixture-only approval challenge, POSIX transaction lock and interrupted recovery

**Date:** 2026-11-22  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Scope:** Strengthen the Phase-26 private ZIP installation **only within GASL-created disposable test profiles**. Add state/version/action binding, POSIX process locking, filesystem sync barriers and recovery from a separate process; **do not** turn on a real Host installer.

## 1. Why this phase exists

- Phase 25 provides a private, version-pinned ZIP and integrity manifest.
- Phase 26 actually places ZIP bytes into a self-created temporary Host layout, backs up the inert previous version and restores it.
- Phase 27 computes a read-only fingerprint of the exact proposed Host target and its contents, without user-directory changes.
- Phase 28 combines those earlier components to test a **separate, exact fixture-only consent challenge**, refusal of concurrent cooperative installers, and recovery after an intentionally interrupted operation, all without altering the user's Agent profiles.

### Command

```bash
./gasl locked-bundle-fixture \
  --plan-id YOUR_EXACT_PLAN_ID \
  --acknowledge-plan-id YOUR_EXACT_PLAN_ID \
  --agent codex --scope project --action replace \
  --checkpoint backed_up \
  --acknowledge-fixture-only GASL_DISPOSABLE_FIXTURE_ONLY
```

Action `install` requires an absent temporary Skill target; `replace` requires an existing inert fixture target. `--checkpoint` accepts `staged`, `backed_up`, `activated`. The command creates and destroys its **own GASL-marked temporary profile**; it does not accept an arbitrary installation destination. It reads an existing locally private bundle but never creates or uses an actual Codex, Cursor or Claude Code user profile.

## 2. Implementation

- Added `tools/fixture_transaction_v2.py` and a `locked-bundle-fixture` dispatch in `tools/gasl.py`. No third-party dependencies added; `fcntl` is used only on supported Unix systems and fails closed elsewhere.
- `preview_fixture_consent` calls the Phase-27 read-only target preflight on the **temporary** profile and hashes a canonical request identity: original 64-char Plan ID, exact ZIP SHA-256, Host, Scope, `install`/`replace`, target path SHA-256 and current prior-target state binding. The resulting `approval_challenge` is separate from the simpler plan acknowledgement. A changed target, different action or different bundle invalidates it. This challenge is **not a secret, cryptographic signature, identity proof or proof of real human approval**.
- `_exclusive_fixture_lock` requires the existing GASL temporary-root marker, opens a stable `.gasl-phase28-transaction.lock` with no symlink following, checks the lock inode is a unique regular file, and applies **nonblocking, cooperative POSIX `flock`**. The lock inode is not removed while the fixture exists. A second process attempting the transaction or recovery while it is held fails closed.
- `enact_fixture_transaction` checks the exact approval challenge while the lock is held, stages only bytes validated by the pinned private ZIP checker, records the existing Phase-26 journal and runs **file and directory `fsync` barriers** on staged data and relevant directory renames. It re-reads the target binding after staging and refuses mismatched state before activation. Staging/backup/activation operate only inside the existing temporary fixture boundaries.
- `recover_fixture_transaction` opens the same process lock from a **separate invocation**, validates the journal, old and new file inventories, refuses altered files/backups, then restores exactly the previous inert fixture version or removes the newly installed fixture copy. Failure preserves conflicting contents for inspection, rather than silently overwriting modifications.
- `rehearse_locked_transaction` is a one-shot, automatically disposed helper used by the CLI and tests. It creates a new disposable root, optionally seeds a previous **self-authored inert** Skill with user-note sentinel, obtains and matches the fixture challenge, invokes the controlled ZIP file transaction, rolls it back, and removes the entire temporary profile. It reports `real_host_files_modified=false`, `third_party_skill_executed=false`, and `production_installation_enabled=false`.

### Meaning and limits of security controls

**No user profile is written.** Reading a private ZIP copies its bytes to a disposable profile as files; it **never runs its scripts, reads its instructions as privileged commands, loads it into a real Agent or starts a model/API call**. Test-only acknowledgements are deliberately not reusable for any real installer. `flock` serializes only cooperating processes; other programs with filesystem access may bypass it. `fsync` reduces durability gaps on supported POSIX filesystems but **does not prove arbitrary power-failure recovery**, atomicity across different volumes, or adversarial concurrent modification safety. These must be handled and tested separately before any production installer exists. Windows does not provide `fcntl` in this code; the test-only transaction refuses to run there.

## 3. Tests and actual Mac results

New `tests/test_fixture_transaction_v2.py`: **19 test methods** with a **36-case subtest matrix** (3 local Host adapters × 2 scopes × 2 actions × 3 checkpoints). The test suite exercises:

- Correct temporary action/Host/Scope/version/state binding; stale and missing challenge rejection.
- Refusal when the package or existing target changes after preview or between staging and activation.
- Failed staged durability sync, corrupt journal, modified activated content or backup, and preservation of local edits.
- Symlink and hardlink attacks on the lock inode; absence of POSIX file-lock support fails closed.
- Actual nonblocking conflict while a **second OS process** tries to acquire the same lock.
- Actual rollback initiated by a **separate Python process** after backup and after activation checkpoints, restoring the prior file hashes and the user-note sentinel.
- No real Agent directory change, third-party Skill execution, model invocation or package publication.

The complete Mac test suite passed **384 tests and 179 subtests**, Python byte-compilation and Git whitespace checks passed.

**Actual locally private ZIP smoke:** reused `academy-guide` from Phase 25 (Plan ID `f52f11b345714191c780bd63b6e18e1d05a9f2ed3257c3b791a9e2fa00e45fcb`). Ran all six Codex/project scenarios (`install` and `replace`, each at `staged`, `backed_up` and `activated` checkpoints). All six returned `fixture_locked_transaction_rollback_verified`, `previous_files_restored=true`, `real_host_files_modified=false` and `third_party_skill_executed=false`. A deliberately wrong `--acknowledge-fixture-only` value exited unsuccessfully. The original ZIP and its private manifest remain Git-ignored; the actual ZIP bytes were **never** committed or uploaded to GitHub Actions.

## 4. Dedicated Linux CI

New `.github/workflows/gasl-locked-fixture-transaction.yml` uses `ubuntu-24.04`, minimal `contents: read` permission, checkout with no persisted Git credentials, Python compilation, and only **GASL-authored synthetic pinned ZIP fixtures**. It tests cooperative multi-process locking and independent recovery on Linux. Its final step refuses private ZIPs, personal catalogs, or simulated installation ledgers inside the public checkout.

At initial publication, the Linux workflow's result is **not inferred** from the successful Mac tests. The workflow run must be inspected after pushing, and its outcome appended to this report.

## 5. Next gates before production Host installation

1. Obtain **separate, genuine user consent** for exact source, ZIP hash, Host, canonical target, operation and requested permissions. Test-only `approval_challenge` and Plan ID re-entry cannot count as that approval.
2. Add production-grade transaction ownership, non-cooperating file change detection, durable journaling, controlled pending-state recovery and reliable backup restoration on real approved disposable user accounts before any personal profile writes.
3. Review the upstream License/NOTICE, prompt and code security risk, and actual Host discoverability. Codex's independent isolated discovery proof applies only to inert test content. The remaining downloaded Skills are untrusted.
4. Validate Windows and actual per-user Host layouts/permissions, including change conflicts and recovery from real process crashes. Do not assume successful simulated checkpoints establish power-cut safety.

**Phase 28 locally accepted for fixture-only state-bound, serialized ZIP transaction and cross-process rollback. Production installation is still disabled.**
