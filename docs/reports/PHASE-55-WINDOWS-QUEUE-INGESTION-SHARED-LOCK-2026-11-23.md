# Phase 55 — Native Windows queue ingestion and shared on-demand lock

**Date:** 2026-11-23  
**Repository:** `Mahdi-Soleimani/global-ai-skills-library`  
**Baseline:** `0e9269b805c9befe522c59a2cbab67939d44522b`  
**Status:** Implementation and complete local regression passed; native Windows CI acceptance pending.

## Goal / prior limitation
The existing `tools/queue_ingest.py` required POSIX `fcntl.flock` and rejected Windows, even though the rest of GASL's transaction engine had a Windows-native `msvcrt.locking` implementation. Separately, `tools/on_demand.py` directly imported `fcntl` and used the same `registry/discovery/.ingest.lock`. Keeping one consumer Windows-enabled while the other uses an incompatible lock would not guarantee mutual exclusion.

## Changes — scoped by file
- `tools/transaction_file_lock.py`: extend `exclusive_lock_file` with optional `nonblocking=True`; POSIX requests `LOCK_EX|LOCK_NB`, Windows uses one `LK_NBLCK` attempt. Existing transaction defaults and bounded Windows retries are unchanged. An opened lock file must be regular with exactly one hard link, verified through `fstat` **before** initialization/locking, rejecting aliases and unexpected filesystem objects. The lock is persistent, never truncated or unlinked by GASL.
- `tools/queue_ingest.py`: add `ingestion_lock(root)` for the one canonical lock, rejecting symlink/junction components. Read policy, queue and repository selection **inside** the lock. Replace queue-only direct `fcntl` with the cross-platform lock. Apply pre-existing Windows filename/ADS/device-name checks to source SKILL paths and ZIP-relative entries in `make_plan`, without relaxing pinned tree, Git Blob, case-collision, size, fixture or public mirroring controls.
- `tools/on_demand.py`: use that exact same `ingestion_lock(root)` while downloading and statically auditing a selected pinned package; remove direct `fcntl` dependency. Install/execution approvals are still always false; no Skill execution has been introduced.
- `tests/test_queue_ingest_lock.py`: add isolated, self-authored fixture tests for queue CLI download/reuse, process-level lock contention, on-demand/queue lock sharing, corrupt checkpoint preservation, hardlink lock refusal, nonregular lock refusal and Windows-specific reserved/ADS filename rejection.
- `.github/workflows/gasl-windows-project-install.yml`: run `tests.test_queue_ingest_lock` and `tests.test_on_demand` on native Windows; add paths to workflow triggers. Existing SID/ACL, Project Scope, User Scope fixture, ZIP and no-host-change checks remain in place.

## Invariants / boundaries
1. All fixture roots are explicit disposable temporary directories. Never write to real HOME, Codex/Cursor/Claude directories or a developer's live catalog in tests.
2. Windows queue writes remain bounded, hash/size verified and strictly non-executing. Source pin, Security Screen and License decisions are **not** elevated to approved or trusted by download.
3. Both consumers coordinate only with **cooperating GASL processes**. This does not prevent privileged manipulation, noncooperating writers, external sync services or abrupt power loss.
4. Windows directory `fsync` and power-loss durability are not guaranteed; no new durability claim.
5. No Windows User Scope production feature flag, native SID/ACL rules, user clock, personal paths or Git history was changed.
6. No third-party Skill code was executed, and no external network download was performed by the fixture tests.

## Evidence and acceptance
**Local macOS tests:** `python3 -m unittest tests.test_queue_ingest_lock tests.test_on_demand tests.test_queue_ingest -v` — 27 tests, 26 passed, one expected Windows-only Skip.

**Full local regression:** `python3 -m pytest -q` — **798 passed, 28 skipped, 337 subtests passed**, 39.61 seconds. `git diff --check` passed.

**Native Windows acceptance required:**
- The queue CLI test must download only inert fixture bytes to disposable root and verify idempotent reuse.
- A second process must fail to acquire a held `msvcrt` byte-range lock before queue/network planning; on-demand must use the same lock file.
- NTFS hard-link and reserved/ADS path guards must reject unsafe names; corrupt checkpoints must remain unpromoted.
- Existing Windows project, SID/ACL, User Profile fake HOME lifecycle and no-host-modification tests must remain passing.
- Do **not** mark Windows Queue accepted until its CI job is observed green. No public release or production HOME activation follows automatically.

## Git protocol
Before publishing, stage only the five above source/workflow/test files plus this report; run staged diff checks and secret scans, fetch `origin/main`, and push a regular fast-forward commit. Record CI evidence in a follow-up report amendment after the result exists.
