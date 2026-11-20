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
    ("PRIVILEGED_OR_PERSISTENT_ACTION", "high", "medium", re.compile(
        r"chmod\s+\+x|launchctl|osascript|sudo\s|crontab|systemctl enable", re.I),
     "Potential privileged, persistent, or OS automation action"),
]

CODE_SUFFIXES = {".js", ".cjs", ".mjs", ".py", ".sh", ".ps1", ".bat", ".cmd", ".rb", ".go", ".rs", ".php"}
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


def scan_package(source_path):
    metadata = json.loads(source_path.read_text(encoding="utf-8"))
    integrity = []
    findings = []
    for item in metadata.get("files", []):
        local = ROOT / item["local_path"]
        if not local.exists() or not local.is_file():
            integrity.append({"path": item["local_path"], "status": "missing_or_not_regular_file"})
            continue
        digest = sha256(local)
        ok = digest == item["sha256"]
        integrity.append({"path": item["local_path"], "status": "ok" if ok else "hash_mismatch"})
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
            if not code and rule_id != "PROMPT_INJECTION_DIRECTIVE":
                continue
            if rule_id == "SHELL_OR_PROCESS_SPAWN" and test_file:
                severity, confidence = "info", "high"
            for match in pattern.finditer(content):
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

    integrity_ok = bool(integrity) and all(x["status"] == "ok" for x in integrity)
    high_confidence = [x for x in findings if x["confidence"] == "high" and x["severity_signal"] != "info"]
    status = ("integrity_failed" if not integrity_ok else
              "manual_review_required" if findings else
              "no_obvious_static_flags_not_approved")
    metadata["security_status"] = status
    metadata["last_static_scan_at"] = now()
    metadata["static_scan_finding_count"] = len(findings)
    metadata["high_confidence_signals"] = len(high_confidence)
    source_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "repository": metadata.get("repository"),
        "skill_name": metadata.get("skill_name"),
        "skill_path": metadata.get("source_skill_path"),
        "commit_sha": metadata.get("commit_sha"),
        "integrity_ok": integrity_ok,
        "integrity": integrity,
        "security_status": status,
        "high_confidence_signals": len(high_confidence),
        "finding_count": len(findings),
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
