from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import time
import uuid
from typing import Any, TextIO

from .models import APPROVAL, COMPLETED, IDLE, RUNNING
from .paths import task_state_dir


_EVENT_STATE = {
    "SessionStart": (IDLE, "会话就绪"),
    "UserPromptSubmit": (RUNNING, "开始处理"),
    "SubagentStart": (RUNNING, "并行任务运行中"),
    "PermissionRequest": (APPROVAL, "等待权限批准"),
    "PostToolUse": (RUNNING, "继续执行"),
    "Stop": (COMPLETED, "本轮已完成"),
}


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
    return cleaned[:120] or "unknown-session"


def _read_hook_input(stream: TextIO) -> dict[str, Any]:
    raw = stream.read().lstrip("\ufeff")
    if not raw.strip():
        return {}
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, dict) else {}


def write_hook_state(payload: dict[str, Any], directory: Path | None = None) -> Path | None:
    event_name = str(payload.get("hook_event_name") or "")
    mapped = _EVENT_STATE.get(event_name)
    if mapped is None:
        return None

    session_id = str(payload.get("session_id") or "unknown-session")
    turn_id = str(payload.get("turn_id") or "")
    status, phase = mapped
    now = time.time()

    tool_name = str(payload.get("tool_name") or "")
    if event_name == "PostToolUse" and tool_name:
        phase = "继续执行"

    state = {
        "schema": 1,
        "session_id": session_id,
        "turn_id": turn_id,
        "status": status,
        "phase": phase,
        "cwd": str(payload.get("cwd") or ""),
        "updated_at": now,
        "started_at": now if status == RUNNING and event_name == "UserPromptSubmit" else 0.0,
        "source": "hook",
        "event": event_name,
    }

    target_dir = directory or task_state_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{_safe_name(session_id)}.json"
    temporary = target_dir / f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(temporary, target)
    return target


def run_hook(stream: TextIO | None = None) -> int:
    try:
        payload = _read_hook_input(stream or sys.stdin)
        write_hook_state(payload)
    except Exception:
        # Monitoring must never block or fail a Codex action.
        return 0
    return 0
