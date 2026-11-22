# GASL 10-Persona Stress Test — Run 03

Generated: 2026-11-22T12:39:48+00:00  
Branch / HEAD: main / 7e616c0f5a8b6ba906bea59a0ade3fc163d9e418  
Suite SHA-256: b1c4f9406fbb033c2d8998e7f35a87c4ed619a532e448a73284ccea1f2fda0d2  
Search input fingerprint: 1fd7676494bad172887c0c58d5643d14baa0fbf7e3bf91326f66ebae7813a348

> Ten model-simulated domain personas were used. This is not ten independent human reviews. Expected skill families are provisional regression signals, not gold judgments.

## Run summary

| Metric | Result |
|---|---:|
| Review personas | 10 |
| Scenarios / queries | 50 |
| Expected family hit@5 | 32 / 38 (0.8421) |
| Negative-constraint violations in top 5 | 3 |
| Android SMS direct-candidate hits | 0 |
| Top-5 source-pin integrity | 1.0 |
| Average / p95 latency ms | 164.701 / 272.751 |
| Router domain filter | 3 / 3 |
| Router install/execute safety | 3 / 3 |
| Filter invariants | 4 / 4 |
| Invalid-query rejection | 3 / 3 |
| Persian Yeh/Kaf normalization | True |

## Repeatability versus previous run

Identical top-10 order: 50 / 50 (1.0).

## Per-persona results

### R01 — Red-Team Security Architect

Domain: security-compliance. Pressure: multi-tenant isolation, OAuth/OIDC, secrets exposure, incident response, negative constraints.

Expected family hit@5: 4/4; negative-constraint violations: 0.

| Scenario | Type | Difficulty | Top 5 | Expected hit | Avoid hit | Coverage |
|---|---|---|---|---:|---:|---:|
| SEC-01 | positive | high | spring-security, sign-in-with-vercel, find-bugs, mcp-oauth-triage, zoom-oauth | True | False | 0.339 |
| SEC-02 | positive | very-high | secrets-vault-manager, env-secrets-manager, twilio-security-hardening, ciso-review, databricks-unity-catalog | True | False | 0.324 |
| SEC-03 | positive | high | secret-serialization, azure-cosmos-db-py, azure-cosmos-py, shap, azure-appconfiguration-py | True | False | 0.4048 |
| SEC-04 | positive | very-high | sign-in-with-vercel, zoom-oauth, dpop-adoption, zoom-meeting-sdk-android, vercel-connect | True | False | 0.235 |
| SEC-05 | coverage_probe | extreme | cosmos-vulnerability-scanner, jetson-customize-mgbe, doca-comm-channel-admin, doca-bf3-deployment, api-breaking-change-detector | None | False | 0.2248 |

### R02 — Principal Data Platform Engineer

Domain: data-analytics. Pressure: query planning, PostgreSQL, streaming and batch ETL, schema evolution, data quality, Persian terminology.

Expected family hit@5: 3/4; negative-constraint violations: 0.

| Scenario | Type | Difficulty | Top 5 | Expected hit | Avoid hit | Coverage |
|---|---|---|---|---:|---:|---:|
| DATA-01 | positive | high | sql-optimization, clickhouse-managed-postgres-rca, bigquery-optimization, sql-database-assistant, aws-resource-health-diagnose | True | False | 0.3766 |
| DATA-02 | positive | very-high | senior-data-engineer, chief-data-officer-advisor, databricks-spark-structured-streaming, protobuf-grpc-api-review, agent-workflow-designer | True | False | 0.3546 |
| DATA-03 | positive | high | data-quality-auditor, exploratory-data-analysis, nemo-rl-brev-etiquette, tao-finetune-anomalygennext, bench-perf-oss | True | False | 0.33 |
| DATA-04 | positive | very-high | claims-analytics, sql-queries, dashboard-expert, financial-analyst, huggingface-papers | False | False | 0.12 |
| DATA-05 | coverage_probe | extreme | make-data-pipeline, doca-rmax, tao-generate-video-reasoning-annotations, aspnet-core, scribe | None | False | 0.19 |

