#!/usr/bin/env python3
"""Standard-library GASL REST API and lightweight Explorer."""
import argparse
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from gasl_service import domains, health, route, search, skill_content, skill_details
from skill_compare import compare_skills

MAX_BODY_BYTES = 64 * 1024


def make_handler(root=ROOT, api_token=None):
    root = Path(root)

    class Handler(BaseHTTPRequestHandler):
        server_version = "GASL-API/0.1"
        sys_version = ""

        def log_message(self, fmt, *args):
            if os.environ.get("GASL_HTTP_LOG", "1") != "0":
                super().log_message(fmt, *args)

        def _send(self, status, body, content_type="application/json; charset=utf-8", extra_headers=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            for key, value in (extra_headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _json_error(self, status, message):
            self._send(status, {"detail": message})

        def _authorized(self, path):
            if not path.startswith("/v1/") or not api_token:
                return True
            header = self.headers.get("Authorization", "")
            supplied = header[7:] if header.lower().startswith("bearer ") else ""
            return bool(supplied) and hmac.compare_digest(supplied, api_token)

        def _params(self):
            return parse_qs(urlsplit(self.path).query, keep_blank_values=False)

        def _one(self, params, key, default=None):
            values = params.get(key)
            return values[0] if values else default

        def _bool(self, params, key, default=False):
            value = self._one(params, key)
            if value is None:
                return default
            return value.casefold() in ("1", "true", "yes", "on")

        def do_GET(self):
            parsed = urlsplit(self.path)
            path = parsed.path
            if path == "/":
                file_path = root / "web" / "index.html"
                if not file_path.is_file():
                    self._json_error(404, "GASL Explorer was not found.")
                    return
                self._send(200, file_path.read_bytes(), "text/html; charset=utf-8")
                return
            if path == "/health":
                self._send(200, health(root=root))
                return
            if not self._authorized(path):
                self._send(
                    401, {"detail": "A valid GASL bearer token is required."},
                    extra_headers={"WWW-Authenticate": "Bearer"},
                )
                return
            if path == "/v1/domains":
                items = domains(root=root)
                self._send(200, {"count": len(items), "domains": items})
                return
            if path == "/v1/search":
                params = parse_qs(parsed.query)
                query = self._one(params, "q", "").strip()
                if not query:
                    self._json_error(400, "Query parameter 'q' is required.")
                    return
                try:
                    limit = int(self._one(params, "limit", "10"))
                    if not 1 <= limit <= 100:
                        raise ValueError("limit must be between 1 and 100.")
                    result = search(
                        query=query,
                        limit=limit,
                        domain=self._one(params, "domain"),
                        license_spdx=self._one(params, "license_spdx"),
                        security_status=self._one(params, "security_status"),
                        public_only=self._bool(params, "public_only"),
                        content_only=self._bool(params, "content_only"),
                        root=root,
                    )
                    self._send(200, result)
                except ValueError as exc:
                    self._json_error(400, str(exc))
                return
            if path.startswith("/v1/skills/"):
                tail = path[len("/v1/skills/"):]
                if tail.endswith("/content"):
                    source_record_id = unquote(tail[:-len("/content")].rstrip("/"))
                    params = parse_qs(parsed.query)
                    try:
                        max_chars = int(self._one(params, "max_chars", "20000"))
                        fetch_remote = self._bool(params, "fetch_remote", True)
                        result = skill_content(
                            source_record_id, max_chars=max_chars, root=root,
                            fetch_remote=fetch_remote,
                        )
                        self._send(200, result)
                    except KeyError as exc:
                        self._json_error(404, str(exc))
                    except ValueError as exc:
                        self._json_error(400, str(exc))
                    except RuntimeError as exc:
                        self._json_error(502, str(exc))
                    return
                source_record_id = unquote(tail)
                try:
                    self._send(200, skill_details(source_record_id, root=root))
                except KeyError as exc:
                    self._json_error(404, str(exc))
                return
            self._json_error(404, "Endpoint not found.")

        def do_POST(self):
            path = urlsplit(self.path).path
            if not self._authorized(path):
                self._send(
                    401, {"detail": "A valid GASL bearer token is required."},
                    extra_headers={"WWW-Authenticate": "Bearer"},
                )
                return
            if path not in ("/v1/route", "/v1/compare"):
                self._json_error(404, "Endpoint not found.")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._json_error(400, "Invalid Content-Length.")
                return
            if length < 1 or length > MAX_BODY_BYTES:
                self._json_error(413, "Request body must be between 1 byte and {} bytes.".format(MAX_BODY_BYTES))
                return
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError("JSON request body must be an object.")
                if path == "/v1/compare":
                    self._send(200, compare_skills(body.get("ids"), root=root))
                    return
                task = body.get("task")
                if not isinstance(task, str) or not task.strip() or len(task) > 2000:
                    raise ValueError("'task' must be a non-empty string of at most 2000 characters.")
                top_k = int(body.get("top_k", 5))
                if not 1 <= top_k <= 20:
                    raise ValueError("'top_k' must be between 1 and 20.")
                strict_agent = body.get("strict_agent", False)
                if not isinstance(strict_agent, bool):
                    raise ValueError("'strict_agent' must be a JSON boolean.")
                for flag in ("public_only", "content_only"):
                    if flag in body and not isinstance(body[flag], bool):
                        raise ValueError("'{}' must be a JSON boolean.".format(flag))
                result = route(
                    task=task.strip(), top_k=top_k,
                    domain=body.get("domain"), license_spdx=body.get("license_spdx"),
                    agent=body.get("agent"), strict_agent=strict_agent,
                    public_only=body.get("public_only", False),
                    content_only=body.get("content_only", False), root=root,
                )
                self._send(200, result)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json_error(400, "Request body must be valid UTF-8 JSON.")
            except ValueError as exc:
                self._json_error(400, str(exc))
            except KeyError as exc:
                self._json_error(404, str(exc))

    return Handler


def create_server(host="127.0.0.1", port=8787, root=ROOT, api_token=None):
    token = api_token if api_token is not None else os.environ.get("GASL_API_TOKEN")
    return ThreadingHTTPServer((host, port), make_handler(root=root, api_token=token))


def main():
    parser = argparse.ArgumentParser(description="Run the GASL REST API and Explorer.")
    parser.add_argument("--host", default=os.environ.get("GASL_API_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("GASL_API_PORT", "8787")))
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "localhost", "::1") and not os.environ.get("GASL_API_TOKEN"):
        parser.error("GASL_API_TOKEN must be set before binding the API to a non-localhost interface.")
    server = create_server(args.host, args.port)
    print("GASL Explorer/API: http://{}:{}/".format(args.host, server.server_address[1]), flush=True)
    print("REST API: /v1/search, /v1/route, /v1/compare, /v1/skills/{id}, /v1/skills/{id}/content", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
