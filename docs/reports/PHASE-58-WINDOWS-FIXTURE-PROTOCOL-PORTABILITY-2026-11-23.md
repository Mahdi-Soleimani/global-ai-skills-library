# Phase 58 — Windows fixture transactions and protocol portability, increment 1

**Date:** 2026-11-23
**Baseline:** `31f8c4a` (metadata refresh fast-forward after Phase 57).
**Status:** Four previously excluded test modules are implemented for native Windows execution; local verification passed, remote native acceptance pending.

## Design boundary
Phase 53 introduced a distinct Windows project engine under `.gasl-managed/hosts/codex/`. The older POSIX Codex receipt/archive engine uses a different schema and state namespace. Do not enable its write path merely by swapping its lock; doing so could create conflicting ownership histories. This increment ports independent disposable-fixture and protocol components, not legacy Codex production writes.

## Changed files and technical decisions
- `tools/codex_discovery_probe.py`, `tools/other_host_protocol_probe.py`: native anonymous-pipe readiness through Windows PeekNamedPipe, retaining POSIX selectors; bounded reads, JSONL size validation, deadlines, explicit HOME/USERPROFILE/APPDATA/TEMP isolation variables, no inherited arbitrary credentials. Default Windows vendor executable launch remains explicitly gated until separate real-host/profile-isolation acceptance; injected GASL-authored synthetic subprocesses exercise the transport. No actual Windows vendor discovery or sandbox claim.
- `tools/fixture_transaction_v2.py`: reuse the permanent, nonblocking shared POSIX flock / Windows byte lock. Preserve lock-busy refusal, hard-link rejection, exact approval binding, staged inventory verification and rollback. Flush file data on both platforms, retain POSIX directory fsync, explicitly disclose Windows directory-fsync limitation and absence of power-loss durability certification.
- `tools/host_adapters.py`: reject redirected roots/components, NTFS junctions, Windows reparse points and unsafe Windows relative file names before fixture mutation. Still require a marked disposable root immediately below the OS temporary directory.
- `tools/fixture_explicit_consent.py`: retain POSIX 0600, validate Windows owner/DACL for disposable root, signing key and receipt, reject untrusted read as well as write grants; write random key in binary mode, fsync file contents, preserve atomic one-time receipt publication and replay prevention. Temporary write failures clean up only the newly created temporary file after closing its handle.
- `tools/windows_user_profile.py`: optional `require_private` adds a stricter ACL confidentiality condition for fixture consent state. Existing production caller defaults and Windows User Profile gate are unchanged.
- Four test modules: launch generated Python protocol fixtures via the exact Python interpreter on Windows; exercise incomplete/oversized responses, version-only semantics, default vendor launch gate, native junction refusal, untrusted signing-key read ACL, lock contention, exact consent, expiry, tampering, cross-process replay and rollback. Actual CLI refusal tests on Windows use Python entrypoint rather than Unix Bash wrapper.
- `.github/workflows/gasl-cross-platform.yml`: remove four module exclusions (`test_codex_discovery_probe.py`, `test_other_host_protocol_probe.py`, `test_fixture_transaction_v2.py`, `test_fixture_explicit_consent.py`). Nine legacy exclusions remain. Guard still requires the legacy Codex POSIX-only engine to be disabled on Windows.

## Local verification
- Python compile: PASS.
- Focused four-module suite: **69 tests, 65 passed, 4 Windows-specific skipped**.
- Complete macOS pytest: **806 passed, 32 skipped, 337 subtests passed** (45.82 seconds).
- Git diff whitespace checks: PASS.
- The fixture matrix continues testing 36 host/scope/action/checkpoint combinations with and without one-time consent. No real HOME install, production gate change, third-party Skill execution or clock change.

## Native acceptance and remaining work
Require Windows CI to actually exercise the four newly eligible modules, including the new ACL test; record failures if any. The previous Phase 57 three-OS matrix and Daily Refresh passed; evidence appended to its own report. Nine legacy modules remain excluded: six Codex legacy installer/archive/review/explorer modules and three transaction/discovery E2E modules. Do not silently merge the two Codex ownership stores or weaken recovery/security rules. A separate native migration/retirement and independent real-host isolation review remain necessary. No public release or human gold evaluation.

