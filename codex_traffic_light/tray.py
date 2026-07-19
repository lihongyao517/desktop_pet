from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import queue
import sys
import threading


WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_NULL = 0x0000
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_CONTEXTMENU = 0x007B
WM_APP = 0x8000
WM_TRAY_CALLBACK = WM_APP + 1
WM_UPDATE_TOOLTIP = WM_APP + 2

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004

IMAGE_ICON = 1
LR_DEFAULTSIZE = 0x00000040
LR_LOADFROMFILE = 0x00000010
CS_DBLCLKS = 0x0008

MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
TPM_RIGHTBUTTON = 0x0002
TPM_NONOTIFY = 0x0080
TPM_RETURNCMD = 0x0100

MENU_SHOW = 1001
MENU_OPEN_CODEX = 1002
MENU_EXIT = 1003

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
WNDPROC = (
    ctypes.WINFUNCTYPE(
        LRESULT,
        wintypes.HWND,
        wintypes.UINT,
        WPARAM,
        LPARAM,
    )
    if os.name == "nt"
    else ctypes.CFUNCTYPE(
        LRESULT,
        wintypes.HWND,
        wintypes.UINT,
        WPARAM,
        LPARAM,
    )
)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class _TimeoutOrVersion(ctypes.Union):
    _fields_ = [("uTimeout", wintypes.UINT), ("uVersion", wintypes.UINT)]


class NOTIFYICONDATAW(ctypes.Structure):
    _anonymous_ = ("timeout_or_version",)
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("timeout_or_version", _TimeoutOrVersion),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


def tray_icon_path() -> Path | None:
    executable = Path(sys.executable).resolve()
    source_root = Path(__file__).resolve().parents[1]
    candidates = (
        executable.with_name("CodexDesktopPet.ico"),
        executable.parent.parent / "assets" / "CodexDesktopPet.ico",
        source_root / "assets" / "CodexDesktopPet.ico",
    )
    return next((path for path in candidates if path.is_file()), None)


