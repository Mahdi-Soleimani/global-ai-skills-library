#!/usr/bin/env python3
"""Fail-closed Windows current-user profile identity, reparse-point and ACL checks.

Uses the current process token and native Win32 security APIs. No subprocess,
localized icacls parsing, third-party package, or implicit HOME discovery.
"""
import ctypes
import hashlib
import os
from pathlib import Path

if os.name == "nt":
    from ctypes import wintypes


_TOKEN_QUERY = 0x0008
_TOKEN_USER_CLASS = 1
_TOKEN_ELEVATION = 20
_TOKEN_HAS_RESTRICTIONS = 21
_TOKEN_IS_APP_CONTAINER = 29
_ERROR_NO_TOKEN = 1008
_SE_FILE_OBJECT = 1
_OWNER_SECURITY_INFORMATION = 0x00000001
_DACL_SECURITY_INFORMATION = 0x00000004
_ACL_SIZE_INFORMATION_CLASS = 2
_INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400

# ACCESS_ALLOWED_ACE_TYPE, ACCESS_ALLOWED_OBJECT_ACE_TYPE and callback forms.
_ALLOWED_ACE_TYPES = frozenset((0, 5, 9, 11))
_OBJECT_ACE_TYPES = frozenset((5, 11))
_INHERIT_ONLY_ACE = 0x08
# Do not OR FILE_GENERIC_WRITE / FILE_ALL_ACCESS into this mask: those
# aggregate masks also contain READ_CONTROL and SYNCHRONIZE, which are shared
# with read-only ACEs. Detect only write-specific bits plus the two unexpanded
# generic rights. Expanded GENERIC_WRITE / GENERIC_ALL already contain the
# specific bits below.
_WRITE_MASK = (
    0x00000002 |  # FILE_WRITE_DATA / FILE_ADD_FILE
    0x00000004 |  # FILE_APPEND_DATA / FILE_ADD_SUBDIRECTORY
    0x00000010 |  # FILE_WRITE_EA
    0x00000040 |  # FILE_DELETE_CHILD
    0x00000100 |  # FILE_WRITE_ATTRIBUTES
    0x00010000 |  # DELETE
    0x00040000 |  # WRITE_DAC
    0x00080000 |  # WRITE_OWNER
    0x01000000 |  # ACCESS_SYSTEM_SECURITY
    0x10000000 |  # GENERIC_ALL (unexpanded)
    0x40000000    # GENERIC_WRITE (unexpanded)
)


def _ace_grants_write(mask):
    """Classify write capability without mistaking shared read bits as writes."""
    return bool(int(mask) & _WRITE_MASK)


# Creating a sibling in a parent directory cannot modify an already-existing
# profile entry. For ancestors, reject only rights that can remove/replace the
# profile entry or take over its parent's owner/security descriptor.
_PATH_REPLACEMENT_MASK = (
    0x00000040 |  # FILE_DELETE_CHILD
    0x00010000 |  # DELETE
    0x00040000 |  # WRITE_DAC
    0x00080000 |  # WRITE_OWNER
    0x01000000 |  # ACCESS_SYSTEM_SECURITY
    0x10000000    # GENERIC_ALL
)


def _ace_can_replace_child_path(mask):
    return bool(int(mask) & _PATH_REPLACEMENT_MASK)



def _ace_applies_to_current_object(flags):
    # Inherit-only ACEs are evaluated on each descendant's own DACL.
    return not (int(flags) & _INHERIT_ONLY_ACE)
_TRUSTED_OS_OWNERS = frozenset((
    "S-1-5-18",  # LocalSystem
    "S-1-5-32-544",  # BUILTIN\\Administrators
    "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464",  # TrustedInstaller
))
_TRUSTED_NON_USER_WRITERS = _TRUSTED_OS_OWNERS | frozenset((
    "S-1-3-0",  # CREATOR OWNER (inherited child owner)
))


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", ctypes.c_ulong)]


class _TOKEN_USER_STRUCT(ctypes.Structure):
    _fields_ = [("User", _SID_AND_ATTRIBUTES)]


class _ACE_HEADER(ctypes.Structure):
    _fields_ = [("AceType", ctypes.c_ubyte),
                ("AceFlags", ctypes.c_ubyte),
                ("AceSize", ctypes.c_ushort)]


class _ACL_SIZE_INFO(ctypes.Structure):
    _fields_ = [("AceCount", ctypes.c_ulong),
                ("AclBytesInUse", ctypes.c_ulong),
                ("AclBytesFree", ctypes.c_ulong)]


