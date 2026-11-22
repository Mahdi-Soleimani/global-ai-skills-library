#!/usr/bin/env python3
"""Repeatable 10-persona adversarial stress evaluation for local GASL search/router.

The personas are model-simulated, not independent human reviewers.
Retrieval is local only; no Skill is installed or executed.
"""
import argparse
import hashlib
import json
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from skill_search import INDEX_VERSION, ensure_index, search_skills, normalize_text, file_fingerprint
from skill_router import route_task

SUITE_VERSION = "1.2.0"
REVIEWERS = [
{"id":"R01","persona":"Red-Team Security Architect","domain":"security-compliance","pressure":"multi-tenant isolation, OAuth/OIDC, secrets exposure, incident response, negative constraints","scenarios":[
{"id":"SEC-01","kind":"positive","difficulty":"high","query":"Review Spring Security 6 OAuth2 and OIDC login for a multi-tenant SaaS: authorization code with PKCE, JWT validation, refresh-token rotation, CSRF/CORS, session revocation and abuse cases.","expected":["spring-security","zoom-oauth","dpop-adoption"]},
{"id":"SEC-02","kind":"positive","difficulty":"very-high","query":"A production Git repository exposed AWS access keys and bearer refresh tokens. Build the incident response sequence: contain access, revoke sessions, rotate credentials in HashiCorp Vault or AWS Secrets Manager, scan history, identify blast radius and audit access.","expected":["secrets-vault-manager","env-secrets-manager"]},
{"id":"SEC-03","kind":"positive","difficulty":"high","query":"Audit Python dataclass repr, Pydantic model_dump and FastAPI logs for accidental password, API key and bearer-token serialization; propose safe serialization rules and regression checks.","expected":["secret-serialization"]},
{"id":"SEC-04","kind":"positive","difficulty":"very-high","language":"fa","query":"جریان ورود یک SaaS چندمستاجری را با OAuth 2.1 و OIDC، روش PKCE، اعتبارسنجی JWT، چرخش و ابطال Refresh Token، کنترل دسترسی بین Tenantها و سناریوهای سوءاستفاده ممیزی کن.","expected":["spring-security","senior-security","zoom-oauth"]},
{"id":"SEC-05","kind":"coverage_probe","difficulty":"extreme","query":"Formally verify an undocumented proprietary embedded controller secure-boot chain with hardware root of trust, fault injection, side-channel resistance and measured boot; do not substitute a generic web application checklist.","expected":[]}
]},
{"id":"R02","persona":"Principal Data Platform Engineer","domain":"data-analytics","pressure":"query planning, PostgreSQL, streaming and batch ETL, schema evolution, data quality, Persian terminology","scenarios":[
{"id":"DATA-01","kind":"positive","difficulty":"high","query":"Diagnose a slow PostgreSQL analytics query using EXPLAIN ANALYZE, join cardinality, composite and partial indexes, partition pruning and query-plan regressions.","expected":["sql-database-assistant"]},
{"id":"DATA-02","kind":"positive","difficulty":"very-high","query":"Design a production ETL and ELT platform with Airflow, dbt, Kafka and Spark, handling schema evolution, late-arriving events, idempotent loads, data contracts, lineage and data-quality gates.","expected":["senior-data-engineer","data-quality-auditor"]},
{"id":"DATA-03","kind":"positive","difficulty":"high","query":"Profile a large messy CSV and Parquet dataset before model training: missingness, outliers, duplicates, type drift, leakage, distribution shift and reproducible quality report.","expected":["data-quality-auditor","senior-data-engineer"]},
{"id":"DATA-04","kind":"positive","difficulty":"very-high","language":"fa","query":"برای یک پایگاه PostgreSQL با گزارش‌های تحلیلی کند، EXPLAIN ANALYZE، شاخص‌های ترکیبی، Joinها، پارتیشن‌بندی، ETL افزایشی، داده‌های تکراری و کنترل کیفیت داده را بررسی کن.","expected":["sql-database-assistant","senior-data-engineer"]},
{"id":"DATA-05","kind":"coverage_probe","difficulty":"extreme","query":"Build an exactly-once telemetry ingestion and anomaly pipeline for a proprietary 1990s CNC controller that emits undocumented binary serial frames with clock drift and intermittent offline buffers.","expected":[]}
]},
{"id":"R03","persona":"RAG and Agent Reliability Lead","domain":"ai-ml-agents","pressure":"vendor-neutral retrieval, evaluation, prompt injection, tool orchestration, groundedness and multilingual RAG","scenarios":[
{"id":"AI-01","kind":"negative_constraint","difficulty":"very-high","query":"Design a vendor-neutral production RAG system with PostgreSQL pgvector or Qdrant, chunking, embeddings, hybrid retrieval and reranking; explicitly do not use Pinecone or Databricks.","expected":["rag-architect","redis-search"],"avoid":["pinecone-rag","databricks-vector-search"]},
{"id":"AI-02","kind":"positive","difficulty":"extreme","query":"Create a rigorous RAG evaluation suite for retrieval recall, citation correctness, groundedness, hallucination, adversarial prompt injection, multilingual queries, regression testing and human adjudication.","expected":["arize-evaluator","senior-prompt-engineer","ai-prompt-engineering-safety-review","eval-driven-dev"]},
{"id":"AI-03","kind":"positive","difficulty":"very-high","query":"Implement a multi-step n8n AI agent workflow with structured extraction, tool permissions, human approval, retries, tracing, deterministic fallbacks and evaluation gates.","expected":["n8n-ai-nodes-official","n8n-agents"]},
{"id":"AI-04","kind":"positive","difficulty":"very-high","language":"fa","query":"یک سامانه RAG فارسی با قطعه‌بندی اسناد، Embedding، جست‌وجوی ترکیبی، Reranking، ارجاع دقیق به منبع و ارزیابی توهم و Prompt Injection طراحی کن؛ وابسته به یک Vendor خاص نباشد.","expected":["rag-architect","senior-prompt-engineer"]},
{"id":"AI-05","kind":"coverage_probe","difficulty":"extreme","query":"Train and validate a custom multimodal neural codec for a proprietary industrial sensor format with no public architecture, no pretrained checkpoint and strict on-device latency limits.","expected":[]}
]},
{"id":"R04","persona":"Android and Backend Principal Engineer","domain":"software-development","pressure":"native Android, Kotlin, backend APIs, framework-specific implementation, explicit rejection of adjacent technologies","scenarios":[
{"id":"DEV-01","kind":"known_coverage_gap","difficulty":"extreme","query":"Build a native Android Kotlin BroadcastReceiver that receives bank SMS locally, captures the originating sender and full message body, and parses transaction fields; do not recommend Twilio webhooks, SMS gateways or cloud messaging.","expected":[],"avoid":["twilio-messaging-webhooks","twilio-sms-send-message","twilio-isv-sms-best-practices"]},
{"id":"DEV-02","kind":"positive","difficulty":"very-high","query":"Build an asynchronous FastAPI REST service with PostgreSQL, SQLAlchemy migrations, Pydantic validation, OAuth scopes, pytest integration tests, structured errors and production observability.","expected":["fastapi","sql-database-assistant"]},
{"id":"DEV-03","kind":"positive","difficulty":"high","query":"Implement a Next.js App Router application in TypeScript with server components, server actions, authentication, typed API boundaries, caching and end-to-end tests.","expected":["nextjs"]},
{"id":"DEV-04","kind":"known_coverage_gap","difficulty":"extreme","language":"fa","query":"در اپ بومی اندروید با Kotlin و BroadcastReceiver پیامک واریز بانک را روی خود گوشی دریافت کن، سرشماره و متن کامل را بخوان و فیلدهای تراکنش را استخراج کن؛ راهکار Twilio یا Webhook سروری نمی‌خواهم.","expected":[],"avoid":["twilio-messaging-webhooks","twilio-sms-send-message","twilio-isv-sms-best-practices"]},
{"id":"DEV-05","kind":"coverage_probe","difficulty":"extreme","query":"Implement a verified compiler backend and cycle-accurate simulator for an undocumented proprietary RISC-V-derived instruction set with formal equivalence proofs.","expected":[]}
]},
{"id":"R05","persona":"Automation SRE and Workflow Architect","domain":"productivity-automation","pressure":"n8n reliability, webhooks, idempotency, retries, CRM/email/calendar integration and human approval","scenarios":[
{"id":"AUTO-01","kind":"positive","difficulty":"very-high","query":"Design an unattended n8n webhook workflow with idempotency keys, bounded retries, exponential backoff, dead-letter handling, alerting, replay safety and structured error branches.","expected":["n8n-error-handling","n8n-workflow-patterns"]},
{"id":"AUTO-02","kind":"positive","difficulty":"extreme","query":"Synchronize Gmail, a CRM and Google Calendar in n8n without duplicate contacts or events; handle OAuth expiry, webhook replay, rate limits, conflict resolution and human approval.","expected":["n8n-workflow-patterns","n8n-node-configuration-official","n8n-credentials-and-security-official"]},
{"id":"AUTO-03","kind":"positive","difficulty":"high","query":"Build a Telegram bot callback_query workflow with chat state, inline keyboard actions, webhook verification, retries and safe editMessageReplyMarkup error handling.","expected":["chat-sdk"]},
{"id":"AUTO-04","kind":"positive","difficulty":"very-high","language":"fa","query":"در n8n یک گردش‌کار Webhook قابل‌اعتماد بساز که Idempotency، جلوگیری از اجرای تکراری، Retry با Backoff، مدیریت خطا، Dead Letter و تأیید انسانی داشته باشد.","expected":["n8n-error-handling","n8n-workflow-patterns"]},
{"id":"AUTO-05","kind":"coverage_probe","difficulty":"extreme","query":"Automate a closed-source legacy banking desktop application through an undocumented smart-card serial protocol with no API, no accessibility tree and strict audit requirements.","expected":[]}
]},
{"id":"R06","persona":"Cloud Platform and FinOps Engineer","domain":"cloud-infrastructure","pressure":"AWS/Azure provider specificity, Kubernetes, Terraform, secrets, observability, constrained and air-gapped environments","scenarios":[
{"id":"CLOUD-01","kind":"positive","difficulty":"very-high","query":"Deploy an existing FastAPI service to Azure Kubernetes Service using Docker, Helm, ingress, readiness and liveness probes, autoscaling, managed identity and rollback.","expected":["azure-kubernetes-app-deploy","azure-kubernetes"]},
{"id":"CLOUD-02","kind":"negative_constraint","difficulty":"extreme","query":"Provision production AWS EKS with Terraform, private networking, IAM least privilege, external secrets and blue-green delivery; AWS only, explicitly not Azure AKS.","expected":["senior-devops","eks","terraform"],"avoid":["azure-kubernetes","azure-kubernetes-app-deploy"]},
{"id":"CLOUD-03","kind":"positive","difficulty":"high","query":"Build and deploy Cloudflare Workers using Durable Objects, D1, Queues, environment bindings, wrangler and integration tests.","expected":["cloudflare"]},
{"id":"CLOUD-04","kind":"positive","difficulty":"very-high","language":"fa","query":"برای استقرار Production یک سرویس FastAPI روی Kubernetes، Helm، Docker، Health Probe، Autoscaling، مدیریت Secret، مانیتورینگ و Rollback را طراحی کن.","expected":["kubernetes","senior-devops","azure-kubernetes"]},
{"id":"CLOUD-05","kind":"coverage_probe","difficulty":"extreme","query":"Design a fully air-gapped ARM64 and RISC-V Kubernetes platform with a private artifact mirror, offline signing, custom hardware attestation and no external control plane.","expected":[]}
]},
{"id":"R07","persona":"RTL Product Designer and Accessibility Auditor","domain":"design-creative","pressure":"WCAG 2.2, RTL/Persian layout, keyboard and screen reader support, fintech forms, user-flow critique","scenarios":[
{"id":"DES-01","kind":"negative_constraint","difficulty":"very-high","query":"Audit a React fintech dashboard against WCAG 2.2 AA: keyboard navigation, visible focus, screen-reader labels, contrast and validation errors; do not return Apple HIG as the primary standard.","expected":["a11y-audit"],"partial":["accessibility-and-inclusive-visualization","ui-ux-pro-max","accessibility-fix"],"avoid":["apple-hig-expert"]},
{"id":"DES-02","kind":"positive","difficulty":"very-high","query":"Design a Persian RTL fintech dashboard with correct bidirectional numbers, localized forms, responsive data tables, design tokens, accessible typography and consistent component states.","expected":["penpot-uiux-design","ui-ux-pro-max","impeccable"]},
{"id":"DES-03","kind":"positive","difficulty":"high","query":"Critique a multi-step SaaS checkout and onboarding flow using screenshots, task completion, error prevention, cognitive load and actionable UX recommendations.","expected":["audit","ui-ux-pro-max"]},
{"id":"DES-04","kind":"positive","difficulty":"very-high","language":"fa","query":"یک داشبورد مالی راست‌چین فارسی را بر اساس WCAG 2.2 بررسی کن؛ پیمایش صفحه‌کلید، Screen Reader، کنتراست، Focus، خطاهای فرم و نمایش موبایل باید پوشش داده شوند.","expected":["accessibility-and-inclusive-visualization","design-qa"],"partial":["a11y-audit","ui-ux-pro-max"]},
{"id":"DES-05","kind":"coverage_probe","difficulty":"extreme","query":"Design and validate a tactile accessible interface for a proprietary braille and haptic wearable with novel nonvisual interaction patterns and hardware-specific feedback.","expected":[]}
]},
{"id":"R08","persona":"B2B SaaS CFO and Growth Strategist","domain":"business-finance","pressure":"SaaS metrics, pricing and packaging, runway, CAC/LTV, retention, regulated cross-border monetization","scenarios":[
{"id":"BIZ-01","kind":"positive","difficulty":"high","query":"Analyze B2B SaaS ARR, MRR, gross margin, CAC, LTV, payback period, logo churn, revenue churn, NRR and expansion revenue from actual customer cohorts.","expected":["saas-metrics-coach","saas-economics-efficiency-metrics"]},
{"id":"BIZ-02","kind":"positive","difficulty":"very-high","query":"Set B2B SaaS pricing and packaging for a multi-tenant product: compare per-seat, usage-based and value metrics, free tier conversion, willingness to pay and migration risks.","expected":["pricing","saas-metrics-coach","cro-advisor"]},
{"id":"BIZ-03","kind":"positive","difficulty":"high","query":"Build a startup cash runway and burn-rate model with hiring scenarios, revenue sensitivity, fundraising dilution, runway milestones and board reporting.","expected":["cfo-advisor","cfo-review"]},
{"id":"BIZ-04","kind":"positive","difficulty":"very-high","language":"fa","query":"اقتصاد یک SaaS سازمانی را با CAC، LTV، نرخ ریزش مشتری، MRR، ARR، حاشیه سود، دوره بازگشت هزینه جذب و درآمد توسعه‌ای تحلیل کن.","expected":["saas-metrics-coach","saas-economics-efficiency-metrics"]},
{"id":"BIZ-05","kind":"coverage_probe","difficulty":"extreme","query":"Model unit economics for a cross-border regulated microtransaction subscription in a market with fragmented settlement rails, sanctions exposure and no reliable public pricing data.","expected":[]}
]},
{"id":"R09","persona":"Systematic Review Methodologist and Educator","domain":"research-education","pressure":"systematic review protocol, search reproducibility, evidence quality, bias, claim-level papers and educational transfer","scenarios":[
{"id":"RES-01","kind":"positive","difficulty":"very-high","query":"Conduct a reproducible systematic review of AI tutoring in secondary education: databases, Boolean search strategy, protocol, inclusion and exclusion criteria, screening and evidence synthesis.","expected":["literature-review"]},
{"id":"RES-02","kind":"positive","difficulty":"extreme","query":"Critically appraise an education intervention study for selection bias, confounding, measurement validity, statistical power, external validity and certainty of evidence.","expected":["scientific-critical-thinking","scholar-evaluation"]},
{"id":"RES-03","kind":"positive","difficulty":"high","query":"Search scientific papers by DOI and retrieve claim-level evidence from full text, including experiment design, reported statistics, limitations and provenance.","expected":["bgpt-paper-search","literature-review"]},
{"id":"RES-04","kind":"positive","difficulty":"very-high","language":"fa","query":"برای بررسی نظام‌مند اثر معلم هوشمند بر یادگیری دانش‌آموزان متوسطه، راهبرد جست‌وجو، معیار ورود و خروج، غربالگری مقالات، سوگیری و سنتز شواهد را طراحی کن.","expected":["literature-review","scientific-critical-thinking"]},
{"id":"RES-05","kind":"coverage_probe","difficulty":"extreme","query":"Plan a meta-analysis for a newly emerging educational intervention where the evidence base may contain zero eligible studies; distinguish absence of evidence from evidence of no effect.","expected":[]}
]},
{"id":"R10","persona":"Developer Documentation and Localization Editor","domain":"content-writing","pressure":"API docs, OpenAPI, developer onboarding, SEO content strategy, Persian localization and terminology consistency","scenarios":[
{"id":"DOC-01","kind":"positive","difficulty":"high","query":"Write and review developer documentation for an SDK: installation, quickstart, authentication, runnable examples, troubleshooting, API reference and versioned migration guides.","expected":["technical-writer","documentation-writer"]},
{"id":"DOC-02","kind":"positive","difficulty":"very-high","query":"Generate maintainable API documentation from an OpenAPI specification with request and response schemas, authentication, error codes, pagination, examples, versioning and changelog.","expected":["technical-writer","aspnet-minimal-api-openapi"]},
{"id":"DOC-03","kind":"positive","difficulty":"high","query":"Create an SEO content strategy with search intent mapping, keyword clusters, topical authority, internal linking and a prioritized technical blog calendar.","expected":["content-strategy","content-production"]},
{"id":"DOC-04","kind":"positive","difficulty":"very-high","language":"fa","query":"رشته‌های رابط کاربری یک نرم‌افزار را از انگلیسی به فارسی بومی‌سازی کن؛ کلیدها، Placeholderها، جمع‌پذیری CLDR، واژه‌نامه تخصصی، متن راست‌چین و جلوگیری از ترجمه ناسازگار باید کنترل شوند.","expected":["i18n-localization"]},
{"id":"DOC-05","kind":"coverage_probe","difficulty":"extreme","query":"Produce accurate developer documentation for a proprietary binary protocol when no OpenAPI schema, source code, packet examples or vendor specification are available; do not invent undocumented behavior.","expected":[]}
]},
]


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def suite_hash():
    raw = json.dumps({"version": SUITE_VERSION, "reviewers": REVIEWERS}, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


def match_patterns(results, patterns):
    hits = []
    for rank, item in enumerate(results, 1):
        name = str(item.get("skill_name") or "").casefold()
        for pattern in patterns:
            if pattern.casefold() in name:
                hits.append({"pattern": pattern, "rank": rank, "skill_name": item.get("skill_name")})
    return hits


def summarize_result(item):
    return {
        "source_record_id": item.get("source_record_id"),
        "source_record_ids": item.get("source_record_ids") or [item.get("source_record_id")],
        "skill_name": item.get("skill_name"),
        "repository": item.get("repository"),
        "description": str(item.get("description") or "")[:450],
        "relevance_score": item.get("relevance_score"),
        "query_coverage": item.get("query_coverage"),
        "inferred_domains": [d.get("id") for d in item.get("inferred_domains", [])],
        "security_status": item.get("security_status"),
        "license_spdx": item.get("license_spdx"),
        "content_status": item.get("content_status"),
        "duplicate_count": item.get("duplicate_count", 0),
    }


def git_value(root, *args):
    try:
        return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    except Exception:
        return None


def run_round(round_number, output_dir, root=ROOT):
    root = Path(root)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = root / "registry" / "source-catalog.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))["records"]
    source_by_id = {row.get("source_record_id"): row for row in source}
    index_state = ensure_index(root)
    cases, timings = [], []

    for reviewer in REVIEWERS:
        for scenario in reviewer["scenarios"]:
            started = time.perf_counter()
            results = search_skills(scenario["query"], limit=10, root=root)
            elapsed = round((time.perf_counter() - started) * 1000, 3)
            timings.append(elapsed)
            top5 = results[:5]
            expected_hits = match_patterns(top5, scenario.get("expected", []))
            partial_hits = match_patterns(top5, scenario.get("partial", []))
            avoid_hits = match_patterns(top5, scenario.get("avoid", []))
            source_checks = []
            for item in top5:
                for source_id in (item.get("source_record_ids") or [item.get("source_record_id")]):
                    src = source_by_id.get(source_id)
                    source_checks.append({
                        "source_record_id": source_id,
                        "exists": src is not None,
                        "commit_matches": bool(src and item.get("commit_sha") == src.get("commit_sha")),
                        "blob_matches": bool(src and item.get("skill_md_blob_sha") == src.get("skill_md_blob_sha")),
                        "commit_pinned": bool(src and src.get("snapshot_status") == "verified_commit_pinned"),
                    })
            flat_ids = [sid for item in results for sid in (item.get("source_record_ids") or [item.get("source_record_id")]) if sid]
            duplicate_ids = sorted({sid for sid in flat_ids if flat_ids.count(sid) > 1})
            direct_sms = re.compile(r"BroadcastReceiver|SMS_RECEIVED|SmsRetriever|READ_SMS|RECEIVE_SMS|banking SMS", re.I)
            direct_sms_candidates = [
                item.get("skill_name") for item in results
                if direct_sms.search(" ".join([str(item.get("skill_name") or ""), str(item.get("description") or ""), str(item.get("source_path") or "")]))
            ]
            cases.append({
                "reviewer_id": reviewer["id"], "persona": reviewer["persona"],
                "target_domain": reviewer["domain"], "pressure_profile": reviewer["pressure"],
                "scenario_id": scenario["id"], "kind": scenario["kind"],
                "difficulty": scenario["difficulty"], "language": scenario.get("language", "en"),
                "query": scenario["query"], "expected_skill_patterns": scenario.get("expected", []),
                "partial_skill_patterns": scenario.get("partial", []),
                "avoid_skill_patterns": scenario.get("avoid", []),
                "expected_signal_hits_top5": expected_hits,
                "expected_signal_found_top5": bool(expected_hits) if scenario.get("expected") else None,
                "partial_signal_hits_top5": partial_hits,
                "partial_signal_found_top5": bool(partial_hits) if scenario.get("partial") else None,
                "avoid_signal_hits_top5": avoid_hits, "avoid_signal_triggered": bool(avoid_hits),
                "coverage_probe": scenario["kind"] in ("coverage_probe", "known_coverage_gap"),
                "direct_sms_candidates_top10": direct_sms_candidates,
                "direct_sms_candidate_found": bool(direct_sms_candidates),
                "average_top5_query_coverage": round(statistics.mean([float(x.get("query_coverage") or 0) for x in top5]), 4) if top5 else 0.0,
                "search_latency_ms": elapsed, "result_count": len(results),
                "top5": [summarize_result(x) for x in top5],
                "top10_source_ids": [x.get("source_record_ids") or [x.get("source_record_id")] for x in results],
                "source_integrity_checks": source_checks,
                "all_top5_source_pins_valid": bool(source_checks) and all(x["exists"] and x["commit_matches"] and x["blob_matches"] and x["commit_pinned"] for x in source_checks),
                "duplicate_source_ids_after_collapse": duplicate_ids,
            })

    route_probes = [
        ("n8n workflow retries", "Design n8n webhook error handling with idempotency and retries", "productivity-automation"),
        ("Kubernetes deployment", "Deploy a FastAPI service to Kubernetes with Helm and rollback", "cloud-infrastructure"),
        ("OAuth security", "Review OAuth 2.1 PKCE refresh token rotation and JWT validation", "security-compliance"),
    ]
    route_checks = []
    for label, query, domain in route_probes:
        routed = route_task(query, top_k=5, domain=domain, root=root)
        rows = routed.get("results", [])
        route_checks.append({
            "probe": label, "domain": domain, "candidate_pool_size": routed.get("candidate_pool_size"),
            "returned_count": routed.get("returned_count"),
            "domain_filter_valid": all(domain in [d.get("id") for d in x.get("inferred_domains", [])] for x in rows),
            "installation_execution_blocked": all(x.get("installation_allowed") is False and x.get("execution_allowed") is False for x in rows),
            "results": [{"skill_name":x.get("skill_name"),"source_record_id":x.get("source_record_id"),"decision":x.get("decision"),"security_status":x.get("security_status"),"installation_allowed":x.get("installation_allowed"),"execution_allowed":x.get("execution_allowed")} for x in rows],
        })

    filter_specs = [
        ("MIT license filter", {"license_spdx":"MIT"}, "Python API documentation"),
        ("public-only filter", {"public_only":True}, "technical writer API docs"),
        ("content-only filter", {"content_only":True}, "technical writer API docs"),
        ("not-scanned security filter", {"security_status":"not_scanned"}, "Kubernetes deployment"),
    ]
    filter_checks = []
    for label, kwargs, query in filter_specs:
        rows = search_skills(query, limit=10, root=root, **kwargs)
        if "license_spdx" in kwargs:
            valid = all(str(x.get("license_spdx") or "").casefold() == "mit" for x in rows)
        elif kwargs.get("public_only"):
            valid = all(bool(x.get("is_publicly_mirrored")) for x in rows)
        elif kwargs.get("content_only"):
            valid = all(x.get("content_status") in ("downloaded_and_hashed_locally","mirrored_publicly_with_attribution") for x in rows)
        else:
            valid = all(x.get("security_status") == "not_scanned" for x in rows)
        filter_checks.append({"probe":label,"query":query,"kwargs":kwargs,"returned_count":len(rows),"filter_invariant_valid":valid,"results":[summarize_result(x) for x in rows[:5]]})

    invalid_query_checks = []
    for query in ("", "   ", "!!! ???"):
        try:
            search_skills(query, limit=5, root=root)
            invalid_query_checks.append({"query":query,"rejected":False,"error":None})
        except ValueError as exc:
            invalid_query_checks.append({"query":query,"rejected":True,"error":str(exc)})

    fa_arabic, fa_persian = normalize_text("مديريت كاربرد"), normalize_text("مدیریت کاربرد")
    timings_sorted = sorted(timings)
    expected_cases = [x for x in cases if x["expected_skill_patterns"]]
    positive_expected = [x for x in expected_cases if x["kind"] == "positive"]
    negative_expected = [x for x in expected_cases if x["kind"] == "negative_constraint"]
    expected_hits = sum(x["expected_signal_found_top5"] is True for x in expected_cases)
    positive_hits = sum(x["expected_signal_found_top5"] is True for x in positive_expected)
    negative_expected_hits = sum(x["expected_signal_found_top5"] is True for x in negative_expected)
    summary = {
        "reviewer_count":len(REVIEWERS),"scenario_count":len(cases),
        "expected_family_cases":len(expected_cases),"expected_family_hits_top5":expected_hits,
        "expected_family_hit_rate_top5":round(expected_hits/len(expected_cases),4) if expected_cases else None,
        "positive_expected_cases":len(positive_expected),"positive_expected_hits_top5":positive_hits,
        "positive_expected_hit_rate_top5":round(positive_hits/len(positive_expected),4) if positive_expected else None,
        "negative_constraint_expected_cases":len(negative_expected),
        "negative_constraint_expected_hits_top5":negative_expected_hits,
        "negative_constraint_expected_hit_rate_top5":round(negative_expected_hits/len(negative_expected),4) if negative_expected else None,
        "coverage_probe_count":sum(x["coverage_probe"] for x in cases),
        # Backward-compatible aliases; these count every scenario with an expected family,
        # including negative-constraint scenarios. They are not positive-only metrics.
        "expected_signal_hits_top5":expected_hits,
        "expected_signal_hit_rate_top5":round(expected_hits/len(expected_cases),4) if expected_cases else None,
        "partial_signal_hits_top5":sum(x["partial_signal_found_top5"] is True for x in cases),
        "partial_signal_cases":sum(bool(x["partial_skill_patterns"]) for x in cases),
        "negative_constraint_cases":sum(x["kind"]=="negative_constraint" for x in cases),
        "negative_constraint_violations_top5":sum(x["avoid_signal_triggered"] for x in cases if x["kind"]=="negative_constraint"),
        "explicit_exclusion_cases":sum(bool(x["avoid_skill_patterns"]) for x in cases),
        "explicit_exclusion_violations_top5":sum(x["avoid_signal_triggered"] for x in cases if x["avoid_skill_patterns"]),
        "known_android_sms_gap_cases":sum(x["kind"]=="known_coverage_gap" for x in cases),
        "android_abstention_supported":False,
        "android_direct_candidate_hits":sum(x["direct_sms_candidate_found"] for x in cases if x["kind"]=="known_coverage_gap"),
        "top5_source_pin_integrity_rate":round(sum(x["all_top5_source_pins_valid"] for x in cases)/len(cases),4),
        "average_search_latency_ms":round(statistics.mean(timings),3),
        "p95_search_latency_ms":round(timings_sorted[max(0,int(len(timings)*0.95)-1)],3),
        "route_domain_filter_passes":sum(x["domain_filter_valid"] for x in route_checks),
        "route_install_execution_safety_passes":sum(x["installation_execution_blocked"] for x in route_checks),
        "filter_invariant_passes":sum(x["filter_invariant_valid"] for x in filter_checks),
        "invalid_query_rejection_passes":sum(x["rejected"] for x in invalid_query_checks),
        "persian_normalization_pass":fa_arabic==fa_persian,
    }
    payload = {
        "schema_version":"1.0.0","suite_version":SUITE_VERSION,"round":round_number,
        "run_type":"local_search_and_router_stress_test",
        "reviewer_model":"10 domain-specific model-simulated personas; not independent human reviewers",
        "generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "git_branch":git_value(root,"branch","--show-current"),"git_head":git_value(root,"rev-parse","HEAD"),
        "git_worktree_dirty":bool(git_value(root,"status","--porcelain")),
        "search_index_version":INDEX_VERSION,"index_state":index_state,"source_record_count":len(source),
        "source_catalog_sha256":sha256_file(source_path),"taxonomy_sha256":sha256_file(root/"config/taxonomy.json"),
        "search_input_fingerprint":file_fingerprint(root),"suite_sha256":suite_hash(),
        "ranking_code_sha256":hashlib.sha256((root/"tools/skill_search.py").read_bytes()+(root/"tools/skill_router.py").read_bytes()).hexdigest(),
        "reviewer_count":len(REVIEWERS),"scenario_count":len(cases),"queries_executed":len(cases),
        "summary":summary,"cases":cases,"route_checks":route_checks,"filter_checks":filter_checks,
        "invalid_query_checks":invalid_query_checks,
        "persian_normalization":{"arabic_form":fa_arabic,"persian_form":fa_persian,"equivalent":fa_arabic==fa_persian},
        "limitations":[
            "The ten reviewers are model-simulated personas, not independent human reviewers.",
            "Expected skill-name families are provisional regression signals, not adjudicated gold qrels.",
            "Coverage probes are exploratory; only Android SMS has a separate pinned-body audit, and that audit is not a full-catalog proof of absence.",
            "The search engine has no explicit abstention prediction in this test path; a candidate list is not proof that a direct Skill exists.",
            "Search relevance, content quality, safety, licensing and installation eligibility are separate dimensions.",
            "All rounds use the same local catalog and code snapshot; they test repeatability, not independent corpus snapshots."
        ],
    }

    if round_number > 1:
        previous_path = output_dir / f"RUN-{round_number-1:02d}.json"
        if previous_path.is_file():
            previous = json.loads(previous_path.read_text(encoding="utf-8"))
            prev = {x["scenario_id"]:x for x in previous.get("cases",[])}
            comparisons = []
            for case in cases:
                old = prev.get(case["scenario_id"])
                comparisons.append({"scenario_id":case["scenario_id"],"identical_top10_order":bool(old and case["top10_source_ids"]==old.get("top10_source_ids"))})
            same_engine_snapshot = (
                previous.get("search_input_fingerprint") == payload["search_input_fingerprint"]
                and previous.get("ranking_code_sha256") == payload["ranking_code_sha256"]
            )
            payload["repeatability_vs_previous_round"] = {
                "comparison_type":"repeatability" if same_engine_snapshot else "change_impact_vs_previous_round",
                "same_engine_snapshot":same_engine_snapshot,
                "compared_case_count":len(comparisons),
                "identical_top10_count":sum(x["identical_top10_order"] for x in comparisons),
                "identical_top10_rate":round(sum(x["identical_top10_order"] for x in comparisons)/len(comparisons),4),
                "cases":comparisons,
            }
        else:
            payload["repeatability_vs_previous_round"] = {"status":"previous_round_missing","compared_case_count":0}

    json_path = output_dir / f"RUN-{round_number:02d}.json"
    json_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    lines = [
        f"# GASL 10-Persona Stress Test — Run {round_number:02d}","",
        f"Generated: {payload['generated_at']}  ",
        f"Branch / HEAD: {payload['git_branch']} / {payload['git_head']}  ",
        f"Suite SHA-256: {payload['suite_sha256']}  ",
        f"Search input fingerprint: {payload['search_input_fingerprint']}","",
        "> Ten model-simulated domain personas were used. This is not ten independent human reviews. Expected skill families are provisional regression signals, not gold judgments.","",
        "## Run summary","","| Metric | Result |","|---|---:|",
        f"| Review personas | {summary['reviewer_count']} |",
        f"| Scenarios / queries | {summary['scenario_count']} |",
        f"| All expected-family hit@5 | {summary['expected_family_hits_top5']} / {summary['expected_family_cases']} ({summary['expected_family_hit_rate_top5']}) |",
        f"| Positive-scenario hit@5 | {summary['positive_expected_hits_top5']} / {summary['positive_expected_cases']} ({summary['positive_expected_hit_rate_top5']}) |",
        f"| Negative-constraint expected hit@5 | {summary['negative_constraint_expected_hits_top5']} / {summary['negative_constraint_expected_cases']} ({summary['negative_constraint_expected_hit_rate_top5']}) |",
        f"| Partial-family hits in top 5 | {summary['partial_signal_hits_top5']} / {summary['partial_signal_cases']} |",
        f"| Negative-constraint violations in top 5 | {summary['negative_constraint_violations_top5']} |",
        f"| All explicit-exclusion violations in top 5 | {summary['explicit_exclusion_violations_top5']} / {summary['explicit_exclusion_cases']} |",
        f"| Android SMS direct-candidate hits | {summary['android_direct_candidate_hits']} |",
        f"| Explicit abstention support | {summary['android_abstention_supported']} |",
        f"| Top-5 source-pin integrity | {summary['top5_source_pin_integrity_rate']} |",
        f"| Average / p95 latency ms | {summary['average_search_latency_ms']} / {summary['p95_search_latency_ms']} |",
        f"| Router domain filter | {summary['route_domain_filter_passes']} / {len(route_checks)} |",
        f"| Router install/execute safety | {summary['route_install_execution_safety_passes']} / {len(route_checks)} |",
        f"| Filter invariants | {summary['filter_invariant_passes']} / {len(filter_checks)} |",
        f"| Invalid-query rejection | {summary['invalid_query_rejection_passes']} / {len(invalid_query_checks)} |",
        f"| Persian Yeh/Kaf normalization | {summary['persian_normalization_pass']} |",""
    ]
    if "repeatability_vs_previous_round" in payload:
        rep = payload["repeatability_vs_previous_round"]
        lines += ["## Comparison versus previous run","",f"Comparison type: {rep.get('comparison_type')}; same engine snapshot: {rep.get('same_engine_snapshot')}. Identical top-10 order: {rep.get('identical_top10_count',0)} / {rep.get('compared_case_count',0)} ({rep.get('identical_top10_rate')}).",""]
    lines += ["## Per-persona results",""]
    for reviewer in REVIEWERS:
        rows = [x for x in cases if x["reviewer_id"]==reviewer["id"]]
        pos = [x for x in rows if x["expected_skill_patterns"]]
        hits = sum(x["expected_signal_found_top5"] is True for x in pos)
        violations = sum(x["avoid_signal_triggered"] for x in rows if x["kind"]=="negative_constraint")
        lines += [f"### {reviewer['id']} — {reviewer['persona']}","",f"Domain: {reviewer['domain']}. Pressure: {reviewer['pressure']}.","",f"Expected family hit@5: {hits}/{len(pos)}; negative-constraint violations: {violations}.","","| Scenario | Type | Difficulty | Top 5 | Expected hit | Partial hit | Avoid hit | Coverage |","|---|---|---|---|---:|---:|---:|---:|"]
        for row in rows:
            names = ", ".join(x.get("skill_name") or "?" for x in row["top5"])
            lines.append(f"| {row['scenario_id']} | {row['kind']} | {row['difficulty']} | {names} | {row['expected_signal_found_top5']} | {row['partial_signal_found_top5']} | {row['avoid_signal_triggered']} | {row['average_top5_query_coverage']} |")
        lines.append("")
    lines += ["## Cross-cutting router checks","","| Probe | Domain filter | Install/execute blocked | Candidates |","|---|---:|---:|---:|"]
    for row in route_checks:
        lines.append(f"| {row['probe']} | {row['domain_filter_valid']} | {row['installation_execution_blocked']} | {row['returned_count']} |")
    lines += ["","## Query-filter checks","","| Probe | Returned | Invariant valid |","|---|---:|---:|"]
    for row in filter_checks:
        lines.append(f"| {row['probe']} | {row['returned_count']} | {row['filter_invariant_valid']} |")
    lines += ["","## Interpretation guardrails","",
        "- A positive expected-signal miss is a retrieval failure signal requiring review, not proof that no relevant Skill exists.",
        "- An avoid-signal hit is a negative-constraint failure signal; inspect the candidate's actual scope before final adjudication.",
        "- Coverage probes are exploratory and do not receive a no-answer gold label from this harness.",
        "- A returned candidate does not imply safety, license approval, completeness or installation eligibility.",
        "- No ranking code or threshold is changed by this script.","",
        "## Reproduction","",
        f"python3 tools/reviewer_stress_eval.py --round {round_number} --output-dir docs/reports/PHASE-12-REVIEWER-STRESS-2026-11-22",""
    ]
    md_path = output_dir / f"RUN-{round_number:02d}.md"
    md_path.write_text("\n".join(lines),encoding="utf-8")
    return payload,json_path,md_path


def main():
    parser=argparse.ArgumentParser(description="Run one round of the GASL ten-persona stress suite.")
    parser.add_argument("--round",type=int,required=True,choices=(1,2,3,4,5,6,7,8,9,10))
    parser.add_argument("--output-dir",type=Path,default=ROOT/"docs/reports/PHASE-12-REVIEWER-STRESS-2026-11-22")
    parser.add_argument("--root",type=Path,default=ROOT)
    args=parser.parse_args()
    payload,json_path,md_path=run_round(args.round,args.output_dir,args.root)
    print(json.dumps({
        "round":payload["round"],"reviewer_count":payload["reviewer_count"],
        "scenario_count":payload["scenario_count"],"summary":payload["summary"],
        "repeatability_vs_previous_round":{
            "identical_top10_count":payload.get("repeatability_vs_previous_round",{}).get("identical_top10_count"),
            "compared_case_count":payload.get("repeatability_vs_previous_round",{}).get("compared_case_count"),
            "identical_top10_rate":payload.get("repeatability_vs_previous_round",{}).get("identical_top10_rate"),
            "comparison_type":payload.get("repeatability_vs_previous_round",{}).get("comparison_type")},
        "json":str(json_path),"markdown":str(md_path)
    },ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
