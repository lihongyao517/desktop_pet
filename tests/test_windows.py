from __future__ import annotations

import os
import unittest
from unittest.mock import patch
import uuid

from codex_traffic_light.windows import (
    acquire_single_instance,
    close_named_handle,
    consume_named_event,
    create_named_event,
    open_codex_thread,
    release_single_instance,
    signal_named_event,
)


@unittest.skipUnless(os.name == "nt", "Windows mutex behavior")
class SingleInstanceTests(unittest.TestCase):
    @patch("codex_traffic_light.windows.os.startfile")
    def test_thread_link_uses_codex_deep_link(self, startfile: object) -> None:
        self.assertTrue(open_codex_thread("thread id"))
        startfile.assert_called_once_with("codex://threads/thread%20id")

    def test_mutex_rejects_duplicate_and_can_be_reacquired(self) -> None:
        name = f"Local\\CodexDesktopPet.Test.{uuid.uuid4().hex}"
        first = acquire_single_instance(name)
        self.assertIsNotNone(first)
        assert first is not None
        try:
            self.assertIsNone(acquire_single_instance(name))
        finally:
            release_single_instance(first)

        second = acquire_single_instance(name)
        self.assertIsNotNone(second)
        assert second is not None
        release_single_instance(second)

    def test_named_event_wakes_existing_instance_once(self) -> None:
        name = f"Local\\CodexDesktopPet.ShowTest.{uuid.uuid4().hex}"
        event = create_named_event(name)
        try:
            self.assertFalse(consume_named_event(event))
            self.assertTrue(signal_named_event(name))
            self.assertTrue(consume_named_event(event))
            self.assertFalse(consume_named_event(event))
        finally:
            close_named_handle(event)


if __name__ == "__main__":
    unittest.main()
