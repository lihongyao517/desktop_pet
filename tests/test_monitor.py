from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from codex_traffic_light.models import COMPLETED, ERROR, RUNNING
from codex_traffic_light.monitor import SessionLogParser


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

    def test_aborted_turn_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "rollout-019f79ea-498f-7442-8fd4-3df934234cf6.jsonl"
            self.write_records(
                path,
                [
                    {
                        "timestamp": "2026-07-19T10:00:00Z",
                        "type": "event_msg",
                        "payload": {"type": "turn_aborted"},
                    }
                ],
            )
            self.assertEqual(SessionLogParser(path).read_updates().status, ERROR)


if __name__ == "__main__":
    unittest.main()

