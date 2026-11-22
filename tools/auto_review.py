#!/usr/bin/env python3
"""Reproducible, internal-only proxy evaluation. NEVER produce human gold labels."""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from search_benchmark import metrics_for_results
from skill_search import search_skills
from skill_router import route_task

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'private' / 'benchmark-review'
DEFAULT_OUTPUT = REVIEW / 'AUTOMATED-PROXY-EVALUATION-V1.json'

# Task-specific terms are independent of GASL result rank and generated search scores.
# Ordered: core concepts (mandatory), then useful supplementary capabilities.
REQUIREMENTS = {
    'oauth-pkce': {
        'core': [('oauth',), ('pkce', 'proof key')],
        'other': [('authorization code', 'auth code', 'code flow'), ('token', 'refresh'), ('tenant', 'saas')],
    },
    'postgres-tuning': {
        'core': [('postgres', 'postgresql'), ('explain analyze', 'explain', 'query plan'), ('index', 'indexes', 'indexing')],
        'other': [('slow', 'performance', 'tuning', 'optimiz'), ('query', 'sql')],
    },
    'rag-pdf-ingestion': {
        'core': [('rag', 'retrieval augmented', 'retrieval'), ('pdf', 'document'), ('chunk', 'splitting')],
        'other': [('metadata',), ('ingest', 'pipeline', 'loader'), ('embedding', 'vector')],
    },
    'llm-agent-eval': {
        'core': [('agent', 'llm'), ('evaluation', 'eval', 'benchmark', 'testing')],
        'other': [('scoring', 'score', 'metric'), ('regression', 'repeatab'), ('test case', 'scenario', 'test suite')],
    },
    'android-banking-sms': {
        'core': [('android',), ('sms', 'text message'), ('broadcastreceiver', 'sms_received', 'telephony.sms')],
        'other': [('kotlin',), ('transaction', 'banking', 'bank'), ('sender', 'message body', 'message text')],
        'exclude_context': [('twilio', 'twiml', 'webhook', 'azure communication')],
    },
    'playwright-workflow': {
        'core': [('playwright',), ('browser', 'web automation')],
        'other': [('selector', 'locator'), ('screenshot',), ('workflow', 'multi-step', 'automate')],
    },
    'kubernetes-helm': {
        'core': [('kubernetes', 'k8s'), ('helm',)],
        'other': [('probe', 'health check', 'readiness'), ('resource limit', 'limits'), ('deploy', 'deployment', 'container')],
    },
    'etl-data-quality': {
        'core': [('etl', 'extract transform load', 'data pipeline'), ('quality', 'validation', 'validat')],
        'other': [('batch',), ('check', 'rule'), ('pipeline', 'transformation')],
    },
    'agent-prompt-injection': {
        'core': [('prompt injection', 'injection'), ('agent', 'tool')],
        'other': [('untrusted', 'attacker', 'adversarial'), ('threat model', 'security', 'threat'), ('file', 'external tool')],
    },
    'wcag-design-system': {
        'core': [('wcag', 'accessibility', 'a11y'), ('design system', 'ui component', 'interface design')],
        'other': [('contrast',), ('keyboard', 'focus'), ('screen reader', 'aria')],
    },
    'saas-unit-economics': {
        'core': [('saas', 'subscription'), ('unit economics', 'unit economic', 'ltv', 'cac', 'customer acquisition')],
        'other': [('churn', 'retention'), ('arpu', 'revenue'), ('margin', 'profit')],
    },
    'literature-review': {
        'core': [('literature', 'research', 'paper'), ('review', 'systematic review', 'synthesis')],
        'other': [('citation', 'reference'), ('study', 'studies'), ('source', 'evidence'), ('meta analysis', 'meta-analysis')],
    },
    'api-technical-docs': {
        'core': [('api', 'endpoint', 'openapi'), ('documentation', 'docs', 'technical writing')],
        'other': [('example', 'sample', 'snippet'), ('schema', 'specification'), ('developer', 'integration')],
    },
}


