import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from safe_http import PinnedRawGitHubRedirectHandler


class PinnedRawGitHubRedirectTests(unittest.TestCase):
    def setUp(self):
        self.handler = PinnedRawGitHubRedirectHandler()
        self.request = urllib.request.Request(
            "https://raw.githubusercontent.com/example/repo/" + "a" * 40 + "/SKILL.md"
        )

    def test_same_host_https_redirect_is_allowed(self):
        result = self.handler.redirect_request(
            self.request, None, 302, "Found", {},
            "https://raw.githubusercontent.com/example/repo/" + "b" * 40 + "/SKILL.md",
        )
        self.assertIsNotNone(result)
        self.assertEqual(
            urllib.parse.urlsplit(result.full_url).hostname,
            "raw.githubusercontent.com",
        )

    def test_cross_host_redirect_is_blocked_before_following(self):
        targets = [
            "https://example.com/collect",
            "http://raw.githubusercontent.com/example/repo/SKILL.md",
            "https://raw.githubusercontent.com.evil.example/file",
            "https://user@raw.githubusercontent.com/example/repo/SKILL.md",
            "https://raw.githubusercontent.com:8443/example/repo/SKILL.md",
            "http://127.0.0.1:8080/internal",
        ]
        for target in targets:
            with self.subTest(target=target):
                with self.assertRaises(urllib.error.HTTPError):
                    self.handler.redirect_request(
                        self.request, None, 302, "Found", {}, target
                    )


if __name__ == "__main__":
    unittest.main()
