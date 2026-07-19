from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from .paths import codex_home


MARKER = "Codex Desktop Pet status bridge"
LEGACY_MARKER = "Codex Traffic Light status bridge"
HOOK_EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "PermissionRequest",
    "PostToolUse",
    "SubagentStart",
    "Stop",
)


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _python_console_executable() -> Path:
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        console = executable.with_name("python.exe")
        if console.exists():
            return console
    return executable


def hook_command() -> str:
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        helper = executable.with_name("CodexDesktopPetHook.exe")
        if not helper.exists():
            raise FileNotFoundError(f"Missing hook helper: {helper}")
        return subprocess.list2cmdline([str(helper), "--hook"])

    helper = project_root() / "hook_main.py"
    return subprocess.list2cmdline(
        [str(_python_console_executable()), str(helper), "--hook"]
    )


def hooks_path(home: Path | None = None) -> Path:
    return (home or codex_home()) / "hooks.json"


def _is_ours(handler: Any) -> bool:
    if not isinstance(handler, dict):
        return False
    status = str(handler.get("statusMessage") or handler.get("status_message") or "")
    command = str(handler.get("commandWindows") or handler.get("command_windows") or handler.get("command") or "")
    return (
        MARKER in status
        or LEGACY_MARKER in status
        or "CodexDesktopPetHook" in command
        or "CodexTrafficLightHook" in command
        or "hook_main.py" in command
    )


def _clean_groups(groups: Any) -> list[Any]:
    if not isinstance(groups, list):
        return []
    cleaned: list[Any] = []
    for group in groups:
        if not isinstance(group, dict):
            cleaned.append(group)
            continue
        handlers = group.get("hooks")
        if not isinstance(handlers, list):
            cleaned.append(group)
            continue
        remaining = [handler for handler in handlers if not _is_ours(handler)]
        if remaining:
            updated = dict(group)
            updated["hooks"] = remaining
            cleaned.append(updated)
    return cleaned


def hooks_installed(home: Path | None = None) -> bool:
    path = hooks_path(home)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return False
    hooks = data.get("hooks", {}) if isinstance(data, dict) else {}
    if not isinstance(hooks, dict):
        return False
    found = set()
    for event_name, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        if any(
            _is_ours(handler)
            for group in groups
            if isinstance(group, dict)
            for handler in group.get("hooks", [])
            if isinstance(group.get("hooks"), list)
        ):
            found.add(event_name)
    return set(HOOK_EVENTS).issubset(found)


def install_hooks(home: Path | None = None, command: str | None = None) -> Path:
    path = hooks_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Cannot merge invalid JSON in {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"Expected a JSON object in {path}")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(f"hooks.json.backup-{stamp}")
        shutil.copy2(path, backup)
    else:
        data = {"description": "User-level Codex lifecycle hooks."}

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"Expected 'hooks' to be a JSON object in {path}")

    resolved_command = command or hook_command()
    handler = {
        "type": "command",
        "command": resolved_command,
        "commandWindows": resolved_command,
        "timeout": 5,
        "statusMessage": MARKER,
    }
    for event_name in HOOK_EVENTS:
        groups = _clean_groups(hooks.get(event_name))
        group: dict[str, Any] = {"hooks": [dict(handler)]}
        if event_name == "SessionStart":
            group["matcher"] = "startup|resume|clear"
        groups.append(group)
        hooks[event_name] = groups

    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return path


def uninstall_hooks(home: Path | None = None) -> Path:
    """Remove only the hook handlers owned by this application."""
    path = hooks_path(home)
    if not path.exists():
        return path
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Cannot edit invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return path

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(path, path.with_name(f"hooks.json.backup-{stamp}"))
    for event_name in tuple(hooks):
        groups = _clean_groups(hooks[event_name])
        if groups:
            hooks[event_name] = groups
        else:
            hooks.pop(event_name, None)

    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return path
