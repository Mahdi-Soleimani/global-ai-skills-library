# Phase 2 — Cloudflare Security Audit skill: static manual review

- Date: 2026-11-20
- Repository: `cloudflare/security-audit-skill`
- Skill: `security-audit`
- Source commit: `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8`
- License metadata: MIT

## Integrity

- Manifest files: 20
- Total bytes: 314,670
- Every file exists locally and matches its manifest byte size and SHA-256.
- Package completeness: true.

## Static scanner findings

- Total findings: 12
- Rule: `SHELL_OR_PROCESS_SPAWN` (12)
- Files: `validate-coverage-ledger.test.cjs` (6), `validate-findings.test.cjs` (6)
- Every finding is marked `test_harness_context=true`.
- High-confidence signals: 0.

## Manual source review

- The main `SKILL.md` and companion documents define a defensive, source-first workflow and explicitly prohibit live-target testing, external network access, real credentials, and target-code execution outside a strict OS-enforced sandbox.
- The two non-test validator scripts use Node built-in modules only; no third-party dependency manifest was found.
- Reviewed input readers require `O_NOFOLLOW` and `O_NONBLOCK`, reject non-regular files, enforce a 5 MiB input limit, and decode UTF-8 strictly.
- The 12 process-spawn findings are confined to test harnesses that spawn Node and create local test fixtures. Those tests were not executed.
- No non-test child-process or network call site was found in the reviewed package files.

## Safety decision

- Source integrity: PASS.
- Static manual review: completed; no obvious malicious behavior found in the reviewed package.
- Dynamic validation: NOT RUN. The required OS-enforced sandbox with empty environment, no external network, read-only target, bounded scratch, and resource/time limits has not been established.
- Installation: NOT APPROVED.
- Execution: NOT APPROVED.

This is not a claim that dynamic behavior has been proven safe. The package remains uninstalled and its runtime behavior untested.

## Related high-confidence triage

The current 60-package security snapshot has two high-confidence static signals. One belongs to `openai/codex-security:status-summary`, whose source path is explicitly `evals/check-skills/fixtures/status-summary/SKILL.md`; its fixture script sends `DEMO_RELEASE_TOKEN` to `DEMO_STATUS_ENDPOINT` in an HTTP POST body. It is preserved as a security test fixture and excluded from the active Skill candidate set.

The other signal is in `anthropics/skills:claude-api`. Preliminary source inspection indicates the token is placed in the Authorization header while the HTTP body is serialized separately; the scanner appears to have matched across adjacent code. However, `ANTHROPIC_BASE_URL` and `--base-url` can override the default endpoint, so endpoint trust remains an open review item. No code was executed and the package is not approved.

The detailed local review ledger is `reports/security/manual-review-ledger.json` and is intentionally excluded from the public repository.

## Acceptance

- All 20 package files hash-verified: PASS.
- All 12 static findings manually located in test harnesses: PASS.
- No downloaded code executed: PASS.
- Runtime sandbox validation: BLOCKED / NOT RUN.
- Install approval: NOT GRANTED.
