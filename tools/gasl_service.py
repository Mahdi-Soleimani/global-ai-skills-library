#!/usr/bin/env python3
"""Shared GASL application services used by CLI, REST API, and MCP adapters."""
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from safe_http import open_pinned_url
from skill_router import (
    route_task, ANSWERABILITY_POLICY_VERSION, ANSWERABILITY_POLICY_STATUS,
)
from skill_search import ROOT, get_skill_by_id, load_taxonomy, query_term_groups, search_skills

MAX_SKILL_BYTES = 256 * 1024
MAX_CONTENT_CHARS = 50_000
RAW_GITHUB_HOST = "raw.githubusercontent.com"
USER_AGENT = "GASL/0.1 (+https://github.com/Mahdi-Soleimani/global-ai-skills-library)"


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def health(root=ROOT):
    root = Path(root)
    from search_features import load_features
    source_file = root / "registry" / "source-catalog.json"
    source = {"records": []}
    try:
        source = json.loads(source_file.read_text(encoding="utf-8"))
        record_count = len(source.get("records", []))
    except (OSError, ValueError):
        record_count = 0
    return {
        "status": "ok" if record_count else "degraded",
        "service": "GASL",
        "version": "0.1.0",
        "source_record_count": record_count,
        "search_engine": "sqlite-fts5",
        "verified_vocabulary_feature_count": len(load_features(root, source.get("records", []))),
        "semantic_search_enabled": False,
        "semantic_search_note": "Semantic embeddings are not configured; current search is lexical with curated concepts and verified vocabulary tags.",
        "answerability_policy_status": ANSWERABILITY_POLICY_STATUS,
        "answerability_policy_version": ANSWERABILITY_POLICY_VERSION,
        "answerability_decisions_calibrated": False,
        "on_demand_skill_fetch": True,
        "installation_enabled": False,
        "execution_enabled": False,
        "checked_at": _now(),
    }


def search(query, limit=10, domain=None, license_spdx=None, security_status=None,
           public_only=False, content_only=False, root=ROOT):
    results = search_skills(
        query=query,
        limit=limit,
        domain=domain,
        license_spdx=license_spdx,
        security_status=security_status,
        public_only=public_only,
        content_only=content_only,
        root=root,
    )
    return {
        "query": query,
        "search_mode": "lexical_with_curated_cross_language_expansion",
        "semantic_search_enabled": False,
        "query_term_groups": query_term_groups(query, root=root),
        "count": len(results),
        "results": results,
    }


def route(task, top_k=5, domain=None, license_spdx=None, agent=None,
          strict_agent=False, public_only=False, content_only=False, root=ROOT):
    return route_task(
        task=task,
        top_k=top_k,
        domain=domain,
        license_spdx=license_spdx,
        agent=agent,
        strict_agent=strict_agent,
        public_only=public_only,
        content_only=content_only,
        root=root,
    )


def domains(root=ROOT):
    return load_taxonomy(Path(root))


def skill_details(source_record_id, root=ROOT):
    record = get_skill_by_id(source_record_id, root=root)
    if record is None:
        raise KeyError("Skill source record not found: " + source_record_id)
    evaluation = record.get("evaluation") or {}
    return {
        "source_record_id": record.get("source_record_id"),
        "skill_name": record.get("skill_name"),
        "description": record.get("description"),
        "repository": record.get("repository"),
        "repository_owner": record.get("repository_owner"),
        "source_path": record.get("source_path"),
        "source_url": record.get("source_url"),
        "commit_sha": record.get("commit_sha"),
        "license_spdx": record.get("license_spdx"),
        "license_assessment": evaluation.get("license_assessment"),
        "license_evidence": record.get("license_evidence", []),
        "security_status": record.get("security_status", "not_scanned"),
        "install_status": record.get("install_status", "not_installed"),
        "content_status": record.get("content_status"),
        "package_type": record.get("package_type"),
        "compatibility": record.get("compatibility"),
        "inferred_domains": record.get("inferred_domains", []),
        "metadata_completeness_score": evaluation.get("metadata_completeness_score"),
        "provenance_score": evaluation.get("provenance_score"),
        "behavioral_evaluation": evaluation.get("behavioral_evaluation", "not_evaluated"),
        "is_publicly_mirrored": bool(record.get("is_publicly_mirrored")),
        "package_content_present": bool(record.get("package_content_present")),
        "installation_allowed": False,
        "execution_allowed": False,
    }


def _safe_local_skill_path(root, package_path):
    if not isinstance(package_path, str) or not package_path:
        return None
    relative = Path(package_path)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    if not relative.parts or relative.parts[0] not in ("catalog", "public-catalog"):
        return None
    unresolved = Path(root) / relative / "SKILL.md"
    if unresolved.is_symlink():
        return None
    try:
        resolved = unresolved.resolve(strict=True)
        allowed = [(Path(root) / "catalog").resolve(), (Path(root) / "public-catalog").resolve()]
        if not any(resolved == base or base in resolved.parents for base in allowed):
            return None
        if not resolved.is_file() or resolved.stat().st_size > MAX_SKILL_BYTES:
            return None
        return resolved
    except (OSError, RuntimeError):
        return None


