import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from semantic_experiment import hybrid_order, verify_model, passage


class SemanticExperimentTests(unittest.TestCase):
    def test_hybrid_endpoints_and_determinism(self):
        similarities=[.3,.9,.5]
        self.assertEqual(hybrid_order(similarities,0),[0,1,2])
        self.assertEqual(hybrid_order(similarities,1),[1,2,0])
        self.assertEqual(hybrid_order([.5,.5]),[0,1])

    def test_missing_model_is_rejected_before_loading_runtime(self):
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaisesRegex(ValueError,"pinned model file"):
                verify_model(path)

    def test_passage_excludes_untrusted_instructions_and_domain_guesses(self):
        text=passage({"skill_name":"wordpress-plugin","source_path":"skills/plugin/SKILL.md",
                      "verified_feature_terms":["wordpress"],"search_text":"hidden body",
                      "domains_text":"unrelated domain vocabulary"})
        self.assertIn("wordpress plugin",text)
        self.assertNotIn("hidden body",text)
        self.assertNotIn("unrelated domain",text)
