"""Install/check only GASL's optional local MCP runtime; never edit Host config."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 10)
MCP_VERSION = "2.3.0"


def isolated_env():
    env = dict(os.environ)
    for name in list(env):
        if name.upper() in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
            env.pop(name)
    env["PYTHONNOUSERSITE"] = "1"
    return env


def runtime_python(root=ROOT):
    folder = Path(root) / ".venv"
    return folder / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _redirected(path):
    # Do not follow a redirected environment directory or config file.
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)


def validate_layout(root=ROOT):
    folder = Path(root) / ".venv"
    cfg = folder / "pyvenv.cfg"
    python = runtime_python(root)
    if not folder.is_dir() or _redirected(folder):
        raise ValueError("Local .venv is missing or redirected; create a fresh local environment.")
    if not cfg.is_file() or _redirected(cfg) or cfg.stat().st_size > 16384:
        raise ValueError("Invalid local .venv configuration; inspect it manually.")
    values = {}
    for line in cfg.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip().casefold()
            if key in values:
                raise ValueError("Duplicate local .venv configuration key.")
            values[key] = value.strip().casefold()
    if values.get("include-system-site-packages") != "false":
        raise ValueError("Local .venv must exclude system site-packages.")
    if not python.parent.is_dir() or _redirected(python.parent) or not python.is_file():
        raise ValueError("Local .venv interpreter is missing or its directory is redirected.")
    # A normal POSIX venv interpreter may itself be a symlink to the base Python.
    if os.name == "nt" and _redirected(python):
        raise ValueError("Redirected Windows local interpreter.")
    return python


def _run(python, *args):
    return subprocess.run([str(python), "-I", "-B", "-X", "utf8", *args],
                          env=isolated_env(), check=True)


def verify_runtime(root=ROOT, *, require_mcp=True):
    python = validate_layout(root)
    # Check the executing interpreter, not an import visible in the invoking app.
    code = """
import sys
from pathlib import Path
expected = Path(sys.argv[1]).resolve()
if sys.version_info < (3, 10) or Path(sys.prefix).resolve() != expected or sys.prefix == sys.base_prefix:
    raise SystemExit('Wrong or unsupported local Python environment')
if sys.argv[2] == 'yes':
    import importlib.metadata as metadata
    import mcp
    dist = metadata.distribution('mcp')
    if (dist.version != sys.argv[3] or not Path(mcp.__file__).resolve().is_relative_to(expected)
            or not Path(dist.locate_file('')).resolve().is_relative_to(expected)):
        raise SystemExit('Pinned MCP SDK is not installed in the local environment')
"""
    _run(python, "-c", code, str(Path(root)/".venv"), "yes" if require_mcp else "no", MCP_VERSION)
    return python


def setup(root=ROOT, *, check=False):
    root = Path(root).resolve()
    if sys.version_info < MIN_PYTHON:
        raise ValueError("Python 3.10 or newer is required.")
    if not check:
        folder = root / ".venv"
        if not folder.exists() and not folder.is_symlink():
            _run(sys.executable, "-m", "venv", str(folder))
        python = verify_runtime(root, require_mcp=False)
        # Explicit user installation; avoid user-site, injected Python paths and pip cache.
        _run(python, "-m", "pip", "--isolated", "install", "--disable-pip-version-check",
             "--no-cache-dir", "--no-input", "-r", str(root/"requirements-mcp.txt"))
    python = verify_runtime(root)
    print("GASL local MCP runtime verified: Python 3.10+, MCP "+MCP_VERSION)
    return python


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify existing local runtime without installing")
    args = parser.parse_args()
    try:
        setup(check=args.check)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print("GASL runtime setup failed: "+str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