def _apis():
    if os.name != "nt":
        raise ValueError("Native Windows profile checks are available only on Windows")
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    userenv = ctypes.WinDLL("userenv", use_last_error=True)
    return advapi, kernel, userenv


def _raise_winerror(code=None, message="Windows security API failed"):
    if code:
        raise OSError(code, message)
    raise ctypes.WinError(ctypes.get_last_error(), message)


def _reject_thread_impersonation():
    advapi, kernel, _ = _apis()
    advapi.OpenThreadToken.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL,
        ctypes.POINTER(wintypes.HANDLE))
    advapi.OpenThreadToken.restype = wintypes.BOOL
    kernel.GetCurrentThread.restype = wintypes.HANDLE
    handle = wintypes.HANDLE()
    if advapi.OpenThreadToken(kernel.GetCurrentThread(), _TOKEN_QUERY, True,
                              ctypes.byref(handle)):
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL
        kernel.CloseHandle(handle)
        raise ValueError("Refusing an impersonated Windows thread token")
    error = ctypes.get_last_error()
    if error != _ERROR_NO_TOKEN:
        _raise_winerror(error, "Cannot establish the effective Windows thread identity")


def _token():
    _reject_thread_impersonation()
    advapi, kernel, _ = _apis()
    handle = wintypes.HANDLE()
    advapi.OpenProcessToken.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE))
    advapi.OpenProcessToken.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), _TOKEN_QUERY,
                                   ctypes.byref(handle)):
        _raise_winerror(message="Cannot inspect current Windows process token")
    return handle


def _token_identity():
    advapi, kernel, _ = _apis()
    token = _token()
    try:
        advapi.GetTokenInformation.argtypes = (
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
        advapi.GetTokenInformation.restype = wintypes.BOOL
        needed = wintypes.DWORD()
        advapi.GetTokenInformation(token, _TOKEN_USER_CLASS, None, 0,
                                   ctypes.byref(needed))
        if not needed.value or needed.value > 65536:
            _raise_winerror(message="Invalid TokenUser information size")
        user_buffer = ctypes.create_string_buffer(needed.value)
        if not advapi.GetTokenInformation(token, _TOKEN_USER_CLASS, user_buffer,
                                          needed.value, ctypes.byref(needed)):
            _raise_winerror(message="Cannot read current Windows account SID")
        user = ctypes.cast(user_buffer, ctypes.POINTER(_TOKEN_USER_STRUCT)).contents
        sid_pointer = user.User.Sid
        if not sid_pointer:
            raise ValueError("Current Windows token has no user SID")
        advapi.ConvertSidToStringSidW.argtypes = (
            ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR))
        advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
        sid_text = wintypes.LPWSTR()
        if not advapi.ConvertSidToStringSidW(sid_pointer, ctypes.byref(sid_text)):
            _raise_winerror(message="Cannot convert current Windows SID")
        try:
            sid = sid_text.value
        finally:
            kernel.LocalFree.argtypes = (ctypes.c_void_p,)
            kernel.LocalFree.restype = ctypes.c_void_p
            kernel.LocalFree(ctypes.cast(sid_text, ctypes.c_void_p))

        elevation_buffer = wintypes.DWORD()
        returned = wintypes.DWORD()
        if not advapi.GetTokenInformation(
                token, _TOKEN_ELEVATION, ctypes.byref(elevation_buffer),
                ctypes.sizeof(elevation_buffer), ctypes.byref(returned)):
            _raise_winerror(message="Cannot inspect Windows token elevation")
        restricted = wintypes.DWORD()
        if not advapi.GetTokenInformation(
                token, _TOKEN_HAS_RESTRICTIONS, ctypes.byref(restricted),
                ctypes.sizeof(restricted), ctypes.byref(returned)):
            _raise_winerror(message="Cannot inspect Windows token restrictions")
        app_container = wintypes.DWORD()
        if not advapi.GetTokenInformation(
                token, _TOKEN_IS_APP_CONTAINER, ctypes.byref(app_container),
                ctypes.sizeof(app_container), ctypes.byref(returned)):
            _raise_winerror(message="Cannot inspect Windows AppContainer token")
        if sid in ("S-1-5-18", "S-1-5-19", "S-1-5-20"):
            raise ValueError("Windows service accounts cannot install user-profile Skills")
        if restricted.value or app_container.value:
            raise ValueError("Refusing restricted or AppContainer Windows token")
        return {
            "sid": sid,
            "elevated": bool(elevation_buffer.value),
            "restricted": bool(restricted.value),
            "app_container": bool(app_container.value),
        }
    finally:
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL
        kernel.CloseHandle(token)


