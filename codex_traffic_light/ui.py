from __future__ import annotations

import math
import os
import time
import tkinter as tk
from tkinter import messagebox

from .audio import play_async
from .integration import hooks_installed, install_hooks
from .models import APPROVAL, COMPLETED, ERROR, IDLE, RUNNING, AggregateSnapshot
from .monitor import MonitorWorker
from .settings import Settings
from .startup import set_start_with_windows, starts_with_windows
from .windows import flash_window, open_codex


TRANSPARENT = "#010203"
PAPER = "#FFFFFF"
INK = "#20282F"
BORDER = "#D7DEE3"
TEXT = "#20282F"
MUTED = "#697781"
SOFT = "#EEF2F3"
RED = "#EF476F"
AMBER = "#F4A62A"
GREEN = "#22A66F"

STATUS_STYLE = {
    APPROVAL: ("等你批准", RED),
    ERROR: ("遇到异常", RED),
    RUNNING: ("正在工作", AMBER),
    COMPLETED: ("任务完成", GREEN),
    IDLE: ("空闲待命", GREEN),
}


class CanvasTooltip:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.window: tk.Toplevel | None = None
        self.job: str | None = None
        self.key = ""

    def schedule(self, key: str, text: str, x: int, y: int) -> None:
        if key == self.key:
            return
        self.hide()
        self.key = key
        if not key:
            return
        self.job = self.root.after(450, lambda: self._show(text, x, y))

    def _show(self, text: str, x: int, y: int) -> None:
        self.job = None
        self.window = tk.Toplevel(self.root)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.geometry(f"+{x + 10}+{y + 16}")
        tk.Label(
            self.window,
            text=text,
            bg=INK,
            fg=PAPER,
            padx=8,
            pady=5,
            font=("Microsoft YaHei UI", 9),
        ).pack()

    def hide(self) -> None:
        if self.job:
            self.root.after_cancel(self.job)
            self.job = None
        if self.window:
            self.window.destroy()
            self.window = None
        self.key = ""


