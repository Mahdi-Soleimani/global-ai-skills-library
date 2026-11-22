#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PYTHON=python3
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Python 3.10+ is required. Install Python, then run ./install.sh again." >&2
  exit 1
fi

"$PYTHON" - <<'PYTHON'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("GASL MCP requires Python 3.10 or newer.")
print("Using Python {}.{}".format(*sys.version_info[:2]))
PYTHON

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  "$PYTHON" -m venv "$ROOT/.venv"
fi

env -u PYTHONPATH "$ROOT/.venv/bin/python" -m pip install --disable-pip-version-check -r "$ROOT/requirements-mcp.txt"

echo
echo "GASL is ready."
echo "Start the local MCP server with: ./gasl mcp"
echo "Try local search with: ./gasl search --query 'security audit'"
echo "No API key, paid service, Docker, or hosted GASL server is required."