def _profile_from_token():
    advapi, kernel, userenv = _apis()
    token = _token()
    try:
        userenv.GetUserProfileDirectoryW.argtypes = (
            wintypes.HANDLE, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
        userenv.GetUserProfileDirectoryW.restype = wintypes.BOOL
        needed = wintypes.DWORD()
        userenv.GetUserProfileDirectoryW(token, None, ctypes.byref(needed))
        if not needed.value or needed.value > 32768:
            _raise_winerror(message="Cannot determine current Windows user profile")
        buffer = ctypes.create_unicode_buffer(needed.value)
        if not userenv.GetUserProfileDirectoryW(
                token, buffer, ctypes.byref(needed)):
            _raise_winerror(message="Cannot read current Windows user profile path")
        return Path(buffer.value)
    finally:
        kernel.CloseHandle(token)


def _canonical_existing(path):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError("Windows user profile must be an absolute path")
    assert_no_reparse_components(path)
    return path.resolve(strict=True)


def _normal(path):
    return os.path.normcase(os.path.normpath(str(path)))


def assert_no_reparse_components(path):
    """Reject any existing reparse point in the path, not only its final entry."""
    if os.name != "nt":
        raise ValueError("Windows reparse-point checks require Windows")
    _, kernel, _ = _apis()
    kernel.GetFileAttributesW.argtypes = (wintypes.LPCWSTR,)
    kernel.GetFileAttributesW.restype = wintypes.DWORD
    candidate = Path(os.path.abspath(str(path)))
    parts = candidate.parts
    if not parts:
        raise ValueError("Empty Windows path")
    current = Path(parts[0])
    root_attributes = kernel.GetFileAttributesW(str(current))
    if root_attributes == _INVALID_FILE_ATTRIBUTES:
        _raise_winerror(message="Cannot inspect Windows volume root")
    if root_attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError("Windows user-profile volume root is a reparse point")
    for part in parts[1:]:
        current = current / part
        if not current.exists():
            # Missing descendants are created only after all existing parents
            # have been checked. A dangling reparse point is still detected
            # by GetFileAttributesW below.
            attributes = kernel.GetFileAttributesW(str(current))
            if attributes == _INVALID_FILE_ATTRIBUTES:
                continue
        else:
            attributes = kernel.GetFileAttributesW(str(current))
        if attributes != _INVALID_FILE_ATTRIBUTES and attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError("Windows user-profile path contains a reparse point")
        if attributes == _INVALID_FILE_ATTRIBUTES:
            error = ctypes.get_last_error()
            if error not in (2, 3):
                _raise_winerror(error, "Cannot safely inspect Windows profile path")
    return True


def _sid_string(advapi, kernel, pointer):
    advapi.ConvertSidToStringSidW.argtypes = (
        ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR))
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    result = wintypes.LPWSTR()
    if not advapi.ConvertSidToStringSidW(pointer, ctypes.byref(result)):
        _raise_winerror(message="Cannot read a Windows ACL SID")
    try:
        return result.value
    finally:
        kernel.LocalFree.argtypes = (ctypes.c_void_p,)
        kernel.LocalFree.restype = ctypes.c_void_p
        kernel.LocalFree(ctypes.cast(result, ctypes.c_void_p))