def has_term(text, term):
    """Match entire short words and full technical identifiers; allow long stems."""
    if term.endswith('iz') or term.endswith('at') or term.endswith('ab'):
        return re.search(r'(?<!\w)' + re.escape(term), text) is not None
    return re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', text) is not None


def evaluate_candidate(pair, record, strict=False):
    requirements = REQUIREMENTS[pair]
    text = ' '.join(str(record.get(key) or '') for key in ('skill_name','description','search_text')).casefold()
    core_hits = [any(has_term(text, term) for term in terms) for terms in requirements['core']]
    other_hits = [any(has_term(text, term) for term in terms) for terms in requirements['other']]
    core_count, total_core = sum(core_hits), len(core_hits)
    hits, total = core_count + sum(other_hits), total_core + len(other_hits)
    fraction = hits / total if total else 0
    excluded = sum(any(has_term(text, term) for term in terms) for terms in requirements.get('exclude_context', []))
    if core_count == total_core and fraction >= (0.80 if strict else 0.65):
        grade = 3
    elif core_count == total_core and fraction >= (0.48 if strict else 0.35):
        grade = 2
    elif core_count >= 1 or fraction >= 0.30:
        grade = 1
    else:
        grade = 0
    # Provider-side SMS should never be graded as device-side Android reception.
    if pair == 'android-banking-sms' and (not all(core_hits) or excluded):
        grade = min(1, grade)
    return {
        'grade': grade,
        'core_coverage': round(core_count / total_core, 4) if total_core else 0,
        'concept_coverage': round(fraction, 4),
        'core_hits': core_hits,
        'extra_hits': other_hits,
        'context_exclusion_hit': bool(excluded),
    }


