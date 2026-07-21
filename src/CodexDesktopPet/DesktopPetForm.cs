using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Threading;
using System.Windows.Forms;

namespace CodexDesktopPet
{
    internal sealed class DesktopPetForm : Form
    {
        private readonly PetSettings settings;
        private readonly CodexMonitor monitor;
        private readonly System.Windows.Forms.Timer timer;
        private readonly NotifyIcon trayIcon;
        private readonly ContextMenuStrip petMenu;
        private readonly ToolTip tooltip;
        private readonly EventWaitHandle showEvent;
        private AggregateSnapshot snapshot = new AggregateSnapshot();
        private readonly Dictionary<string, string> previousStatuses = new Dictionary<string, string>();
        private bool baselineReady;
        private bool hooksReady;
        private DateTime lastHookCheck = DateTime.MinValue;
        private DateTime lastApprovalSound = DateTime.MinValue;
        private double pulse;
        private bool exiting;
        private bool dragging;
        private string pressedAction;
        private Point dragOffset;
        private Point pointerOrigin;

        public DesktopPetForm(EventWaitHandle showEvent)
        {
            this.showEvent = showEvent;
            settings = PetSettings.Load();
            monitor = new CodexMonitor();
            monitor.Start();

            bool windowed = Environment.GetEnvironmentVariable("CODEX_DESKTOP_PET_WINDOWED") == "1";
            Text = "Codex 桌宠";
            FormBorderStyle = windowed ? FormBorderStyle.Sizable : FormBorderStyle.None;
            ShowInTaskbar = windowed;
            TopMost = settings.AlwaysOnTop;
            BackColor = PetRenderer.Transparent;
            TransparencyKey = PetRenderer.Transparent;
            AutoScaleMode = AutoScaleMode.None;
            DoubleBuffered = true;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                ControlStyles.ResizeRedraw | ControlStyles.StandardClick | ControlStyles.StandardDoubleClick, true);

            Icon appIcon = LoadAppIcon();
            Icon = appIcon;
            trayIcon = new NotifyIcon();
            trayIcon.Icon = appIcon;
            trayIcon.Text = "Codex 桌宠 - 空闲待命";
            trayIcon.Visible = true;
            trayIcon.MouseClick += delegate(object sender, MouseEventArgs args)
            {
                if (args.Button == MouseButtons.Left) ShowPet();
            };
            trayIcon.DoubleClick += delegate { ShowPet(); };
            trayIcon.ContextMenuStrip = BuildTrayMenu();

            petMenu = new ContextMenuStrip();
            petMenu.Font = new Font("Microsoft YaHei UI", 10.5f);
            petMenu.Opening += delegate { RebuildPetMenu(); };
            tooltip = new ToolTip { InitialDelay = 400, ReshowDelay = 100, AutoPopDelay = 4000 };

            ApplyInitialPosition();
            timer = new System.Windows.Forms.Timer { Interval = 80 };
            timer.Tick += OnTick;
            timer.Start();
        }

        protected override void OnPaint(PaintEventArgs args)
        {
            base.OnPaint(args);
            PetRenderer.Draw(args.Graphics, snapshot, settings.CompactMode, settings.FullSceneOriginY, settings.BubbleOnRight, pulse, settings.SoundEnabled, hooksReady);
        }

        protected override void OnMouseDown(MouseEventArgs args)
        {
            base.OnMouseDown(args);
            if (args.Button == MouseButtons.Right)
            {
                petMenu.Show(this, args.Location);
                return;
            }
            if (args.Button != MouseButtons.Left) return;
            pressedAction = HitAction(args.Location);
            dragging = false;
            pointerOrigin = Cursor.Position;
            dragOffset = new Point(Cursor.Position.X - Left, Cursor.Position.Y - Top);
        }

        protected override void OnMouseMove(MouseEventArgs args)
        {
            base.OnMouseMove(args);
            string action = HitAction(args.Location);
            Cursor = action == null ? Cursors.SizeAll : Cursors.Hand;
            tooltip.SetToolTip(this, TooltipFor(action));
            if ((args.Button & MouseButtons.Left) == 0 || pressedAction != null) return;
            Point cursor = Cursor.Position;
            if (!dragging && Math.Abs(cursor.X - pointerOrigin.X) + Math.Abs(cursor.Y - pointerOrigin.Y) < 3) return;
            dragging = true;
            Rectangle work = Screen.FromPoint(cursor).WorkingArea;
            int x = Math.Max(work.Left, Math.Min(cursor.X - dragOffset.X, work.Right - Width));
            int y = Math.Max(work.Top, Math.Min(cursor.Y - dragOffset.Y, work.Bottom - Height));
            Location = new Point(x, y);
        }