### R03 — RAG and Agent Reliability Lead

Domain: ai-ml-agents. Pressure: vendor-neutral retrieval, evaluation, prompt injection, tool orchestration, groundedness and multilingual RAG.

Expected family hit@5: 3/4; negative-constraint violations: 1.

| Scenario | Type | Difficulty | Top 5 | Expected hit | Avoid hit | Coverage |
|---|---|---|---|---:|---:|---:|
| AI-01 | negative_constraint | very-high | rag-architect, pinecone-rag, qdrant-search-strategies, databricks-mlflow-evaluation, databricks-vector-search | True | True | 0.4314 |
| AI-02 | positive | extreme | arize-evaluator, api-test-suite-builder, post-patch-validation, redis-search, databricks-vector-search | False | False | 0.23 |
| AI-03 | positive | very-high | n8n-agents, n8n-ai-nodes-official, n8n-error-handling, n8n-subworkflows-official, n8n-subworkflows | True | False | 0.4552 |
| AI-04 | positive | very-high | rag-architect, ai-security, chief-ai-officer-advisor, google-cloud-solution-rag-enterprise-search-gke-sqldb, pinecone-rag | True | False | 0.1128 |
| AI-05 | coverage_probe | extreme | tao-train-visual-changenet, tao-validate-recipe-transfer, kermt-pretrain-scratch, tao-train-dinov3, codonfm-embed | None | False | 0.2736 |

### R04 — Android and Backend Principal Engineer

Domain: software-development. Pressure: native Android, Kotlin, backend APIs, framework-specific implementation, explicit rejection of adjacent technologies.

Expected family hit@5: 2/2; negative-constraint violations: 0.

| Scenario | Type | Difficulty | Top 5 | Expected hit | Avoid hit | Coverage |
|---|---|---|---|---:|---:|---:|
| DEV-01 | known_coverage_gap | extreme | twilio-messaging-webhooks, twilio-rcs-messaging, twilio-marketing-promotions-advisor, twilio-sms-send-message, twilio-whatsapp-send-message | None | True | 0.288 |
| DEV-02 | positive | very-high | api-test-suite-builder, senior-ml-engineer, planning-oracle-to-postgres-migration-integration-testing, senior-backend, fastapi-router-py | True | False | 0.3526 |
| DEV-03 | positive | high | senior-frontend, typescript-data-visualization-engineering, nextjs, senior-qa, breakdown-epic-arch | True | False | 0.51 |
| DEV-04 | known_coverage_gap | extreme | twilio-webhook-architecture, twilio-messaging-webhooks, twilio-sendgrid-webhooks, twilio-sendgrid-inbound-parse, twilio-whatsapp-manage-senders | None | True | 0.077 |
| DEV-05 | coverage_probe | extreme | game-engine, programmatic-seo, soc2-audit-prep, medchem, executing-plans | None | False | 0.188 |

### R05 — Automation SRE and Workflow Architect

Domain: productivity-automation. Pressure: n8n reliability, webhooks, idempotency, retries, CRM/email/calendar integration and human approval.

Expected family hit@5: 3/4; negative-constraint violations: 0.

| Scenario | Type | Difficulty | Top 5 | Expected hit | Avoid hit | Coverage |
|---|---|---|---|---:|---:|---:|
| AUTO-01 | positive | very-high | n8n-error-handling, n8n-error-handling-official, n8n-workflow-patterns, n8n-credentials-and-security-official, n8n-ai-nodes-official | True | False | 0.3582 |
| AUTO-02 | positive | extreme | verify-agent-action, openfda-database, build-zoom-rest-api-app, n8n-self-hosting, n8n-credentials-and-security-official | True | False | 0.2106 |
| AUTO-03 | positive | high | build-zoom-team-chat-app, chat-sdk, diagnose, build-zoom-rest-api-app, telemetry | False | False | 0.3664 |
| AUTO-04 | positive | very-high | n8n-error-handling, n8n-workflow-patterns, n8n-expression-syntax, n8n-error-handling-official, build-zoom-rest-api-app | True | False | 0.1962 |
| AUTO-05 | coverage_probe | extreme | pytdc, api-breaking-change-detector, google-ads-api-mcp-setup, security-scan, security-scan | None | False | 0.26 |

