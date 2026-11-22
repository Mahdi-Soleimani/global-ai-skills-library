#!/usr/bin/env python3
"""SQLite FTS5 search over attributed Skill source records. No Skill code is executed."""
import argparse
from contextlib import closing
import hashlib
import json
import os
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from skill_evaluation import evaluate_record, identity
from path_rules import is_test_fixture_path

ROOT = Path(__file__).resolve().parents[1]
INDEX_VERSION = "1.2.2"
DB_NAME = "gasl-search.sqlite3"
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
STOP_WORDS = {
    "a", "an", "the", "and", "or", "for", "to", "of", "in", "on", "with",
    "by", "from", "about", "how", "what", "where", "when", "why", "can",
    "could", "would", "should", "please", "me", "my", "our", "we", "i",
    "you", "your", "is", "are", "was", "were", "be", "do", "does", "did", "not", "only",
    "it", "this", "that", "these", "those", "as", "at", "into",
    "و", "از", "به", "در", "با", "برای", "یک", "این", "آن", "را", "می",
    "کن", "چطور", "چگونه", "من", "ما", "شما", "میخواهم", "میخوام", "نمی", "خواهم", "یا", "های", "بر", "اساس", "بررسی", "باید", "پوشش", "شوند", "نیز", "هم", "است", "هست", "شود", "شده",
}

NEGATION_ENTITY_TERMS = {
    "twilio", "sms", "webhook", "webhooks", "pinecone", "databricks",
    "azure", "aks", "aws", "eks", "gcp", "google", "microsoft",
    "apple", "hig", "qdrant", "pgvector", "postgres", "postgresql",
    "mysql", "mongodb", "redis", "weaviate", "chroma", "supabase",
    "firebase", "vercel", "netlify", "stripe", "paypal", "zapier", "make",
    "n8n", "langchain", "langgraph", "openai", "anthropic", "ollama",
    "pytorch", "tensorflow", "huggingface", "android", "ios", "windows",
    "linux", "macos", "telegram", "whatsapp", "slack", "discord", "zoom",
    "salesforce", "hubspot", "wordpress", "shopify", "react", "nextjs",
    "fastapi", "django", "flask", "spring", "kubernetes", "terraform",
    "docker", "helm", "airflow", "kafka", "spark", "dbt", "api", "cloudflare",
}
NEGATED_ACTION_RE = re.compile(
    r"\b(?:do\s+not|don't|dont|never|avoid|exclude|without)\s+"
    r"(?:(?:use|recommend|return|suggest|choose|select|include|surface|provide|prefer)\s+)?"
    r"(?P<clause>[^.;!?]+)", re.IGNORECASE
)
NEGATED_NOT_RE = re.compile(
    r"\bnot\s+(?P<clause>[A-Za-z0-9][A-Za-z0-9.+#_-]*(?:\s+[A-Za-z0-9][A-Za-z0-9.+#_-]*){0,3})",
    re.IGNORECASE
)
PERSIAN_SUFFIX_NEGATION_RE = re.compile(
    r"(?P<prefix>.+?)(?P<marker>\s+نمی(?:‌|\s*)خواهم|\s+نمی(?:‌|\s*)خوام)",
    re.IGNORECASE
)
PERSIAN_WITHOUT_RE = re.compile(r"بدون\s+(?P<clause>[^،,؛;.!؟?]+)")
PERSIAN_USE_NOT_RE = re.compile(r"از\s+(?P<clause>.+?)\s+استفاده\s+نکن")


def _negated_entity_tokens(value):
    """Extract named technologies/providers from a negated clause, not generic prose."""
    found = set()
    for raw in TOKEN_RE.findall(str(value or "")):
        token = normalize_text(raw)
        if not token:
            continue
        if token in NEGATION_ENTITY_TERMS or raw.isupper() or (
            len(raw) > 1 and raw[0].isupper() and raw[1:].islower()
        ):
            found.add(token)
    return found