        protected override void OnMouseUp(MouseEventArgs args)
        {
            base.OnMouseUp(args);
            if (args.Button != MouseButtons.Left) return;
            string released = HitAction(args.Location);
            if (pressedAction != null && released == pressedAction) ActivateAction(released);
            else if (dragging) SavePosition();
            pressedAction = null;
            dragging = false;
        }

        protected override void OnMouseDoubleClick(MouseEventArgs args)
        {
            base.OnMouseDoubleClick(args);
            if (args.Button == MouseButtons.Left && HitAction(args.Location) == null) ToggleCompact();
        }

        protected override void OnFormClosing(FormClosingEventArgs args)
        {
            if (!exiting)
            {
                args.Cancel = true;
                HideToTray();
                return;
            }
            base.OnFormClosing(args);
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                timer.Dispose();
                monitor.Dispose();
                trayIcon.Visible = false;
                trayIcon.Dispose();
                petMenu.Dispose();
                tooltip.Dispose();
            }
            base.Dispose(disposing);
        }

        private void OnTick(object sender, EventArgs args)
        {
            if (showEvent != null && showEvent.WaitOne(0)) ShowPet();
            AggregateSnapshot next = monitor.Current;
            HandleAlerts(next);
            snapshot = next;
            pulse = (pulse + 0.16) % (Math.PI * 2);
            if ((DateTime.UtcNow - lastHookCheck).TotalSeconds >= 5)
            {
                lastHookCheck = DateTime.UtcNow;
                hooksReady = HookIntegration.IsInstalled() || HookIntegration.IsClaudeInstalled() || HookIntegration.IsOpenCodeInstalled();
            }
            UpdateTrayText();
            Invalidate();
        }

        private void HandleAlerts(AggregateSnapshot next)
        {
            Dictionary<string, string> current = next.Tasks.ToDictionary(CodexMonitor.TaskKey, item => item.Status);
            if (!baselineReady)
            {
                foreach (KeyValuePair<string, string> pair in current) previousStatuses[pair.Key] = pair.Value;
                baselineReady = true;
                return;
            }
            bool approval = false, error = false, completed = false;
            foreach (TaskSnapshot task in next.Tasks)
            {
                string previous;
                if (!previousStatuses.TryGetValue(CodexMonitor.TaskKey(task), out previous) || previous == task.Status) continue;
                approval |= task.Status == TaskStatus.Approval;
                error |= task.Status == TaskStatus.Error;
                completed |= task.Status == TaskStatus.Completed;
            }
            previousStatuses.Clear();
            foreach (KeyValuePair<string, string> pair in current) previousStatuses[pair.Key] = pair.Value;
            string alert = approval ? "approval" : error ? "error" : completed ? "completed" : null;
            if (approval) lastApprovalSound = DateTime.UtcNow;
            if (next.Status == TaskStatus.Approval && (DateTime.UtcNow - lastApprovalSound).TotalSeconds >= settings.ApprovalRepeatSeconds)
            {
                alert = "approval";
                lastApprovalSound = DateTime.UtcNow;
            }
            if (alert != null && settings.SoundEnabled) AudioAlerts.Play(alert);
        }

        private void UpdateTrayText()
        {
            string count = snapshot.VisibleTasks.Count > 0 ? " (" + snapshot.VisibleTasks.Count + ")" : "";
            string text = "Codex 桌宠 - " + PetRenderer.StatusName(snapshot.Status) + count;
            trayIcon.Text = text.Length <= 63 ? text : text.Substring(0, 63);
        }

        private ContextMenuStrip BuildTrayMenu()
        {
            ContextMenuStrip menu = new ContextMenuStrip();
            menu.Font = new Font("Microsoft YaHei UI", 10.5f);
            menu.Items.Add("显示桌宠", null, delegate { ShowPet(); });
            menu.Items.Add("打开 Codex", null, delegate { WindowsIntegration.OpenCodex(); });
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add("退出桌宠", null, delegate { ExitApp(); });
            return menu;
        }

        private void RebuildPetMenu()
        {
            petMenu.Items.Clear();
            petMenu.Items.Add("打开 Codex", null, delegate { WindowsIntegration.OpenCodex(); });
            ToolStripMenuItem tasks = new ToolStripMenuItem("任务（" + snapshot.VisibleTasks.Count + "）");
            if (snapshot.VisibleTasks.Count == 0) tasks.DropDownItems.Add(new ToolStripMenuItem("当前没有任务") { Enabled = false });
            foreach (TaskSnapshot task in snapshot.VisibleTasks)
            {
                TaskSnapshot selectedTask = task.Clone();
                string providerLabel = selectedTask.Provider == "codex" ? "Codex" : AgentProcessMonitor.ProviderName(selectedTask.Provider);
                tasks.DropDownItems.Add(PetRenderer.TaskStatusName(task.Status) + "  [" + providerLabel + "]  " + Truncate(task.Title, 28), null,
                    delegate { OpenTask(selectedTask); });
            }
            petMenu.Items.Add(tasks);
            petMenu.Items.Add(new ToolStripSeparator());
            ToolStripMenuItem sound = new ToolStripMenuItem("声音提醒") { Checked = settings.SoundEnabled };
            sound.Click += delegate { settings.SoundEnabled = !settings.SoundEnabled; settings.Save(); };
            petMenu.Items.Add(sound);
            ToolStripMenuItem top = new ToolStripMenuItem("始终置顶") { Checked = settings.AlwaysOnTop };
            top.Click += delegate { settings.AlwaysOnTop = !settings.AlwaysOnTop; TopMost = settings.AlwaysOnTop; settings.Save(); };
            petMenu.Items.Add(top);
            ToolStripMenuItem startup = new ToolStripMenuItem("开机启动") { Checked = StartupIntegration.IsEnabled };
            startup.Click += delegate
            {
                try { StartupIntegration.SetEnabled(!StartupIntegration.IsEnabled); }
                catch (Exception error) { MessageBox.Show(error.Message, "Codex 桌宠", MessageBoxButtons.OK, MessageBoxIcon.Error); }
            };
            petMenu.Items.Add(startup);
            petMenu.Items.Add("测试声音", null, delegate { AudioAlerts.Play("test"); });
            ToolStripMenuItem agents = new ToolStripMenuItem("连接 Agent");
            agents.DropDownItems.Add("Codex Hooks", null, delegate { EnableHooks(); });
            agents.DropDownItems.Add("Claude Code Hooks", null, delegate { ConnectClaude(); });
            agents.DropDownItems.Add("OpenCode 插件", null, delegate { ConnectOpenCode(); });
            agents.DropDownItems.Add("CLI 进程监控（自动）", null, null).Enabled = false;
            petMenu.Items.Add(agents);
            petMenu.Items.Add(new ToolStripSeparator());
            petMenu.Items.Add(settings.CompactMode ? "展开状态气泡" : "收起状态气泡", null, delegate { ToggleCompact(); });
            petMenu.Items.Add("隐藏到系统托盘", null, delegate { HideToTray(); });
            petMenu.Items.Add("退出桌宠", null, delegate { ExitApp(); });
        }

        private void ActivateAction(string action)
        {
            if (action == "sound") { settings.SoundEnabled = !settings.SoundEnabled; settings.Save(); if (settings.SoundEnabled) AudioAlerts.Play("test"); }
            else if (action == "close") HideToTray();
            else if (action == "hooks") EnableHooks();
            else if (action == "open") WindowsIntegration.OpenCodex();
            else if (action == "compact") ToggleCompact();
            else if (action != null && action.StartsWith("task:"))
            {
                TaskSnapshot task = snapshot.VisibleTasks.FirstOrDefault(item =>
                    CodexMonitor.TaskKey(item) == action.Substring(5));
                OpenTask(task);
            }
        }

        private string HitAction(Point point)
        {
            if (settings.CompactMode) return null;
            int offset = settings.BubbleOnRight ? PetRenderer.RightBubbleOffset : 0;
            if (new Rectangle(236 + offset, 19, 24, 24).Contains(point)) return "sound";
            if (new Rectangle(266 + offset, 19, 24, 24).Contains(point)) return "close";
            for (int index = 0; index < Math.Min(4, snapshot.VisibleTasks.Count); index++)
                if (new Rectangle(18 + offset, 86 + index * 23, 272, 20).Contains(point))
                    return "task:" + CodexMonitor.TaskKey(snapshot.VisibleTasks[index]);
            if (!hooksReady && new Rectangle(232 + offset, 212, 52, 25).Contains(point)) return "hooks";
            if (new Rectangle(24 + offset, 269, 144, 27).Contains(point)) return "open";
            if (new Rectangle(178 + offset, 269, 106, 27).Contains(point)) return "compact";
            return null;
        }

        private static string TooltipFor(string action)
        {
            if (action == "sound") return "开启或关闭声音";
            if (action == "close") return "隐藏到系统托盘";
            if (action == "hooks") return "连接 Codex Hooks";
            if (action == "open") return "打开 Codex";
            if (action == "compact") return "切换迷你模式";
            if (action != null && action.StartsWith("task:")) return "打开这个 Agent 任务";
            return "";
        }

        private void OpenTask(TaskSnapshot task)
        {
            if (task == null) return;
            bool opened = task.Provider == "codex"
                ? WindowsIntegration.OpenCodexThread(task.SessionId)
                : WindowsIntegration.OpenAgent(task.Provider, task.SessionId, task.Cwd);
            if (opened && task.Status == TaskStatus.Completed)
            {
                monitor.MarkReviewed(task);
                foreach (TaskSnapshot item in snapshot.Tasks)
                    if (CodexMonitor.TaskKey(item) == CodexMonitor.TaskKey(task)) item.Unread = false;
                snapshot = AggregateResolver.Resolve(snapshot.Tasks, HookBridge.UnixNow());
                Invalidate();
            }
        }

        private void EnableHooks()
        {
            try
            {
                string path = HookIntegration.Install(null);
                hooksReady = true;
                MessageBox.Show("Hooks 已写入：\r\n" + path, "Codex 桌宠", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception error)
            {
                MessageBox.Show(error.Message, "Codex 桌宠", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void ConnectClaude()
        {
            try
            {
                string path = HookIntegration.InstallClaude();
                hooksReady = true;
                MessageBox.Show("Claude Code Hooks 已写入：\r\n" + path + "\r\n\r\n重启 Claude Code 后生效。", "Codex 桌宠", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception error) { MessageBox.Show(error.Message, "Codex 桌宠", MessageBoxButtons.OK, MessageBoxIcon.Error); }
        }

        private void ConnectOpenCode()
        {
            try
            {
                string path = HookIntegration.InstallOpenCode();
                hooksReady = true;
                MessageBox.Show("OpenCode 插件已写入：\r\n" + path + "\r\n\r\n重启 OpenCode 后生效。", "Codex 桌宠", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception error) { MessageBox.Show(error.Message, "Codex 桌宠", MessageBoxButtons.OK, MessageBoxIcon.Error); }
        }

        private void ToggleCompact()
        {
            Point oldOrigin = SceneOrigin();
            Point anchor = new Point(Left + oldOrigin.X, Top + oldOrigin.Y);
            settings.CompactMode = !settings.CompactMode;
            Rectangle work = Screen.FromPoint(anchor).WorkingArea;
            if (settings.CompactMode)
            {
                ClientSize = PetRenderer.CompactSize;
                int x = LayoutMath.Clamp(anchor.X - PetRenderer.CompactOrigin.X, work.Left, work.Right - Width);
                int y = LayoutMath.Clamp(anchor.Y - PetRenderer.CompactOrigin.Y, work.Top, work.Bottom - Height);
                Location = new Point(x, y);
            }
            else
            {
                ClientSize = PetRenderer.FullSize;
                settings.BubbleOnRight = LayoutMath.ChooseBubbleOnRight(
                    anchor.X,
                    work.Left,
                    work.Right,
                    Width,
                    PetRenderer.FullOriginX,
                    PetRenderer.FullOriginXWithRightBubble);
                int y;
                int originY;
                LayoutMath.FitExpandedVertically(anchor.Y, work.Top, work.Bottom, Height, out y, out originY);
                settings.FullSceneOriginY = originY;
                int sceneOriginX = PetRenderer.FullSceneOriginX(settings.BubbleOnRight);
                int x = LayoutMath.Clamp(anchor.X - sceneOriginX, work.Left, work.Right - Width);
                Location = new Point(x, y);
            }
            SavePosition();
            Invalidate();
        }

        private Point SceneOrigin()
        {
            return settings.CompactMode
                ? PetRenderer.CompactOrigin
                : new Point(PetRenderer.FullSceneOriginX(settings.BubbleOnRight), settings.FullSceneOriginY);
        }

        private void ApplyInitialPosition()
        {
            ClientSize = settings.CompactMode ? PetRenderer.CompactSize : PetRenderer.FullSize;
            Rectangle work = Screen.PrimaryScreen.WorkingArea;
            int x = settings.WindowX.HasValue ? settings.WindowX.Value : work.Right - Width - 24;
            int y = settings.WindowY.HasValue ? settings.WindowY.Value : work.Bottom - Height - 24;
            Location = new Point(LayoutMath.Clamp(x, work.Left, work.Right - Width), LayoutMath.Clamp(y, work.Top, work.Bottom - Height));
        }

        private void SavePosition()
        {
            settings.WindowX = Left;
            settings.WindowY = Top;
            settings.Save();
        }

        private void HideToTray()
        {
            SavePosition();
            Hide();
        }

        private void ShowPet()
        {
            Show();
            WindowState = FormWindowState.Normal;
            TopMost = settings.AlwaysOnTop;
            Activate();
            BringToFront();
        }

        private void ExitApp()
        {
            exiting = true;
            SavePosition();
            Close();
        }

        private static string Truncate(string text, int limit)
        {
            if (String.IsNullOrWhiteSpace(text)) return "Codex 任务";
            return text.Length <= limit ? text : text.Substring(0, limit - 1) + "…";
        }

        private static Icon LoadAppIcon()
        {
            try
            {
                if (File.Exists(AppPaths.IconFile)) return new Icon(AppPaths.IconFile);
                return Icon.ExtractAssociatedIcon(Process.GetCurrentProcess().MainModule.FileName);
            }
            catch { return SystemIcons.Application; }
        }
    }
}