## Increment 2 — three additional disposable Codex E2E modules

Base implementation commit `5c7d6d68f13d5d78ee094734010a7e2d3f7c1723`; metadata-only refresh `674f9bb` fast-forwarded. Native Windows project/user-profile transaction workflow [45288144506](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45288144506) succeeded. Daily refresh [45288144384](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45288144384) succeeded. Previous broad matrix [45288145002](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45288145002) macOS and Ubuntu succeeded; Windows result was still running at last check before publication.

- `tools/codex_transaction_e2e.py` and `tools/codex_third_party_discovery.py`: reuse the cross-platform bounded pipe selector; default real Windows vendor process invocation fails closed before any fixture materialization. Synthetic tests explicitly inject a controlled Python subprocess or query. Report flags distinguish injected evidence from default vendor observation.
- `tools/codex_pinned_bundle_e2e.py`: Windows default vendor query blocked before bundle staging; existing exact acknowledgement, pinned identity, static review, inventory and rollback gates preserved.
- `tests/test_codex_transaction_e2e.py`, `tests/test_codex_third_party_discovery.py`, `tests/test_codex_pinned_bundle_e2e.py`: Windows-safe interpreter/fixture paths, simulated vendor list responses, native-only default vendor gating, rejection of symlink executables, stale/disabled/malformed results, wrong Blob and package/scope, and exact verified disposable rollback. The third-party-discovery regression uses GASL-authored inert bytes, not fetched third-party Skill execution.
- `.github/workflows/gasl-cross-platform.yml`: three more module exclusions removed, leaving six legacy Codex-only transaction/archive/provenance/explorer modules. Seven of thirteen modules are implementation-ready; native acceptance depends on actual CI. Existing production flags unchanged.

Verification: focused E2E suite 33 tests (30 passed, 3 Windows-only skipped); complete macOS regression 806 passed, 35 skipped, 337 subtests passed (40.35s); compile and whitespace checks passed. No actual Windows vendor isolation claim, no real HOME mutation, no third-party execution or installation approval.

## Increment 3 — actual native CI failure correction and ownership namespace boundary

Previous push `90151a308c3bf228614d9d94788b724a61fd62ef` confirmed published. Real inert Codex POSIX lifecycle workflow 45288811661 and Daily Refresh 45288811667 succeeded. Broad Windows matrix results (both failed, not accepted):
- [45288145002](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45288145002), job 138089705805: 24 failed, 630 passed, 6 skipped. All 24 failures were fixture consent requests refused by the existing SID/DACL verifier.
- [45288811860](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45288811860), job 138091971468: 27 failed, 660 passed, 6 skipped. The same 24 receipt cases plus 3 dependent one-time-receipt E2E cases failed. macOS/Ubuntu passed in both matrices. This is not seven-module native acceptance.
- Exact primary traceback: `request_fixture_consent -> _secret(create=True) -> _verify_private_fixture_path(fixture, directory=True) -> verify_owned_path` rejected an Administrators-owned temporary directory lacking explicit current-token SID modify/delete ACE. No relaxation of owner, DACL, confidentiality, or reparse checks.

Changes:
- `tools/host_transaction_fixture.py`: protect a newly created empty, directly-under-temp GASL disposable fixture before marker/data creation. On Windows, build a native protected inheritable DACL with full access only for the exact process token SID and LocalSystem; verify it through the unchanged strict checker. Refuse nonempty or redirected paths; no existing receipt repair, no real HOME changes, no change to real user-scope policy. POSIX path unchanged.
- `tests/test_fixture_explicit_consent.py`: verify root, key and receipt ACL inheritance and reject attempts to re-protect populated fixtures; keep untrusted read grant, expiry, tampering and replay regression coverage.
- `tools/codex_project_install.py`, `tools/host_project_install.py`: add read-only bidirectional schema boundary for alternate Codex receipts, journals, uninstall markers, backup history and unresolved stages. Preserve unknown data unchanged; refuse migration automatically. Native Codex also acquires the legacy project coordination lock before its host-scoped lock; legacy engine rechecks alternate state after its own lock. Only local cooperating process coordination is claimed, not network/distributed or old-binary cross-OS safety. Cursor/Claude remain independent. No receipt format conversion, no enabling legacy Windows writes.
- `tests/test_codex_state_boundary.py`: test both directions across five evidence types, independent host/Skill, unsafe state directory and native Windows lock refusal. The six legacy modules remain excluded pending explicit safe migration or verified retirement.
- `.github/workflows/gasl-locked-fixture-transaction.yml`: separate targeted Ubuntu/Windows Python 3.13 matrix covering real file locks, consent and schema boundaries; no third-party downloads/execution. Portable checkout guard.

