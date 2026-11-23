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
