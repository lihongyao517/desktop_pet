from __future__ import annotations

from dataclasses import dataclass, replace
import time
from typing import Iterable


IDLE = "idle"
RUNNING = "running"
APPROVAL = "approval"
COMPLETED = "completed"
CANCELLED = "cancelled"
ERROR = "error"


@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    session_id: str
    status: str = IDLE
    phase: str = "会话就绪"
    title: str = "Codex 任务"
    cwd: str = ""
    turn_id: str = ""
    updated_at: float = 0.0
    started_at: float = 0.0
    source: str = "unknown"
    unread: bool | None = None

    def with_title(self, title: str) -> "TaskSnapshot":
        return replace(self, title=title or self.title)


@dataclass(frozen=True, slots=True)
class AggregateSnapshot:
    status: str
    selected: TaskSnapshot | None
    tasks: tuple[TaskSnapshot, ...]
    running_count: int = 0
    approval_count: int = 0
    error_count: int = 0
    recent_completed_count: int = 0
    cancelled_count: int = 0
    visible_tasks: tuple[TaskSnapshot, ...] = ()


def resolve_aggregate(
    tasks: Iterable[TaskSnapshot],
    *,
    now: float | None = None,
    stale_running_seconds: float = 30 * 60,
    stale_approval_seconds: float = 12 * 60 * 60,
    completed_visible_seconds: float = 15 * 60,
    cancelled_visible_seconds: float = 10 * 60,
    error_visible_seconds: float = 60 * 60,
) -> AggregateSnapshot:
    current = time.time() if now is None else now
    ordered = tuple(sorted(tasks, key=lambda item: item.updated_at, reverse=True))

    approvals = [
        task
        for task in ordered
        if task.status == APPROVAL
        and current - task.updated_at <= stale_approval_seconds
    ]
    errors = [
        task
        for task in ordered
        if task.status == ERROR and current - task.updated_at <= error_visible_seconds
    ]
    running = [
        task
        for task in ordered
        if task.status == RUNNING
        and current - task.updated_at <= stale_running_seconds
    ]
    completed = [
        task
        for task in ordered
        if task.status == COMPLETED
        and (
            task.unread is True
            or (
                task.unread is None
                and current - task.updated_at <= completed_visible_seconds
            )
        )
    ]
    cancelled = [
        task
        for task in ordered
        if task.status == CANCELLED
        and current - task.updated_at <= cancelled_visible_seconds
    ]

    if approvals:
        status, selected = APPROVAL, approvals[0]
    elif running:
        status, selected = RUNNING, running[0]
    elif errors:
        status, selected = ERROR, errors[0]
    elif cancelled:
        status, selected = CANCELLED, cancelled[0]
    elif completed:
        status, selected = COMPLETED, completed[0]
    else:
        idle = [task for task in ordered if task.status == IDLE]
        status, selected = IDLE, idle[0] if idle else None

    priority = {APPROVAL: 0, RUNNING: 1, ERROR: 2, CANCELLED: 3, COMPLETED: 4}
    visible_tasks = tuple(
        sorted(
            (*approvals, *running, *errors, *cancelled, *completed),
            key=lambda task: (priority[task.status], -task.updated_at),
        )
    )

    return AggregateSnapshot(
        status=status,
        selected=selected,
        tasks=ordered,
        running_count=len(running),
        approval_count=len(approvals),
        error_count=len(errors),
        recent_completed_count=len(completed),
        cancelled_count=len(cancelled),
        visible_tasks=visible_tasks,
    )
