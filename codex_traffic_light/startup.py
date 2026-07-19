from __future__ import annotations

from pathlib import Path
import os
import sys

from .integration import project_root


def startup_file() -> Path:
    app_data = os.environ.get("APPDATA")
    base = Path(app_data) if app_data else Path.home() / "AppData" / "Roaming"
    return (
        base
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / "CodexTrafficLight.vbs"
    )


def _escape_vbs(value: str) -> str:
    return value.replace('"', '""')


def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'
    executable = Path(sys.executable)
    if executable.name.lower() == "python.exe":
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.exists():
            executable = pythonw
    return f'"{executable}" "{project_root() / "main.py"}"'


def set_start_with_windows(enabled: bool) -> None:
    path = startup_file()
    if not enabled:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    command = _escape_vbs(launch_command())
    content = (
        'Set shell = CreateObject("WScript.Shell")\n'
        f'shell.Run "{command}", 0, False\n'
    )
    path.write_text(content, encoding="utf-8")


def starts_with_windows() -> bool:
    return startup_file().exists()

