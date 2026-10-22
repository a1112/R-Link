"""Private permissions for application-owned R-File identity paths only."""
import os
from pathlib import Path
import stat


def checked_identity_path(path, *, directory=False):
    info = Path(path).lstat()
    if (stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            or (not directory and info.st_nlink != 1)):
        raise ValueError('Unsafe identity path')
    return info


def make_private(path, *, directory=False):
    checked_identity_path(path, directory=directory)
    if os.name == 'nt':
        _windows_private(Path(path), directory)
    else:
        mode = 0o700 if directory else 0o600
        os.chmod(path, mode, follow_symlinks=False)
        if stat.S_IMODE(checked_identity_path(path, directory=directory).st_mode) != mode:
            raise OSError('Identity permissions could not be verified')


def _windows_private(path, directory):
    """Seal and verify a non-reparse handle; never propagate ACLs to other paths."""
    import ctypes as c
    from ctypes import wintypes as w

    adv = c.WinDLL('advapi32', use_last_error=True)
    kernel = c.WinDLL('kernel32', use_last_error=True)
    pointer = c.c_void_p
    pointer_out = c.POINTER(pointer)
    def function(dll, name, result, args):
        value = getattr(dll, name)
        value.restype, value.argtypes = result, args
        return value
    close = function(kernel, 'CloseHandle', w.BOOL, [w.HANDLE])
    free = function(kernel, 'LocalFree', pointer, [pointer])
    current_process = function(kernel, 'GetCurrentProcess', w.HANDLE, [])
    open_token = function(adv, 'OpenProcessToken', w.BOOL, [w.HANDLE, w.DWORD, pointer_out])
    token_info = function(adv, 'GetTokenInformation', w.BOOL,
                          [w.HANDLE, w.DWORD, pointer, w.DWORD, c.POINTER(w.DWORD)])
    sid_text = function(adv, 'ConvertSidToStringSidW', w.BOOL, [pointer, c.POINTER(w.LPWSTR)])
    convert = function(adv, 'ConvertStringSecurityDescriptorToSecurityDescriptorW', w.BOOL,
                       [w.LPCWSTR, w.DWORD, pointer_out, c.POINTER(w.DWORD)])
    get_dacl = function(adv, 'GetSecurityDescriptorDacl', w.BOOL,
                        [pointer, c.POINTER(w.BOOL), pointer_out, c.POINTER(w.BOOL)])
    get_control = function(adv, 'GetSecurityDescriptorControl', w.BOOL,
                           [pointer, c.POINTER(w.WORD), c.POINTER(w.DWORD)])
    get_ace = function(adv, 'GetAce', w.BOOL, [pointer, w.DWORD, pointer_out])
    set_security = function(adv, 'SetSecurityInfo', w.DWORD,
                            [w.HANDLE, w.DWORD, w.DWORD, pointer, pointer, pointer, pointer])
    get_security = function(adv, 'GetSecurityInfo', w.DWORD,
                            [w.HANDLE, w.DWORD, w.DWORD, pointer_out, pointer_out,
                             pointer_out, pointer_out, pointer_out])
    open_file = function(kernel, 'CreateFileW', w.HANDLE,
                         [w.LPCWSTR, w.DWORD, w.DWORD, pointer, w.DWORD, w.DWORD, w.HANDLE])
    class FileInfo(c.Structure):
        _fields_ = [('attributes', w.DWORD), ('created', w.FILETIME), ('accessed', w.FILETIME),
                    ('written', w.FILETIME), ('volume', w.DWORD), ('size_high', w.DWORD),
                    ('size_low', w.DWORD), ('links', w.DWORD), ('index_high', w.DWORD), ('index_low', w.DWORD)]
    file_info = function(kernel, 'GetFileInformationByHandle', w.BOOL, [w.HANDLE, c.POINTER(FileInfo)])
    class Acl(c.Structure):
        _fields_ = [('revision', w.BYTE), ('reserved', w.BYTE), ('size', w.WORD),
                    ('count', w.WORD), ('reserved2', w.WORD)]
    class Ace(c.Structure):
        _fields_ = [('kind', w.BYTE), ('flags', w.BYTE), ('size', w.WORD), ('mask', w.DWORD)]
    def check(ok):
        if not ok:
            raise c.WinError(c.get_last_error())
    def sid_string(sid):
        value = w.LPWSTR()
        check(sid_text(sid, c.byref(value)))
        try:
            return value.value
        finally:
            free(c.cast(value, pointer))
    token = pointer()
    check(open_token(current_process(), 0x8, c.byref(token)))  # TOKEN_QUERY
    try:
        size = w.DWORD()
        token_info(token, 1, None, 0, c.byref(size))  # TokenUser
        if not size.value:
            raise c.WinError(c.get_last_error())
        buffer = c.create_string_buffer(size.value)
        check(token_info(token, 1, buffer, size, c.byref(size)))
        user = sid_string(pointer.from_buffer(buffer).value)
    finally:
        close(token)
    allowed = {user, 'S-1-5-18'}  # process user and SYSTEM
    # SetSecurityInfo does not propagate ACLs from a MAXIMUM_ALLOWED handle.
    # File sharing permits the caller's still-empty mkstemp descriptor to stay open.
    handle = open_file(os.path.abspath(path), 0x02000000 if directory else 0x60080,
                       0 if directory else 3, None, 3,
                       0x02000000 | 0x00200000, None)  # backup semantics + open reparse point
    if handle == pointer(-1).value:
        raise c.WinError(c.get_last_error())
    descriptor = pointer()
    try:
        info = FileInfo()
        check(file_info(handle, c.byref(info)))
        if (info.attributes & 0x400 or bool(info.attributes & 0x10) != directory
                or (not directory and info.links != 1)):
            raise ValueError('Unsafe identity handle')
        owner, existing = pointer(), pointer()
        error = get_security(handle, 1, 1, c.byref(owner), None, None, None, c.byref(existing))
        if error:
            raise c.WinError(error)
        try:
            if sid_string(owner) not in allowed | {'S-1-5-32-544'}:
                raise ValueError('Identity path is owned by another user')
        finally:
            free(existing)
        flags = 'OICI' if directory else ''
        sddl = 'D:P' + ''.join(f'(A;{flags};FA;;;{sid})' for sid in sorted(allowed))
        check(convert(sddl, 1, c.byref(descriptor), None))
        present, defaulted, dacl = w.BOOL(), w.BOOL(), pointer()
        check(get_dacl(descriptor, c.byref(present), c.byref(dacl), c.byref(defaulted)))
        if not present.value or not dacl.value:
            raise OSError('Missing identity DACL')
        error = set_security(handle, 1, 0x80000004, None, None, dacl, None)  # protected DACL
        if error:
            raise c.WinError(error)
        actual, actual_dacl = pointer(), pointer()
        error = get_security(handle, 1, 4, None, None, c.byref(actual_dacl), None, c.byref(actual))
        if error:
            raise c.WinError(error)
        try:
            control, revision = w.WORD(), w.DWORD()
            check(get_control(actual, c.byref(control), c.byref(revision)))
            if not control.value & 0x1000 or not actual_dacl.value:
                raise OSError('Unprotected identity DACL')
            acl = Acl.from_address(actual_dacl.value)
            found = set()
            for index in range(acl.count):
                item = pointer()
                check(get_ace(actual_dacl, index, c.byref(item)))
                ace = Ace.from_address(item.value)
                if (ace.kind != 0 or ace.size < c.sizeof(Ace) + 12
                        or ace.flags != (3 if directory else 0) or ace.mask != 0x1F01FF):
                    raise OSError('Unexpected identity permission')
                sid = sid_string(item.value + c.sizeof(Ace))
                if sid not in allowed:
                    raise OSError('Unexpected identity permission')
                found.add(sid)
            if found != allowed or acl.count != len(allowed):
                raise OSError('Incomplete identity DACL')
        finally:
            free(actual)
    finally:
        if descriptor.value:
            free(descriptor)
        close(handle)
