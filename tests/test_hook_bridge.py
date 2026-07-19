from __future__ import annotations

import json
import io
from pathlib import Path
import tempfile
import unittest

from codex_traffic_light.hook_bridge import _read_hook_input, write_hook_state
from codex_traffic_light.models import APPROVAL, COMPLETED, RUNNING


class HookBridgeTests(unittest.TestCase):
    def test_accepts_utf8_bom_from_windows_pipelines(self) -> None:
        payload = _read_hook_input(
            io.StringIO('\ufeff{"hook_event_name":"PermissionRequest"}')
        )
        self.assertEqual(payload["hook_event_name"], "PermissionRequest")

    def test_maps_lifecycle_without_storing_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = write_hook_state(
                {
                    "hook_event_name": "PermissionRequest",
                    "session_id": "session-1",
                    "turn_id": "turn-2",
                    "cwd": "C:/work/demo",
                    "tool_input": {"command": "secret command"},
                    "prompt": "secret prompt",
                },
                directory,
            )
            self.assertIsNotNone(path)
            assert path is not None
            raw = path.read_text(encoding="utf-8")
            state = json.loads(raw)
            self.assertEqual(state["status"], APPROVAL)
            self.assertNotIn("secret command", raw)
            self.assertNotIn("secret prompt", raw)

    def test_start_and_stop_states(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            start = write_hook_state(
                {"hook_event_name": "UserPromptSubmit", "session_id": "a"}, directory
            )
            assert start is not None
            self.assertEqual(json.loads(start.read_text(encoding="utf-8"))["status"], RUNNING)
            stop = write_hook_state(
                {"hook_event_name": "Stop", "session_id": "a"}, directory
            )
            assert stop is not None
            self.assertEqual(json.loads(stop.read_text(encoding="utf-8"))["status"], COMPLETED)


if __name__ == "__main__":
    unittest.main()
