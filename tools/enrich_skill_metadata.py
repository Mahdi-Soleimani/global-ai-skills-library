#!/usr/bin/env python3
"""Fetch only pinned SKILL.md files and retain compact search metadata locally."""
import argparse
import hashlib
import json
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_registry import parse_frontmatter
from gasl_service import MAX_SKILL_BYTES, USER_AGENT, _pinned_raw_url, _safe_local_skill_path, verify_skill_blob
from safe_http import open_pinned_url
from skill_search import enrich_records

CACHE_PATH = ROOT / "private" / "skill-metadata-cache.json"
CACHE_VERSION = "1.0.0"
MAX_SEARCH_CHARS = 1800
SAVE_EVERY = 25
FETCH_ATTEMPTS = 3
FETCH_TIMEOUT_SECONDS = 25


class OversizedSkillError(RuntimeError):
    """A source Skill exceeded the bounded metadata-fetch size limit."""



def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_cache(path):
    if not path.exists():
        return {"schema_version": CACHE_VERSION, "records": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != CACHE_VERSION or not isinstance(data.get("records"), dict):
        raise ValueError("Unsupported or invalid private metadata cache schema.")
    return data


def body_without_frontmatter(text):
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].strip()
    return text.strip()


def compact_tags(value):
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()][:20]
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()][:20]
    return []


def parse_search_metadata(text, record, source_sha256, source_kind):
    frontmatter = parse_frontmatter(text)
    name = str(frontmatter.get("name") or record.get("skill_name") or "").strip()
    description = frontmatter.get("description")
    if not isinstance(description, str):
        description = record.get("description")
    description = description.strip() if isinstance(description, str) else ""
    compatibility = frontmatter.get("compatibility") or record.get("compatibility")
    tags = compact_tags(frontmatter.get("tags") or frontmatter.get("keywords"))
    body = body_without_frontmatter(text)
    parts = ["Skill: " + name]
    if description:
        parts.append("Description: " + description)
    if compatibility:
        parts.append("Compatibility: " + str(compatibility))
    if tags:
        parts.append("Tags: " + ", ".join(tags))
    if body:
        parts.append(body)
    search_text = "\n".join(parts)[:MAX_SEARCH_CHARS]
    return {
        "source_record_id": record.get("source_record_id"),
        "repository": record.get("repository"),
        "source_path": record.get("source_path"),
        "source_url": record.get("source_url"),
        "commit_sha": record.get("commit_sha"),
        "skill_name": name,
        "description": description or None,
        "compatibility": str(compatibility).strip() if compatibility else None,
        "tags": tags,
        "search_text": search_text,
        "source_content_sha256": source_sha256,
        "source_kind": source_kind,
        "fetch_status": "ok",
        "updated_at": now(),
    }


def fetch_pinned_bytes(url):
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/plain",
    })
    last_error = None
    for attempt in range(FETCH_ATTEMPTS):
        try:
            with open_pinned_url(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
                final_host = urllib.parse.urlparse(response.geturl()).hostname
                if final_host != "raw.githubusercontent.com":
                    raise RuntimeError("Upstream redirected to an unapproved host.")
                raw = response.read(MAX_SKILL_BYTES + 1)
            if len(raw) > MAX_SKILL_BYTES:
                raise OversizedSkillError("SKILL.md exceeded the safety size limit.")
            return raw
        except urllib.error.HTTPError as exc:
            if exc.code not in (408, 425, 429, 500, 502, 503, 504):
                raise RuntimeError("Upstream returned HTTP {}.".format(exc.code))
            last_error = "HTTP {}".format(exc.code)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            last_error = "Network error: {}".format(reason)
        if attempt + 1 < FETCH_ATTEMPTS:
            time.sleep(min(0.8 * (2 ** attempt), 5.0))
    raise RuntimeError("Pinned source fetch failed after {} attempts: {}".format(
        FETCH_ATTEMPTS, last_error
    ))


def fetch_record(record, root):
    local_path = _safe_local_skill_path(root, record.get("package_path"))
    if local_path:
        raw = local_path.read_bytes()
        source_kind = "local_package"
    else:
        raw = fetch_pinned_bytes(_pinned_raw_url(record))
        source_kind = "pinned_upstream_fetch"
    if len(raw) > MAX_SKILL_BYTES:
        raise OversizedSkillError("SKILL.md exceeded the safety size limit.")
    blob = verify_skill_blob(raw, record)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RuntimeError("Pinned SKILL.md is not valid UTF-8 text.") from exc
    result = parse_search_metadata(text, record, hashlib.sha256(raw).hexdigest(), source_kind)
    result["git_blob_sha"] = blob
    result["git_blob_verified"] = True
    return result


def save_cache(path, cache):
    path.parent.mkdir(parents=True, exist_ok=True)
    cache["generated_at"] = now()
    cache["record_count"] = len(cache["records"])
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")) + "\n",
                    encoding="utf-8")
    temp.replace(path)


def round_robin_by_repository(records):
    """Interleave repositories so a bounded batch does not overfit one large source."""
    grouped = {}
    for record in records:
        grouped.setdefault(record.get("repository") or "", []).append(record)
    ordered = []
    max_group_size = max((len(items) for items in grouped.values()), default=0)
    for index in range(max_group_size):
        for items in grouped.values():
            if index < len(items):
                ordered.append(items[index])
    return ordered


