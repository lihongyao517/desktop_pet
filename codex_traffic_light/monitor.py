from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any

from .models import (
    AggregateSnapshot,
    CANCELLED,
    COMPLETED,
    ERROR,
    IDLE,
    RUNNING,
    TaskSnapshot,
    resolve_aggregate,
)
from .paths import codex_home, task_state_dir


_SESSION_ID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$",
    re.IGNORECASE,
)
_MAX_SESSION_FILES = 80
_MAX_INITIAL_TAIL_BYTES = 2 * 1024 * 1024


def _timestamp(value: Any, fallback: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return fallback
    return fallback


def _title_fallback(cwd: str) -> str:
    if cwd:
        name = Path(cwd).name
        if name:
            return name
    return "Codex 任务"


def _session_id_from_path(path: Path) -> str:
    matched = _SESSION_ID_RE.search(path.name)
    return matched.group(1) if matched else path.stem


def _tool_phase(name: str) -> str:
    lowered = name.lower()
    if "apply_patch" in lowered or lowered in {"edit", "write"}:
        return "正在修改文件"
    if "shell" in lowered or "exec" in lowered:
        return "正在执行命令"
    if "web" in lowered or "search" in lowered:
        return "正在检索资料"
    if "wait" in lowered:
        return "等待后台任务"
    return "正在使用工具"


class SessionLogParser:
    """Incrementally turns a rollout JSONL file into a privacy-safe state."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.session_id = _session_id_from_path(path)
        self.offset = 0
        self.partial = b""
        self.snapshot = TaskSnapshot(
            session_id=self.session_id,
            title="Codex 任务",
            source="session-log",
        )

    def read_updates(self, initial_tail_bytes: int = _MAX_INITIAL_TAIL_BYTES) -> TaskSnapshot:
        try:
            size = self.path.stat().st_size
        except OSError:
            return self.snapshot

        if size < self.offset:
            self.offset = 0
            self.partial = b""
        elif size == self.offset:
            return self.snapshot

        first_read = self.offset == 0
        start = self.offset
        discard_first = False
        if first_read and size > initial_tail_bytes:
            start = size - initial_tail_bytes
            discard_first = True

        try:
            with self.path.open("rb") as stream:
                stream.seek(start)
                chunk = stream.read()
                self.offset = stream.tell()
        except OSError:
            return self.snapshot

        if not chunk:
            return self.snapshot
        if discard_first:
            newline = chunk.find(b"\n")
            chunk = chunk[newline + 1 :] if newline >= 0 else b""

        data = self.partial + chunk
        lines = data.split(b"\n")
        self.partial = lines.pop() if lines else b""
        for raw_line in lines:
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(record, dict):
                self._consume(record)
        return self.snapshot

    def _update(
        self,
        *,
        status: str | None = None,
        phase: str | None = None,
        updated_at: float | None = None,
        started_at: float | None = None,
        turn_id: str | None = None,
        cwd: str | None = None,
    ) -> None:
        previous = self.snapshot
        effective_status = status or previous.status
        effective_started = previous.started_at
        if started_at:
            effective_started = started_at
        elif effective_status == RUNNING and not effective_started:
            effective_started = updated_at or time.time()

        self.snapshot = replace(
            previous,
            status=effective_status,
            phase=phase or previous.phase,
            updated_at=max(previous.updated_at, updated_at or 0.0),
            started_at=effective_started,
            turn_id=turn_id if turn_id is not None else previous.turn_id,
            cwd=cwd if cwd is not None else previous.cwd,
            title=_title_fallback(cwd if cwd is not None else previous.cwd),
        )

    def _consume(self, record: dict[str, Any]) -> None:
        record_type = str(record.get("type") or "")
        payload = record.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        stamp = _timestamp(record.get("timestamp"), time.time())

        if record_type == "session_meta":
            session_id = str(payload.get("session_id") or payload.get("id") or self.session_id)
            cwd = str(payload.get("cwd") or self.snapshot.cwd)
            self.session_id = session_id
            self.snapshot = replace(
                self.snapshot,
                session_id=session_id,
                cwd=cwd,
                title=_title_fallback(cwd),
            )
            return

        if record_type == "event_msg":
            event_type = str(payload.get("type") or "")
            turn_id = str(payload.get("turn_id") or self.snapshot.turn_id)
            if event_type == "task_started":
                started = _timestamp(payload.get("started_at"), stamp)
                self._update(
                    status=RUNNING,
                    phase="开始处理",
                    updated_at=stamp,
                    started_at=started,
                    turn_id=turn_id,
                )
            elif event_type == "user_message":
                self._update(status=RUNNING, phase="开始处理", updated_at=stamp)
            elif event_type == "agent_reasoning":
                self._update(status=RUNNING, phase="正在分析", updated_at=stamp)
            elif event_type == "agent_message":
                phase_name = str(payload.get("phase") or "")
                phase = "整理结果" if phase_name == "final_answer" else "正在汇报进度"
                self._update(status=RUNNING, phase=phase, updated_at=stamp)
            elif event_type == "patch_apply_end":
                self._update(status=RUNNING, phase="正在修改文件", updated_at=stamp)
            elif event_type == "mcp_tool_call_end":
                self._update(status=RUNNING, phase="正在使用工具", updated_at=stamp)
            elif event_type == "web_search_end":
                self._update(status=RUNNING, phase="正在检索资料", updated_at=stamp)
            elif event_type == "context_compacted":
                self._update(status=RUNNING, phase="正在整理上下文", updated_at=stamp)
            elif event_type == "task_complete":
                self._update(status=COMPLETED, phase="本轮已完成", updated_at=stamp)
            elif event_type == "turn_aborted":
                reason = str(payload.get("reason") or "").lower()
                failed = any(word in reason for word in ("error", "fail", "crash", "panic"))
                self._update(
                    status=ERROR if failed else CANCELLED,
                    phase="任务异常中止" if failed else "任务已终止",
                    updated_at=stamp,
                )
            return

        if record_type != "response_item":
            return
        item_type = str(payload.get("type") or "")
        if item_type in {"custom_tool_call", "function_call"}:
            self._update(
                status=RUNNING,
                phase=_tool_phase(str(payload.get("name") or "")),
                updated_at=stamp,
            )
        elif item_type in {"custom_tool_call_output", "function_call_output"}:
            self._update(status=RUNNING, phase="正在处理工具结果", updated_at=stamp)


class CodexMonitor:
    def __init__(
        self,
        *,
        home: Path | None = None,
        state_dir: Path | None = None,
    ) -> None:
        self.home = home or codex_home()
        self.state_dir = state_dir or task_state_dir()
        self.tasks: dict[str, TaskSnapshot] = {}
        self.parsers: dict[Path, SessionLogParser] = {}
        self._state_mtimes: dict[Path, int] = {}
        self._titles: dict[str, str] = {}
        self._title_mtime = 0
        self._unread_ids: set[str] | None = None
        self._unread_mtime = 0
        self._last_discovery = 0.0
        self._last_full_discovery = 0.0

    def scan(self) -> AggregateSnapshot:
        self._load_titles()
        self._load_unread_ids()
        self._scan_hook_states()
        self._discover_sessions()
        for parser in list(self.parsers.values()):
            snapshot = parser.read_updates()
            self._merge(snapshot)
        self._apply_titles()
        self._apply_unread_ids()
        return resolve_aggregate(self.tasks.values())

    def _load_unread_ids(self) -> None:
        path = self.home / ".codex-global-state.json"
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            return
        if mtime == self._unread_mtime:
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            atoms = data.get("electron-persisted-atom-state", {})
            unread_by_host = atoms.get("unread-thread-ids-by-host-v1", {})
            local = unread_by_host.get("local", [])
            if not isinstance(local, list):
                return
            unread_ids = {str(item) for item in local if item}
        except (OSError, AttributeError, json.JSONDecodeError):
            return
        self._unread_ids = unread_ids
        self._unread_mtime = mtime

    def _load_titles(self) -> None:
        path = self.home / "session_index.jsonl"
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            return
        if mtime == self._title_mtime:
            return
        titles: dict[str, str] = {}
        try:
            with path.open("r", encoding="utf-8-sig") as stream:
                for line in stream:
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(item, dict):
                        continue
                    session_id = str(item.get("id") or "")
                    name = str(item.get("thread_name") or "").strip()
                    if session_id and name:
                        titles[session_id] = name
        except OSError:
            return
        self._titles = titles
        self._title_mtime = mtime

    def _scan_hook_states(self) -> None:
        try:
            paths = tuple(self.state_dir.glob("*.json"))
        except OSError:
            return
        for path in paths:
            try:
                mtime = path.stat().st_mtime_ns
            except OSError:
                continue
            if self._state_mtimes.get(path) == mtime:
                continue
            self._state_mtimes[path] = mtime
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                session_id = str(data.get("session_id") or path.stem)
                snapshot = TaskSnapshot(
                    session_id=session_id,
                    status=str(data.get("status") or IDLE),
                    phase=str(data.get("phase") or "会话就绪"),
                    title=_title_fallback(str(data.get("cwd") or "")),
                    cwd=str(data.get("cwd") or ""),
                    turn_id=str(data.get("turn_id") or ""),
                    updated_at=float(data.get("updated_at") or 0.0),
                    started_at=float(data.get("started_at") or 0.0),
                    source="hook",
                )
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            self._merge(snapshot)

    def _discover_sessions(self) -> None:
        now = time.time()
        if now - self._last_discovery < 0.4:
            return
        self._last_discovery = now
        sessions = self.home / "sessions"
        try:
            today = datetime.now()
            current_dir = sessions / f"{today.year:04d}" / f"{today.month:02d}" / f"{today.day:02d}"
            candidates = [path for path in current_dir.glob("rollout-*.jsonl") if path.is_file()]
            if not self.parsers or now - self._last_full_discovery >= 30:
                self._last_full_discovery = now
                candidates.extend(
                    path for path in sessions.rglob("rollout-*.jsonl") if path.is_file()
                )
        except OSError:
            return
        unique = tuple(dict.fromkeys(candidates))
        try:
            ordered = sorted(unique, key=lambda path: path.stat().st_mtime, reverse=True)
        except OSError:
            return
        for path in ordered[:_MAX_SESSION_FILES]:
            self.parsers.setdefault(path, SessionLogParser(path))

    def _merge(self, incoming: TaskSnapshot) -> None:
        previous = self.tasks.get(incoming.session_id)
        if previous is None:
            self.tasks[incoming.session_id] = incoming
            return
        if incoming.updated_at < previous.updated_at:
            return
        started = incoming.started_at or previous.started_at
        title = incoming.title
        if title == "Codex 任务" and previous.title != "Codex 任务":
            title = previous.title
        cwd = incoming.cwd or previous.cwd
        turn_id = incoming.turn_id or previous.turn_id
        self.tasks[incoming.session_id] = replace(
            incoming,
            started_at=started,
            title=title,
            cwd=cwd,
            turn_id=turn_id,
        )

    def _apply_titles(self) -> None:
        for session_id, task in tuple(self.tasks.items()):
            title = self._titles.get(session_id)
            if title and title != task.title:
                self.tasks[session_id] = task.with_title(title)

    def _apply_unread_ids(self) -> None:
        if self._unread_ids is None:
            return
        for session_id, task in tuple(self.tasks.items()):
            unread = session_id in self._unread_ids
            if task.unread != unread:
                self.tasks[session_id] = replace(task, unread=unread)


class MonitorWorker:
    def __init__(self, monitor: CodexMonitor | None = None, interval: float = 0.2) -> None:
        self.monitor = monitor or CodexMonitor()
        self.interval = interval
        self._lock = threading.Lock()
        self._snapshot = AggregateSnapshot(IDLE, None, ())
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="codex-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def snapshot(self) -> AggregateSnapshot:
        with self._lock:
            return self._snapshot

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                snapshot = self.monitor.scan()
                with self._lock:
                    self._snapshot = snapshot
            except Exception:
                # A partially written or future log format must not kill the widget.
                pass
            self._stop.wait(self.interval)