class SystemTray:
    """Windows notification-area icon with a message loop on its own thread."""

    def __init__(self, tooltip: str = "Codex 桌宠") -> None:
        self.actions: queue.SimpleQueue[str] = queue.SimpleQueue()
        self.tooltip = tooltip[:127]
        self.available = False
        self.error: BaseException | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._hwnd = 0
        self._icon = 0
        self._added = False
        self._taskbar_created = 0
        self._class_name = f"CodexDesktopPet.Tray.{os.getpid()}"
        self._wndproc: WNDPROC | None = None
        self._nid = NOTIFYICONDATAW()

    def start(self, timeout: float = 4.0) -> bool:
        if os.name != "nt":
            return False
        if self._thread and self._thread.is_alive():
            return self.available
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="codex-desktop-pet-tray",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait(timeout)
        return self.available

    def poll_action(self) -> str | None:
        try:
            return self.actions.get_nowait()
        except queue.Empty:
            return None

    def set_tooltip(self, tooltip: str) -> None:
        value = tooltip[:127]
        if value == self.tooltip:
            return
        self.tooltip = value
        if os.name == "nt" and self._hwnd:
            ctypes.windll.user32.PostMessageW(
                wintypes.HWND(self._hwnd), WM_UPDATE_TOOLTIP, 0, 0
            )

    def stop(self, timeout: float = 4.0) -> None:
        if os.name == "nt" and self._hwnd:
            ctypes.windll.user32.PostMessageW(wintypes.HWND(self._hwnd), WM_CLOSE, 0, 0)
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout)

    def _run(self) -> None:
        try:
            self._message_loop()
        except BaseException as exc:
            self.error = exc
            self.available = False
            self._ready.set()

    def _message_loop(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        get_module_handle = kernel32.GetModuleHandleW
        get_module_handle.argtypes = (wintypes.LPCWSTR,)
        get_module_handle.restype = wintypes.HINSTANCE
        hinstance = get_module_handle(None)

        user32.DefWindowProcW.argtypes = (
            wintypes.HWND,
            wintypes.UINT,
            WPARAM,
            LPARAM,
        )
        user32.DefWindowProcW.restype = LRESULT
        user32.RegisterWindowMessageW.argtypes = (wintypes.LPCWSTR,)
        user32.RegisterWindowMessageW.restype = wintypes.UINT
        user32.GetMessageW.argtypes = (
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
        )
        user32.GetMessageW.restype = wintypes.BOOL
        user32.TranslateMessage.argtypes = (ctypes.POINTER(wintypes.MSG),)
        user32.TranslateMessage.restype = wintypes.BOOL
        user32.DispatchMessageW.argtypes = (ctypes.POINTER(wintypes.MSG),)
        user32.DispatchMessageW.restype = LRESULT
        user32.DestroyWindow.argtypes = (wintypes.HWND,)
        user32.DestroyWindow.restype = wintypes.BOOL
        user32.PostQuitMessage.argtypes = (ctypes.c_int,)
        user32.PostQuitMessage.restype = None
        self._wndproc = WNDPROC(self._window_proc)
        window_class = WNDCLASSW(
            style=CS_DBLCLKS,
            lpfnWndProc=self._wndproc,
            cbClsExtra=0,
            cbWndExtra=0,
            hInstance=hinstance,
            hIcon=None,
            hCursor=None,
            hbrBackground=None,
            lpszMenuName=None,
            lpszClassName=self._class_name,
        )

        register_class = user32.RegisterClassW
        register_class.argtypes = (ctypes.POINTER(WNDCLASSW),)
        register_class.restype = ctypes.c_ushort
        user32.UnregisterClassW.argtypes = (wintypes.LPCWSTR, wintypes.HINSTANCE)
        user32.UnregisterClassW.restype = wintypes.BOOL
        if not register_class(ctypes.byref(window_class)):
            raise ctypes.WinError(kernel32.GetLastError())

        try:
            create_window = user32.CreateWindowExW
            create_window.argtypes = (
                wintypes.DWORD,
                wintypes.LPCWSTR,
                wintypes.LPCWSTR,
                wintypes.DWORD,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.HWND,
                wintypes.HMENU,
                wintypes.HINSTANCE,
                ctypes.c_void_p,
            )
            create_window.restype = wintypes.HWND
            hwnd = create_window(
                0,
                self._class_name,
                "Codex Desktop Pet Tray",
                0,
                0,
                0,
                0,
                0,
                None,
                None,
                hinstance,
                None,
            )
            if not hwnd:
                raise ctypes.WinError(kernel32.GetLastError())
            self._hwnd = int(hwnd)
            self._taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")
            self._icon = self._load_icon()
            self._add_icon()
            self.available = True
            self._ready.set()

            message = wintypes.MSG()
            while True:
                result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result <= 0:
                    break
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
        finally:
            self._remove_icon()
            if self._icon:
                user32.DestroyIcon.argtypes = (wintypes.HICON,)
                user32.DestroyIcon.restype = wintypes.BOOL
                user32.DestroyIcon(wintypes.HICON(self._icon))
                self._icon = 0
            self._hwnd = 0
            self.available = False
            self._ready.set()
            user32.UnregisterClassW(self._class_name, hinstance)

    def _load_icon(self) -> int:
        user32 = ctypes.windll.user32
        path = tray_icon_path()
        if path:
            load_image = user32.LoadImageW
            load_image.argtypes = (
                wintypes.HINSTANCE,
                wintypes.LPCWSTR,
                wintypes.UINT,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.UINT,
            )
            load_image.restype = wintypes.HANDLE
            icon = load_image(
                None,
                str(path),
                IMAGE_ICON,
                0,
                0,
                LR_LOADFROMFILE | LR_DEFAULTSIZE,
            )
            if icon:
                return int(icon)

        large = wintypes.HICON()
        extract_icon = ctypes.windll.shell32.ExtractIconExW
        extract_icon.argtypes = (
            wintypes.LPCWSTR,
            ctypes.c_int,
            ctypes.POINTER(wintypes.HICON),
            ctypes.POINTER(wintypes.HICON),
            wintypes.UINT,
        )
        extract_icon.restype = wintypes.UINT
        extracted = extract_icon(
            sys.executable, 0, ctypes.byref(large), None, 1
        )
        if extracted and large:
            return int(large.value)
        raise OSError("Unable to load the Codex Desktop Pet tray icon")

    def _add_icon(self) -> None:
        self._nid = NOTIFYICONDATAW()
        self._nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self._nid.hWnd = wintypes.HWND(self._hwnd)
        self._nid.uID = 1
        self._nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        self._nid.uCallbackMessage = WM_TRAY_CALLBACK
        self._nid.hIcon = wintypes.HICON(self._icon)
        self._nid.szTip = self.tooltip
        shell_notify = ctypes.windll.shell32.Shell_NotifyIconW
        shell_notify.argtypes = (wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW))
        shell_notify.restype = wintypes.BOOL
        if not shell_notify(NIM_ADD, ctypes.byref(self._nid)):
            raise OSError("Unable to add the Codex Desktop Pet tray icon")
        self._added = True

    def _remove_icon(self) -> None:
        if not self._added:
            return
        ctypes.windll.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
        self._added = False

    def _update_tooltip(self) -> None:
        if not self._added:
            return
        self._nid.uFlags = NIF_TIP
        self._nid.szTip = self.tooltip
        ctypes.windll.shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))

    def _window_proc(self, hwnd: int, message: int, wparam: int, lparam: int) -> int:
        try:
            if message == WM_TRAY_CALLBACK:
                if lparam in {WM_LBUTTONUP, WM_LBUTTONDBLCLK}:
                    self.actions.put("show")
                    return 0
                if lparam in {WM_RBUTTONUP, WM_CONTEXTMENU}:
                    self._show_popup_menu(hwnd)
                    return 0
            elif message == WM_UPDATE_TOOLTIP:
                self._update_tooltip()
                return 0
            elif self._taskbar_created and message == self._taskbar_created:
                self._added = False
                self._add_icon()
                return 0
            elif message == WM_CLOSE:
                ctypes.windll.user32.DestroyWindow(hwnd)
                return 0
            elif message == WM_DESTROY:
                self._remove_icon()
                ctypes.windll.user32.PostQuitMessage(0)
                return 0
        except BaseException as exc:
            self.error = exc
        return ctypes.windll.user32.DefWindowProcW(hwnd, message, wparam, lparam)

    def _show_popup_menu(self, hwnd: int) -> None:
        user32 = ctypes.windll.user32
        user32.CreatePopupMenu.argtypes = ()
        user32.CreatePopupMenu.restype = wintypes.HMENU
        user32.AppendMenuW.argtypes = (
            wintypes.HMENU,
            wintypes.UINT,
            ctypes.c_size_t,
            wintypes.LPCWSTR,
        )
        user32.AppendMenuW.restype = wintypes.BOOL
        user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
        user32.GetCursorPos.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
        user32.SetForegroundWindow.restype = wintypes.BOOL
        user32.TrackPopupMenu.argtypes = (
            wintypes.HMENU,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            ctypes.c_void_p,
        )
        user32.TrackPopupMenu.restype = wintypes.UINT
        user32.PostMessageW.argtypes = (
            wintypes.HWND,
            wintypes.UINT,
            WPARAM,
            LPARAM,
        )
        user32.PostMessageW.restype = wintypes.BOOL
        user32.DestroyMenu.argtypes = (wintypes.HMENU,)
        user32.DestroyMenu.restype = wintypes.BOOL
        menu = user32.CreatePopupMenu()
        if not menu:
            return
        try:
            user32.AppendMenuW(menu, MF_STRING, MENU_SHOW, "显示桌宠")
            user32.AppendMenuW(menu, MF_STRING, MENU_OPEN_CODEX, "打开 Codex")
            user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(menu, MF_STRING, MENU_EXIT, "退出桌宠")
            point = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            user32.SetForegroundWindow(hwnd)
            command = user32.TrackPopupMenu(
                menu,
                TPM_RIGHTBUTTON | TPM_NONOTIFY | TPM_RETURNCMD,
                point.x,
                point.y,
                0,
                hwnd,
                None,
            )
            action = {
                MENU_SHOW: "show",
                MENU_OPEN_CODEX: "open_codex",
                MENU_EXIT: "exit",
            }.get(command)
            if action:
                self.actions.put(action)
            user32.PostMessageW(hwnd, WM_NULL, 0, 0)
        finally:
            user32.DestroyMenu(menu)
