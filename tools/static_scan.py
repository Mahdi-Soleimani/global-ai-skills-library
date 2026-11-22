#!/usr/bin/env python3
"""Context-aware static review. Heuristics only; no code is executed and no package is auto-approved."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog"
REPORTS = ROOT / "reports" / "security"

RULES = [
    ("PROMPT_INJECTION_DIRECTIVE", "high", "medium", re.compile(
        r"ignore (all )?(previous|prior) instructions|disregard (all )?(previous|prior) instructions|"
        r"override (the )?system prompt|reveal (the )?(secret|credential|token)|"
        r"send (the )?(secret|credential|token).{0,100}(http|url|server|webhook)", re.I),
     "Explicit instruction to override model instructions or disclose credentials"),
    ("SECRET_STORE_ACCESS", "high", "medium", re.compile(
        r"\.ssh/|\.aws/credentials|security find-generic-password|"
        r"keychain.{0,80}(password|secret|token)|"
        r"process\.env\.(?:TOKEN|SECRET|KEY|PASSWORD)|os\.environ", re.I),
     "Potential local secret or credential access"),
    ("SECRET_TO_HTTP_BODY", "high", "high", re.compile(
        r"(?:token|secret|api[_-]?key|password).{0,300}(?:Request|urlopen|fetch|requests\.post|axios\.post)"
        r".{0,120}(?:data\s*=|json\s*=|body\s*=|\.encode\(\))", re.I | re.S),
     "Credential-like value appears to be placed in an outbound HTTP request body"),
    ("DYNAMIC_CODE_EXECUTION", "high", "medium", re.compile(
        r"\beval\s*\(|new Function\s*\(|base64\s+(-d|--decode)|"
        r"atob\s*\(|Buffer\.from\([^\n]+base64", re.I),
     "Dynamic execution or encoded payload pattern"),
    ("UNESCAPED_DESCRIPTION_CODE_TEMPLATE", "high", "medium", re.compile(
        r"f[\"'][^\n]*\{[^}\n]*(?:\[['\"]description['\"]\]|"
        r"\.description|get\([\"']description[\"']\))[^}\n]*\}", re.I),
     "Untrusted description text is interpolated into generated source code without an evident encoder"),
    ("WILDCARD_CORS_ORIGIN", "medium", "high", re.compile(
        r"Access-Control-Allow-Origin[\"']?\s*(?::|,)\s*[\"']\*[\"']", re.I),
     "Wildcard CORS accepts requests from every web origin; restrict origins before exposing the server"),
    ("NODE_SERVER_IMPLICIT_ALL_INTERFACES", "medium", "medium", re.compile(
        r"\.listen\(\s*(?:port|PORT|[0-9]{2,5})\s*(?:\)|,\s*(?:\(\s*\)\s*=>|function\s*\(|[A-Za-z_$][\w$]*\s*\)))", re.I),
     "Node HTTP server listens without an explicit loopback address; confirm network exposure and origin/auth controls"),
    ("SHELL_OR_PROCESS_SPAWN", "medium", "low", re.compile(
        r"child_process|subprocess\.(?:run|Popen|call)|os\.system\s*\(|"
        r"execFile\s*\(|spawn(?:Sync)?\s*\(", re.I),
     "Code can start subprocesses; inspect exact call and input handling"),
    ("NETWORK_ACCESS", "medium", "low", re.compile(
        r"\b(fetch\s*\(|https?\.request|requests\.(?:get|post)|"
        r"urllib\.request|axios\.|curl\s|wget\s)", re.I),
     "Code or instructions include network access"),
    ("PACKAGE_INSTALL", "medium", "low", re.compile(
        r"\b(npm install|pip install|uv add|brew install|apt-get install|pnpm add)\b", re.I),
     "Package installation command detected"),
    ("UNPINNED_REMOTE_PACKAGE_EXECUTION", "medium", "medium", re.compile(
        r"\b(?:npx|pnpm\s+dlx|bunx|yarn\s+dlx|npm\s+(?:exec|create))\s+"
        r"(?:(?:--yes|-y)\s+)*([@A-Za-z0-9][A-Za-z0-9._/@+-]*)", re.I),
     "Package runner may download and execute a mutable or unpinned registry package; inspect and pin an exact version"),
    ("PRIVILEGED_OR_PERSISTENT_ACTION", "high", "medium", re.compile(
        r"chmod\s+\+x|launchctl|osascript|sudo\s|crontab|systemctl enable", re.I),
     "Potential privileged, persistent, or OS automation action"),
]

CODE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".cjs", ".mjs", ".py", ".sh", ".ps1", ".bat", ".cmd", ".rb", ".go", ".rs", ".php"}
TEXT_SUFFIXES = CODE_SUFFIXES | {".md", ".txt", ".json", ".yaml", ".yml"}


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def is_test_file(path):
    low = str(path).lower()
    return ("/test/" in low or "/tests/" in low or ".test." in low or
            ".spec." in low or low.endswith(("_test.py", "_tests.py")))


def _is_regular_bounded_path(root, package_dir, relative_path):
    """Allow only ordinary files belonging to this exact package; never follow symlinks."""
    if (not isinstance(relative_path, str) or not relative_path or "\\" in relative_path or
            "\x00" in relative_path):
        return None
    relative = Path(relative_path)
    if (relative.is_absolute() or any(part in ("..", ".") for part in relative.parts) or
            not relative.parts or relative.parts[0] != "catalog"):
        return None
    target = root / relative
    try:
        target.relative_to(package_dir)
    except ValueError:
        return None
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return None
    if not target.is_file():
        return None
    return target


def verified_internal_checkpoint(path, metadata):
    """Recognize a legacy downloader JSON sidecar only if it matches the inventory.

    It is not executable Skill content and is never trusted as authority for
    the inventory: each entry must match a separately hashed source.json row.
    """
    if (path.name != ".gasl-download-checkpoint.json" or path.is_symlink() or
            not path.is_file() or path.stat().st_size > 256 * 1024):
        return False
    try:
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        if set(checkpoint) != {"repository", "commit_sha", "source_skill_path", "files", "updated_at"}:
            return False
        if any(checkpoint.get(key) != metadata.get(key) for key in
               ("repository", "commit_sha", "source_skill_path")):
            return False
        files = checkpoint.get("files")
        if not isinstance(files, dict):
            return False
        entries = {item["source_path"]: item for item in metadata.get("files", [])}
        if not files or set(files) != set(entries):
            return False
        return all(
            source in entries and isinstance(saved, dict) and
            all(saved.get(key) == entries[source].get(key) for key in
                ("source_path", "local_path", "size_bytes", "sha256", "git_blob_sha"))
            for source, saved in files.items()
        )
    except (OSError, ValueError, TypeError, KeyError):
        return False


def _is_exact_pinned_npm_spec(spec):
    """Only an exact x.y.z package version counts as pinned for remote runners."""
    if not isinstance(spec, str) or spec.startswith((".", "/", "file:", "git+")):
        return True
    version_at = spec.rfind("@")
    if version_at <= 0:
        return False
    if spec.startswith("@") and version_at <= spec.find("/"):
        return False
    version = spec[version_at + 1:]
    return bool(re.fullmatch(
        r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", version))


def scan_package(source_path, root=ROOT, persist=True):
    # Keep root/source spelling consistent on macOS (/var -> /private/var).
    # Do not resolve the source file here: doing so could hide a symlink.
    root = Path(root).absolute()
    source_path = Path(source_path)
    if not source_path.is_absolute():
        source_path = root / source_path
    source_path = Path(source_path)
    package_dir = source_path.parent
    if source_path.is_symlink():
        raise ValueError("Symlink in security-scan source path")
    if (source_path.name != "source.json" or
            package_dir.is_symlink() or root / "catalog" not in package_dir.parents or
            not package_dir.is_dir() or not package_dir.resolve().is_relative_to((root / "catalog").resolve())):
        raise ValueError("Security scan requires a regular source.json inside the local catalog")
    # Reject symlinked directory components, even if they resolve inside catalog.
    current = root
    for component in source_path.relative_to(root).parts:
        current = current / component
        if current.is_symlink():
            raise ValueError("Symlink in security-scan source path")
    metadata = json.loads(source_path.read_text(encoding="utf-8"))
    integrity = []
    findings = []
    seen = set()
    files = metadata.get("files", [])
    if not isinstance(files, list) or not files:
        files = []
    for item in files:
        if not isinstance(item, dict):
            integrity.append({"path": None, "status": "invalid_inventory_entry"})
            continue
        local_path = item.get("local_path")
        if not isinstance(local_path, str) or local_path in seen:
            integrity.append({"path": local_path, "status": "invalid_or_duplicate_path"})
            continue
        seen.add(local_path)
        local = _is_regular_bounded_path(root, package_dir, local_path)
        if local is None:
            integrity.append({"path": local_path, "status": "unsafe_missing_or_nonregular_path"})
            continue
        expected_size = item.get("size_bytes")
        if (not isinstance(expected_size, int) or isinstance(expected_size, bool) or
                expected_size < 0 or expected_size > 10 * 1024 * 1024 or
                local.stat().st_size != expected_size):
            integrity.append({"path": local_path, "status": "size_mismatch_or_scan_limit_exceeded"})
            continue
        digest = sha256(local)
        ok = digest == item.get("sha256")
        integrity.append({"path": local_path, "status": "ok" if ok else "hash_mismatch"})
        if not ok or local.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            content = local.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        suffix = local.suffix.lower()
        code = suffix in CODE_SUFFIXES
        test_file = is_test_file(item["local_path"])
        for rule_id, severity, confidence, pattern, description in RULES:
            if not code and rule_id not in {"PROMPT_INJECTION_DIRECTIVE", "UNPINNED_REMOTE_PACKAGE_EXECUTION"}:
                continue
            if rule_id == "NODE_SERVER_IMPLICIT_ALL_INTERFACES" and suffix not in {".js", ".jsx", ".ts", ".tsx", ".cjs", ".mjs"}:
                continue
            if rule_id == "SHELL_OR_PROCESS_SPAWN" and test_file:
                severity, confidence = "info", "high"
            for match in pattern.finditer(content):
                if (rule_id == "UNPINNED_REMOTE_PACKAGE_EXECUTION" and
                        _is_exact_pinned_npm_spec(match.group(1))):
                    continue
                line_no = content.count("\n", 0, match.start()) + 1
                lines = content.splitlines()
                start = max(0, line_no - 2)
                end = min(len(lines), line_no + 1)
                excerpt = "\n".join(lines[start:end])[:500]
                findings.append({
                    "rule_id": rule_id,
                    "severity_signal": severity,
                    "confidence": confidence,
                    "file": item["local_path"],
                    "line": line_no,
                    "evidence": match.group(0)[:160],
                    "context_excerpt": excerpt,
                    "test_harness_context": test_file,
                    "description": description
                })
                if len(findings) >= 300:
                    break
            if len(findings) >= 300:
                break

    # An attacker could add an unlisted file with executable content. Verify
    # the full local inventory, not only entries declared by source.json.
    existing = set()
    for local in package_dir.rglob("*"):
        relative = local.relative_to(root).as_posix()
        if local.is_symlink() or not (local.is_file() or local.is_dir()):
            integrity.append({"path": relative, "status": "unexpected_symlink_or_nonregular_entry"})
        elif local.is_file():
            existing.add(relative)
    ignored_checkpoints = 0
    for unexpected in sorted(existing - seen - {(source_path.relative_to(root)).as_posix()}):
        local = root / unexpected
        if (local.parent == package_dir and
                verified_internal_checkpoint(local, metadata)):
            ignored_checkpoints += 1
            continue
        integrity.append({"path": unexpected, "status": "unlisted_package_file"})
    integrity_ok = bool(integrity) and all(x["status"] == "ok" for x in integrity)
    actionable_findings = [x for x in findings if x["severity_signal"] != "info"]
    high_confidence = [x for x in actionable_findings if x["confidence"] == "high"]
    status = ("integrity_failed" if not integrity_ok else
              "manual_review_required" if actionable_findings else
              "no_obvious_static_flags_not_approved")
    metadata["security_status"] = status
    metadata["last_static_scan_at"] = now()
    metadata["static_scan_finding_count"] = len(findings)
    metadata["static_scan_actionable_finding_count"] = len(actionable_findings)
    metadata["high_confidence_signals"] = len(high_confidence)
    metadata["install_status"] = "not_approved"
    if persist:
        source_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "repository": metadata.get("repository"),
        "skill_name": metadata.get("skill_name"),
        "skill_path": metadata.get("source_skill_path"),
        "commit_sha": metadata.get("commit_sha"),
        "integrity_ok": integrity_ok,
        "integrity": integrity,
        "recognized_legacy_internal_checkpoints": ignored_checkpoints,
        "security_status": status,
        "high_confidence_signals": len(high_confidence),
        "finding_count": len(findings),
        "actionable_finding_count": len(actionable_findings),
        "informational_finding_count": len(findings) - len(actionable_findings),
        "findings": findings,
        "execution_performed": False,
        "scanned_at": now()
    }


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    packages = list(CATALOG.glob("**/source.json"))
    if not packages:
        print("No downloaded packages found.")
        return
    results = []
    for source in packages:
        result = scan_package(source)
        results.append(result)
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_",
                      (result["repository"] or "repo") + "__" + (result["skill_name"] or "skill"))
        out = REPORTS / (safe + ".json")
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(result["repository"], result["skill_name"], result["security_status"],
              "integrity_ok=", result["integrity_ok"],
              "high_confidence=", result["high_confidence_signals"],
              "signals=", result["finding_count"])
    summary = {
        "schema_version": "0.2.0",
        "scanned_at": now(),
        "package_count": len(results),
        "execution_performed": False,
        "results": results
    }
    (REPORTS / "scan-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Static scan complete. No downloaded code was executed.")
    print("A clean scan is not a security approval; manual review and behavior evaluation remain separate gates.")


if __name__ == "__main__":
    main()