Local results: focused fixture/E2E 61 tests (57 passed, four Windows-only skipped); targeted Codex/backup/recovery suites 184 tests (183 passed, one Windows-only skipped); full macOS **809 passed, 37 skipped, 347 subtests passed** in 51.14s. YAML parse and diff checks passed. Native correction requires fresh CI; do not mark Phase 58 accepted before that result.

## Increment 4 — confirmed Windows ACL fix and read-only Codex migration audit

Base implementation `bf96378a772bf24ae0c524dc0383a3492a8d0d17` confirmed published. Dedicated [locked-fixture CI 45289586100](https://github.com/Mahdi-Soleimani/global-ai-skills-library/actions/runs/45289586100) completed SUCCESS: native Windows job 138094619314 ran all 51 tests successfully (including private ACL inheritance, untrusted read grant refusal, native Codex coordination); Ubuntu job 138094618660 ran 51 tests with four platform-specific skips. Native Windows project/user-profile fixture CI 45289586311 also passed. Broad matrix 45289586203: Ubuntu and macOS completed successfully, Windows still running at last check; no broad-matrix acceptance claimed yet.

Changes:
- `tools/codex_migration_audit.py`: bounded record reads, duplicate JSON key rejection, regular file and hardlink checks, complete legacy active receipt/backup inventory and ordered lineage validation, explicit alternate namespace and pending-stage/journal refusal. Only simple fresh-install/replace chains with recognized exact metadata fields can be represented in the existing host-scoped schema. Validate the candidate receipt and backup manifests in memory through existing native validators. Keep recorded Plan IDs and bindings as historical metadata, not proof of provenance or new authorization.
- Return deterministic SHA-256 digests of original record bytes, inventory and candidate metadata; re-read the entire snapshot and refuse observable concurrent drift. No project path disclosure, candidate receipt publication, lock creation, file write, source retrieval, real Host invocation or migration consent. This is not an atomic/cooperatively locked snapshot or power-loss/rollback certification.
- Uninstall markers (including retained historical markers), manual/unmanaged origin, unknown historical fields/actions, conflicting ownership, incomplete backup chains and changed content block the candidate. No unsupported history is silently downgraded or converted.
- `tools/transaction_file_lock.py`: opt-in portable Windows filename validation on POSIX as well as Windows, without changing existing callers' platform-gated behavior.
- `tools/gasl.py`: `codex-migration-audit --selected-root ABSOLUTE_GIT_PROJECT --skill-name SKILL`; JSON, exit 0 only for compatible in-memory candidate metadata; exit 2 for blocked audit. No apply command.
- `tests/test_codex_migration_audit.py`: 13 tests for deterministic complete-chain evidence, exact local byte preservation, drift, conflicting state, unknown/unmanaged history, invalid/duplicate JSON, hardlinks, portable filenames and CLI exit codes. Extend dedicated Ubuntu/Windows workflow and README.

Local verification: focused suite 64 tests (60 passed, four skipped); complete macOS pytest **822 passed, 37 skipped, 355 subtests passed** in 53.48 seconds. Compilation and whitespace checks passed. All six legacy POSIX installer/review modules remain excluded on Windows; migration is NOT implemented as a write path. Next safe gate is a disposable-only reversible migration transaction design, with archived original records, journal, crash checkpoints, schema boundary during transition and exact post-migration validation. Production migration remains disabled.
