"""Portable CLI/STDIO launcher; no install, download, or configuration edits."""
import os
import subprocess
import sys
from pathlib import Path

# Python -I excludes script directory; restore only the trusted local tools path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runtime_setup import ROOT, MIN_PYTHON, isolated_env, validate_layout


def main():
    try:
        if sys.version_info < MIN_PYTHON:
            raise ValueError("Python 3.10 or newer is required.")
        folder = ROOT / ".venv"
        python = validate_layout(ROOT) if folder.exists() or folder.is_symlink() else sys.executable
        argv = [str(python), "-I", "-B", "-X", "utf8", str(ROOT/"tools/gasl.py"), *sys.argv[1:]]
        if os.name == "posix":
            os.execve(str(python), argv, isolated_env())
        return subprocess.call(argv, env=isolated_env())
    except (OSError, ValueError) as exc:
        print("GASL launcher: "+str(exc),file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
