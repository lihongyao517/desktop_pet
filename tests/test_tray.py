from __future__ import annotations

import os
import unittest

from codex_traffic_light.tray import SystemTray, tray_icon_path


class TrayAssetTests(unittest.TestCase):
    def test_tray_icon_asset_can_be_found(self) -> None:
        path = tray_icon_path()
        self.assertIsNotNone(path)
        assert path is not None
        self.assertTrue(path.is_file())


@unittest.skipUnless(os.name == "nt", "Windows notification area")
class SystemTrayTests(unittest.TestCase):
    def test_native_tray_icon_starts_updates_and_stops_cleanly(self) -> None:
        tray = SystemTray("Codex 桌宠 - 测试")
        try:
            self.assertTrue(tray.start())
            self.assertIsNone(tray.error)
            tray.set_tooltip("Codex 桌宠 - 正在工作（2）")
        finally:
            tray.stop()
        self.assertFalse(tray.available)
        self.assertIsNone(tray.error)


if __name__ == "__main__":
    unittest.main()
