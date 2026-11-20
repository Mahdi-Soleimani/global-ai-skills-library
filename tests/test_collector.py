import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import collector
from path_rules import is_test_fixture_path


class CollectorPathTests(unittest.TestCase):
    def test_excludes_generated_and_vendor_directories(self):
        self.assertTrue(collector.is_excluded_path("skills/demo/node_modules/pkg/index.js"))
        self.assertTrue(collector.is_excluded_path("skills/demo/.git/config"))
        self.assertFalse(collector.is_excluded_path("skills/demo/references/guide.md"))

    def test_eval_fixtures_are_classified_separately(self):
        self.assertTrue(is_test_fixture_path("evals/check-skills/fixtures/status-summary/SKILL.md"))
        self.assertFalse(is_test_fixture_path("plugins/codex-security/skills/security-scan/SKILL.md"))
        self.assertFalse(is_test_fixture_path("skills/webapp-testing/SKILL.md"))

    def test_skill_directory_discovery(self):
        paths = [
            "skills/a/SKILL.md",
            "skills/b/SKILL.md",
            "skills/b/nested/SKILL.md",
        ]
        self.assertEqual(
            collector.skill_dirs(paths),
            ["skills/a", "skills/b", "skills/b/nested"]
        )

    def test_parent_collection_excludes_nested_skill(self):
        paths = ["skills/parent/SKILL.md", "skills/parent/child/SKILL.md"]
        dirs = collector.skill_dirs(paths)
        self.assertTrue(
            collector.belongs_to_nested_skill("skills/parent/child/SKILL.md", "skills/parent", dirs)
        )
        self.assertFalse(
            collector.belongs_to_nested_skill("skills/parent/references/guide.md", "skills/parent", dirs)
        )


if __name__ == "__main__":
    unittest.main()
