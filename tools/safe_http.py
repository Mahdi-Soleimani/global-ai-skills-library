#!/usr/bin/env python3
"""Small HTTPS fetch helper that rejects cross-host redirects before following them."""
import urllib.error
import urllib.parse
import urllib.request


class PinnedRawGitHubRedirectHandler(urllib.request.HTTPRedirectHandler):
    allowed_host = "raw.githubusercontent.com"

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        approved = (
            parsed.scheme == "https"
            and parsed.hostname == self.allowed_host
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
        )
        if not approved:
            raise urllib.error.HTTPError(
                req.full_url,
                code,
                "Blocked redirect to an unapproved host.",
                headers,
                fp,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_pinned_url(request, timeout=20):
    """Open a request while allowing redirects only within the pinned raw host."""
    opener = urllib.request.build_opener(PinnedRawGitHubRedirectHandler())
    return opener.open(request, timeout=timeout)
