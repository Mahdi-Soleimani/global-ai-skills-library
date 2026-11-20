import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_registry


class RegistryParsingTests(unittest.TestCase):
    def test_frontmatter_name_and_multiline_description(self):
        text = """---
name: sample-skill
description: |
  Helps with a specific task.
  Handles the common edge cases.
---
Body
"""
        data = build_registry.parse_frontmatter(text)
        self.assertTrue(data["_valid"])
        self.assertEqual(data["name"], "sample-skill")
        self.assertIn("common edge cases", data["description"])

    def test_missing_required_frontmatter_is_invalid(self):
        data = build_registry.parse_frontmatter("---\ndescription: missing name\n---\n")
        self.assertFalse(data["_valid"])

    def test_test_fixture_is_not_classified_as_installable_skill(self):
        meta = {"source_skill_path": "evals/check-skills/fixtures/status-summary/SKILL.md"}
        self.assertEqual(build_registry.classify_package(meta), "test_fixture")
        meta = {"source_skill_path": "plugins/codex-security/skills/security-scan/SKILL.md"}
        self.assertEqual(build_registry.classify_package(meta), "skill_candidate")

    def test_normalized_hash_ignores_line_endings_and_trailing_spaces(self):
        a = "name: x  \r\ndescription: y\r\n"
        b = "name: x\ndescription: y\n"
        self.assertEqual(build_registry.normalized_content_hash(a),
                         build_registry.normalized_content_hash(b))


if __name__ == "__main__":
    unittest.main()
