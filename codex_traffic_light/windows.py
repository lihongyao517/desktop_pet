from __future__ import annotations

import ctypes
from ctypes import wintypes
import os


SW_RESTORE = 9
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


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