def verify_owned_path(path, sid, *, directory=None, require_owner=True):
    """Require safe DACLs and, by default, current SID ownership."""
    if os.name != "nt":
        raise ValueError("Windows ACL checks require Windows")
    path = Path(path)
    assert_no_reparse_components(path)
    if not path.exists():
        raise ValueError("Windows ACL target does not exist")
    is_dir = path.is_dir()
    if directory is not None and is_dir != directory:
        raise ValueError("Windows profile path has the wrong filesystem type")
    if not is_dir and path.stat().st_nlink > 1:
        raise ValueError("Windows profile state file has an external hard-link alias")

    advapi, kernel, _ = _apis()
    advapi.GetNamedSecurityInfoW.argtypes = (
        wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p))
    advapi.GetNamedSecurityInfoW.restype = wintypes.DWORD
    owner = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    descriptor = ctypes.c_void_p()
    status = advapi.GetNamedSecurityInfoW(
        str(path), _SE_FILE_OBJECT,
        _OWNER_SECURITY_INFORMATION | _DACL_SECURITY_INFORMATION,
        ctypes.byref(owner), None, ctypes.byref(dacl), None,
        ctypes.byref(descriptor))
    if status:
        _raise_winerror(status, "Cannot read Windows profile owner/DACL")
    try:
        if not owner.value:
            raise ValueError("Windows profile path has no readable owner SID")
        owner_sid = _sid_string(advapi, kernel, owner)
        owner_matches = owner_sid == sid
        if owner_sid not in (_TRUSTED_OS_OWNERS | {sid}):
            raise ValueError("Windows profile path is not owned by the current account or a trusted OS principal")

        present = wintypes.BOOL()
        defaulted = wintypes.BOOL()
        dacl_pointer = ctypes.c_void_p()
        advapi.GetSecurityDescriptorDacl.argtypes = (
            ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL),
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.BOOL))
        advapi.GetSecurityDescriptorDacl.restype = wintypes.BOOL
        if not advapi.GetSecurityDescriptorDacl(
                descriptor, ctypes.byref(present), ctypes.byref(dacl_pointer),
                ctypes.byref(defaulted)):
            _raise_winerror(message="Cannot inspect Windows profile DACL")
        if not present.value or not dacl_pointer.value:
            raise ValueError("Windows profile has a NULL or absent DACL")

        info = _ACL_SIZE_INFO()
        advapi.GetAclInformation.argtypes = (
            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.c_int)
        advapi.GetAclInformation.restype = wintypes.BOOL
        if not advapi.GetAclInformation(
                dacl_pointer, ctypes.byref(info), ctypes.sizeof(info),
                _ACL_SIZE_INFORMATION_CLASS):
            _raise_winerror(message="Cannot enumerate Windows profile DACL")
        advapi.GetAce.argtypes = (
            ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p))
        advapi.GetAce.restype = wintypes.BOOL
        allowed_writers = _TRUSTED_NON_USER_WRITERS | {sid}
        current_sid_write_mask = 0
        for index in range(info.AceCount):
            ace_pointer = ctypes.c_void_p()
            if not advapi.GetAce(dacl_pointer, index, ctypes.byref(ace_pointer)):
                _raise_winerror(message="Cannot inspect Windows profile ACE")
            header = ctypes.cast(
                ace_pointer, ctypes.POINTER(_ACE_HEADER)).contents
            # INHERIT_ONLY_ACE does not grant access to this object. Every
            # descendant to which it propagates is checked independently.
            if not _ace_applies_to_current_object(header.AceFlags):
                continue
            if header.AceType not in _ALLOWED_ACE_TYPES:
                if header.AceType not in (1, 2, 3, 6, 7, 8, 10, 12, 13, 14):
                    raise ValueError("Unsupported Windows profile ACL entry type")
                continue
            base = ace_pointer.value
            mask = ctypes.cast(
                ctypes.c_void_p(base + ctypes.sizeof(_ACE_HEADER)),
                ctypes.POINTER(wintypes.DWORD)).contents.value
            sid_offset = 8
            if header.AceType in _OBJECT_ACE_TYPES:
                flags = ctypes.cast(
                    ctypes.c_void_p(base + 8),
                    ctypes.POINTER(wintypes.DWORD)).contents.value
                if flags & ~3:
                    raise ValueError("Malformed Windows object ACL flags")
                sid_offset = 12 + (16 if flags & 1 else 0) + (16 if flags & 2 else 0)
            if header.AceSize < sid_offset + 8:
                raise ValueError("Malformed Windows profile access-control entry")
            ace_sid = _sid_string(
                advapi, kernel, ctypes.c_void_p(base + sid_offset))
            if ace_sid == sid:
                current_sid_write_mask |= mask
                if mask & 0x10000000:  # GENERIC_ALL
                    current_sid_write_mask |= 0x001F01FF
                if mask & 0x40000000:  # GENERIC_WRITE
                    current_sid_write_mask |= 0x00120116
            unsafe_ancestor_right = (
                not require_owner and _ace_can_replace_child_path(mask))
            unsafe_owned_path_right = (
                require_owner and _ace_grants_write(mask))
            if ((unsafe_ancestor_right or unsafe_owned_path_right)
                    and ace_sid not in allowed_writers):
                raise ValueError(
                    "Windows profile ACL grants unsafe write/delete access to an untrusted SID "
                    f"(ace_sid_sha256={hashlib.sha256(ace_sid.encode()).hexdigest()[:12]}, "
                    f"expected_sid_sha256={hashlib.sha256(sid.encode()).hexdigest()[:12]}, "
                    f"mask=0x{mask:08x}, ace_type={header.AceType}, "
                    f"ace_flags=0x{header.AceFlags:02x})")
        # A trusted OS owner (e.g. BUILTIN\\Administrators on hosted runners)
        # is acceptable only when this exact user SID has explicit modify and
        # delete rights. Ancestors are checked for untrusted writers, but need
        # not grant the current user write access.
        if require_owner and not owner_matches:
            has_modify = (current_sid_write_mask & 0x00120116) == 0x00120116
            has_delete = bool(current_sid_write_mask & (0x00010000 | 0x00000040))
            if not (has_modify and has_delete):
                raise ValueError(
                    "Trusted Windows profile owner lacks explicit current-user modify/delete ACL")
        return {
            "owner_sid_matches": owner_matches,
            "owner_sid_accepted": True,
            "current_sid_explicit_write": bool(current_sid_write_mask & _WRITE_MASK),
            "dacl_present": True,
            "untrusted_write_aces": 0,
            "directory": is_dir,
        }
    finally:
        kernel.LocalFree.argtypes = (ctypes.c_void_p,)
        kernel.LocalFree.restype = ctypes.c_void_p
        kernel.LocalFree(descriptor)