### R06 — Cloud Platform and FinOps Engineer

Domain: cloud-infrastructure. Pressure: AWS/Azure provider specificity, Kubernetes, Terraform, secrets, observability, constrained and air-gapped environments.

Expected family hit@5: 4/4; negative-constraint violations: 1.

| Scenario | Type | Difficulty | Top 5 | Expected hit | Avoid hit | Coverage |
|---|---|---|---|---:|---:|---:|
| CLOUD-01 | positive | very-high | azure-kubernetes-app-deploy, azure-kubernetes-app-deploy, foundry-hosted-agent-copilotkit, azure-kubernetes, azure-kubernetes | True | False | 0.4572 |
| CLOUD-02 | negative_constraint | extreme | kubernetes-skill, aws-resource-query, azure-kubernetes, azure-kubernetes, google-cicd-terraform | True | True | 0.31 |
| CLOUD-03 | positive | high | durable-objects, durable-objects, cloudflare-deploy, building-ai-agent-on-cloudflare, wrangler | True | False | 0.6196 |
| CLOUD-04 | positive | very-high | azure-kubernetes-app-deploy, azure-kubernetes-app-deploy, senior-ml-engineer, gem-devops-guidelines, devops-rollout-plan | True | False | 0.344 |
| CLOUD-05 | coverage_probe | extreme | google-cloud-solution-guided-gke-ai-migration, tao-train-single-step, cdf-orchestration-write-dag, lab-hardware-cad, tao-data-io | None | False | 0.27 |

### R07 — RTL Product Designer and Accessibility Auditor

Domain: design-creative. Pressure: WCAG 2.2, RTL/Persian layout, keyboard and screen reader support, fintech forms, user-flow critique.

Expected family hit@5: 2/4; negative-constraint violations: 1.

| Scenario | Type | Difficulty | Top 5 | Expected hit | Avoid hit | Coverage |
|---|---|---|---|---:|---:|---:|
| DES-01 | negative_constraint | very-high | apple-hig-expert, design-qa, product-skills, data-visualization, game-ui-frontend | False | True | 0.2696 |
| DES-02 | positive | very-high | ui-styling, databricks-app-design, penpot-uiux-design, macos-golden-gate-design, impeccable | True | False | 0.3894 |
| DES-03 | positive | high | audit, form-cro, url-to-code, cja-funnel-health-check, flowstudio-power-automate-debug | True | False | 0.3556 |
| DES-04 | positive | very-high | design-qa, copy-editing, screen-recording, boltz-protein-screen, boltz-small-molecule-screen | False | False | 0.0584 |
| DES-05 | coverage_probe | extreme | omniverse-realtime-viewer, ui-styling, shadcn, anti-ui-slop, ui-ux-pro-max | None | False | 0.2624 |

### R08 — B2B SaaS CFO and Growth Strategist

Domain: business-finance. Pressure: SaaS metrics, pricing and packaging, runway, CAC/LTV, retention, regulated cross-border monetization.

Expected family hit@5: 4/4; negative-constraint violations: 0.

| Scenario | Type | Difficulty | Top 5 | Expected hit | Avoid hit | Coverage |
|---|---|---|---|---:|---:|---:|
| BIZ-01 | positive | high | saas-metrics-coach, cro-advisor, finance-metrics-quickref, cfo-advisor, org-health-diagnostic | True | False | 0.5792 |
| BIZ-02 | positive | very-high | pricing, pricing-strategist, pricing-strategy, pricing-strategy, finance-based-pricing-advisor | True | False | 0.5364 |
| BIZ-03 | positive | high | cfo-advisor, cfo-review, saas-economics-efficiency-metrics, board-prep, founder-mode | True | False | 0.5002 |
| BIZ-04 | positive | very-high | cfo-advisor, saas-metrics-coach, finance-skills, finance-metrics-quickref, board-prep | True | False | 0.25 |
| BIZ-05 | coverage_probe | extreme | board-meeting, pricing-strategist, public-equity-investing, paywalls, comps-valuation | None | False | 0.2946 |

