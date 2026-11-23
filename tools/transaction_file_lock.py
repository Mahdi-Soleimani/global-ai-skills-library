#!/usr/bin/env python3
"""Portable advisory lock and Windows junction checks for GASL transactions.

Locks coordinate cooperating GASL processes, not arbitrary external writers.
The lock remains acquired throughout transaction journal / rename / receipt.
"""
import contextlib
import os
import re
import time
from pathlib import Path

try:
    import fcntl
except ImportError:
    fcntl = None
try:
    import msvcrt
except ImportError:
    msvcrt = None


def supported_platform():
    return (os.name == "posix" and fcntl is not None) or (
        os.name == "nt" and msvcrt is not None)


def is_redirected(path):
    """Reject links *and* NTFS junctions (Path.is_symlink misses junctions)."""
    path = Path(path)
    return path.is_symlink() or (
        hasattr(path, "is_junction") and path.is_junction())


@contextlib.contextmanager
def exclusive_lock_file(path, *, attempts=35, pause_seconds=0.10):
    """Use a secure permanent lockfile with POSIX flock or Windows byte lock.

    Windows LK_NBLCK waits explicitly with a bounded timeout instead of
    relying on LK_LOCK's implicit retries. Lock file is never truncated.
    """
    if not supported_platform():
        raise ValueError("GASL transaction locking needs POSIX or Windows")
    path = Path(path)
    if is_redirected(path) or (path.exists() and not path.is_file()):
        raise ValueError("Unsafe host transaction lock (symlink, junction or non-regular file)")
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "a+b") as stream:
        if os.name == "posix":
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield stream
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)
        else:
            # Windows lock applies at current seek offset for one byte.
            stream.seek(0)
            if path.stat().st_size == 0:
                stream.write(b"\0")
                stream.flush()
                os.fsync(stream.fileno())
            acquired = False
            try:
                for i in range(attempts):
                    try:
                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                        acquired = True
                        break
                    except OSError:
                        if i + 1 == attempts:
                            raise ValueError("Concurrent GASL Windows transaction lock busy")
                        time.sleep(pause_seconds)
                yield stream
            finally:
                if acquired:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


_WINDOWS_DEVICES = frozenset(("CON", "PRN", "AUX", "NUL")
                             + tuple("COM"+str(n) for n in range(1,10))
                             + tuple("LPT"+str(n) for n in range(1,10)))


def require_windows_filename_safety(path):
    """Fail-closed for Windows-only file name aliases, ADS and device names."""
    if os.name != "nt":
        return path
    if not isinstance(path,str) or not path or "\\" in path:
        raise ValueError("Unsafe Windows ZIP relative filename")
    for component in path.split("/"):
        if (not component or component in (".", "..") or
                component[-1] in ". " or
                re.search(r'[<>:"|?*\\]',component) or
                component.upper().split(".")[0] in _WINDOWS_DEVICES or
                any(ord(c)<32 for c in component)):
            raise ValueError("Windows-reserved Skill ZIP path component")
    return path
