from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codex_traffic_light.settings import Settings


class SettingsMigrationTests(unittest.TestCase):
    def test_explicit_data_directory_does_not_read_legacy_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = root / "CodexTrafficLight"
            override = root / "isolated"
            legacy.mkdir()
            legacy.joinpath("settings.json").write_text(
                json.dumps({"compact_mode": True}),
                encoding="utf-8",
            )

            environment = {
                "LOCALAPPDATA": str(root),
                "CODEX_DESKTOP_PET_HOME": str(override),
            }
            with patch.dict(os.environ, environment, clear=False):
                self.assertFalse(Settings.load().compact_mode)

    def test_legacy_settings_are_loaded_during_normal_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = root / "CodexTrafficLight"
            legacy.mkdir()
            legacy.joinpath("settings.json").write_text(
                json.dumps({"compact_mode": True}),
                encoding="utf-8",
            )

            environment = {"LOCALAPPDATA": str(root)}
            with patch.dict(os.environ, environment, clear=False):
                os.environ.pop("CODEX_DESKTOP_PET_HOME", None)
                os.environ.pop("CODEX_TRAFFIC_LIGHT_HOME", None)
                self.assertTrue(Settings.load().compact_mode)


if __name__ == "__main__":
    unittest.main()
