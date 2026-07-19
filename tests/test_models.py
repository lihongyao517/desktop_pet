from __future__ import annotations

import unittest

from codex_traffic_light.models import (
    APPROVAL,
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

    def test_stale_running_task_becomes_idle(self) -> None:
        snapshot = resolve_aggregate(
            [self.task("old", RUNNING, 100)],
            now=2000,
            stale_running_seconds=300,
        )
        self.assertEqual(snapshot.status, IDLE)


if __name__ == "__main__":
    unittest.main()

