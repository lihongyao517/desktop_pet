from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "CodexDesktopPet"
LEGACY_APP_NAME = "CodexTrafficLight"


def app_data_dir() -> Path:
    override = os.environ.get("CODEX_DESKTOP_PET_HOME") or os.environ.get(
        "CODEX_TRAFFIC_LIGHT_HOME"
    )
    if override:
        return Path(override).expanduser().resolve()

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_NAME
    return Path.home() / "AppData" / "Local" / APP_NAME


def codex_home() -> Path:
    override = os.environ.get("CODEX_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".codex"


def task_state_dir() -> Path:
    return app_data_dir() / "tasks"


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def legacy_settings_path() -> Path:
    if os.environ.get("CODEX_DESKTOP_PET_HOME") or os.environ.get(
        "CODEX_TRAFFIC_LIGHT_HOME"
    ):
        return settings_path()
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / LEGACY_APP_NAME / "settings.json"
