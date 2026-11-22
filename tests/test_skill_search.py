import gc
import json
import warnings
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from skill_evaluation import build_evaluations
from skill_search import (
    build_index, ensure_index, get_skill_by_id, search_skills, normalize_text, query_tokens, query_term_groups,
    query_term_group_specs, collapse_duplicate_results, _relevance_details, strip_query_exclusions
)


def record(record_id, name, description, repo, path, **extra):
    item = {
        "source_record_id": record_id,
        "skill_name": name,
        "description": description,
        "repository": repo,
        "repository_owner": repo.split("/")[0],
        "repository_url": "https://github.com/" + repo,
        "source_path": path,
        "source_url": "https://github.com/" + repo + "/blob/" + "a" * 40 + "/" + path,
        "commit_sha": "a" * 40,
        "skill_md_blob_sha": "b" * 40,
        "license_spdx": "MIT",
        "license_evidence_path": "LICENSE",
        "license_assessment": "repository_license_metadata_only",
        "content_status": "not_downloaded_reference_record",
        "security_status": "not_scanned",
        "install_status": "not_installed",
        "snapshot_status": "verified_commit_pinned",
        "research_leads": ["EN-675"],
        "ownership": "third_party",
        "original_author": None,
        "gasl_claims_exclusive_ownership": False,
    }
    item.update(extra)
    return item


class SkillSearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "registry").mkdir()
        (self.root / "public-catalog").mkdir()
        (self.root / "config").mkdir()
        records = [
            record("s1", "security-audit", "Audit cloud configuration and identify security vulnerabilities.",
                   "example/security-skills", "skills/security-audit/SKILL.md"),
            record("s2", "data-pipeline-analysis", "Analyze datasets, SQL queries and data pipelines.",
                   "example/data-skills", "skills/data-pipeline-analysis/SKILL.md"),
            record("s3", "python-api-builder", "Build and test Python backend APIs.",
                   "example/dev-skills", "skills/python-api-builder/SKILL.md"),
            record("s5", "agent-memory-tools", "Build AI agents that use tools and persistent memory.",
                   "example/agent-skills", "skills/agent-memory-tools/SKILL.md"),
            record("s6", "minecraft-plugin-development", "Build Minecraft plugin development projects for Paper servers.",
                   "example/game-skills", "skills/minecraft-plugin-development/SKILL.md"),
            record("s7", "content-management-systems", "WordPress plugin development for content management systems.",
                   "example/cms-skills", "skills/content-management-systems/SKILL.md"),
            record("s4", "fixture-security-test", "Security audit test fixture.",
                   "example/security-skills", "evals/fixtures/security-test/SKILL.md"),
        ]
        (self.root / "registry" / "source-catalog.json").write_text(
            json.dumps({"records": records}, ensure_ascii=False), encoding="utf-8")
        (self.root / "registry" / "skills.json").write_text(
            json.dumps({"records": [{
                "repository": "example/dev-skills", "source_skill_path": "skills/python-api-builder/SKILL.md",
                "commit_sha": "a" * 40, "compatibility": "Codex", "frontmatter_valid": True,
                "package_type": "skill_candidate", "package_content_present": True,
                "security_status": "no_obvious_static_flags_not_approved",
            }]}), encoding="utf-8")
        (self.root / "public-catalog" / "index.json").write_text(
            json.dumps({"packages": {
                "pub1": {
                    "repository": "example/security-skills",
                    "source_skill_path": "skills/security-audit/SKILL.md",
                    "commit_sha": "a" * 40,
                    "license_evidence": [{"source_path": "LICENSE", "blob_sha": "c" * 40}],
                    "package_path": "public-catalog/packages/pub1",
                }
            }}), encoding="utf-8")
        taxonomy = {
            "query_expansions": [
                {"terms": ["هوش مصنوعی", "هوش‌مصنوعی"], "expand": ["artificial intelligence", "ai", "llm"]},
                {"terms": ["ایجنت", "عامل هوشمند"], "expand": ["agent", "agents"]},
                {"terms": ["ابزار"], "expand": ["tool", "tools", "function calling"]},
                {"terms": ["حافظه"], "expand": ["memory", "persistent memory", "context"]},
                {"terms": ["امنیت"], "expand": ["security", "cybersecurity"]},
                {"terms": ["ممیزی امنیتی"], "expand": ["security audit", "security review", "vulnerability assessment"]},
                {"terms": ["ساخت"], "expand": ["build", "create", "develop"]},
                {"terms": ["توسعه"], "expand": ["develop", "development", "build"]},
                {"terms": ["افزونه وردپرس"], "expand": ["wordpress plugin", "wordpress plugins"]},
                {"terms": ["وردپرس"], "expand": ["wordpress", "woocommerce"]},
                {"terms": ["افزونه"], "expand": ["plugin", "plugins", "extension"]},
                {"terms": ["وب سایت", "وب‌سایت"], "expand": ["website", "web site", "web application"]},
                {"terms": ["نکست جی اس", "نکست‌جی‌اس"], "expand": ["next.js", "nextjs", "next js"]},
                {"terms": ["تایپ اسکریپت", "تایپ‌اسکریپت"], "expand": ["typescript", "type script"]},
                {"terms": ["اکسل"], "expand": ["excel", "spreadsheet", "workbook"]},
                {"terms": ["تحلیل داده"], "expand": ["data analysis", "data analytics", "analyze data"]},
                {"terms": ["داده کاوی"], "expand": ["data mining", "data analysis"]},
                {"terms": ["نمودار"], "expand": ["chart", "charts", "data visualization", "visualization"]},
                {"terms": ["گیت هاب اکشنز", "گیت‌هاب اکشنز"], "expand": ["github actions", "github action"]},
                {"terms": ["اتوماسیون"], "expand": ["automation", "workflow"]},
                {"terms": ["بهینه سازی", "بهینه‌سازی"], "expand": ["optimization", "optimize", "optimized"]},
                {"terms": ["محتوا", "محتوای"], "expand": ["content", "content writing", "content creation"]},
                {"terms": ["تحقیق"], "expand": ["research", "investigation"]},
                {"terms": ["استقرار"], "expand": ["deployment", "deploy", "release"]},
                {"terms": ["تست"], "expand": ["test", "testing", "tests"]},
            ],
            "domains": [
                {"id": "security-compliance", "label": "Security", "keywords": ["security", "audit", "امنیت"]},
                {"id": "data-analytics", "label": "Data", "keywords": ["data", "sql", "داده کاوی"]},
                {"id": "software-development", "label": "Software", "keywords": ["python", "api", "backend"]},
            ]
        }
        (self.root / "config" / "taxonomy.json").write_text(
            json.dumps(taxonomy, ensure_ascii=False), encoding="utf-8")
        build_evaluations(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_search_ranks_exact_skill_name_above_description_only(self):
        results = search_skills("security audit", limit=5, root=self.root)
        self.assertEqual(results[0]["skill_name"], "security-audit")
        self.assertGreater(results[0]["relevance_score"], 90)

    def test_domain_filter_uses_inferred_taxonomy(self):
        results = search_skills("security audit", limit=5, domain="security-compliance", root=self.root)
        self.assertTrue(results)
        self.assertTrue(all(any(x["id"] == "security-compliance" for x in r["inferred_domains"]) for r in results))

    def test_license_and_public_filters(self):
        results = search_skills("security audit", public_only=True, license_spdx="MIT", root=self.root)
        self.assertEqual([x["skill_name"] for x in results], ["security-audit"])

    def test_content_filter_excludes_reference_only_records(self):
        results = search_skills("security audit", content_only=True, root=self.root)
        self.assertEqual([x["skill_name"] for x in results], ["security-audit"])

    def test_test_fixtures_are_excluded_by_default(self):
        results = search_skills("security audit", limit=10, root=self.root)
        self.assertNotIn("fixture-security-test", [x["skill_name"] for x in results])

    def test_persian_query_and_arabic_character_normalization(self):
        self.assertEqual(normalize_text("كِتاب ي"), "کتاب ی")
        self.assertEqual(normalize_text("هوش‌مصنوعی"), "هوش مصنوعی")
        self.assertIn("داده", query_tokens("برای تحلیل داده کاوی"))
        results = search_skills("داده کاوی", root=self.root)
        self.assertEqual(results[0]["skill_name"], "data-pipeline-analysis")

    def test_inferred_domain_does_not_invent_keyword_evidence(self):
        # Membership in a domain is not evidence for every synonym in its vocabulary.
        results = search_skills("داده کاوی", root=self.root)
        best = results[0]
        self.assertNotIn("داده کاوی", best["domains_text"])
        self.assertTrue(any(x["id"] == "data-analytics" for x in best["inferred_domains"]))

    def test_identical_pinned_skill_copies_are_collapsed_only_in_search_results(self):
        first = {
            "source_record_id": "source-a",
            "skill_name": "agent-memory",
            "repository": "example/skills",
            "source_path": "skills/agent-memory/SKILL.md",
            "source_url": "https://github.com/example/skills/blob/a/skills/agent-memory/SKILL.md",
            "commit_sha": "a" * 40,
            "skill_md_blob_sha": "b" * 40,
            "research_leads": ["EN-675"],
            "relevance_score": 80,
            "fts_rank": -2,
        }
        second = {
            **first,
            "source_record_id": "source-b",
            "source_path": "plugins/agent-memory/SKILL.md",
            "source_url": "https://github.com/example/skills/blob/a/plugins/agent-memory/SKILL.md",
            "research_leads": ["FA-234"],
            "relevance_score": 75,
            "fts_rank": -1,
        }
        collapsed = collapse_duplicate_results([first, second])
        self.assertEqual(len(collapsed), 1)
        self.assertEqual(collapsed[0]["source_record_id"], "source-a")
        self.assertEqual(collapsed[0]["source_record_ids"], ["source-a", "source-b"])
        self.assertEqual(collapsed[0]["duplicate_source_record_ids"], ["source-b"])
        self.assertEqual(collapsed[0]["source_paths"], [
            "skills/agent-memory/SKILL.md", "plugins/agent-memory/SKILL.md"
        ])
        self.assertEqual(collapsed[0]["research_leads"], ["EN-675", "FA-234"])
        self.assertEqual(collapsed[0]["duplicate_count"], 1)

    def test_different_commits_are_not_collapsed_even_when_blob_is_same(self):
        first = {
            "source_record_id": "source-a", "repository": "example/skills",
            "source_path": "skills/a/SKILL.md", "commit_sha": "a" * 40,
            "skill_md_blob_sha": "b" * 40,
        }
        second = {**first, "source_record_id": "source-b", "commit_sha": "c" * 40}
        self.assertEqual(len(collapse_duplicate_results([first, second])), 2)

    def test_duplicate_content_with_different_security_evidence_is_not_collapsed(self):
        first = {
            "source_record_id": "source-a", "repository": "example/skills",
            "source_path": "skills/a/SKILL.md", "commit_sha": "a" * 40,
            "skill_md_blob_sha": "b" * 40, "security_status": "not_scanned",
        }
        second = {
            **first, "source_record_id": "source-b",
            "source_path": "plugins/a/SKILL.md",
            "security_status": "manual_review_required",
        }
        self.assertEqual(len(collapse_duplicate_results([first, second])), 2)

    def test_expansion_phrase_matches_token_boundaries(self):
        groups = query_term_groups("email integration", root=self.root)
        flattened = {token for group in groups for token in group}
        self.assertNotIn("agent", flattened)
        self.assertNotIn("artificial", flattened)

    def test_persian_agent_query_expands_to_english_skill_vocabulary(self):
        groups = query_term_groups("ساخت ایجنت هوش مصنوعی با ابزار و حافظه", root=self.root)
        flattened = {token for group in groups for token in group}
        self.assertIn("agent", flattened)
        self.assertIn("artificial", flattened)
        self.assertIn("tools", flattened)
        self.assertIn("memory", flattened)
        results = search_skills("ساخت ایجنت هوش مصنوعی با ابزار و حافظه", root=self.root)
        self.assertEqual(results[0]["skill_name"], "agent-memory-tools")
        self.assertGreater(results[0]["relevance_score"], 40)

    def test_phrase_completeness_ranks_wordpress_plugin_above_generic_plugins(self):
        results = search_skills("توسعه افزونه وردپرس", limit=5, root=self.root)
        self.assertEqual(results[0]["skill_name"], "content-management-systems")
        self.assertEqual(results[0]["query_coverage"], 1.0)
        minecraft = next(x for x in results if x["skill_name"] == "minecraft-plugin-development")
        self.assertLess(minecraft["query_coverage"], results[0]["query_coverage"])

    def test_security_is_not_expanded_to_unrelated_audit_concepts(self):
        groups = query_term_groups("امنیت API با پایتون", root=self.root)
        security_group = next(group for group in groups if "امنیت" in group)
        self.assertIn("security", security_group)
        self.assertNotIn("audit", security_group)
        self.assertNotIn("vulnerability", security_group)

    def test_persian_wordpress_plugin_query_expands_to_english(self):
        groups = query_term_groups("توسعه افزونه وردپرس", root=self.root)
        flattened = {token for group in groups for token in group}
        self.assertIn("wordpress", flattened)
        self.assertIn("plugin", flattened)
        self.assertIn("develop", flattened)

    def test_persian_nextjs_typescript_query_expands_to_english(self):
        groups = query_term_groups("توسعه وب سایت با نکست جی اس و تایپ اسکریپت", root=self.root)
        flattened = {token for group in groups for token in group}
        self.assertIn("next", flattened)
        self.assertIn("typescript", flattened)
        self.assertIn("website", flattened)

    def test_persian_spreadsheet_analysis_query_expands_to_english(self):
        groups = query_term_groups("تحلیل داده در اکسل و ساخت نمودار", root=self.root)
        flattened = {token for group in groups for token in group}
        self.assertIn("excel", flattened)
        self.assertIn("spreadsheet", flattened)
        self.assertIn("visualization", flattened)

    def test_persian_ci_cd_query_expands_to_github_actions(self):
        groups = query_term_groups("اتوماسیون تست و استقرار با گیت هاب اکشنز", root=self.root)
        flattened = {token for group in groups for token in group}
        self.assertIn("github", flattened)
        self.assertIn("actions", flattened)
        self.assertIn("automation", flattened)

    def test_english_seo_content_phrase_is_kept_as_one_concept(self):
        specs = query_term_group_specs("SEO content optimization", root=ROOT)
        exact = next(x for x in specs if x["label"] == "seo content optimization")
        self.assertEqual(exact["alternatives"], [["seo", "content", "optimization"]])
        self.assertGreater(exact["weight"], 1.0)

    def test_specific_technology_concepts_receive_explicit_priority(self):
        specs = query_term_group_specs("توسعه افزونه وردپرس", root=ROOT)
        wordpress = next(x for x in specs if "wordpress" in x["terms"])
        development = next(x for x in specs if x["label"] == "توسعه")
        self.assertGreater(wordpress["weight"], development["weight"])

    def test_description_evidence_outweighs_a_mention_only_in_full_skill_body(self):
        specs = query_term_group_specs("Next.js frontend development", root=ROOT)
        body_only = {
            "skill_name": "generic-guide", "description": "General engineering guidance.",
            "source_path": "skills/generic-guide/SKILL.md", "repository": "example/skills",
            "domains_text": "", "research_leads": "",
            "search_text": "Next.js frontend development",
        }
        focused = {
            "skill_name": "nextjs-frontend", "description": "Build Next.js frontend applications.",
            "source_path": "skills/nextjs-frontend/SKILL.md", "repository": "example/skills",
            "domains_text": "", "research_leads": "",
            "search_text": "Next.js frontend development",
        }
        self.assertGreater(
            _relevance_details("Next.js frontend development", focused, term_group_specs=specs)["score"],
            _relevance_details("Next.js frontend development", body_only, term_group_specs=specs)["score"],
        )

    def test_query_coverage_prevents_generic_title_from_beating_specific_match(self):
        results = search_skills("WordPress plugin development", limit=5, root=self.root)
        self.assertEqual(results[0]["skill_name"], "content-management-systems")
        minecraft = next(x for x in results if x["skill_name"] == "minecraft-plugin-development")
        self.assertEqual(results[0]["query_coverage"], 1.0)
        self.assertLess(minecraft["query_coverage"], 1.0)
        self.assertIn(["wordpress"], results[0]["matched_query_groups"])

    def test_common_query_stopwords_do_not_dominate_ranking(self):
        self.assertEqual(query_tokens("review a cloud configuration for security risks"),
                         ["review", "cloud", "configuration", "security", "risks"])

    def test_index_reuses_matching_inputs_and_rebuilds_after_change(self):
        first = build_index(self.root)
        second = ensure_index(self.root)
        self.assertEqual(first["record_count"], 7)
        self.assertTrue(second["reused"])
        path = self.root / "registry" / "source-catalog.json"
        data = json.loads(path.read_text())
        data["records"][0]["description"] += " risk management"
        path.write_text(json.dumps(data), encoding="utf-8")
        third = ensure_index(self.root)
        self.assertFalse(third["reused"])

    def test_fts_query_is_parameterized_and_empty_query_rejected(self):
        with self.assertRaises(ValueError):
            search_skills("the and for", root=self.root)
        # FTS syntax is escaped into quoted tokens, not passed through as raw operators.
        results = search_skills('security" OR *', root=self.root)
        self.assertIsInstance(results, list)


    def test_english_named_provider_negations_are_removed_and_excluded(self):
        positive, excluded = strip_query_exclusions(
            "Design a RAG system with Qdrant; explicitly do not use Pinecone or Databricks."
        )
        self.assertIn("Qdrant", positive)
        self.assertNotIn("Pinecone", positive)
        self.assertNotIn("Databricks", positive)
        self.assertTrue({"pinecone", "databricks"}.issubset(excluded))

    def test_standalone_not_excludes_named_cloud_provider(self):
        positive, excluded = strip_query_exclusions(
            "Provision AWS EKS with Terraform; AWS only, explicitly not Azure AKS."
        )
        self.assertIn("AWS", positive)
        self.assertNotIn("Azure", positive)
        self.assertTrue({"azure", "aks"}.issubset(excluded))

    def test_persian_suffix_negation_preserves_positive_kotlin_and_android(self):
        positive, excluded = strip_query_exclusions(
            "در اپ بومی اندروید با Kotlin و BroadcastReceiver پیامک بانکی را دریافت کن؛ راهکار Twilio یا Webhook سروری نمی‌خواهم."
        )
        self.assertIn("Kotlin", positive)
        self.assertIn("اندروید", positive)
        self.assertNotIn("Twilio", positive)
        self.assertNotIn("Webhook", positive)
        self.assertTrue({"twilio", "webhook"}.issubset(excluded))
        self.assertNotIn("kotlin", excluded)

    def test_negative_provider_filter_removes_irrelevant_results(self):
        catalog_path = self.root / "registry" / "source-catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog["records"].extend([
            record("s8", "rag-architect", "Design vendor-neutral RAG architecture with Qdrant and pgvector.",
                   "example/ai-skills", "skills/rag-architect/SKILL.md"),
            record("s9", "pinecone-rag", "Build RAG pipelines using Pinecone vector database.",
                   "example/pinecone-skills", "skills/pinecone-rag/SKILL.md"),
            record("s10", "databricks-vector-search", "Use Databricks vector search for RAG and semantic search.",
                   "example/databricks-skills", "skills/databricks-vector-search/SKILL.md"),
            record("s11", "aws-eks", "Deploy AWS EKS with Terraform and private networking.",
                   "example/aws-skills", "skills/aws-eks/SKILL.md"),
            record("s12", "azure-kubernetes", "Deploy Azure Kubernetes Service AKS clusters.",
                   "example/azure-skills", "skills/azure-kubernetes/SKILL.md"),
        ])
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        rag = search_skills(
            "Design a RAG system with Qdrant; do not use Pinecone or Databricks.",
            limit=10, root=self.root
        )
        rag_names = [x["skill_name"] for x in rag]
        self.assertIn("rag-architect", rag_names)
        self.assertNotIn("pinecone-rag", rag_names)
        self.assertNotIn("databricks-vector-search", rag_names)
        aws = search_skills(
            "Provision AWS EKS with Terraform; AWS only, explicitly not Azure AKS.",
            limit=10, root=self.root
        )
        aws_names = [x["skill_name"] for x in aws]
        self.assertIn("aws-eks", aws_names)
        self.assertNotIn("azure-kubernetes", aws_names)

    def test_persian_phrase_expansions_survive_punctuation_and_shared_words(self):
        taxonomy_path = self.root / "config" / "taxonomy.json"
        taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        taxonomy["query_expansions"].extend([
            {"terms": ["کنترل کیفیت داده"], "expand": ["data quality"]},
            {"terms": ["داده های تکراری"], "expand": ["duplicate data"]},
        ])
        taxonomy_path.write_text(json.dumps(taxonomy, ensure_ascii=False), encoding="utf-8")
        specs = query_term_group_specs("کنترل کیفیت داده، داده‌های تکراری", root=self.root)
        labels = {x["label"] for x in specs}
        self.assertIn("کنترل کیفیت داده", labels)
        self.assertIn("داده های تکراری", labels)
        flattened = {token for group in specs for token in group["terms"]}
        self.assertIn("duplicate", flattened)
        self.assertIn("quality", flattened)


    def test_accessibility_query_expands_screen_reader_focus_and_form_labels(self):
        taxonomy_path = self.root / "config" / "taxonomy.json"
        taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        taxonomy["query_expansions"].extend([
            {"terms": ["Screen Reader"], "expand": ["aria", "assistive technology"]},
            {"terms": ["Focus"], "expand": ["focus management", "keyboard focus", "tab order"]},
            {"terms": ["خطاهای فرم"], "expand": ["form validation", "form labels"]},
        ])
        taxonomy_path.write_text(json.dumps(taxonomy, ensure_ascii=False), encoding="utf-8")
        specs = query_term_group_specs(
            "Screen Reader Focus خطاهای فرم", root=self.root
        )
        by_label = {x["label"]: x for x in specs}
        self.assertIn(["aria"], by_label["screen reader"]["alternatives"])
        self.assertIn(["focus", "management"], by_label["focus"]["alternatives"])
        self.assertIn(["form", "labels"], by_label["خطاهای فرم"]["alternatives"])

    def test_persian_function_words_are_removed_without_removing_domain_terms(self):
        tokens = query_tokens("بر اساس بررسی باید کنترل کیفیت داده شوند")
        self.assertNotIn("بر", tokens)
        self.assertNotIn("اساس", tokens)
        self.assertNotIn("بررسی", tokens)
        self.assertNotIn("باید", tokens)
        self.assertNotIn("شوند", tokens)
        self.assertIn("داده", tokens)
        self.assertIn("کیفیت", tokens)



    def test_read_only_sqlite_connections_are_closed_after_search(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            ensure_index(self.root)
            get_skill_by_id("s1", root=self.root)
            search_skills("security audit", limit=3, root=self.root)
            gc.collect()
        leaked = [str(item.message) for item in caught
                  if issubclass(item.category, ResourceWarning)
                  and "unclosed database" in str(item.message).casefold()]
        self.assertEqual(leaked, [])



if __name__ == "__main__":
    unittest.main()