def strip_query_exclusions(query):
    """Remove explicit negative clauses from positive retrieval terms and return excluded entities.

    This deliberately handles named technology/provider exclusions, not arbitrary natural-language
    negation or logical reasoning. Generic words in a negated sentence are not treated as entities.
    """
    positive = str(query or "")
    excluded = set()
    spans = []

    for pattern in (NEGATED_ACTION_RE,):
        for match in pattern.finditer(positive):
            terms = _negated_entity_tokens(match.group("clause"))
            if terms:
                excluded.update(terms)
                spans.append(match.span())

    for match in NEGATED_NOT_RE.finditer(positive):
        terms = _negated_entity_tokens(match.group("clause"))
        if terms:
            excluded.update(terms)
            spans.append(match.span())

    for pattern in (PERSIAN_WITHOUT_RE, PERSIAN_USE_NOT_RE):
        for match in pattern.finditer(positive):
            terms = _negated_entity_tokens(match.group("clause"))
            if terms:
                excluded.update(terms)
                spans.append(match.span())

    for match in PERSIAN_SUFFIX_NEGATION_RE.finditer(positive):
        prefix = match.group("prefix")
        boundary = max((prefix.rfind(mark) for mark in (";", "؛", ".", "!", "؟", "?", "،", ",")), default=-1)
        local_start = boundary + 1
        local_prefix = prefix[local_start:]
        cues = list(re.finditer(r"(?:راهکار|سرویس|فناوری|ابزار|پلتفرم|گزینه)\s+", local_prefix))
        if cues:
            local_start += cues[-1].start()
        elif boundary < 0:
            words = list(re.finditer(r"\S+", local_prefix))
            if len(words) > 5:
                local_start += words[-5].start()
        terms = _negated_entity_tokens(prefix[local_start:])
        if terms:
            excluded.update(terms)
            spans.append((match.start("prefix") + local_start, match.end()))

    for start, end in sorted(spans, reverse=True):
        positive = positive[:start] + " " + positive[end:]
    return re.sub(r"\s+", " ", positive).strip(" ,،;；") , excluded



