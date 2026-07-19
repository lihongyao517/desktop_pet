from __future__ import annotations

import unittest

from codex_traffic_light.ui import (
    CodexDesktopPetApp,
    anchored_window_position,
    fit_expanded_scene_y,
)


class FakeRoot:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def winfo_x(self) -> int:
        return 120

    def winfo_y(self) -> int:
        return 240

    def withdraw(self) -> None:
        self.calls.append("withdraw")

    def deiconify(self) -> None:
        self.calls.append("deiconify")

    def lift(self) -> None:
        self.calls.append("lift")

    def attributes(self, *args: object) -> None:
        self.calls.append(args)

    def focus_force(self) -> None:
        self.calls.append("focus_force")


class FakeSettings:
    always_on_top = True
    window_x: int | None = None
    window_y: int | None = None

    def save(self) -> None:
        pass


class FakeTooltip:
    def hide(self) -> None:
        pass


class FakeTray:
    available = True
    error = None

    def poll_action(self) -> str | None:
        return None

    def set_tooltip(self, _tooltip: str) -> None:
        pass

    def stop(self) -> None:
        pass


class WindowAnchoringTests(unittest.TestCase):
    def test_scene_anchor_stays_fixed_when_mode_changes(self) -> None:
        compact = (20, 39)
        full = (310, 55)

        expanded = anchored_window_position(900, 300, compact, full)
        self.assertEqual(expanded, (610, 284))
        self.assertEqual(
            (expanded[0] + full[0], expanded[1] + full[1]),
            (900 + compact[0], 300 + compact[1]),
        )
        self.assertEqual(
            anchored_window_position(*expanded, full, compact),
            (900, 300),
        )

    def test_expansion_near_taskbar_moves_scene_inside_window_not_on_screen(self) -> None:
        screen_height = 1080
        compact_height = 250
        compact_origin_y = 39
        compact_window_y = screen_height - compact_height - 48
        anchor_y = compact_window_y + compact_origin_y

        expanded_window_y, expanded_origin_y = fit_expanded_scene_y(
            anchor_y,
            screen_height,
            320,
        )

        self.assertEqual(expanded_window_y, 712)
        self.assertEqual(expanded_origin_y, 109)
        self.assertEqual(expanded_window_y + expanded_origin_y, anchor_y)
        self.assertLessEqual(expanded_window_y + 320, screen_height - 48)

    def test_close_action_hides_and_show_restores_the_same_app(self) -> None:
        app = CodexDesktopPetApp.__new__(CodexDesktopPetApp)
        app.root = FakeRoot()
        app.settings = FakeSettings()
        app.tooltip = FakeTooltip()
        app.tray = FakeTray()

        app._activate_action("close")
        self.assertIn("withdraw", app.root.calls)
        self.assertEqual((app.settings.window_x, app.settings.window_y), (120, 240))

        app.show()
        self.assertEqual(
            app.root.calls[-4:],
            ["deiconify", "lift", ("-topmost", True), "focus_force"],
        )


if __name__ == "__main__":
    unittest.main()
