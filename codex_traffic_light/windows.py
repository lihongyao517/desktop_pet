from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from urllib.parse import quote


SW_RESTORE = 9
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
WAIT_OBJECT_0 = 0


def acquire_single_instance(name: str) -> int | None:
    """Hold a named Windows mutex; return None when another instance owns it."""
    if os.name != "nt":
        return 0
    kernel32 = ctypes.windll.kernel32
    create_mutex = kernel32.CreateMutexW
    create_mutex.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    create_mutex.restype = wintypes.HANDLE
    handle = create_mutex(None, False, name)
    error = kernel32.GetLastError()
    if not handle:
        raise ctypes.WinError(error)
    if error == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return None
    return int(handle)


def release_single_instance(handle: int) -> None:
    if os.name == "nt" and handle:
        ctypes.windll.kernel32.CloseHandle(wintypes.HANDLE(handle))


def create_named_event(name: str) -> int:
    """Create an auto-reset event used to restore the hidden pet."""
    if os.name != "nt":
        return 0
    kernel32 = ctypes.windll.kernel32
    create_event = kernel32.CreateEventW
    create_event.argtypes = (
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    )
    create_event.restype = wintypes.HANDLE
    handle = create_event(None, False, False, name)
    if not handle:
        raise ctypes.WinError(kernel32.GetLastError())
    return int(handle)


def signal_named_event(name: str) -> bool:
    if os.name != "nt":
        return False
    kernel32 = ctypes.windll.kernel32
    open_event = kernel32.OpenEventW
    open_event.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    open_event.restype = wintypes.HANDLE
    handle = open_event(EVENT_MODIFY_STATE, False, name)
    if not handle:
        return False
    try:
        set_event = kernel32.SetEvent
        set_event.argtypes = (wintypes.HANDLE,)
        set_event.restype = wintypes.BOOL
        return bool(set_event(handle))
    finally:
        kernel32.CloseHandle(handle)


def consume_named_event(handle: int) -> bool:
    if os.name != "nt" or not handle:
        return False
    wait = ctypes.windll.kernel32.WaitForSingleObject
    wait.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    wait.restype = wintypes.DWORD
    return wait(wintypes.HANDLE(handle), 0) == WAIT_OBJECT_0


def close_named_handle(handle: int) -> None:
    if os.name == "nt" and handle:
        ctypes.windll.kernel32.CloseHandle(wintypes.HANDLE(handle))


def focus_window_by_title(title: str) -> bool:
    if os.name != "nt":
        return False
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    flash_window(hwnd)
    return True


def open_codex() -> bool:
    if os.name != "nt":
        return False
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    found: list[int] = []

    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @enum_proc
    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not process:
            return True
        try:
            size = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
                name = os.path.basename(buffer.value).lower()
                if name in {"chatgpt.exe", "codex.exe"}:
                    found.append(hwnd)
                    return False
        finally:
            kernel32.CloseHandle(process)
        return True

    user32.EnumWindows(callback, 0)
    if found:
        hwnd = found[0]
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        return True
    try:
        os.startfile("codex://")
        return True
    except OSError:
        return False


def open_codex_thread(session_id: str) -> bool:
    if os.name != "nt" or not session_id:
        return False
    try:
        os.startfile(f"codex://threads/{quote(session_id, safe='')}")
        return True
    except OSError:
        return open_codex()


def flash_window(hwnd: int) -> None:
    if os.name != "nt":
        return

    class FLASHWINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("hwnd", wintypes.HWND),
            ("dwFlags", wintypes.DWORD),
            ("uCount", wintypes.UINT),
            ("dwTimeout", wintypes.DWORD),
        ]

    info = FLASHWINFO(
        ctypes.sizeof(FLASHWINFO), hwnd, 0x00000003 | 0x0000000C, 5, 0
    )
    ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
