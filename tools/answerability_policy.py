#!/usr/bin/env python3
"""Conservative, transparent heuristic routing decisions — NOT calibrated truth."""
import re

POLICY_VERSION = '0.2.0-experimental'
POLICY_STATUS = 'experimental_heuristic_not_calibrated'
# Generic and ambiguous acronyms should not be treated as indispensable identifiers.
GENERIC_ACRONYMS = {'API', 'AI', 'UI', 'UX', 'SDK', 'HTTP', 'JSON', 'CSV', 'HTML', 'CSS', 'PDF', 'LLM', 'SQL', 'SAAS'}


def technical_identifiers(query):
    """Identify uncommon syntax-bearing technical names without corpus or task hardcoding."""
    found=[]
    for word in re.findall(r'(?<!\w)[A-Za-z][\w]*(?!\w)', query):
        if word.upper() in GENERIC_ACRONYMS:
            continue
        # Preserve exact-cased acronyms and embedded-uppercase identifiers.
        technical = (len(word)>=3 and word.isupper()) or re.search(r'[a-z][A-Z]', word)
        if technical and word.casefold() not in {x.casefold() for x in found}:
            found.append(word)
    return found


def _has_group_match(candidate, identifier):
    target=identifier.casefold()
    for group in candidate.get('query_group_coverage') or []:
        label=str(group.get('label') or '').casefold().replace(' ','').replace('_','').replace('-','')
        term=target.replace('_','').replace('-','')
        if term == label and float(group.get('coverage') or 0)>0.0:
            return True
    # Sometimes a compound identifier appears in a title/description instead of a query group.
    public_text=' '.join(str(candidate.get(k) or '') for k in ('skill_name','description')).casefold()
    return bool(re.search(r'(?<!\w)'+re.escape(target)+r'(?!\w)',public_text))


def decide(query, candidates):
    """Return a recommendation/search-abstain/undetermined decision using only visible evidence.

    Here 'abstain' means *insufficient retrieved evidence*, NOT the proof that a
    relevant Skill is absent from the entire corpus. Neither this function nor
    the router installs/executes a Skill.
    """
    if not candidates:
        return {
            'decision':'abstain', 'reason_code':'no_eligible_candidates',
            'reason':'No eligible candidate remained after retrieval and filters; catalog absence is not established.',
            'matched_technical_identifiers':[], 'unmatched_technical_identifiers':technical_identifiers(query),
            'top_query_coverage':0.0,
        }
    shortlist=candidates[:5]
    identifiers=technical_identifiers(query)
    matched=[item for item in identifiers if any(_has_group_match(c,item) for c in shortlist)]
    missing=[item for item in identifiers if item not in matched]
    top=shortlist[0]
    coverage=float(top.get('query_coverage') or 0.0)
    if missing:
        decision='abstain'
        reason_code='required_technical_identifiers_not_supported_by_top_candidates'
        reason='None of the leading candidates demonstrates all exact technical identifiers; no confident recommendation can be made.'
    elif coverage >= 0.52 and float(top.get('relevance_score') or 0)>0:
        decision='recommend'
        reason_code='strong_lexical_match_in_discovery_pool'
        reason='Leading candidate has broad lexical coverage and no uncovered exact technical identifiers; review the candidate and its security evidence before use.'
    elif coverage < 0.18:
        decision='abstain'
        reason_code='very_low_candidate_coverage'
        reason='Leading candidates have insufficient lexical coverage for a defensible suggestion; no corpus-wide absence is inferred.'
    else:
        decision='undetermined'
        reason_code='partial_or_ambiguous_evidence'
        reason='Some relevant terms matched, but the evidence is insufficient for a confident heuristic suggestion.'
    return {
        'decision':decision,'reason_code':reason_code,'reason':reason,
        'matched_technical_identifiers':matched,'unmatched_technical_identifiers':missing,
        'top_query_coverage':round(coverage,4),
    }
