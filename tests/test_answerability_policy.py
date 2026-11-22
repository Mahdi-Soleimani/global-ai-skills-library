import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from answerability_policy import decide, technical_identifiers


def c(score=10, coverage=.6, groups=None, name='skill'):
    return {
        'relevance_score':score, 'query_coverage':coverage,
        'query_group_coverage':[{'label':label,'coverage':match} for label,match in (groups or [])],
        'skill_name':name, 'description':'',
    }


class AnswerabilityPolicyTests(unittest.TestCase):
    def test_strong_coverage_is_provisional_recommend(self):
        r=decide('WordPress plugin development',[c(20,.8, name='wordpress-cms')])
        self.assertEqual(r['decision'],'recommend')
        self.assertEqual(r['reason_code'],'strong_lexical_match_in_discovery_pool')

    def test_android_broadcastreceiver_missing_forces_abstain(self):
        query='Build Android Kotlin banking SMS BroadcastReceiver parser'
        r=decide(query,[c(35,.8,[('android',1),('sms',1),('kotlin',1),('broadcastreceiver',0)])])
        self.assertEqual(r['decision'],'abstain')
        self.assertIn('BroadcastReceiver',r['unmatched_technical_identifiers'])

    def test_all_technical_identifiers_present_allows_recommend(self):
        r=decide('Implement OAuth 2.1 PKCE',[
            c(20,.8,[('oauth',1),('pkce',1)])
        ])
        self.assertEqual(r['decision'],'recommend')

    def test_partial_coverage_is_undetermined(self):
        self.assertEqual(decide('Run a carefully specified protocol', [c(10,.4)])['decision'],'undetermined')

    def test_very_low_coverage_abstains(self):
        self.assertEqual(decide('generic large task', [c(12,.1)])['decision'],'abstain')

    def test_empty_candidates_abstain_without_claiming_absence(self):
        r=decide('unknown technology',[])
        self.assertEqual(r['decision'],'abstain')
        self.assertEqual(r['reason_code'],'no_eligible_candidates')

    def test_common_acronyms_are_not_required(self):
        self.assertEqual(technical_identifiers('Build an API with JSON for LLM'),[])


if __name__=='__main__':
    unittest.main()