def select_pending_records(records, cached, refresh=False, retry_errors=False):
    pending = []
    cache_hits = 0
    skipped = 0
    for record in records:
        record_id = record.get("source_record_id")
        old = cached.get(record_id)
        same_pin = bool(
            old
            and old.get("repository") == record.get("repository")
            and old.get("source_path") == record.get("source_path")
            and old.get("commit_sha") == record.get("commit_sha")
        )
        if not refresh and same_pin and old.get("fetch_status") in ("ok", "skipped"):
            cache_hits += 1
            continue
        if retry_errors:
            if not (same_pin and old and old.get("fetch_status") == "error"):
                skipped += 1
                continue
        elif not refresh and same_pin and old and old.get("fetch_status") == "error":
            skipped += 1
            continue
        pending.append(record)
    return pending, cache_hits, skipped


def enrich(root=ROOT, limit=None, workers=4, refresh=False, retry_errors=False):
    root = Path(root)
    records = enrich_records(root)
    cache_path = root / "private" / "skill-metadata-cache.json"
    cache = read_cache(cache_path) if cache_path.exists() else {
        "schema_version": CACHE_VERSION, "records": {},
    }
    cached = cache["records"]
    pending, cache_hits, skipped = select_pending_records(
        records, cached, refresh=refresh, retry_errors=retry_errors
    )
    pending = round_robin_by_repository(pending)
    if limit is not None:
        pending = pending[:max(0, int(limit))]

    lock = threading.Lock()
    counters = {
        "success": 0,
        "error": 0,
        "cache_hits": cache_hits,
        "skipped_unprocessed": skipped,
        "skipped_safety_limit": 0,
    }
    completed = 0

    def work(record):
        try:
            return record["source_record_id"], fetch_record(record, root), None
        except OversizedSkillError as exc:
            return record["source_record_id"], {
                "source_record_id": record.get("source_record_id"),
                "repository": record.get("repository"),
                "source_path": record.get("source_path"),
                "source_url": record.get("source_url"),
                "commit_sha": record.get("commit_sha"),
                "skill_name": record.get("skill_name"),
                "description": record.get("description"),
                "search_text": "Skill: " + str(record.get("skill_name") or ""),
                "fetch_status": "skipped",
                "skip_reason": "safety_size_limit",
                "error": str(exc)[:300],
                "updated_at": now(),
            }, "skipped"
        except Exception as exc:
            return record["source_record_id"], {
                "source_record_id": record.get("source_record_id"),
                "repository": record.get("repository"),
                "source_path": record.get("source_path"),
                "source_url": record.get("source_url"),
                "commit_sha": record.get("commit_sha"),
                "skill_name": record.get("skill_name"),
                "description": record.get("description"),
                "search_text": "Skill: " + str(record.get("skill_name") or ""),
                "fetch_status": "error",
                "error": str(exc)[:300],
                "updated_at": now(),
            }, exc

    print("Source records: {}".format(len(records)), flush=True)
    print("Cached and unchanged: {}".format(counters["cache_hits"]), flush=True)
    print("Skipped (not selected): {}".format(counters["skipped_unprocessed"]), flush=True)
    print("To enrich: {} (workers={})".format(len(pending), workers), flush=True)
    with ThreadPoolExecutor(max_workers=max(1, min(int(workers), 8))) as pool:
        futures = [pool.submit(work, record) for record in pending]
        for future in as_completed(futures):
            record_id, result, error = future.result()
            with lock:
                cached[record_id] = result
                if error == "skipped":
                    counters["skipped_safety_limit"] += 1
                elif error:
                    counters["error"] += 1
                else:
                    counters["success"] += 1
                completed += 1
                if completed % SAVE_EVERY == 0:
                    save_cache(cache_path, cache)
                    print("Checkpoint {}/{} — success={}, error={}, skipped={}".format(
                        completed, len(pending), counters["success"], counters["error"],
                        counters["skipped_safety_limit"]), flush=True)
    save_cache(cache_path, cache)
    descriptions = sum(bool(x.get("description")) for x in cached.values())
    summary = {
        "source_record_count": len(records),
        "cache_record_count": len(cached),
        "cache_hits": counters["cache_hits"],
        "skipped_unprocessed": counters["skipped_unprocessed"],
        "fetched_successfully": counters["success"],
        "fetch_errors": counters["error"],
        "skipped_safety_limit": sum(1 for item in cached.values()
                                    if item.get("fetch_status") == "skipped"
                                    and item.get("skip_reason") == "safety_size_limit"),
        "skipped_safety_limit_this_run": counters["skipped_safety_limit"],
        "descriptions_available": descriptions,
        "search_text_available": sum(bool(x.get("search_text")) for x in cached.values()),
        "cache_path": str(cache_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description="Enrich local search metadata from pinned SKILL.md files only.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--retry-errors", action="store_true")
    args = parser.parse_args()
    enrich(limit=args.limit, workers=args.workers, refresh=args.refresh, retry_errors=args.retry_errors)


if __name__ == "__main__":
    main()
