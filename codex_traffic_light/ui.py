from __future__ import annotations

import math
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


BG = "#101418"
PANEL = "#171C21"
PANEL_ALT = "#1D2329"
BORDER = "#303840"
TEXT = "#F3F5F7"
MUTED = "#929CA6"
RED = "#FF5263"
AMBER = "#F5B942"
GREEN = "#38D07D"

STATUS_STYLE = {
    APPROVAL: ("等待批准", RED),
    ERROR: ("任务异常", RED),
    RUNNING: ("正在工作", AMBER),
    COMPLETED: ("任务完成", GREEN),
    IDLE: ("空闲", GREEN),
}


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.window: tk.Toplevel | None = None
        self.job: str | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _schedule(self, _event: tk.Event) -> None:
        self._hide()
        self.job = self.widget.after(450, self._show)

    def _show(self) -> None:
        x = self.widget.winfo_rootx() + 8
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.window = tk.Toplevel(self.widget)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.geometry(f"+{x}+{y}")
        tk.Label(
            self.window,
            text=self.text,
            bg="#2A3138",
            fg=TEXT,
            padx=8,
            pady=5,
            font=("Microsoft YaHei UI", 9),
        ).pack()

    def _hide(self, _event: tk.Event | None = None) -> None:
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.window:
            self.window.destroy()
            self.window = None


class TrafficLight(tk.Canvas):
    def __init__(self, master: tk.Widget) -> None:
        super().__init__(
            master,
            width=126,
            height=234,
            bg=BG,
            highlightthickness=0,
        )
        self.status = IDLE
        self.pulse = 0.0
        self._draw()

    def set_status(self, status: str) -> None:
        if status != self.status:
            self.status = status
            self.pulse = 0.0
            self._draw()

    def animate(self) -> None:
        self.pulse = (self.pulse + 0.16) % (math.pi * 2)
        if self.status in {RUNNING, APPROVAL}:
            self._draw()

    def _round_rect(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        radius: int,
        **kwargs: str,
    ) -> int:
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _draw(self) -> None:
        self.delete("all")
        self._round_rect(9, 4, 117, 230, 24, fill="#0B0E11", outline="#39424A")
        self._round_rect(17, 12, 109, 222, 18, fill="#151A1F", outline="#242B31")

        active = {
            APPROVAL: "red",
            ERROR: "red",
            RUNNING: "amber",
            COMPLETED: "green",
            IDLE: "green",
        }.get(self.status, "green")
        bulbs = (
            ("red", 52, RED, "#3A171D"),
            ("amber", 116, AMBER, "#382D14"),
            ("green", 180, GREEN, "#153522"),
        )
        for name, y, color, off_color in bulbs:
            is_active = name == active
            if is_active:
                pulse = (math.sin(self.pulse) + 1) / 2
                glow_width = int(5 + pulse * 4) if self.status in {APPROVAL, RUNNING} else 6
                self.create_oval(
                    25 - glow_width,
                    y - 37 - glow_width,
                    101 + glow_width,
                    y + 37 + glow_width,
                    fill=self._blend(color, BG, 0.22),
                    outline="",
                )
            self.create_oval(28, y - 34, 98, y + 34, fill="#090B0D", outline="#30373E", width=2)
            self.create_oval(
                33,
                y - 29,
                93,
                y + 29,
                fill=color if is_active else off_color,
                outline=self._blend(color, "#FFFFFF", 0.35) if is_active else "#23292F",
                width=2,
            )
            if is_active:
                self.create_oval(46, y - 19, 67, y + 2, fill="#FFFFFF", outline="", stipple="gray50")

    @staticmethod
    def _blend(a: str, b: str, amount: float) -> str:
        ar, ag, ab = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)
        br, bg, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)
        values = (
            int(ar * (1 - amount) + br * amount),
            int(ag * (1 - amount) + bg * amount),
            int(ab * (1 - amount) + bb * amount),
        )
        return "#%02X%02X%02X" % values