def evaluate(root=ROOT, review=REVIEW):
    root, review = Path(root), Path(review)
    manifest = json.loads((review / 'SEARCH-GOLD-V2-QUERY-MANIFEST.json').read_text(encoding='utf-8'))
    metadata = json.loads((root / 'private' / 'skill-metadata-cache.json').read_text(encoding='utf-8'))['records']
    with (review / 'SEARCH-GOLD-V2-REVIEWER-A-INTAKE-V2.csv').open(encoding='utf-8-sig', newline='') as file:
        candidates = list(csv.DictReader(file))
    pairs = {item['pair_id'] for item in candidates}
    if pairs != set(REQUIREMENTS):
        raise ValueError('Rubric pair IDs differ from active benchmark manifest')
    if len(candidates) != manifest['candidate_count_total']:
        raise ValueError('Candidate pool does not match the active benchmark manifest')
    if not all(item['source_record_id'] in metadata for item in candidates):
        raise ValueError('Missing pinned metadata for a candidate')
    evaluated=[]
    by_pair = {pair:{} for pair in pairs}
    for row in candidates:
        pair, source_id = row['pair_id'], row['source_record_id']
        candidate = metadata[source_id]
        if candidate.get('commit_sha') != row['commit_sha'] or candidate.get('source_path') != row['source_path']:
            raise ValueError('Pinned metadata mismatch: '+source_id)
        regular = evaluate_candidate(pair, candidate, strict=False)
        strict = evaluate_candidate(pair, candidate, strict=True)
        grade = min(regular['grade'], strict['grade'])
        by_pair[pair][source_id]=grade
        evaluated.append({
            'pair_id':pair,'source_record_id':source_id,'skill_name':row['skill_name'],
            'regular_grade':regular['grade'],'strict_grade':strict['grade'],
            'consensus_proxy_grade':grade,'disagrees':regular['grade']!=strict['grade'],
            'core_coverage':strict['core_coverage'],'concept_coverage':strict['concept_coverage'],
            'source_pin':row['commit_sha'],'evidence_scope':'cached verified 1800-character skill text; not full behavioral execution',
        })
    query_reports=[]
    for query in manifest['queries']:
        pair=query['pair_id']
        grades=by_pair[pair]
        eligible=sum(g>=2 for g in grades.values())
        # No strong match in the audited pool is NOT proof of catalog absence.
        provisional_status='proxy_answerable' if eligible else 'uncertain_coverage_gap'
        results=search_skills(query['query'],limit=10,root=root)
        router=route_task(query['query'],top_k=5,root=root)
        metrics=metrics_for_results(results,grades,k=5,mrr_k=10) if eligible else None
        query_reports.append({
            'query_id':query['id'],'pair_id':pair,'language':query['language'],
            'provisional_answerability':provisional_status,'pooled_relevant_proxy_count':eligible,
            'router_decision_experimental':router['routing_decision'],
            'router_reason_code':router['answerability']['reason_code'],
            'router_policy_version':router['answerability']['policy_version'],
            'retrieval_metrics_proxy':metrics,
            'top5':[
                {'skill_name':r.get('skill_name'),'source_ids':r.get('source_record_ids') or [r.get('source_record_id')],
                 'proxy_grade':max((grades.get(sid,0) for sid in (r.get('source_record_ids') or [r.get('source_record_id')])),default=0)}
                for r in results[:5]
            ],
        })
    metrics=[q['retrieval_metrics_proxy'] for q in query_reports if q['retrieval_metrics_proxy']]
    summaries={key:round(sum(row[key] for row in metrics)/len(metrics),4) if metrics else None for key in ('precision_at_k','recall_at_k','mrr_at_k','ndcg_at_k')}
    return {
        'schema_version':'auto-proxy-v1',
        'status':'internal_weak_labels_not_human_gold_not_independent',
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'source_catalog_sha256':hashlib.sha256((root/'registry/source-catalog.json').read_bytes()).hexdigest(),
        'review_manifest_sha256':hashlib.sha256((review/'SEARCH-GOLD-V2-QUERY-MANIFEST.json').read_bytes()).hexdigest(),
        'cached_metadata_sha256':hashlib.sha256((root/'private/skill-metadata-cache.json').read_bytes()).hexdigest(),
        'candidate_count':len(evaluated),
        'query_count':len(query_reports),
        'pair_count':len(pairs),
        'grade_distribution':dict(sorted(Counter(str(r['consensus_proxy_grade']) for r in evaluated).items())),
        'auto_reviewer_grade_disagreement_count':sum(r['disagrees'] for r in evaluated),
        'answerability_summary':dict(sorted(Counter(r['provisional_answerability'] for r in query_reports).items())),
        'metrics_on_proxy_answerable_queries_only':summaries,
        'metric_query_count':len(metrics),
        'router_decisions_on_proxy_answerable':dict(sorted(Counter(r['router_decision_experimental'] for r in query_reports if r['provisional_answerability']=='proxy_answerable').items())),
        'router_decisions_on_uncertain_gaps':dict(sorted(Counter(r['router_decision_experimental'] for r in query_reports if r['provisional_answerability']=='uncertain_coverage_gap').items())),
        'limitations':[
            'Two thresholds are two variants of the same deterministic heuristic, NOT independent reviewers.',
            'Proxy grades use cached first 1800 characters of pinned Skill text and may miss relevant details.',
            'The same text may contribute to search indexing and proxy grading: measured retrieval metrics are not independent quality evidence.',
            'Unjudged sources outside the candidate pool count as zero under proxy metrics.',
            'No no-answer gold labels are created; uncertain coverage gap is not corpus-wide absence.',
            'No threshold was tuned on independent human gold. A Router recommendation is advisory, not security approval.',
        ],
        'candidate_grades':evaluated,
        'queries':query_reports,
    }


def main():
    parser=argparse.ArgumentParser(description='Run internal rubric-based proxy review; does not create gold data.')
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--review',type=Path,default=REVIEW)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    result=evaluate(args.root,args.review)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key not in ('candidate_grades','queries')},ensure_ascii=False,indent=2))
    print('report='+str(args.output))

if __name__=='__main__':
    main()