def current_profile():
    """Return current token SID, its profile path and elevation status."""
    identity = _token_identity()
    profile = _canonical_existing(_profile_from_token())
    _, kernel, _ = _apis()
    kernel.GetDriveTypeW.argtypes = (wintypes.LPCWSTR,)
    kernel.GetDriveTypeW.restype = wintypes.UINT
    drive_type = kernel.GetDriveTypeW(str(profile.anchor))
    if drive_type != 3:  # DRIVE_FIXED; network/removable/unknown profiles are unsupported.
        raise ValueError("Windows User Profile must reside on a local fixed drive")
    env_profile = os.environ.get("USERPROFILE")
    if not env_profile:
        raise ValueError("USERPROFILE environment variable is missing")
    exported = _canonical_existing(Path(env_profile))
    home = _canonical_existing(Path.home())
    if _normal(profile) != _normal(exported) or _normal(profile) != _normal(home):
        raise ValueError("Windows profile path does not match token, USERPROFILE and Path.home")
    acl = verify_owned_path(profile, identity["sid"], directory=True)
    # The profile's parent directories can replace/delete the profile itself.
    # They need not be owned by this user, but must not grant write/delete
    # capabilities to other untrusted principals.
    ancestor = profile.parent
    while True:
        verify_owned_path(ancestor, identity["sid"], directory=True,
                          require_owner=False)
        if ancestor == ancestor.parent:
            break
        ancestor = ancestor.parent
    info = profile.stat()
    if not info.st_ino or not info.st_dev:
        raise ValueError("Windows profile filesystem does not expose a stable directory identity")
    return {
        "sid": identity["sid"],
        "profile": profile,
        "elevated": identity["elevated"],
        "drive_type": drive_type,
        "acl": acl,
    }


def profile_identity(profile):
    """Opaque stable binding to current SID and an owned profile directory.

    Production callers first pass through user_profile_install._root, which
    binds the selected path to GetUserProfileDirectoryW and rejects elevation.
    This lower-level helper also supports owned disposable test HOME roots.
    """
    identity = _token_identity()
    profile = _canonical_existing(profile)
    verify_owned_path(profile, identity["sid"], directory=True)
    info = profile.stat()
    import hashlib
    import json
    payload = {
        "sid": identity["sid"],
        "volume": int(info.st_dev),
        "file_index": int(info.st_ino),
        "profile": _normal(profile),
        "scope": "user",
    }
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def verify_owned_tree(root, sid):
    """Validate owner, DACL and reparse status for every item in a Skill tree."""
    root = Path(root)
    verify_owned_path(root, sid, directory=True)
    for item in sorted(root.rglob("*"), key=lambda value: value.as_posix()):
        if item.is_dir():
            verify_owned_path(item, sid, directory=True)
        elif item.is_file():
            verify_owned_path(item, sid, directory=False)
            if item.stat().st_nlink > 1:
                raise ValueError("Windows Skill tree contains a multiply-linked file")
        else:
            raise ValueError("Windows Skill tree contains a non-regular entry")
    return True