class StickFigurePet(tk.Canvas):
    FULL_SIZE = (470, 270)
    COMPACT_SIZE = (220, 250)

    def __init__(self, master: tk.Widget, settings: Settings) -> None:
        super().__init__(
            master,
            width=self.FULL_SIZE[0],
            height=self.FULL_SIZE[1],
            bg=TRANSPARENT,
            highlightthickness=0,
            borderwidth=0,
        )
        self.settings = settings
        self.status = IDLE
        self.phase = "等待新任务"
        self.task_title = "Codex 任务"
        self.elapsed = "--:--"
        self.activity = "没有活动任务"
        self.hooks_ready = False
        self.pulse = 0.0
        self.compact = settings.compact_mode
        self._draw()

    @property
    def size(self) -> tuple[int, int]:
        return self.COMPACT_SIZE if self.compact else self.FULL_SIZE

    def set_compact(self, compact: bool) -> None:
        self.compact = compact
        width, height = self.size
        self.configure(width=width, height=height)
        self._draw()

    def set_snapshot(
        self,
        status: str,
        phase: str,
        task_title: str,
        elapsed: str,
        activity: str,
    ) -> None:
        self.status = status
        self.phase = phase
        self.task_title = task_title
        self.elapsed = elapsed
        self.activity = activity

    def set_hooks_ready(self, ready: bool) -> None:
        if ready != self.hooks_ready:
            self.hooks_ready = ready
            self._draw()

    def animate(self) -> None:
        self.pulse = (self.pulse + 0.16) % (math.pi * 2)
        self._draw()

    def action_at(self, x: int, y: int) -> str | None:
        for item in reversed(self.find_overlapping(x, y, x, y)):
            for tag in self.gettags(item):
                if tag.startswith("action:"):
                    return tag.split(":", 1)[1]
        return None

    def _round_rect(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        radius: float,
        **kwargs: object,
    ) -> int:
        points = (
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        )
        return self.create_polygon(points, smooth=True, splinesteps=12, **kwargs)

    def _action_box(
        self,
        name: str,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        *,
        label: str,
        fill: str = SOFT,
        foreground: str = TEXT,
        font: tuple[str, int] | tuple[str, int, str] = ("Microsoft YaHei UI", 9),
    ) -> None:
        tags = ("action", f"action:{name}")
        self._round_rect(x1, y1, x2, y2, 7, fill=fill, outline="", tags=tags)
        self.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=label,
            fill=foreground,
            font=font,
            tags=tags,
        )

    def _draw(self) -> None:
        self.delete("all")
        if self.compact:
            self._draw_compact_label()
            self._draw_scene(20, 39, 1.0)
        else:
            self._draw_bubble()
            self._draw_scene(280, 42, 1.02)

    def _draw_compact_label(self) -> None:
        status_name, color = STATUS_STYLE.get(self.status, STATUS_STYLE[IDLE])
        self._round_rect(45, 4, 175, 36, 8, fill=PAPER, outline=BORDER, width=1)
        self.create_polygon(101, 35, 110, 45, 119, 35, fill=PAPER, outline=BORDER)
        self.create_oval(57, 16, 65, 24, fill=color, outline="")
        self.create_text(
            72,
            20,
            text=status_name,
            fill=TEXT,
            anchor="w",
            font=("Microsoft YaHei UI", 9, "bold"),
        )

    def _draw_bubble(self) -> None:
        status_name, color = STATUS_STYLE.get(self.status, STATUS_STYLE[IDLE])
        self.create_polygon(
            247,
            82,
            281,
            102,
            247,
            119,
            fill=PAPER,
            outline=BORDER,
            width=2,
        )
        self._round_rect(8, 10, 252, 218, 8, fill=PAPER, outline=BORDER, width=2)

        self.create_oval(24, 27, 36, 39, fill=color, outline="")
        self.create_text(
            44,
            33,
            text=status_name,
            fill=TEXT,
            anchor="w",
            font=("Microsoft YaHei UI", 13, "bold"),
        )

        icon_tags = ("action", "action:sound")
        self.create_rectangle(188, 19, 212, 43, fill=PAPER, outline="", tags=icon_tags)
        self.create_text(
            200,
            31,
            text="♪",
            fill=MUTED if self.settings.sound_enabled else RED,
            font=("Segoe UI Symbol", 13),
            tags=icon_tags,
        )
        if not self.settings.sound_enabled:
            self.create_line(194, 37, 206, 24, fill=RED, width=2, tags=icon_tags)

        close_tags = ("action", "action:close")
        self.create_rectangle(218, 19, 242, 43, fill=PAPER, outline="", tags=close_tags)
        self.create_text(
            230,
            30,
            text="×",
            fill=MUTED,
            font=("Segoe UI Symbol", 13),
            tags=close_tags,
        )

        self.create_text(
            24,
            63,
            text=self.phase,
            fill=TEXT,
            anchor="w",
            width=205,
            font=("Microsoft YaHei UI", 10),
        )
        self.create_text(
            24,
            90,
            text=self.task_title,
            fill=MUTED,
            anchor="w",
            width=205,
            font=("Microsoft YaHei UI", 9),
        )
        self.create_text(
            24,
            116,
            text=f"{self.elapsed}   {self.activity}",
            fill=MUTED,
            anchor="w",
            width=205,
            font=("Cascadia Mono", 9),
        )
        self.create_line(24, 136, 236, 136, fill=SOFT, width=1)

        hook_color = GREEN if self.hooks_ready else AMBER
        hook_text = "Hooks 已连接" if self.hooks_ready else "当前使用日志监控"
        self.create_oval(24, 151, 32, 159, fill=hook_color, outline="")
        self.create_text(
            40,
            155,
            text=hook_text,
            fill=MUTED,
            anchor="w",
            font=("Microsoft YaHei UI", 8),
        )
        if not self.hooks_ready:
            self._action_box(
                "hooks",
                184,
                143,
                236,
                168,
                label="连接",
                fill="#FFF4D8",
                foreground="#9A6500",
                font=("Microsoft YaHei UI", 8, "bold"),
            )

        self._action_box(
            "open",
            24,
            179,
            145,
            205,
            label="打开 Codex",
            fill=INK,
            foreground=PAPER,
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        self._action_box("compact", 153, 179, 236, 205, label="收起")

    def _draw_scene(self, origin_x: float, origin_y: float, scale: float) -> None:
        if self.status == RUNNING:
            self._draw_working_scene(origin_x, origin_y, scale)
        elif self.status == COMPLETED:
            self._draw_exhausted_scene(origin_x, origin_y, scale)
        elif self.status == APPROVAL:
            self._draw_approval_scene(origin_x, origin_y, scale)
        elif self.status == ERROR:
            self._draw_error_scene(origin_x, origin_y, scale)
        else:
            self._draw_fish_tank_scene(origin_x, origin_y, scale)

    @staticmethod
    def _point(
        origin_x: float,
        origin_y: float,
        scale: float,
        x: float,
        y: float,
    ) -> tuple[float, float]:
        return origin_x + x * scale, origin_y + y * scale

    def _scene_line(
        self,
        origin_x: float,
        origin_y: float,
        scale: float,
        points: tuple[tuple[float, float], ...],
        *,
        fill: str = INK,
        width: float = 5,
        smooth: bool = True,
        **kwargs: object,
    ) -> int:
        coordinates = [
            coordinate
            for x, y in points
            for coordinate in self._point(origin_x, origin_y, scale, x, y)
        ]
        if fill == INK and width >= 4:
            self.create_line(
                *coordinates,
                fill="#F7F9F8",
                width=max(2, int((width + 3) * scale)),
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
                smooth=smooth,
                **kwargs,
            )
        return self.create_line(
            *coordinates,
            fill=fill,
            width=max(1, int(width * scale)),
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
            smooth=smooth,
            **kwargs,
        )

    def _scene_oval(
        self,
        origin_x: float,
        origin_y: float,
        scale: float,
        box: tuple[float, float, float, float],
        **kwargs: object,
    ) -> int:
        x1, y1 = self._point(origin_x, origin_y, scale, box[0], box[1])
        x2, y2 = self._point(origin_x, origin_y, scale, box[2], box[3])
        return self.create_oval(x1, y1, x2, y2, **kwargs)

    def _scene_polygon(
        self,
        origin_x: float,
        origin_y: float,
        scale: float,
        points: tuple[tuple[float, float], ...],
        **kwargs: object,
    ) -> int:
        coordinates = [
            coordinate
            for x, y in points
            for coordinate in self._point(origin_x, origin_y, scale, x, y)
        ]
        return self.create_polygon(coordinates, **kwargs)

    def _draw_head(
        self,
        origin_x: float,
        origin_y: float,
        scale: float,
        center: tuple[float, float],
        radius: float,
        expression: str,
    ) -> None:
        cx, cy = center
        self._scene_oval(
            origin_x,
            origin_y,
            scale,
            (cx - radius, cy - radius, cx + radius, cy + radius),
            fill="#FFFDF8",
            outline=INK,
            width=max(3, int(4 * scale)),
        )

        if expression in {"tired", "sad"}:
            eye_y = cy - 4
            eye_slant = 3 if expression == "sad" else 1
            self._scene_line(
                origin_x,
                origin_y,
                scale,
                ((cx - 10, eye_y + eye_slant), (cx - 4, eye_y)),
                width=2,
                smooth=False,
            )
            self._scene_line(
                origin_x,
                origin_y,
                scale,
                ((cx + 4, eye_y), (cx + 10, eye_y + eye_slant)),
                width=2,
                smooth=False,
            )
        else:
            look = 2 if expression in {"focused", "curious"} else 0
            for eye_x in (cx - 8, cx + 8):
                self._scene_oval(
                    origin_x,
                    origin_y,
                    scale,
                    (eye_x - 2 + look, cy - 6, eye_x + 2 + look, cy - 2),
                    fill=INK,
                    outline="",
                )

        if expression == "surprised":
            self._scene_oval(
                origin_x,
                origin_y,
                scale,
                (cx - 4, cy + 6, cx + 4, cy + 15),
                fill="",
                outline=INK,
                width=2,
            )
        elif expression == "tired":
            self._scene_oval(
                origin_x,
                origin_y,
                scale,
                (cx + 1, cy + 5, cx + 10, cy + 13),
                fill="",
                outline=INK,
                width=2,
            )
        elif expression == "sad":
            x1, y1 = self._point(origin_x, origin_y, scale, cx - 9, cy + 7)
            x2, y2 = self._point(origin_x, origin_y, scale, cx + 9, cy + 20)
            self.create_arc(x1, y1, x2, y2, start=20, extent=140, style=tk.ARC, outline=INK, width=2)
        elif expression == "focused":
            self._scene_line(
                origin_x,
                origin_y,
                scale,
                ((cx + 1, cy + 10), (cx + 9, cy + 10)),
                width=2,
                smooth=False,
            )
        else:
            x1, y1 = self._point(origin_x, origin_y, scale, cx - 9, cy + 2)
            x2, y2 = self._point(origin_x, origin_y, scale, cx + 9, cy + 15)
            self.create_arc(x1, y1, x2, y2, start=200, extent=140, style=tk.ARC, outline=INK, width=2)

    def _draw_scarf(
        self,
        origin_x: float,
        origin_y: float,
        scale: float,
        x: float,
        y: float,
        color: str,
        wave: float = 0,
    ) -> None:
        self._scene_line(origin_x, origin_y, scale, ((x - 8, y), (x + 9, y)), fill=color, width=4)
        self._scene_line(
            origin_x,
            origin_y,
            scale,
            ((x + 7, y + 1), (x + 20, y + 7 + wave)),
            fill=color,
            width=3,
        )

    def _draw_working_scene(self, ox: float, oy: float, scale: float) -> None:
        typing = math.sin(self.pulse * 4.5) * 2.6
        breathe = math.sin(self.pulse * 2) * 0.8
        blink = int(self.pulse * 2) % 2 == 0

        self._scene_oval(ox, oy, scale, (10, 193, 178, 205), fill="#CBD3D8", outline="")

        # Chair and seated lower body sit behind the desk.
        x1, y1 = self._point(ox, oy, scale, 12, 78)
        x2, y2 = self._point(ox, oy, scale, 57, 151)
        self._round_rect(x1, y1, x2, y2, 7 * scale, fill="#DDE4E7", outline=INK, width=2)
        self._scene_line(ox, oy, scale, ((24, 148), (18, 195)), fill=INK, width=4)
        self._scene_line(ox, oy, scale, ((52, 148), (66, 195)), fill=INK, width=4)

        self._scene_line(ox, oy, scale, ((57, 83), (59, 136)), width=6)
        self._scene_line(ox, oy, scale, ((59, 136), (88, 151), (99, 194)), width=6)
        self._scene_line(ox, oy, scale, ((59, 136), (49, 161), (69, 194)), width=6)
        self._scene_line(ox, oy, scale, ((92, 194), (108, 194)), width=5)
        self._scene_line(ox, oy, scale, ((62, 194), (77, 194)), width=5)

        # Desk, laptop and a steaming mug.
        self._scene_polygon(
            ox,
            oy,
            scale,
            ((76, 128), (179, 128), (179, 138), (76, 138)),
            fill="#B9C3C8",
            outline=INK,
            width=2,
        )
        self._scene_line(ox, oy, scale, ((87, 138), (80, 199)), width=5)
        self._scene_line(ox, oy, scale, ((169, 138), (176, 199)), width=5)

        self._scene_polygon(
            ox,
            oy,
            scale,
            ((106, 77), (168, 77), (161, 126), (99, 126)),
            fill="#303A40",
            outline=INK,
            width=2,
        )
        self._scene_polygon(
            ox,
            oy,
            scale,
            ((111, 83), (162, 83), (157, 118), (106, 118)),
            fill="#DDF8F4",
            outline="",
        )
        self._scene_line(ox, oy, scale, ((113, 91), (145, 91)), fill="#2E7D78", width=2, smooth=False)
        self._scene_line(ox, oy, scale, ((113, 99), (151, 99)), fill=AMBER, width=2, smooth=False)
        self._scene_line(ox, oy, scale, ((113, 107), (137, 107)), fill="#2E7D78", width=2, smooth=False)
        if blink:
            self._scene_line(ox, oy, scale, ((142, 107), (151, 107)), fill=INK, width=2, smooth=False)
        self._scene_polygon(
            ox,
            oy,
            scale,
            ((96, 126), (166, 126), (174, 132), (91, 132)),
            fill="#65727A",
            outline=INK,
            width=2,
        )
        self._scene_oval(ox, oy, scale, (84, 111, 99, 128), fill="#FFF7E7", outline=INK, width=2)
        self._scene_line(ox, oy, scale, ((98, 115), (104, 115), (104, 123), (99, 123)), width=2)
        steam = math.sin(self.pulse * 2) * 2
        self._scene_line(ox, oy, scale, ((89, 108), (87 + steam, 102), (90, 96)), fill=MUTED, width=2)
        self._scene_line(ox, oy, scale, ((95, 108), (97 - steam, 101), (95, 94)), fill=MUTED, width=2)

        # Torso, typing arms and focused face.
        self._scene_line(ox, oy, scale, ((57, 79), (83, 102), (111, 128 + typing)), width=5)
        self._scene_line(ox, oy, scale, ((58, 84), (76, 115), (127, 129 - typing)), width=5)
        self._scene_oval(ox, oy, scale, (107, 125 + typing, 115, 133 + typing), fill="#FFFDF8", outline=INK, width=1)
        self._scene_oval(ox, oy, scale, (123, 125 - typing, 131, 133 - typing), fill="#FFFDF8", outline=INK, width=1)
        self._draw_scarf(ox, oy, scale, 57, 78, AMBER, math.sin(self.pulse * 2) * 1.5)
        self._draw_head(ox, oy, scale, (52, 53 + breathe), 22, "focused")
        self._scene_line(ox, oy, scale, ((31, 48 + breathe), (37, 45 + breathe)), width=2, smooth=False)

    def _draw_fish_tank_scene(self, ox: float, oy: float, scale: float) -> None:
        hand_x = 106 + math.sin(self.pulse * 1.7) * 7
        hand_y = 125 + math.cos(self.pulse * 1.7) * 6
        fish_x = 137 - math.sin(self.pulse * 1.25) * 18
        fish_y = 119 + math.sin(self.pulse * 2.1) * 6

        self._scene_oval(ox, oy, scale, (3, 193, 183, 204), fill="#CBD3D8", outline="")

        # Tank water and interior details.
        self._scene_polygon(
            ox,
            oy,
            scale,
            ((76, 60), (179, 60), (174, 180), (81, 180)),
            fill="#E9FBFC",
            outline="",
        )
        self._scene_polygon(
            ox,
            oy,
            scale,
            ((79, 77), (177, 77), (173, 177), (82, 177)),
            fill="#BFECEF",
            outline="",
        )
        self._scene_polygon(
            ox,
            oy,
            scale,
            ((82, 164), (104, 157), (129, 166), (151, 158), (174, 165), (173, 178), (82, 178)),
            fill="#F2D37E",
            outline="",
        )
        self._scene_line(ox, oy, scale, ((103, 165), (102, 137), (94, 127)), fill="#2E9B78", width=3)
        self._scene_line(ox, oy, scale, ((103, 151), (112, 140)), fill="#2E9B78", width=3)
        self._scene_line(ox, oy, scale, ((158, 164), (159, 143), (151, 134)), fill="#3BAA72", width=3)
        self._scene_line(ox, oy, scale, ((159, 151), (168, 141)), fill="#3BAA72", width=3)
        self._scene_oval(ox, oy, scale, (121, 165, 144, 176), fill="#A8B0B3", outline="")

        self._draw_fish(ox, oy, scale, fish_x, fish_y, direction=1, color="#FF8C55")
        self._draw_fish(ox, oy, scale, 151 + math.sin(self.pulse) * 8, 145, direction=-1, color="#6A8FE8", small=True)
        for index, (bubble_x, offset) in enumerate(((117, 0), (148, 19), (165, 37))):
            bubble_y = 155 - ((self.pulse * 13 + offset) % 67)
            radius = 2 + index * 0.6
            self._scene_oval(
                ox,
                oy,
                scale,
                (bubble_x - radius, bubble_y - radius, bubble_x + radius, bubble_y + radius),
                fill="",
                outline="#4AAEB8",
                width=1,
            )

        # The curious stick figure leans over and reaches into the water.
        self._scene_line(ox, oy, scale, ((43, 89), (46, 146)), width=6)
        self._scene_line(ox, oy, scale, ((46, 146), (25, 195)), width=6)
        self._scene_line(ox, oy, scale, ((46, 146), (63, 195)), width=6)
        self._scene_line(ox, oy, scale, ((19, 195), (34, 195)), width=5)
        self._scene_line(ox, oy, scale, ((57, 195), (72, 195)), width=5)
        self._scene_line(ox, oy, scale, ((44, 96), (68, 75), (84, 69)), width=5)
        self._scene_oval(ox, oy, scale, (80, 65, 88, 73), fill="#FFFDF8", outline=INK, width=1)
        self._scene_line(ox, oy, scale, ((46, 99), (74, 105), (91, 111), (hand_x, hand_y)), width=5)
        self._scene_oval(ox, oy, scale, (hand_x - 5, hand_y - 5, hand_x + 5, hand_y + 5), fill="#FFFDF8", outline=INK, width=1)
        self._scene_line(ox, oy, scale, ((hand_x - 4, hand_y + 1), (hand_x - 9, hand_y + 6)), width=1.5)
        self._scene_line(ox, oy, scale, ((hand_x + 1, hand_y + 4), (hand_x + 3, hand_y + 10)), width=1.5)
        self._draw_scarf(ox, oy, scale, 43, 89, GREEN, math.sin(self.pulse) * 2)
        self._draw_head(ox, oy, scale, (32, 67 + math.sin(self.pulse) * 1.2), 21, "curious")

        # Crisp glass edges and animated ripples stay above the submerged arm.
        self._scene_line(ox, oy, scale, ((76, 60), (179, 60), (174, 180), (81, 180), (76, 60)), fill="#3D8F98", width=3, smooth=False)
        self._scene_line(ox, oy, scale, ((79, 77), (177, 77)), fill="#4AAEB8", width=2)
        ripple = 4 + (math.sin(self.pulse * 2) + 1) * 3
        self._scene_line(ox, oy, scale, ((84 - ripple, 78), (84, 76), (84 + ripple, 78)), fill="#2F9EAD", width=1.5)
        self._scene_line(ox, oy, scale, ((88, 68), (86, 113)), fill="#FFFFFF", width=2)
        self._scene_line(ox, oy, scale, ((169, 70), (166, 99)), fill="#FFFFFF", width=2)

    def _draw_fish(
        self,
        ox: float,
        oy: float,
        scale: float,
        x: float,
        y: float,
        *,
        direction: int,
        color: str,
        small: bool = False,
    ) -> None:
        body_w = 11 if small else 15
        body_h = 6 if small else 8
        tail_x = x - direction * (body_w + 8)
        self._scene_polygon(
            ox,
            oy,
            scale,
            ((x - direction * body_w, y), (tail_x, y - body_h), (tail_x, y + body_h)),
            fill=color,
            outline=INK,
            width=1,
        )
        self._scene_oval(ox, oy, scale, (x - body_w, y - body_h, x + body_w, y + body_h), fill=color, outline=INK, width=1)
        eye_x = x + direction * (body_w - 4)
        self._scene_oval(ox, oy, scale, (eye_x - 1.5, y - 2.5, eye_x + 1.5, y + 0.5), fill=INK, outline="")
        self._scene_line(ox, oy, scale, ((x - 2, y), (x + direction * 4, y + 4)), fill="#FFFFFF", width=1.5)

    def _draw_exhausted_scene(self, ox: float, oy: float, scale: float) -> None:
        breath = math.sin(self.pulse * 2) * 2.2
        shoulder_y = 101 + breath
        head_y = 77 + breath

        self._scene_oval(ox, oy, scale, (13, 190, 174, 203), fill="#CBD3D8", outline="")
        self._scene_line(ox, oy, scale, ((72, 126), (53, 155), (40, 193)), width=6)
        self._scene_line(ox, oy, scale, ((72, 126), (99, 157), (124, 193)), width=6)
        self._scene_line(ox, oy, scale, ((34, 193), (49, 193)), width=5)
        self._scene_line(ox, oy, scale, ((117, 193), (134, 193)), width=5)

        self._scene_line(ox, oy, scale, ((72, 126), (104, shoulder_y)), width=7)
        self._scene_line(ox, oy, scale, ((101, shoulder_y + 3), (78, 132), (54, 155)), width=5)
        self._scene_line(ox, oy, scale, ((106, shoulder_y + 4), (121, 133), (99, 157)), width=5)
        self._scene_oval(ox, oy, scale, (49, 151, 59, 160), fill="#FFFDF8", outline=INK, width=1)
        self._scene_oval(ox, oy, scale, (94, 153, 104, 162), fill="#FFFDF8", outline=INK, width=1)
        self._draw_scarf(ox, oy, scale, 105, shoulder_y, GREEN, 3 + breath)
        self._draw_head(ox, oy, scale, (128, head_y), 23, "tired")

        # Looping sweat droplets and breath puffs communicate recovery.
        for index, (drop_x, delay) in enumerate(((145, 0), (155, 17), (116, 31))):
            travel = (self.pulse * 11 + delay) % 42
            drop_y = 44 + travel
            self._draw_sweat_drop(ox, oy, scale, drop_x, drop_y, 4 - index * 0.5)

        puff_phase = (self.pulse * 13) % 34
        for index in range(3):
            distance = (puff_phase + index * 11) % 34
            radius = 5 - distance * 0.07
            self._scene_oval(
                ox,
                oy,
                scale,
                (157 + distance - radius, 88 - radius, 157 + distance + radius, 88 + radius),
                fill="",
                outline="#AAB5BB",
                width=max(1, int(2 * scale)),
            )
        self._scene_line(ox, oy, scale, ((61, 139), (66, 142)), fill=RED, width=2)
        self._scene_line(ox, oy, scale, ((111, 141), (116, 137)), fill=RED, width=2)

    def _draw_sweat_drop(
        self,
        ox: float,
        oy: float,
        scale: float,
        x: float,
        y: float,
        radius: float,
    ) -> None:
        self._scene_polygon(
            ox,
            oy,
            scale,
            ((x, y - radius * 1.7), (x - radius, y + radius), (x, y + radius * 1.5), (x + radius, y + radius)),
            fill="#3AB8D4",
            outline="#257F98",
            width=1,
            smooth=True,
        )

    def _draw_approval_scene(self, ox: float, oy: float, scale: float) -> None:
        wave = math.sin(self.pulse * 4) * 8
        bob = math.sin(self.pulse * 2) * 1.5
        self._scene_oval(ox, oy, scale, (21, 192, 166, 203), fill="#CBD3D8", outline="")
        self._scene_line(ox, oy, scale, ((88, 82 + bob), (88, 141 + bob)), width=7)
        self._scene_line(ox, oy, scale, ((88, 141), (57, 194)), width=6)
        self._scene_line(ox, oy, scale, ((88, 141), (119, 194)), width=6)
        self._scene_line(ox, oy, scale, ((50, 194), (65, 194)), width=5)
        self._scene_line(ox, oy, scale, ((112, 194), (127, 194)), width=5)
        self._scene_line(ox, oy, scale, ((88, 91), (54, 58 + wave)), width=5)
        self._scene_line(ox, oy, scale, ((88, 91), (125, 58 - wave)), width=5)
        self._scene_oval(ox, oy, scale, (49, 53 + wave, 59, 63 + wave), fill="#FFFDF8", outline=INK, width=1)
        self._scene_oval(ox, oy, scale, (120, 53 - wave, 130, 63 - wave), fill="#FFFDF8", outline=INK, width=1)
        self._draw_scarf(ox, oy, scale, 88, 82 + bob, RED, math.sin(self.pulse * 3) * 3)
        self._draw_head(ox, oy, scale, (88, 55 + bob), 23, "surprised")
        pulse_size = 4 + (math.sin(self.pulse * 3) + 1) * 2
        x1, y1 = self._point(ox, oy, scale, 144 - pulse_size, 35 - pulse_size)
        x2, y2 = self._point(ox, oy, scale, 144 + pulse_size, 35 + pulse_size)
        self.create_oval(x1, y1, x2, y2, fill=RED, outline="")
        self.create_text(
            *self._point(ox, oy, scale, 144, 35),
            text="!",
            fill=PAPER,
            font=("Segoe UI", max(9, int(11 * scale)), "bold"),
        )

    def _draw_error_scene(self, ox: float, oy: float, scale: float) -> None:
        droop = math.sin(self.pulse) * 1.2
        self._scene_oval(ox, oy, scale, (9, 191, 178, 203), fill="#CBD3D8", outline="")
        self._scene_line(ox, oy, scale, ((54, 96 + droop), (61, 143)), width=7)
        self._scene_line(ox, oy, scale, ((61, 143), (37, 190)), width=6)
        self._scene_line(ox, oy, scale, ((61, 143), (89, 190)), width=6)
        self._scene_line(ox, oy, scale, ((31, 190), (45, 190)), width=5)
        self._scene_line(ox, oy, scale, ((83, 190), (98, 190)), width=5)
        self._scene_line(ox, oy, scale, ((55, 105), (83, 128), (112, 143)), width=5)
        self._scene_line(ox, oy, scale, ((56, 108), (75, 138), (94, 154)), width=5)
        self._draw_scarf(ox, oy, scale, 54, 96 + droop, RED, -2)
        self._draw_head(ox, oy, scale, (43, 74 + droop), 22, "sad")

        flicker = RED if int(self.pulse * 3) % 2 else "#B73A54"
        self._scene_polygon(
            ox,
            oy,
            scale,
            ((112, 116), (171, 127), (162, 165), (105, 153)),
            fill="#343E44",
            outline=INK,
            width=2,
        )
        self._scene_line(ox, oy, scale, ((121, 129), (150, 153)), fill=flicker, width=4)
        self._scene_line(ox, oy, scale, ((151, 135), (122, 149)), fill=flicker, width=4)
        self._scene_polygon(
            ox,
            oy,
            scale,
            ((103, 153), (163, 165), (173, 172), (101, 158)),
            fill="#66737A",
            outline=INK,
            width=2,
        )


class CodexDesktopPetApp:
    ACTION_TOOLTIPS = {
        "sound": "开启或关闭声音",
        "close": "退出桌宠",
        "hooks": "连接 Codex Hooks",
        "open": "打开 Codex",
        "compact": "切换迷你模式",
    }

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.settings = Settings.load()
        self.worker = MonitorWorker()
        self.worker.start()
        self._baseline_ready = False
        self._task_statuses: dict[str, str] = {}
        self._last_approval_sound = 0.0
        self._last_snapshot = AggregateSnapshot(IDLE, None, ())
        self._drag_offset = (0, 0)
        self._pointer_origin = (0, 0)
        self._pressed_action: str | None = None
        self._dragging = False
        self._last_integration_check = 0.0

        self.root.title("Codex 桌宠")
        self.root.configure(bg=TRANSPARENT)
        self.root.resizable(False, False)
        self.root.overrideredirect(os.environ.get("CODEX_DESKTOP_PET_WINDOWED") != "1")
        self.root.attributes("-topmost", self.settings.always_on_top)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.pet = StickFigurePet(root, self.settings)
        self.pet.pack()
        self.tooltip = CanvasTooltip(root)
        self._build_menu()
        self._bind_pointer_events()
        self._apply_mode(initial=True)
        self._place_window()

        self.root.after(120, self._tick)
        self.root.after(80, self._animate)

    def _bind_pointer_events(self) -> None:
        self.pet.bind("<Button-1>", self._pointer_down)
        self.pet.bind("<B1-Motion>", self._pointer_move)
        self.pet.bind("<ButtonRelease-1>", self._pointer_up)
        self.pet.bind("<Motion>", self._hover)
        self.pet.bind("<Leave>", lambda _event: self.tooltip.hide())
        self.pet.bind("<Button-3>", self._show_menu)
        self.pet.bind("<Double-Button-1>", self._double_click)

    def _build_menu(self) -> None:
        self.menu = tk.Menu(
            self.root,
            tearoff=False,
            bg=PAPER,
            fg=TEXT,
            activebackground=SOFT,
            activeforeground=TEXT,
            borderwidth=1,
            relief="solid",
            font=("Microsoft YaHei UI", 9),
        )
        self.sound_var = tk.BooleanVar(value=self.settings.sound_enabled)
        self.topmost_var = tk.BooleanVar(value=self.settings.always_on_top)
        self.startup_var = tk.BooleanVar(value=starts_with_windows())
        self.menu.add_command(label="打开 Codex", command=open_codex)
        self.menu.add_separator()
        self.menu.add_checkbutton(label="声音提醒", variable=self.sound_var, command=self._menu_sound)
        self.menu.add_checkbutton(label="始终置顶", variable=self.topmost_var, command=self._menu_topmost)
        self.menu.add_checkbutton(label="开机启动", variable=self.startup_var, command=self._menu_startup)
        self.menu.add_command(label="测试声音", command=lambda: play_async("test"))
        self.menu.add_command(label="修复 Hooks", command=self.enable_hooks)
        self.menu.add_separator()
        self.menu.add_command(label="显示/隐藏状态气泡", command=self.toggle_compact)
        self.menu.add_command(label="退出桌宠", command=self.close)

    def _show_menu(self, event: tk.Event) -> None:
        self.tooltip.hide()
        self.sound_var.set(self.settings.sound_enabled)
        self.topmost_var.set(self.settings.always_on_top)
        self.startup_var.set(starts_with_windows())
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _pointer_down(self, event: tk.Event) -> None:
        self.tooltip.hide()
        self._pointer_origin = (event.x_root, event.y_root)
        self._drag_offset = (
            event.x_root - self.root.winfo_x(),
            event.y_root - self.root.winfo_y(),
        )
        self._pressed_action = self.pet.action_at(event.x, event.y)
        self._dragging = False

    def _pointer_move(self, event: tk.Event) -> None:
        if self._pressed_action:
            return
        distance = abs(event.x_root - self._pointer_origin[0]) + abs(event.y_root - self._pointer_origin[1])
        if distance < 3:
            return
        self._dragging = True
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.root.geometry(f"+{x}+{y}")

    def _pointer_up(self, event: tk.Event) -> None:
        action = self.pet.action_at(event.x, event.y)
        if self._pressed_action and action == self._pressed_action:
            self._activate_action(action)
        elif self._dragging:
            self._save_position()
        self._pressed_action = None
        self._dragging = False

    def _double_click(self, event: tk.Event) -> None:
        if not self.pet.action_at(event.x, event.y):
            self.toggle_compact()

    def _hover(self, event: tk.Event) -> None:
        action = self.pet.action_at(event.x, event.y)
        self.pet.configure(cursor="hand2" if action else "fleur")
        key = action or ""
        self.tooltip.schedule(
            key,
            self.ACTION_TOOLTIPS.get(key, ""),
            event.x_root,
            event.y_root,
        )

    def _activate_action(self, action: str) -> None:
        if action == "sound":
            self.toggle_sound()
        elif action == "close":
            self.close()
        elif action == "hooks":
            self.enable_hooks()
        elif action == "open":
            open_codex()
        elif action == "compact":
            self.toggle_compact()

    def _place_window(self) -> None:
        self.root.update_idletasks()
        width, height = self.pet.size
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        default_x = max(0, screen_w - width - 24)
        default_y = max(0, screen_h - height - 72)
        x = self.settings.window_x if self.settings.window_x is not None else default_x
        y = self.settings.window_y if self.settings.window_y is not None else default_y
        x = min(max(0, x), max(0, screen_w - width))
        y = min(max(0, y), max(0, screen_h - height - 48))
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _apply_mode(self, initial: bool = False) -> None:
        self.pet.set_compact(self.settings.compact_mode)
        width, height = self.pet.size
        if initial:
            self.root.geometry(f"{width}x{height}")
            return
        x, y = self.root.winfo_x(), self.root.winfo_y()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = min(max(0, x), max(0, screen_w - width))
        y = min(max(0, y), max(0, screen_h - height - 48))
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def toggle_compact(self) -> None:
        self.tooltip.hide()
        self.settings.compact_mode = not self.settings.compact_mode
        self._apply_mode()
        self.settings.save()

    def toggle_sound(self) -> None:
        self.settings.sound_enabled = not self.settings.sound_enabled
        self.sound_var.set(self.settings.sound_enabled)
        self.settings.save()
        self.pet._draw()
        if self.settings.sound_enabled:
            play_async("test")

    def _menu_sound(self) -> None:
        self.settings.sound_enabled = self.sound_var.get()
        self.settings.save()
        self.pet._draw()

    def _menu_topmost(self) -> None:
        self.settings.always_on_top = self.topmost_var.get()
        self.root.attributes("-topmost", self.settings.always_on_top)
        self.settings.save()

    def _menu_startup(self) -> None:
        try:
            set_start_with_windows(self.startup_var.get())
        except OSError as exc:
            messagebox.showerror("Codex 桌宠", f"无法修改开机启动：\n{exc}")
            self.startup_var.set(starts_with_windows())

    def enable_hooks(self) -> None:
        try:
            path = install_hooks()
        except (OSError, ValueError) as exc:
            messagebox.showerror("Codex 桌宠", f"Hooks 安装失败：\n{exc}")
            return
        self._update_integration(force=True)
        messagebox.showinfo(
            "Codex 桌宠",
            f"Hooks 已写入：\n{path}\n\n首次使用请在 Codex 中打开 /hooks 并信任这些 hooks。",
        )

    def _tick(self) -> None:
        snapshot = self.worker.snapshot()
        self._render(snapshot)
        self._handle_alerts(snapshot)
        self._update_integration()
        self.root.after(250, self._tick)

    def _animate(self) -> None:
        self.pet.animate()
        self.root.after(80, self._animate)

    def _render(self, snapshot: AggregateSnapshot) -> None:
        self._last_snapshot = snapshot
        task = snapshot.selected
        if task:
            phase = self._truncate(task.phase, 24)
            task_title = self._truncate(task.title, 27)
            elapsed = self._elapsed(task.started_at, task.updated_at, task.status)
        else:
            phase = "等待新任务"
            task_title = "Codex 任务"
            elapsed = "--:--"

        parts = []
        if snapshot.approval_count:
            parts.append(f"{snapshot.approval_count} 待批准")
        if snapshot.running_count:
            parts.append(f"{snapshot.running_count} 运行中")
        if snapshot.error_count:
            parts.append(f"{snapshot.error_count} 异常")
        activity = " · ".join(parts) if parts else "没有活动任务"
        self.pet.set_snapshot(snapshot.status, phase, task_title, elapsed, activity)

    def _handle_alerts(self, snapshot: AggregateSnapshot) -> None:
        current = {task.session_id: task.status for task in snapshot.tasks}
        if not self._baseline_ready:
            self._task_statuses = current
            self._baseline_ready = True
            return

        transitions: list[str] = []
        for task in snapshot.tasks:
            previous = self._task_statuses.get(task.session_id)
            if previous == task.status or previous is None:
                continue
            if task.status in {APPROVAL, COMPLETED, ERROR}:
                transitions.append(task.status)
        self._task_statuses = current

        alert = None
        if APPROVAL in transitions:
            alert = "approval"
            self._last_approval_sound = time.time()
        elif ERROR in transitions:
            alert = "error"
        elif COMPLETED in transitions:
            alert = "completed"

        now = time.time()
        if (
            snapshot.status == APPROVAL
            and now - self._last_approval_sound >= self.settings.approval_repeat_seconds
        ):
            alert = "approval"
            self._last_approval_sound = now

        if alert:
            if self.settings.sound_enabled:
                play_async(alert)
            self.root.lift()
            flash_window(self.root.winfo_id())

    def _update_integration(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_integration_check < 5:
            return
        self._last_integration_check = now
        self.pet.set_hooks_ready(hooks_installed())

    def _save_position(self) -> None:
        self.settings.window_x = self.root.winfo_x()
        self.settings.window_y = self.root.winfo_y()
        self.settings.save()

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        cleaned = " ".join(text.split())
        return cleaned if len(cleaned) <= limit else cleaned[: limit - 1] + "…"

    @staticmethod
    def _elapsed(started_at: float, updated_at: float, status: str) -> str:
        if not started_at:
            return "--:--"
        end = time.time() if status in {RUNNING, APPROVAL} else max(updated_at, started_at)
        seconds = max(0, int(end - started_at))
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"

    def close(self) -> None:
        self.tooltip.hide()
        self.worker.stop()
        self._save_position()
        self.root.destroy()


# Kept as an import-compatible alias for existing integrations.
CodexTrafficLightApp = CodexDesktopPetApp


def run_app() -> None:
    root = tk.Tk()
    CodexDesktopPetApp(root)
    root.mainloop()
