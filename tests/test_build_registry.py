import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_registry import merge_previous_registry_records


class BuildRegistryTests(unittest.TestCase):
    def test_preserves_old_public_metadata_when_runner_has_no_local_catalog(self):
        previous = [
            {"repository": "Org/Repo", "source_skill_path": "skills/a/SKILL.md",
             "commit_sha": "a" * 40, "package_path": "catalog/a",
             "package_complete": True, "skill_name": "a"},
            {"repository": "Org/Repo", "source_skill_path": "skills/b/SKILL.md",
             "commit_sha": "b" * 40, "package_path": "catalog/b",
             "package_complete": True, "skill_name": "b"}
        ]
        current = [{"repository": "Org/Repo", "source_skill_path": "skills/a/SKILL.md",
                    "commit_sha": "a" * 40, "skill_name": "a-new"}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "catalog/a").mkdir(parents=True)
            (root / "catalog/a/source.json").write_text("{}")
            result = merge_previous_registry_records(current, previous, root)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["skill_name"], "a-new")
        self.assertTrue(result[1]["historical_registry_record"])
        self.assertFalse(result[1]["package_content_present"])
        self.assertEqual(result[1]["content_status"], "historical_package_metadata_only_content_not_on_runner")

    def test_does_not_duplicate_historical_records(self):
        previous = [{"repository": "Org/Repo", "source_skill_path": "skills/a/SKILL.md",
                     "commit_sha": "a" * 40}]
        current = [{"repository": "org/repo", "source_skill_path": "skills/a/SKILL.md",
                    "commit_sha": "a" * 40}]
        with tempfile.TemporaryDirectory() as tmp:
            result = merge_previous_registry_records(current, previous, Path(tmp))
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
