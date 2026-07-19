from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
import unittest

from codex_traffic_light.models import CANCELLED, COMPLETED, ERROR, RUNNING
from codex_traffic_light.monitor import CodexMonitor, SessionLogParser


class SessionLogParserTests(unittest.TestCase):
    def write_records(self, path: Path, records: list[dict]) -> None:
        path.write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )

    def test_parses_running_tool_and_completion_incrementally(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "rollout-019f79ea-498f-7442-8fd4-3df934234cf6.jsonl"
            records = [
                {
                    "timestamp": "2026-07-19T10:00:00Z",
                    "type": "session_meta",
                    "payload": {"id": "session-a", "cwd": "C:/work/project"},
                },
                {
                    "timestamp": "2026-07-19T10:00:01Z",
                    "type": "event_msg",
                    "payload": {"type": "task_started", "turn_id": "turn-a"},
                },
                {
                    "timestamp": "2026-07-19T10:00:02Z",
                    "type": "response_item",
                    "payload": {"type": "custom_tool_call", "name": "apply_patch"},
                },
            ]
            self.write_records(path, records)
            parser = SessionLogParser(path)
            running = parser.read_updates()
            self.assertEqual(running.status, RUNNING)
            self.assertEqual(running.phase, "正在修改文件")
            self.assertEqual(running.title, "project")

            with path.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {
                            "timestamp": "2026-07-19T10:00:03Z",
                            "type": "event_msg",
                            "payload": {"type": "task_complete"},
                        }
                    )
                    + "\n"
                )
            completed = parser.read_updates()
            self.assertEqual(completed.status, COMPLETED)

    def test_user_aborted_turn_is_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "rollout-019f79ea-498f-7442-8fd4-3df934234cf6.jsonl"
            self.write_records(
                path,
                [
                    {
                        "timestamp": "2026-07-19T10:00:00Z",
                        "type": "event_msg",
                        "payload": {"type": "turn_aborted", "reason": "interrupted"},
                    }
                ],
            )
            self.assertEqual(SessionLogParser(path).read_updates().status, CANCELLED)

    def test_failed_abort_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "rollout-019f79ea-498f-7442-8fd4-3df934234cf6.jsonl"
            self.write_records(
                path,
                [
                    {
                        "timestamp": "2026-07-19T10:00:00Z",
                        "type": "event_msg",
                        "payload": {"type": "turn_aborted", "reason": "runtime_error"},
                    }
                ],
            )
            self.assertEqual(SessionLogParser(path).read_updates().status, ERROR)

    def test_codex_unread_state_controls_completed_visibility(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            sessions = home / "sessions" / "2026" / "07" / "19"
            sessions.mkdir(parents=True)
            path = sessions / "rollout-2026-07-19T10-00-00-019f79ea-498f-7442-8fd4-3df934234cf6.jsonl"
            self.write_records(
                path,
                [
                    {
                        "timestamp": time.time() - 1,
                        "type": "session_meta",
                        "payload": {"id": "session-a", "cwd": "C:/work/project"},
                    },
                    {
                        "timestamp": time.time(),
                        "type": "event_msg",
                        "payload": {"type": "task_complete"},
                    },
                ],
            )
            global_state = home / ".codex-global-state.json"

            def write_unread(ids: list[str]) -> None:
                global_state.write_text(
                    json.dumps(
                        {
                            "electron-persisted-atom-state": {
                                "unread-thread-ids-by-host-v1": {"local": ids}
                            }
                        }
                    ),
                    encoding="utf-8",
                )

            write_unread(["session-a"])
            monitor = CodexMonitor(home=home, state_dir=home / "task-state")
            unread = monitor.scan()
            self.assertEqual(unread.status, COMPLETED)
            self.assertEqual(unread.recent_completed_count, 1)

            write_unread([])
            read = monitor.scan()
            self.assertEqual(read.status, "idle")
            self.assertEqual(read.recent_completed_count, 0)
            self.assertEqual(read.visible_tasks, ())


if __name__ == "__main__":
    unittest.main()