### R09 — Systematic Review Methodologist and Educator

Domain: research-education. Pressure: systematic review protocol, search reproducibility, evidence quality, bias, claim-level papers and educational transfer.

Expected family hit@5: 3/4; negative-constraint violations: 0.

| Scenario | Type | Difficulty | Top 5 | Expected hit | Avoid hit | Coverage |
|---|---|---|---|---:|---:|---:|
| RES-01 | positive | very-high | literature-review, bgpt-paper-search, app-store-optimization, autonomous-investigation, autonomous-investigation | True | False | 0.3894 |
| RES-02 | positive | extreme | scientific-critical-thinking, experimental-design, statistical-analysis, pharmacoepidemiology, statistical-power | True | False | 0.3466 |
| RES-03 | positive | high | bgpt-paper-search, literature-review, paperclip, pubmed-database, literature-search-europepmc | True | False | 0.4826 |
| RES-04 | positive | very-high | planning-with-files-ar | False | False | 0.043 |
| RES-05 | coverage_probe | extreme | scientific-critical-thinking, doc-and-modernize, post-patch-validation, market-research-reports, literature-review | None | False | 0.3112 |

### R10 — Developer Documentation and Localization Editor

Domain: content-writing. Pressure: API docs, OpenAPI, developer onboarding, SEO content strategy, Persian localization and terminology consistency.

Expected family hit@5: 4/4; negative-constraint violations: 0.

| Scenario | Type | Difficulty | Top 5 | Expected hit | Avoid hit | Coverage |
|---|---|---|---|---:|---:|---:|
| DOC-01 | positive | high | technical-writer, data-manager-api-audience-ingestion, pyzotero, zoom-meeting-sdk-electron, eas-workflows | True | False | 0.4754 |
| DOC-02 | positive | very-high | openapi-to-application-code, openapi-to-application-java-spring-boot, aspnet-minimal-api-openapi, flowstudio-power-automate-debug, msa-search-nim | True | False | 0.4376 |
| DOC-03 | positive | high | site-architecture, content-creator, content-strategy, content-production, seo-audit | True | False | 0.4914 |
| DOC-04 | positive | very-high | i18n-localization, ui-ux-pro-max, game-ui-frontend, shopify-pos-ui, shopify-pos-ui | True | False | 0.0458 |
| DOC-05 | coverage_probe | extreme | matlab, openai-docs, spec-to-code-compliance, doca-structured-tools-contract, nvflare-autofl | None | False | 0.3618 |

## Cross-cutting router checks

| Probe | Domain filter | Install/execute blocked | Candidates |
|---|---:|---:|---:|
| n8n workflow retries | True | True | 5 |
| Kubernetes deployment | True | True | 5 |
| OAuth security | True | True | 5 |

## Query-filter checks

| Probe | Returned | Invariant valid |
|---|---:|---:|
| MIT license filter | 10 | True |
| public-only filter | 1 | True |
| content-only filter | 10 | True |
| not-scanned security filter | 10 | True |

## Interpretation guardrails

- A positive expected-signal miss is a retrieval failure signal requiring review, not proof that no relevant Skill exists.
- An avoid-signal hit is a negative-constraint failure signal; inspect the candidate's actual scope before final adjudication.
- Coverage probes are exploratory and do not receive a no-answer gold label from this harness.
- A returned candidate does not imply safety, license approval, completeness or installation eligibility.
- No ranking code or threshold is changed by this script.

## Reproduction

python3 tools/reviewer_stress_eval.py --round 3 --output-dir docs/reports/PHASE-12-REVIEWER-STRESS-2026-11-22
