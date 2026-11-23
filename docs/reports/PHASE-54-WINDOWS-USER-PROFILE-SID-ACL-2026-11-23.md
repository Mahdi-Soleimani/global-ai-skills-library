# Phase 54 — Windows current-user Profile identity and ACL security

**Date:** 2026-11-23  
**Repository:** Mahdi-Soleimani/global-ai-skills-library  
**Status at report creation:** implementation and inert test coverage added; Windows User Scope remains fail-closed until native Windows CI passes.

## 1. Objective

Extend Phase 52's existing current-user Profile transaction engine from POSIX to Windows without weakening the existing macOS/Linux passwd/UID/mode-bit checks. Preserve the same transactional operations for Codex, Cursor and Claude Code: preview, fresh install, explicit replace, full backup, restore, archive uninstall, reinstall and crash recovery.

**No actual Windows user's Agent directories or HOME were modified.** Tests use temporary directories, inert Skill packages and read-only inspection of the runner's actual current profile.

## 2. Native Windows identity gates

New tools/windows_user_profile.py uses only Python standard library ctypes and native Win32 APIs:

- OpenProcessToken + GetTokenInformation(TokenUser) retrieves the current process token's exact account SID.
- GetUserProfileDirectoryW retrieves the profile path associated with that same token.
- That path must match USERPROFILE, Path.home() and the explicitly selected absolute directory after canonicalization.
- Reject elevated, restricted, AppContainer, LocalSystem/LocalService/NetworkService and impersonated-thread execution contexts.
- Reject reparse points (including NTFS Junctions) in every existing path component, including the selected path, volume root and profile ancestors. Only local fixed drives are accepted; network and removable profiles are refused.
- Native GetNamedSecurityInfoW, GetSecurityDescriptorDacl, GetAclInformation and GetAce inspect owner SID and actual DACL ACEs. Profile root and every mutable directory/file must be owned by the current SID, or by a trusted OS principal (SYSTEM, BUILTIN Administrators or TrustedInstaller) with an explicit current-SID modify/delete ACE. Ancestors need not grant the current SID write access, but their owner must be the current SID or a trusted OS principal and they may not grant write/delete capabilities to untrusted SIDs.
- A NULL/absent DACL, unknown DACL ACE type, broad/untrusted write grant (including SACL-write capability), hard-link alias, owner mismatch or unreadable ACL is a hard failure. SYSTEM, BUILTIN Administrators, TrustedInstaller and CREATOR OWNER are the only non-current-account write principals accepted.
- Profile identity is an opaque SHA-256 binding to SID, volume serial, file index, normalized profile path and scope. Raw SID and profile path are never stored in receipts.
- TokenHasRestrictions, TokenIsAppContainer, elevation and thread impersonation are checked before a profile write can be considered.

The DACL policy is intentionally conservative: it rejects any untrusted allow-write ACE even if another deny ACE appears to shadow it. It does not try to calculate every possible Windows effective-access combination.

## 3. Transaction engine integration

tools/user_profile_install.py now selects its platform implementation without importing unavailable POSIX pwd on Windows:

- macOS/Linux retain their existing UID, passwd, HOME, non-root and mode-bit policy.
- Windows binds to the process token SID and actual Windows profile path, rejects elevation and validates ACLs before writes.
- The shared exclusive_lock_file provides POSIX flock or Windows msvcrt.locking; the Windows lock file and its parent ACL are verified.
- Every existing state directory, receipt, journal, marker, backup and manifest under .gasl-managed/user/hosts/HOST/ is checked for reparse points, owner SID and ACLs before use.
- Active, staged, archived and recovered Skill trees are checked recursively for owner, DACL, reparse points, regular file type and hard-link aliases.
- New state records are verified immediately after creation. Existing transaction hashes, one-time local TTY approvals, separate download/ZIP/install approvals, Backup lineage, journals and fail-closed recovery remain unchanged.
- Directory fsync durability is **not claimed on Windows**. msvcrt locks coordinate cooperating GASL processes only, not unrelated editors or privileged actors. Power-loss durability, network shares, sync clients and external concurrent writers remain outside the guarantee.

The CLI parser and wizard remain shared. A Windows-specific gate currently requires GASL_ENABLE_WINDOWS_USER_PROFILE_CI=1; that variable is set only inside the disposable Windows CI job. Normal Windows invocations therefore refuse User Profile writes until the native Windows tests are green and the gate is deliberately removed in a follow-up commit.

## 4. Native Windows tests

tests/test_windows_user_profile.py covers:

- Actual current token SID, GetUserProfileDirectoryW, USERPROFILE, Path.home(), local fixed-drive check and profile root owner/DACL (read-only).
- Opaque stable account/profile identity.
- Owned disposable profile and nested file/directory ACL validation.
- Wrong owner SID refusal.
- Everyone write ACE refusal using icacls against a disposable temporary directory only.
- NTFS Junction/reparse-point refusal.
- Elevated token refusal and explicit current-profile path matching.
- Fail-closed Windows User Profile feature gate.
- Thread impersonation refusal.
- Hard-link alias rejection.
- Import without POSIX account modules.

The existing tests/test_user_profile_install.py suite is adapted for Windows: POSIX UID and chmod-mode tests are skipped in favor of SID/DACL-specific tests; the symlink test uses a disposable NTFS Junction on Windows. All lifecycle tests still use only a fake temporary HOME root.

The Windows workflow now runs:
1. Existing native Windows project transaction suite.
2. Native token/profile/ACL suite.
3. Complete User Profile transaction lifecycle against disposable fake HOME roots.
4. Existing private ZIP, target preflight and Host adapter regressions.

## 5. Acceptance boundary

Until the native Windows workflow passes, host_adapters continues to report Windows User Scope as disabled and the production feature gate remains closed. The native workflow itself temporarily opens the gate only to exercise fake profile roots. A green run is required before removing that gate and declaring Windows User Scope available.

Even after acceptance:
- This validates filesystem ownership/transaction safety, **not** live discovery by Codex, Cursor or Claude Code.
- No real Agent was launched and no third-party Skill was executed.
- Cursor may synchronize User Skills to Cloud Agents when Sync Skills is enabled.
- User-wide installs can affect all local projects and require the same exact local interactive TTY consent as POSIX.\n\n