class CodexTrafficLightApp:
    FULL_SIZE = (334, 400)
    COMPACT_SIZE = (152, 320)

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
        self._last_integration_check = 0.0

        self.root.title("Codex Traffic Light")
        self.root.configure(bg=BORDER)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", self.settings.always_on_top)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.shell = tk.Frame(root, bg=BG, highlightbackground=BORDER, highlightthickness=1)
        self.shell.pack(fill="both", expand=True)
        self._build_header()
        self._build_content()
        self._build_menu()
        self._apply_mode(initial=True)
        self._place_window()

        for widget in (self.shell, self.header, self.traffic):
            widget.bind("<Button-3>", self._show_menu, add="+")
        self.traffic.bind("<Double-Button-1>", lambda _event: self.toggle_compact())

        self.root.after(200, self._tick)

    def _build_header(self) -> None:
        self.header = tk.Frame(self.shell, bg=PANEL, height=40)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        self.header.bind("<ButtonPress-1>", self._start_drag)
        self.header.bind("<B1-Motion>", self._drag)
        self.header.bind("<ButtonRelease-1>", self._end_drag)

        self.brand = tk.Label(
            self.header,
            text="CODEX SIGNAL",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 10),
        )
        self.brand.pack(side="left", padx=(12, 4))
        self.brand.bind("<ButtonPress-1>", self._start_drag)
        self.brand.bind("<B1-Motion>", self._drag)
        self.brand.bind("<ButtonRelease-1>", self._end_drag)

        self.close_button = self._header_button("×", self.close, "退出监控器")
        self.compact_button = self._header_button("▣", self.toggle_compact, "切换迷你模式")
        self.compact_button.pack(side="right")
        self.sound_button = self._header_button("♪", self.toggle_sound, "开启或关闭声音")
        self.sound_button.pack(side="right")

    def _header_button(self, text: str, command: object, tooltip: str) -> tk.Label:
        label = tk.Label(
            self.header,
            text=text,
            bg=PANEL,
            fg=MUTED,
            width=3,
            cursor="hand2",
            font=("Segoe UI Symbol", 12),
        )
        label.bind("<Button-1>", lambda _event: command())
        label.bind("<Enter>", lambda _event: label.configure(bg=PANEL_ALT, fg=TEXT))
        label.bind("<Leave>", lambda _event: label.configure(bg=PANEL, fg=MUTED))
        Tooltip(label, tooltip)
        return label

    def _build_content(self) -> None:
        self.content = tk.Frame(self.shell, bg=BG)
        self.content.pack(fill="both", expand=True)

        self.signal_row = tk.Frame(self.content, bg=BG)
        self.signal_row.pack(fill="x", padx=8, pady=(8, 0))
        self.traffic = TrafficLight(self.signal_row)
        self.traffic.pack(side="left")

        self.info = tk.Frame(self.signal_row, bg=BG)
        self.info.pack(side="left", fill="both", expand=True, padx=(8, 8), pady=(22, 10))

        self.status_label = tk.Label(
            self.info,
            text="正在连接",
            bg=BG,
            fg=MUTED,
            anchor="w",
            font=("Microsoft YaHei UI", 17, "bold"),
        )
        self.status_label.pack(fill="x")
        self.phase_label = tk.Label(
            self.info,
            text="读取 Codex 状态",
            bg=BG,
            fg=MUTED,
            anchor="w",
            justify="left",
            wraplength=160,
            font=("Microsoft YaHei UI", 10),
        )
        self.phase_label.pack(fill="x", pady=(7, 0))
        self.elapsed_label = tk.Label(
            self.info,
            text="--:--",
            bg=BG,
            fg=TEXT,
            anchor="w",
            font=("Cascadia Mono", 12),
        )
        self.elapsed_label.pack(fill="x", pady=(14, 0))
        self.count_label = tk.Label(
            self.info,
            text="0 个活动任务",
            bg=BG,
            fg=MUTED,
            anchor="w",
            justify="left",
            wraplength=160,
            font=("Microsoft YaHei UI", 9),
        )
        self.count_label.pack(fill="x", pady=(5, 0))

        self.compact_status = tk.Label(
            self.content,
            text="空闲",
            bg=BG,
            fg=GREEN,
            font=("Microsoft YaHei UI", 12, "bold"),
        )

        self.details = tk.Frame(
            self.content,
            bg=PANEL,
            highlightbackground="#242B31",
            highlightthickness=1,
        )
        self.details.pack(fill="x", padx=12, pady=(4, 6))
        self.task_title = tk.Label(
            self.details,
            text="Codex 任务",
            bg=PANEL,
            fg=TEXT,
            anchor="w",
            justify="left",
            wraplength=286,
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.task_title.pack(fill="x", padx=10, pady=(8, 2))
        self.integration_label = tk.Label(
            self.details,
            text="正在检查监控集成",
            bg=PANEL,
            fg=MUTED,
            anchor="w",
            font=("Microsoft YaHei UI", 8),
        )
        self.integration_label.pack(side="left", padx=10, pady=(0, 8))
        self.enable_button = tk.Label(
            self.details,
            text="启用 Hooks",
            bg=PANEL_ALT,
            fg=AMBER,
            cursor="hand2",
            padx=7,
            pady=2,
            font=("Microsoft YaHei UI", 8),
        )
        self.enable_button.pack(side="right", padx=8, pady=(0, 7))
        self.enable_button.bind("<Button-1>", lambda _event: self.enable_hooks())

        self.footer = tk.Frame(self.content, bg=BG)
        self.footer.pack(fill="x", padx=12, pady=(0, 10))
        self._text_button(self.footer, "打开 Codex", open_codex).pack(side="left", fill="x", expand=True)
        self._text_button(self.footer, "收起", self.toggle_compact).pack(side="left", padx=(8, 0))

    def _text_button(self, master: tk.Widget, text: str, command: object) -> tk.Label:
        label = tk.Label(
            master,
            text=text,
            bg=PANEL_ALT,
            fg=TEXT,
            cursor="hand2",
            padx=12,
            pady=7,
            font=("Microsoft YaHei UI", 9),
        )
        label.bind("<Button-1>", lambda _event: command())
        label.bind("<Enter>", lambda _event: label.configure(bg="#29323A"))
        label.bind("<Leave>", lambda _event: label.configure(bg=PANEL_ALT))
        return label

    def _build_menu(self) -> None:
        self.menu = tk.Menu(
            self.root,
            tearoff=False,
            bg=PANEL_ALT,
            fg=TEXT,
            activebackground="#303A43",
            activeforeground=TEXT,
            borderwidth=0,
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
        self.menu.add_command(label="切换迷你模式", command=self.toggle_compact)
        self.menu.add_command(label="退出", command=self.close)

    def _show_menu(self, event: tk.Event) -> None:
        self.sound_var.set(self.settings.sound_enabled)
        self.topmost_var.set(self.settings.always_on_top)
        self.startup_var.set(starts_with_windows())
        self.menu.tk_popup(event.x_root, event.y_root)

    def _start_drag(self, event: tk.Event) -> None:
        self._drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag(self, event: tk.Event) -> None:
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.root.geometry(f"+{x}+{y}")

    def _end_drag(self, _event: tk.Event) -> None:
        self.settings.window_x = self.root.winfo_x()
        self.settings.window_y = self.root.winfo_y()
        self.settings.save()

    def _place_window(self) -> None:
        self.root.update_idletasks()
        width, height = self._preferred_size()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        default_x = max(0, screen_w - width - 28)
        default_y = max(0, screen_h - height - 76)
        x = self.settings.window_x if self.settings.window_x is not None else default_x
        y = self.settings.window_y if self.settings.window_y is not None else default_y
        x = min(max(0, x), max(0, screen_w - width - 24))
        y = min(max(0, y), max(0, screen_h - height - 96))
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _apply_mode(self, initial: bool = False) -> None:
        compact = self.settings.compact_mode
        if compact:
            self.brand.configure(text="CODEX")
            self.sound_button.pack_forget()
            self.info.pack_forget()
            self.details.pack_forget()
            self.footer.pack_forget()
            self.compact_status.pack(fill="x", pady=(2, 0))
        else:
            self.brand.configure(text="CODEX SIGNAL")
            if not self.sound_button.winfo_manager():
                self.sound_button.pack(side="right", before=self.compact_button)
            self.compact_status.pack_forget()
            if not self.info.winfo_manager():
                self.info.pack(side="left", fill="both", expand=True, padx=(8, 8), pady=(22, 10))
            if not self.details.winfo_manager():
                self.details.pack(fill="x", padx=12, pady=(4, 6))
            if not self.footer.winfo_manager():
                self.footer.pack(fill="x", padx=12, pady=(0, 10))
        self.root.update_idletasks()
        width, height = self._preferred_size()
        if initial:
            self.root.geometry(f"{width}x{height}")
        else:
            x, y = self.root.winfo_x(), self.root.winfo_y()
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            x = min(max(0, x), max(0, screen_w - width - 24))
            y = min(max(0, y), max(0, screen_h - height - 96))
            self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _preferred_size(self) -> tuple[int, int]:
        minimum = self.COMPACT_SIZE if self.settings.compact_mode else self.FULL_SIZE
        requested = (self.shell.winfo_reqwidth(), self.shell.winfo_reqheight())
        return max(minimum[0], requested[0]), max(minimum[1], requested[1])

    def toggle_compact(self) -> None:
        self.settings.compact_mode = not self.settings.compact_mode
        self._apply_mode()
        self.settings.save()

    def toggle_sound(self) -> None:
        self.settings.sound_enabled = not self.settings.sound_enabled
        self.sound_var.set(self.settings.sound_enabled)
        self.settings.save()
        self._update_sound_button()
        if self.settings.sound_enabled:
            play_async("test")

    def _menu_sound(self) -> None:
        self.settings.sound_enabled = self.sound_var.get()
        self.settings.save()
        self._update_sound_button()

    def _menu_topmost(self) -> None:
        self.settings.always_on_top = self.topmost_var.get()
        self.root.attributes("-topmost", self.settings.always_on_top)
        self.settings.save()

    def _menu_startup(self) -> None:
        try:
            set_start_with_windows(self.startup_var.get())
        except OSError as exc:
            messagebox.showerror("Codex Traffic Light", f"无法修改开机启动：\n{exc}")
            self.startup_var.set(starts_with_windows())

    def _update_sound_button(self) -> None:
        self.sound_button.configure(fg=MUTED if self.settings.sound_enabled else RED)

    def enable_hooks(self) -> None:
        try:
            path = install_hooks()
        except (OSError, ValueError) as exc:
            messagebox.showerror("Codex Traffic Light", f"Hooks 安装失败：\n{exc}")
            return
        self._update_integration(force=True)
        messagebox.showinfo(
            "Codex Traffic Light",
            f"Hooks 已写入：\n{path}\n\n首次使用请在 Codex 中打开 /hooks 并信任这些 hooks。",
        )

    def _tick(self) -> None:
        snapshot = self.worker.snapshot()
        self._render(snapshot)
        self._handle_alerts(snapshot)
        self.traffic.animate()
        self._update_integration()
        self.root.after(250, self._tick)

    def _render(self, snapshot: AggregateSnapshot) -> None:
        self._last_snapshot = snapshot
        status_name, color = STATUS_STYLE.get(snapshot.status, STATUS_STYLE[IDLE])
        self.traffic.set_status(snapshot.status)
        self.status_label.configure(text=status_name, fg=color)
        self.compact_status.configure(text=status_name, fg=color)
        task = snapshot.selected
        if task:
            self.phase_label.configure(text=task.phase)
            self.task_title.configure(text=self._truncate(task.title, 42))
            self.elapsed_label.configure(text=self._elapsed(task.started_at, task.updated_at, task.status))
        else:
            self.phase_label.configure(text="等待新任务")
            self.task_title.configure(text="Codex 任务")
            self.elapsed_label.configure(text="--:--")

        parts = []
        if snapshot.approval_count:
            parts.append(f"{snapshot.approval_count} 个待批准")
        if snapshot.running_count:
            parts.append(f"{snapshot.running_count} 个运行中")
        if snapshot.error_count:
            parts.append(f"{snapshot.error_count} 个异常")
        if not parts:
            parts.append("没有活动任务")
        self.count_label.configure(text=" · ".join(parts))

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
        installed = hooks_installed()
        self.integration_label.configure(
            text="Hooks 已连接" if installed else "当前仅使用日志监控",
            fg=GREEN if installed else AMBER,
        )
        if installed:
            self.enable_button.pack_forget()
        elif not self.enable_button.winfo_manager():
            self.enable_button.pack(side="right", padx=8, pady=(0, 7))

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
        self.worker.stop()
        self.settings.window_x = self.root.winfo_x()
        self.settings.window_y = self.root.winfo_y()
        self.settings.save()
        self.root.destroy()


def run_app() -> None:
    root = tk.Tk()
    app = CodexTrafficLightApp(root)
    app._update_sound_button()
    root.mainloop()
