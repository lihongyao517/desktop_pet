from __future__ import annotations

import unittest

from codex_traffic_light.models import (
    APPROVAL,
    CANCELLED,
    COMPLETED,
    ERROR,
    IDLE,
    RUNNING,
    TaskSnapshot,
    resolve_aggregate,
)


class AggregateTests(unittest.TestCase):
    def task(self, session: str, status: str, updated: float) -> TaskSnapshot:
        return TaskSnapshot(session_id=session, status=status, updated_at=updated)

    def test_approval_has_highest_priority(self) -> None:
        snapshot = resolve_aggregate(
            [
                self.task("running", RUNNING, 990),
                self.task("error", ERROR, 995),
                self.task("approval", APPROVAL, 980),
            ],
            now=1000,
        )
        self.assertEqual(snapshot.status, APPROVAL)
        self.assertEqual(snapshot.selected.session_id, "approval")

    def test_running_beats_recent_completion(self) -> None:
        snapshot = resolve_aggregate(
            [self.task("done", COMPLETED, 999), self.task("run", RUNNING, 990)],
            now=1000,
        )
        self.assertEqual(snapshot.status, RUNNING)

    def test_running_beats_error_and_cancelled_history(self) -> None:
        snapshot = resolve_aggregate(
            [
                self.task("cancelled", CANCELLED, 999),
                self.task("error", ERROR, 998),
                self.task("running", RUNNING, 997),
            ],
            now=1000,
        )
        self.assertEqual(snapshot.status, RUNNING)
        self.assertEqual(snapshot.selected.session_id, "running")
        self.assertEqual(
            [task.session_id for task in snapshot.visible_tasks],
            ["running", "error", "cancelled"],
        )

    def test_visible_tasks_exclude_stale_history(self) -> None:
        snapshot = resolve_aggregate(
            [
                self.task("current", RUNNING, 999),
                self.task("old", COMPLETED, 1),
            ],
            now=1000,
            completed_visible_seconds=60,
        )
        self.assertEqual([task.session_id for task in snapshot.visible_tasks], ["current"])

    def test_read_completion_is_removed_from_visible_tasks(self) -> None:
        completed = TaskSnapshot(
            session_id="done",
            status=COMPLETED,
            updated_at=999,
            unread=False,
        )
        snapshot = resolve_aggregate([completed], now=1000)
        self.assertEqual(snapshot.status, IDLE)
        self.assertIsNone(snapshot.selected)
        self.assertEqual(snapshot.visible_tasks, ())

    def test_unread_completion_stays_visible_until_codex_marks_it_read(self) -> None:
        completed = TaskSnapshot(
            session_id="done",
            status=COMPLETED,
            updated_at=1,
            unread=True,
        )
        snapshot = resolve_aggregate(
            [completed],
            now=100_000,
            completed_visible_seconds=1,
        )
        self.assertEqual(snapshot.status, COMPLETED)
        self.assertEqual(snapshot.recent_completed_count, 1)

    def test_stale_running_task_becomes_idle(self) -> None:
        snapshot = resolve_aggregate(
            [self.task("old", RUNNING, 100)],
            now=2000,
            stale_running_seconds=300,
        )
        self.assertEqual(snapshot.status, IDLE)


if __name__ == "__main__":
    unittest.main()