def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_text(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    value = value.replace("ي", "ی").replace("ك", "ک").replace("ـ", "")
    value = value.replace(chr(0x200c), " ").replace(chr(0x200d), "")
    value = "".join(ch for ch in value if unicodedata.category(ch) not in ("Mn", "Cf"))
    value = re.sub(r"[_./\\\\-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def tokenize(value):
    return TOKEN_RE.findall(normalize_text(value))


def query_tokens(value):
    raw = list(dict.fromkeys(tokenize(value)))
    filtered = [token for token in raw if token not in STOP_WORDS and len(token) > 1]
    return filtered or [token for token in raw if token not in STOP_WORDS]


def phrase_match_text(value):
    """Normalize punctuation to spaces so phrase expansions survive commas and brackets."""
    return re.sub(r"[^\w\s]", " ", normalize_text(value), flags=re.UNICODE)


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def query_term_group_specs(query, root=ROOT):
    """Return concept groups with phrase-level alternatives preserved.

    Each alternative is a phrase whose tokens must match together. Keeping
    phrases intact prevents a generic word such as "plugin" from satisfying a
    more specific concept such as "WordPress plugin".
    """
    root = Path(root)
    positive_query, _ = strip_query_exclusions(query)
    original = query_tokens(positive_query)
    if not original:
        return []

    config = read_json(root / "config" / "taxonomy.json", {})
    rules = config.get("query_expansions", [])
    normalized_query = phrase_match_text(positive_query)
    specs = []
    consumed = set()

    candidates = []
    for rule in rules:
        for phrase in rule.get("terms", []):
            normalized_phrase = phrase_match_text(phrase)
            if normalized_phrase and (" " + normalized_phrase + " ") in (" " + normalized_query + " "):
                candidates.append((len(normalized_phrase), normalized_phrase, rule.get("expand", []), rule.get("weight", 1.0)))
    candidates.sort(key=lambda item: item[0], reverse=True)

    for _, phrase, alternatives, group_weight in candidates:
        phrase_tokens = query_tokens(phrase)
        if not phrase_tokens or set(phrase_tokens).issubset(consumed):
            continue
        phrase_alternatives = [phrase_tokens]
        for alternative in alternatives:
            tokens = query_tokens(alternative)
            if tokens:
                phrase_alternatives.append(tokens)
        unique_alternatives = []
        seen_alternatives = set()
        for alternative in phrase_alternatives:
            key = tuple(alternative)
            if key not in seen_alternatives:
                unique_alternatives.append(alternative)
                seen_alternatives.add(key)
        terms = list(dict.fromkeys(token for alternative in unique_alternatives for token in alternative))
        specs.append({
            "label": phrase,
            "terms": terms,
            "alternatives": unique_alternatives,
            "weight": max(0.25, min(float(group_weight), 3.0)),
        })
        consumed.update(phrase_tokens)

    for token in original:
        if token not in consumed:
            specs.append({
                "label": token,
                "terms": [token],
                "alternatives": [[token]],
                "weight": 1.0,
            })
    return specs


def query_term_groups(query, root=ROOT):
    """Return flattened FTS terms while preserving phrase alternatives for ranking."""
    return [spec["terms"] for spec in query_term_group_specs(query, root=root)]


def file_fingerprint(root):
    files = [
        root / "registry" / "source-catalog.json",
        root / "registry" / "search-features.json",
        root / "registry" / "skill-evaluations.json",
        root / "registry" / "skills.json",
        root / "public-catalog" / "index.json",
        root / "config" / "taxonomy.json",
        root / "private" / "skill-metadata-cache.json",
    ]
    digest = hashlib.sha256()
    for path in files:
        rel = str(path.relative_to(root))
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        if path.is_file():
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
        else:
            digest.update(b"<missing>")
        digest.update(b"\0")
    return digest.hexdigest()


def load_taxonomy(root):
    data = read_json(root / "config" / "taxonomy.json", {"domains": []})
    return data.get("domains", [])


def infer_domains(record, taxonomy):
    text = normalize_text(" ".join(str(record.get(key) or "") for key in (
        "skill_name", "description", "search_text", "source_path", "repository", "compatibility"
    )))
    tokens = set(tokenize(text))
    found = []
    for domain in taxonomy:
        evidence = []
        for keyword in domain.get("keywords", []):
            term = normalize_text(keyword)
            if not term:
                continue
            if " " in term:
                matched = term in text
            else:
                matched = term in tokens
            if matched:
                evidence.append(keyword)
        if evidence:
            found.append({"id": domain["id"], "label": domain.get("label", domain["id"]),
                          "evidence": evidence[:8]})
    return found


def _map_by_identity(records, path_field):
    result = {}
    for item in records:
        key = (
            str(item.get("repository") or "").casefold(),
            item.get(path_field),
            item.get("commit_sha"),
        )
        if all(key):
            result[key] = item
    return result


def enrich_records(root):
    source = read_json(root / "registry" / "source-catalog.json", {"records": []})
    local = read_json(root / "registry" / "skills.json", {"records": []}).get("records", [])
    public = read_json(root / "public-catalog" / "index.json", {"packages": {}}).get("packages", {})
    local_by_key = _map_by_identity(local, "source_skill_path")
    public_by_key = _map_by_identity(list(public.values()), "source_skill_path")
    taxonomy = load_taxonomy(root)
    metadata_cache = read_json(
        root / "private" / "skill-metadata-cache.json", {"records": {}}
    ).get("records", {})
    from search_features import load_features
    features = load_features(root, source.get("records", []))
    records = []
    for original in source.get("records", []):
        record = dict(original)
        record["feature_terms"] = features.get(record.get("source_record_id"), {}).get("terms", [])
        key = identity(record)
        local_item = local_by_key.get(key, {})
        public_item = public_by_key.get(key, {})
        for field in (
            "skill_id", "compatibility", "frontmatter_valid", "package_type",
            "package_path", "package_complete", "package_content_present",
            "package_file_count", "package_bytes", "security_finding_count",
            "high_confidence_signals", "license_frontmatter", "install_eligibility",
            "skill_md_sha256_raw", "skill_md_sha256_normalized"
        ):
            if _has(local_item.get(field)):
                record[field] = local_item[field]
        for field in ("skill_name", "description", "security_status", "install_status",
                      "license_spdx", "source_url", "repository_url"):
            if _has(local_item.get(field)):
                record[field] = local_item[field]
            elif _has(public_item.get(field)):
                record[field] = public_item[field]

        if public_item:
            record["is_publicly_mirrored"] = True
            record["content_status"] = "mirrored_publicly_with_attribution"
            record["public_mirror_status"] = "published_publicly_with_attribution"
            record["license_evidence"] = public_item.get("license_evidence", [])
            record["package_path"] = public_item.get("package_path")
            record["package_file_count"] = public_item.get("file_count")
            record["package_bytes"] = public_item.get("package_bytes")
        else:
            record["is_publicly_mirrored"] = False
        if local_item and local_item.get("package_content_present", True):
            record["package_content_present"] = True
            if record.get("content_status") == "not_downloaded_reference_record":
                record["content_status"] = "downloaded_and_hashed_locally"

        cached_metadata = metadata_cache.get(record.get("source_record_id"), {})
        if (
            cached_metadata
            and cached_metadata.get("repository") == record.get("repository")
            and cached_metadata.get("source_path") == record.get("source_path")
            and cached_metadata.get("commit_sha") == record.get("commit_sha")
        ):
            for field in ("skill_name", "description", "compatibility"):
                if _has(cached_metadata.get(field)):
                    record[field] = cached_metadata[field]
            if _has(cached_metadata.get("search_text")):
                record["search_text"] = cached_metadata["search_text"]
            record["metadata_cache_status"] = cached_metadata.get("fetch_status", "unknown")
            record["metadata_source_content_sha256"] = cached_metadata.get("source_content_sha256")

        if record["feature_terms"]:
            record["search_text"] = " ".join((str(record.get("search_text") or ""),
                                              " ".join(record["feature_terms"]))).strip()

        if not record.get("package_type"):
            path = record.get("source_path") or ""
            record["package_type"] = "test_fixture" if is_test_fixture_path(path) else "skill_candidate"
        if not record.get("security_status"):
            record["security_status"] = "not_scanned"
        if not record.get("install_status"):
            record["install_status"] = "not_installed"

        # Recompute from the enriched record so local-only metadata is reflected
        # in the local search index without leaking it into the public evaluation file.
        evaluation = evaluate_record(record, public_item)
        record["_evaluation"] = evaluation
        record["_domains"] = infer_domains(record, taxonomy)
        records.append(record)
    return records


def _has(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def build_index(root=ROOT, force=True):
    root = Path(root)
    source_path = root / "registry" / "source-catalog.json"
    if not source_path.exists():
        raise FileNotFoundError("Missing registry/source-catalog.json; run discovery/source catalog first.")
    records = enrich_records(root)
    taxonomy = load_taxonomy(root)
    taxonomy_by_id = {x["id"]: x for x in taxonomy}
    db_path = root / "registry" / DB_NAME
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = db_path.with_name(db_path.name + ".tmp")
    if temp_path.exists():
        temp_path.unlink()

    connection = sqlite3.connect(str(temp_path))
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript("""
            CREATE TABLE index_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE skills (
                source_record_id TEXT PRIMARY KEY,
                skill_name TEXT NOT NULL,
                description TEXT NOT NULL,
                search_text TEXT NOT NULL,
                repository TEXT NOT NULL,
                repository_owner TEXT,
                source_path TEXT NOT NULL,
                source_url TEXT,
                commit_sha TEXT,
                skill_md_blob_sha TEXT,
                license_spdx TEXT,
                license_assessment TEXT,
                license_status TEXT,
                content_status TEXT,
                security_status TEXT,
                install_status TEXT,
                package_type TEXT,
                compatibility TEXT,
                domains_json TEXT NOT NULL,
                domains_text TEXT NOT NULL,
                research_leads TEXT NOT NULL,
                metadata_completeness_score INTEGER,
                provenance_score INTEGER,
                evaluation_status TEXT,
                is_publicly_mirrored INTEGER NOT NULL,
                is_test_fixture INTEGER NOT NULL,
                metadata_json TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE skills_fts USING fts5(
                skill_name,
                description,
                repository,
                source_path,
                compatibility,
                domains,
                research_leads,
                search_text,
                tokenize='unicode61 remove_diacritics 2'
            );
        """)
        for record in records:
            evaluation = record["_evaluation"]
            domains = record["_domains"]
            domain_ids = [x["id"] for x in domains]
            domain_terms = []
            for domain in domains:
                source_domain = taxonomy_by_id.get(domain["id"], {})
                domain_terms.extend([domain["id"], domain.get("label", "")])
                domain_terms.extend(domain.get("evidence", []))
            domain_text = "|" + "|".join(domain_ids) + "| " + " ".join(domain_terms)
            research_leads = record.get("research_leads") or []
            name = str(record.get("skill_name") or "")
            description = str(record.get("description") or "")
            repository = str(record.get("repository") or "")
            source_path_value = str(record.get("source_path") or "")
            compatibility = str(record.get("compatibility") or "")
            search_text = str(record.get("search_text") or " ".join(
                x for x in (name, description, compatibility, source_path_value, repository) if x
            ))
            metadata = {k: v for k, v in record.items()
                        if not k.startswith("_") and k != "search_text"}
            metadata["inferred_domains"] = domains
            metadata["evaluation"] = evaluation
            cursor = connection.execute("""
                INSERT INTO skills (
                    source_record_id, skill_name, description, search_text, repository, repository_owner,
                    source_path, source_url, commit_sha, skill_md_blob_sha, license_spdx,
                    license_assessment, license_status, content_status, security_status,
                    install_status, package_type, compatibility, domains_json, domains_text,
                    research_leads, metadata_completeness_score, provenance_score,
                    evaluation_status, is_publicly_mirrored, is_test_fixture, metadata_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                record.get("source_record_id"), name, description, search_text, repository,
                record.get("repository_owner"), source_path_value, record.get("source_url"),
                record.get("commit_sha"), record.get("skill_md_blob_sha"),
                record.get("license_spdx"), record.get("license_assessment"),
                evaluation.get("license_assessment"), record.get("content_status"),
                record.get("security_status"), record.get("install_status"),
                record.get("package_type"), compatibility,
                json.dumps(domains, ensure_ascii=False), domain_text,
                json.dumps(research_leads, ensure_ascii=False),
                evaluation.get("metadata_completeness_score"), evaluation.get("provenance_score"),
                evaluation.get("evaluation_status"), int(bool(record.get("is_publicly_mirrored"))),
                int(record.get("package_type") == "test_fixture"),
                json.dumps(metadata, ensure_ascii=False),
            ))
            connection.execute("""
                INSERT INTO skills_fts (
                    rowid, skill_name, description, repository, source_path,
                    compatibility, domains, research_leads, search_text
                ) VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                cursor.lastrowid, name, description, repository, source_path_value,
                compatibility, domain_text,
                " ".join(research_leads), search_text,
            ))

        meta = {
            "schema_version": INDEX_VERSION,
            "built_at": now(),
            "input_fingerprint": file_fingerprint(root),
            "record_count": str(len(records)),
            "fts5": "true",
        }
        connection.executemany("INSERT INTO index_meta(key,value) VALUES(?,?)", meta.items())
        connection.commit()
        connection.execute("PRAGMA optimize")
    finally:
        connection.close()
    os.replace(str(temp_path), str(db_path))
    return {"database": str(db_path), "record_count": len(records),
            "schema_version": INDEX_VERSION, "built_at": meta["built_at"]}


def ensure_index(root=ROOT):
    root = Path(root)
    db_path = root / "registry" / DB_NAME
    expected = file_fingerprint(root)
    if db_path.exists():
        try:
            with closing(sqlite3.connect(str(db_path))) as connection:
                current = dict(connection.execute("SELECT key,value FROM index_meta"))
            if current.get("schema_version") == INDEX_VERSION and current.get("input_fingerprint") == expected:
                return {"database": str(db_path), "record_count": int(current.get("record_count", 0)),
                        "schema_version": INDEX_VERSION, "built_at": current.get("built_at"),
                        "reused": True}
        except (sqlite3.Error, ValueError):
            pass
    result = build_index(root)
    result["reused"] = False
    return result


def get_skill_by_id(source_record_id, root=ROOT):
    """Return one indexed source record by its stable GASL source ID."""
    root = Path(root)
    ensure_index(root)
    db_path = root / "registry" / DB_NAME
    with closing(sqlite3.connect(str(db_path))) as connection:
        row = connection.execute(
            "SELECT metadata_json FROM skills WHERE source_record_id = ? AND is_test_fixture = 0",
            (source_record_id,),
        ).fetchone()
    if row is None:
        return None
    return json.loads(row[0])


def _fts_query(tokens):
    return " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens)


def _relevance_details(query, record, term_groups=None, term_group_specs=None):
    if term_group_specs is None:
        if term_groups is None:
            term_group_specs = [
                {"label": token, "terms": [token], "alternatives": [[token]]}
                for token in query_tokens(query)
            ]
        else:
            term_group_specs = [
                {"label": " ".join(group), "terms": list(group),
                 "alternatives": [list(group)], "weight": 1.0}
                for group in term_groups
            ]
    if not term_group_specs:
        return {
            "score": 0.0,
            "coverage": 0.0,
            "matched_groups": [],
            "unmatched_groups": [],
            "group_coverage": [],
        }
    name_tokens = set(tokenize(record["skill_name"]))
    description_tokens = set(tokenize(record["description"]))
    path_tokens = set(tokenize(record["source_path"]))
    repo_tokens = set(tokenize(record["repository"]))
    domain_tokens = set(tokenize(record["domains_text"]))
    research_tokens = set(tokenize(record["research_leads"]))
    search_tokens = set(tokenize(record.get("search_text", "")))
    feature_tokens = set(record.get("feature_terms", []))

    def token_weight(token):
        return max(
            5.0 if token in name_tokens else 0.0,
            4.0 if token in description_tokens else 0.0,
            2.0 if token in path_tokens else 0.0,
            1.0 if token in repo_tokens else 0.0,
            1.0 if token in domain_tokens else 0.0,
            0.5 if token in research_tokens else 0.0,
            1.25 if token in search_tokens else 0.0,
            3.5 if token in feature_tokens else 0.0,
        )

    weighted = 0.0
    matched_groups = []
    unmatched_groups = []
    group_coverage = []
    coverage_total = 0.0
    total_group_weight = sum(float(spec.get("weight", 1.0)) for spec in term_group_specs)
    for spec in term_group_specs:
        group_priority = float(spec.get("weight", 1.0))
        best = None
        for alternative in spec["alternatives"]:
            weights = [token_weight(token) for token in alternative]
            matched = [token for token, weight in zip(alternative, weights) if weight > 0]
            alternative_coverage = len(matched) / len(alternative) if alternative else 0.0
            alternative_score = sum(weights) / len(weights) if weights else 0.0
            candidate = (alternative_coverage, alternative_score, matched, alternative)
            if best is None or candidate[:2] > best[:2]:
                best = candidate

        best_coverage, best_score, matched, alternative = best or (0.0, 0.0, [], [])
        weighted += best_score * group_priority
        coverage_total += best_coverage * group_priority
        group_coverage.append({
            "label": spec["label"],
            "weight": group_priority,
            "coverage": round(best_coverage, 3),
            "matched_terms": matched,
            "matched_alternative": alternative,
        })
        if best_coverage > 0:
            matched_groups.append(list(alternative))
        else:
            unmatched_groups.append(list(spec["terms"]))

    coverage = coverage_total / total_group_weight if total_group_weight else 0.0
    score = 100.0 * weighted / (5.0 * total_group_weight) if total_group_weight else 0.0
    # Require phrase-level concept coverage, not just one generic token.
    score *= 0.55 + (0.45 * coverage)

    phrase = normalize_text(query)
    name = normalize_text(record["skill_name"])
    description = normalize_text(record["description"])
    if phrase and phrase in name:
        score += 12.0
    elif phrase and phrase in description:
        score += 6.0
    return {
        "score": round(min(score, 100.0), 2),
        "coverage": round(coverage, 3),
        "matched_groups": matched_groups,
        "unmatched_groups": unmatched_groups,
        "group_coverage": group_coverage,
    }


def _relevance_score(query, record, term_groups=None, term_group_specs=None):
    return _relevance_details(
        query, record, term_groups=term_groups, term_group_specs=term_group_specs
    )["score"]


def _duplicate_result_key(item):
    repository = str(item.get("repository") or "").casefold()
    commit = str(item.get("commit_sha") or "")
    metadata = item.get("metadata") or {}
    # Do not collapse records when their license or security evidence differs.
    evidence = (
        str(item.get("license_spdx") or "").upper(),
        str(item.get("license_status") or ""),
        str(item.get("security_status") or ""),
        str(item.get("install_status") or ""),
    )
    if repository and commit:
        content_sha = metadata.get("metadata_source_content_sha256")
        if content_sha:
            return ("content", repository, commit, "sha256", content_sha, *evidence)
        raw_sha = metadata.get("skill_md_sha256_raw")
        if raw_sha:
            return ("content", repository, commit, "sha256", raw_sha, *evidence)
        blob_sha = item.get("skill_md_blob_sha") or metadata.get("skill_md_blob_sha")
        if blob_sha:
            return ("content", repository, commit, "git-blob", blob_sha, *evidence)
        source_path = str(item.get("source_path") or "")
        if source_path:
            return ("source", repository, source_path, commit, *evidence)
    return ("record", item.get("source_record_id"))


def collapse_duplicate_results(results):
    """Collapse identical pinned source copies for display without merging registry records."""
    grouped = {}
    ordered = []
    for item in results:
        key = _duplicate_result_key(item)
        current = grouped.get(key)
        if current is None:
            current = dict(item)
            current["source_record_ids"] = [item.get("source_record_id")]
            current["duplicate_source_record_ids"] = []
            current["source_paths"] = [item.get("source_path")] if item.get("source_path") else []
            current["alternate_sources"] = []
            current["duplicate_count"] = 0
            current["duplicate_reason"] = None
            grouped[key] = current
            ordered.append(current)
            continue

        source_id = item.get("source_record_id")
        if source_id and source_id not in current["source_record_ids"]:
            current["source_record_ids"].append(source_id)
            current["duplicate_source_record_ids"].append(source_id)
        source_path = item.get("source_path")
        if source_path and source_path not in current["source_paths"]:
            current["source_paths"].append(source_path)
        current["alternate_sources"].append({
            "source_record_id": source_id,
            "source_path": source_path,
            "source_url": item.get("source_url"),
            "commit_sha": item.get("commit_sha"),
            "license_spdx": item.get("license_spdx"),
            "license_status": item.get("license_status"),
            "security_status": item.get("security_status"),
            "install_status": item.get("install_status"),
        })
        current["research_leads"] = sorted(set(
            (current.get("research_leads") or []) + (item.get("research_leads") or [])
        ))
        current["duplicate_count"] += 1
        current["duplicate_reason"] = (
            "same_repository_commit_and_content_hash"
            if key[0] == "content" else "same_pinned_source_identity"
        )
    return ordered


def search_skills(query, limit=10, domain=None, license_spdx=None,
                  security_status=None, public_only=False, content_only=False, root=ROOT):
    root = Path(root)
    positive_query, excluded_terms = strip_query_exclusions(query)
    term_group_specs = query_term_group_specs(positive_query, root=root)
    term_groups = [spec["terms"] for spec in term_group_specs]
    tokens = list(dict.fromkeys(token for group in term_groups for token in group))
    if not tokens:
        raise ValueError("Search query must contain at least one meaningful search term.")
    limit = max(1, min(int(limit), 100))
    ensure_index(root)
    db_path = root / "registry" / DB_NAME
    sql = """
        SELECT s.*, bm25(skills_fts, 10.0, 5.0, 1.0, 2.0, 0.5, 1.0, 0.5, 3.0) AS fts_rank
        FROM skills_fts
        JOIN skills s ON s.rowid = skills_fts.rowid
        WHERE skills_fts MATCH ?
          AND s.is_test_fixture = 0
    """
    params = [_fts_query(tokens)]
    if domain:
        sql += " AND instr(s.domains_text, ?) > 0"
        params.append("|" + domain + "|")
    if license_spdx:
        sql += " AND lower(s.license_spdx) = lower(?)"
        params.append(license_spdx)
    if security_status:
        sql += " AND s.security_status = ?"
        params.append(security_status)
    if public_only:
        sql += " AND s.is_publicly_mirrored = 1"
    if content_only:
        sql += " AND s.content_status IN ('downloaded_and_hashed_locally','mirrored_publicly_with_attribution')"
    sql += " ORDER BY fts_rank ASC LIMIT ?"
    params.append(min(max(limit * 20, 100), 1000))

    with closing(sqlite3.connect(str(db_path))) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(sql, params).fetchall()

    results = []
    for row in rows:
        item = dict(row)
        metadata = json.loads(item.pop("metadata_json"))
        search_text_value = item.pop("search_text", "")
        candidate_tokens = set(tokenize(" ".join((
            item.get("skill_name", ""), item.get("description", ""),
            item.get("repository", ""), item.get("source_path", ""),
            item.get("compatibility", ""), search_text_value,
        ))))
        if excluded_terms.intersection(candidate_tokens):
            continue
        domains = json.loads(item.pop("domains_json"))
        research_leads = json.loads(item.pop("research_leads"))
        fts_rank = item.pop("fts_rank")
        item["inferred_domains"] = domains
        item["research_leads"] = research_leads
        relevance = _relevance_details(query, {
            "skill_name": item["skill_name"], "description": item["description"],
            "source_path": item["source_path"], "repository": item["repository"],
            "domains_text": item["domains_text"], "research_leads": " ".join(research_leads),
            "search_text": search_text_value, "feature_terms": metadata.get("feature_terms", []),
        }, term_group_specs=term_group_specs)
        item["relevance_score"] = relevance["score"]
        item["query_coverage"] = relevance["coverage"]
        item["matched_query_groups"] = relevance["matched_groups"]
        item["unmatched_query_groups"] = relevance["unmatched_groups"]
        item["query_group_coverage"] = relevance["group_coverage"]
        item["fts_rank"] = round(float(fts_rank), 8)
        item["verified_feature_terms"] = metadata.get("feature_terms", [])
        item["metadata"] = metadata
        item["excluded_query_terms"] = sorted(excluded_terms)
        results.append(item)
    results.sort(key=lambda x: (-x["query_coverage"], -x["relevance_score"], x["fts_rank"], x["skill_name"].casefold()))
    return collapse_duplicate_results(results)[:limit]


def main():
    parser = argparse.ArgumentParser(description="Build the local GASL SQLite FTS5 index.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true", help="Build/reuse the index and run a smoke query.")
    args = parser.parse_args()
    result = build_index(args.root)
    if args.check:
        smoke = search_skills("security audit", limit=3, root=args.root)
        result["smoke_query_count"] = len(smoke)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