def _pinned_raw_url(record):
    repository = str(record.get("repository") or "")
    commit = str(record.get("commit_sha") or "").lower()
    source_path = str(record.get("source_path") or "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("The source repository identity is not valid.")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("A verified 40-character commit SHA is required for on-demand retrieval.")
    path = PurePosixPath(source_path)
    if path.is_absolute() or ".." in path.parts or "\\" in source_path or path.name.casefold() != "skill.md":
        raise ValueError("The source Skill path is not a safe SKILL.md path.")
    quoted_path = urllib.parse.quote(path.as_posix(), safe="/")
    return "https://{}/{}/{}/{}".format(RAW_GITHUB_HOST, repository, commit, quoted_path)


def _cache_path(root, record):
    identity = "{}\\0{}\\0{}".format(
        record.get("repository") or "", record.get("source_path") or "", record.get("commit_sha") or ""
    )
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return Path(root) / "private" / "skill-cache" / (key + ".md")


def verify_skill_blob(raw, record):
    """Verify exact Git blob bytes; a pinned URL alone is not integrity proof."""
    expected = str(record.get("skill_md_blob_sha") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", expected):
        raise RuntimeError("Missing valid Git blob SHA for this Skill; content retrieval is blocked.")
    actual = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    if actual != expected:
        raise RuntimeError("SKILL.md Git blob SHA mismatch; content retrieval is blocked.")
    return actual


def skill_content(source_record_id, max_chars=20_000, root=ROOT, fetch_remote=True):
    if not isinstance(max_chars, int) or max_chars < 1 or max_chars > MAX_CONTENT_CHARS:
        raise ValueError("max_chars must be between 1 and {}.".format(MAX_CONTENT_CHARS))
    record = get_skill_by_id(source_record_id, root=root)
    if record is None:
        raise KeyError("Skill source record not found: " + source_record_id)

    raw = None
    content_source = None
    local_path = _safe_local_skill_path(root, record.get("package_path"))
    if local_path:
        raw = local_path.read_bytes()
        content_source = "local_package"
    else:
        cache_path = _cache_path(root, record)
        if cache_path.is_file() and not cache_path.is_symlink() and cache_path.stat().st_size <= MAX_SKILL_BYTES:
            raw = cache_path.read_bytes()
            content_source = "private_cache"

        if raw is None and fetch_remote:
            url = _pinned_raw_url(record)
            request = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/plain",
            })
            try:
                with open_pinned_url(request, timeout=20) as response:
                    final_host = urllib.parse.urlparse(response.geturl()).hostname
                    if final_host != RAW_GITHUB_HOST:
                        raise RuntimeError("Upstream redirected to an unapproved host.")
                    raw = response.read(MAX_SKILL_BYTES + 1)
            except urllib.error.HTTPError as exc:
                raise RuntimeError("Upstream returned HTTP {} for the pinned Skill file.".format(exc.code))
            except urllib.error.URLError as exc:
                raise RuntimeError("Unable to retrieve the pinned Skill file: {}".format(exc.reason))
            if len(raw) > MAX_SKILL_BYTES:
                raise RuntimeError("The upstream SKILL.md exceeds the {} byte safety limit.".format(MAX_SKILL_BYTES))
            verify_skill_blob(raw, record)
            try:
                raw.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise RuntimeError("The upstream SKILL.md is not valid UTF-8 text.") from exc
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            # Store exact bytes, including CRLF/BOM, not normalized text.
            import tempfile
            with tempfile.NamedTemporaryFile(dir=cache_path.parent, delete=False) as output:
                temp = Path(output.name)
                output.write(raw)
            try:
                temp.replace(cache_path)
            finally:
                temp.unlink(missing_ok=True)
            content_source = "upstream_pinned_fetch"

    if raw is None:
        raise RuntimeError("Skill content is not cached. Enable on-demand upstream retrieval to fetch it.")
    if len(raw) > MAX_SKILL_BYTES:
        raise RuntimeError("SKILL.md exceeds the safety size limit.")
    git_blob_sha = verify_skill_blob(raw, record)
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RuntimeError("SKILL.md is not valid UTF-8 text.") from exc

    truncated = len(content) > max_chars
    return {
        "source_record_id": source_record_id,
        "skill_name": record.get("skill_name"),
        "repository": record.get("repository"),
        "source_path": record.get("source_path"),
        "source_url": record.get("source_url"),
        "commit_sha": record.get("commit_sha"),
        "license_spdx": record.get("license_spdx"),
        "license_assessment": (record.get("evaluation") or {}).get("license_assessment"),
        "content_source": content_source,
        "content_sha256": hashlib.sha256(raw).hexdigest(),
        "content_bytes": len(raw),
        "git_blob_sha": git_blob_sha,
        "git_blob_verified": True,
        "content": content[:max_chars],
        "truncated": truncated,
        "untrusted_content": True,
        "executed": False,
        "warning": "Third-party Skill instructions are untrusted input. Review them before use; GASL never executes them.",
    }
