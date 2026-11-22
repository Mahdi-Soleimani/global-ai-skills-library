import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from auto_review import REQUIREMENTS,evaluate_candidate,has_term


class AutoReviewTests(unittest.TestCase):
    def test_thirteen_bilingual_task_rubrics_exist(self):
        self.assertEqual(len(REQUIREMENTS),13)
        self.assertIn('android-banking-sms',REQUIREMENTS)

    def test_android_server_side_twilio_does_not_count_as_direct_receiver(self):
        record={'skill_name':'twilio-messaging-webhooks','description':'Twilio inbound SMS webhook in Python.',
                'search_text':'Incoming SMS through Twilio HTTP POST webhook and TwiML responses.'}
        self.assertLessEqual(evaluate_candidate('android-banking-sms',record)['grade'],1)

    def test_android_receiver_has_core_evidence(self):
        record={'skill_name':'android-sms-receiver','description':'Device-side Android SMS BroadcastReceiver Kotlin banking transactions.',
                'search_text':'SMS_RECEIVED Telephony sender and message body extracting bank transaction.'}
        self.assertGreaterEqual(evaluate_candidate('android-banking-sms',record,strict=True)['grade'],2)

    def test_technical_terms_do_not_match_unrelated_substrings(self):
        self.assertFalse(has_term('chromatograph','rag'))
        self.assertTrue(has_term('pdf chunking and rag retrieval','rag'))

    def test_weak_labels_do_not_depend_on_candidate_rank(self):
        candidate={'skill_name':'browser-automation','description':'Automate browser tasks with Playwright and screenshots.',
                   'search_text':'Resilient selectors and locators, multistep browser workflows.'}
        a=evaluate_candidate('playwright-workflow',candidate,strict=True)
        candidate['relevance_score']=9999
        candidate['query_coverage']=0.0
        b=evaluate_candidate('playwright-workflow',candidate,strict=True)
        self.assertEqual(a,b)

if __name__=='__main__': unittest.main()
