from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from codex_traffic_light.integration import (
    HOOK_EVENTS,
    hooks_installed,
    install_hooks,
    uninstall_hooks,
)


class IntegrationTests(unittest.TestCase):
    def test_install_preserves_existing_hooks_and_uninstall_removes_only_ours(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            original = {
                "description": "existing",
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "existing-tool",
                                    "statusMessage": "Existing hook",
                                }
                            ]
                        }
                    ]
                },
            }
            (home / "hooks.json").write_text(json.dumps(original), encoding="utf-8")
            install_hooks(home, command='"C:/monitor.exe" --hook')
            self.assertTrue(hooks_installed(home))
            installed = json.loads((home / "hooks.json").read_text(encoding="utf-8"))
            self.assertTrue(all(event in installed["hooks"] for event in HOOK_EVENTS))
            self.assertIn("existing-tool", json.dumps(installed))

            uninstall_hooks(home)
            removed = json.loads((home / "hooks.json").read_text(encoding="utf-8"))
            self.assertIn("existing-tool", json.dumps(removed))
            self.assertNotIn("Codex Traffic Light", json.dumps(removed))


if __name__ == "__main__":
    unittest.main()

