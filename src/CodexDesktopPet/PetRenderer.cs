using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Text;
using System.Linq;

namespace CodexDesktopPet
{
    internal static class PetRenderer
    {
        public static readonly Size FullSize = new Size(500, 320);
        public static readonly Size CompactSize = new Size(220, 250);
        public static readonly Point CompactOrigin = new Point(20, 39);
        public const int FullOriginX = 310;
        public const int DefaultFullOriginY = 55;

        public static readonly Color Transparent = Color.FromArgb(1, 2, 3);
        public static readonly Color Paper = Color.White;
        public static readonly Color Ink = Color.FromArgb(32, 40, 47);
        public static readonly Color Border = Color.FromArgb(215, 222, 227);
        public static readonly Color Muted = Color.FromArgb(105, 119, 129);
        public static readonly Color Soft = Color.FromArgb(238, 242, 243);
        public static readonly Color Red = Color.FromArgb(239, 71, 111);
        public static readonly Color Amber = Color.FromArgb(244, 166, 42);
        public static readonly Color Green = Color.FromArgb(34, 166, 111);

        private static readonly Font StatusFont = new Font("Microsoft YaHei UI", 13, FontStyle.Bold, GraphicsUnit.Point);
        private static readonly Font BodyFont = new Font("Microsoft YaHei UI", 10.5f, FontStyle.Regular, GraphicsUnit.Point);
        private static readonly Font SmallFont = new Font("Microsoft YaHei UI", 9.5f, FontStyle.Regular, GraphicsUnit.Point);
        private static readonly Font SmallBoldFont = new Font("Microsoft YaHei UI", 9.5f, FontStyle.Bold, GraphicsUnit.Point);
        private static readonly Font MonoFont = new Font("Cascadia Mono", 8.5f, FontStyle.Regular, GraphicsUnit.Point);
        private static readonly Font SymbolFont = new Font("Segoe UI Symbol", 13, FontStyle.Regular, GraphicsUnit.Point);
        private static readonly Font AlertFont = new Font("Segoe UI", 30, FontStyle.Bold, GraphicsUnit.Point);

        public static void Draw(
            Graphics graphics,
            AggregateSnapshot snapshot,
            bool compact,
            int fullOriginY,
            double pulse,
            bool soundEnabled,
            bool hooksReady)
        {
            graphics.SmoothingMode = SmoothingMode.AntiAlias;
            graphics.PixelOffsetMode = PixelOffsetMode.HighQuality;
            graphics.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
            graphics.Clear(Transparent);
            if (compact) DrawCompactLabel(graphics, snapshot);
            else DrawBubble(graphics, snapshot, fullOriginY, soundEnabled, hooksReady);
            Point origin = compact ? CompactOrigin : new Point(FullOriginX, fullOriginY);
            DrawScene(graphics, snapshot.Status, origin.X, origin.Y, pulse);
        }

        public static string StatusName(string status)
        {
            if (status == TaskStatus.Approval) return "等你批准";
            if (status == TaskStatus.Error) return "遇到异常";
            if (status == TaskStatus.Running) return "正在工作";
            if (status == TaskStatus.Completed) return "任务完成";
            if (status == TaskStatus.Cancelled) return "任务已终止";
            return "空闲待命";
        }

        public static Color StatusColor(string status)
        {
            if (status == TaskStatus.Approval || status == TaskStatus.Error) return Red;
            if (status == TaskStatus.Running) return Amber;
            if (status == TaskStatus.Cancelled) return Muted;
            return Green;
        }

        public static string TaskStatusName(string status)
        {
            if (status == TaskStatus.Approval) return "待批准";
            if (status == TaskStatus.Running) return "运行中";
            if (status == TaskStatus.Error) return "异常";
            if (status == TaskStatus.Cancelled) return "已终止";
            if (status == TaskStatus.Completed) return "已完成";
            return "空闲";
        }

        private static void DrawCompactLabel(Graphics g, AggregateSnapshot snapshot)
        {
            string text = StatusName(snapshot.Status);
            if (snapshot.VisibleTasks.Count > 1) text += " · " + snapshot.VisibleTasks.Count;
            RoundRect(g, new Rectangle(45, 4, 130, 32), 8, Paper, Border, 1);
            using (Brush paper = new SolidBrush(Paper))
            using (Pen border = new Pen(Border, 1))
            {
                Point[] pointer = new Point[] { new Point(101, 35), new Point(110, 45), new Point(119, 35) };
                g.FillPolygon(paper, pointer);
                g.DrawLines(border, pointer);
            }
            using (Brush color = new SolidBrush(StatusColor(snapshot.Status))) g.FillEllipse(color, 57, 16, 8, 8);
            DrawText(g, text, SmallBoldFont, Ink, new Rectangle(72, 10, 95, 20), StringAlignment.Near, StringAlignment.Center);
        }

        private static void DrawBubble(Graphics g, AggregateSnapshot snapshot, int originY, bool soundEnabled, bool hooksReady)
        {
            int shift = originY - DefaultFullOriginY;
            using (Brush paper = new SolidBrush(Paper))
            using (Pen border = new Pen(Border, 2))
            {
                Point[] pointer = new Point[]
                {
                    new Point(295, 91 + shift), new Point(318, 108 + shift), new Point(295, 126 + shift)
                };
                g.FillPolygon(paper, pointer);
                g.DrawPolygon(border, pointer);
            }
            RoundRect(g, new Rectangle(8, 10, 292, 298), 8, Paper, Border, 2);
            using (Brush color = new SolidBrush(StatusColor(snapshot.Status))) g.FillEllipse(color, 24, 27, 12, 12);
            DrawText(g, StatusName(snapshot.Status), StatusFont, Ink, new Rectangle(44, 20, 185, 27), StringAlignment.Near, StringAlignment.Center);
            DrawText(g, soundEnabled ? "♪" : "♩", SymbolFont, soundEnabled ? Muted : Red, new Rectangle(236, 19, 24, 24), StringAlignment.Center, StringAlignment.Center);
            DrawText(g, "×", SymbolFont, Muted, new Rectangle(266, 19, 24, 24), StringAlignment.Center, StringAlignment.Center);

            string phase = snapshot.Selected == null ? "等待新任务" : Truncate(snapshot.Selected.Phase, 24);
            DrawText(g, phase, BodyFont, Ink, new Rectangle(24, 52, 260, 22), StringAlignment.Near, StringAlignment.Center);
            using (Pen divider = new Pen(Soft, 1)) g.DrawLine(divider, 24, 79, 284, 79);

            List<TaskSnapshot> rows = snapshot.VisibleTasks.Take(4).ToList();
            bool overflow = snapshot.VisibleTasks.Count > 4;
            if (overflow) rows = snapshot.VisibleTasks.Take(3).ToList();
            for (int index = 0; index < rows.Count; index++) DrawTaskRow(g, rows[index], index);
            if (overflow)
            {
                int y = 96 + 3 * 23;
                using (Brush dot = new SolidBrush(Muted)) g.FillEllipse(dot, 24, y - 4, 8, 8);
                DrawText(g, "另有 " + (snapshot.VisibleTasks.Count - 3) + " 个任务", SmallFont, Ink, new Rectangle(40, y - 10, 220, 20), StringAlignment.Near, StringAlignment.Center);
            }
            if (snapshot.VisibleTasks.Count == 0)
                DrawText(g, "当前没有任务", SmallFont, Muted, new Rectangle(24, 94, 220, 20), StringAlignment.Near, StringAlignment.Center);

            List<string> activity = new List<string>();
            if (snapshot.ApprovalCount > 0) activity.Add(snapshot.ApprovalCount + " 待批准");
            if (snapshot.RunningCount > 0) activity.Add(snapshot.RunningCount + " 运行中");
            if (snapshot.ErrorCount > 0) activity.Add(snapshot.ErrorCount + " 异常");
            if (snapshot.CancelledCount > 0) activity.Add(snapshot.CancelledCount + " 已终止");
            if (snapshot.CompletedCount > 0) activity.Add(snapshot.CompletedCount + " 已完成");
            DrawText(g, activity.Count == 0 ? "没有活动任务" : String.Join(" · ", activity.ToArray()), SmallFont, Muted, new Rectangle(24, 180, 260, 20), StringAlignment.Near, StringAlignment.Center);
            using (Pen divider = new Pen(Soft, 1)) g.DrawLine(divider, 24, 205, 284, 205);

            Color hookColor = hooksReady ? Green : Amber;
            using (Brush dot = new SolidBrush(hookColor)) g.FillEllipse(dot, 24, 220, 8, 8);
            DrawText(g, hooksReady ? "Hooks 已连接" : "当前使用日志监控", MonoFont, Muted, new Rectangle(40, 213, 175, 22), StringAlignment.Near, StringAlignment.Center);
            if (!hooksReady) ActionBox(g, new Rectangle(232, 212, 52, 25), "连接", Color.FromArgb(255, 244, 216), Color.FromArgb(154, 101, 0));
            ActionBox(g, new Rectangle(24, 269, 144, 27), "打开 Codex", Ink, Paper);
            ActionBox(g, new Rectangle(178, 269, 106, 27), "收起", Soft, Ink);
        }

        private static void DrawTaskRow(Graphics g, TaskSnapshot task, int index)
        {
            int y = 96 + index * 23;
            Color color = StatusColor(task.Status);
            using (Brush dot = new SolidBrush(color)) g.FillEllipse(dot, 24, y - 4, 8, 8);
            DrawText(g, Truncate(task.Title, 18), SmallFont, Ink, new Rectangle(40, y - 10, 150, 20), StringAlignment.Near, StringAlignment.Center);
            string detail = TaskStatusName(task.Status) + " " + Elapsed(task);
            DrawText(g, detail, MonoFont, color, new Rectangle(190, y - 10, 94, 20), StringAlignment.Far, StringAlignment.Center);
        }

        private static void ActionBox(Graphics g, Rectangle rect, string text, Color fill, Color foreground)
        {
            RoundRect(g, rect, 7, fill, Color.Transparent, 0);
            DrawText(g, text, SmallBoldFont, foreground, rect, StringAlignment.Center, StringAlignment.Center);
        }

        private static void DrawScene(Graphics g, string status, float ox, float oy, double pulse)
        {
            if (status == TaskStatus.Running) DrawWorking(g, ox, oy, pulse);
            else if (status == TaskStatus.Completed) DrawExhausted(g, ox, oy, pulse);
            else if (status == TaskStatus.Approval) DrawApproval(g, ox, oy, pulse);
            else if (status == TaskStatus.Error) DrawError(g, ox, oy, pulse);
            else DrawFishTank(g, ox, oy, pulse);
        }

        private static void DrawWorking(Graphics g, float ox, float oy, double pulse)
        {
            float typing = (float)Math.Sin(pulse * 4.5) * 2.6f;
            float breathe = (float)Math.Sin(pulse * 2) * .8f;
            FillEllipse(g, Color.FromArgb(203, 211, 216), ox + 10, oy + 193, 168, 12);
            RoundRect(g, new RectangleF(ox + 12, oy + 78, 45, 73), 7, Color.FromArgb(221, 228, 231), Ink, 2);
            Line(g, ox, oy, new PointF[] { P(24, 148), P(18, 195) }, Ink, 4);
            Line(g, ox, oy, new PointF[] { P(52, 148), P(66, 195) }, Ink, 4);
            Line(g, ox, oy, new PointF[] { P(57, 83), P(59, 136), P(88, 151), P(99, 194) }, Ink, 6);
            Line(g, ox, oy, new PointF[] { P(59, 136), P(49, 161), P(69, 194) }, Ink, 6);
            Line(g, ox, oy, new PointF[] { P(92, 194), P(108, 194) }, Ink, 5);
            Line(g, ox, oy, new PointF[] { P(62, 194), P(77, 194) }, Ink, 5);

            FillPolygon(g, ox, oy, new PointF[] { P(76, 128), P(179, 128), P(179, 138), P(76, 138) }, Color.FromArgb(185, 195, 200), Ink, 2);
            Line(g, ox, oy, new PointF[] { P(87, 138), P(80, 199) }, Ink, 5);
            Line(g, ox, oy, new PointF[] { P(169, 138), P(176, 199) }, Ink, 5);
            FillPolygon(g, ox, oy, new PointF[] { P(106, 77), P(168, 77), P(161, 126), P(99, 126) }, Color.FromArgb(48, 58, 64), Ink, 2);
            FillPolygon(g, ox, oy, new PointF[] { P(111, 83), P(162, 83), P(157, 118), P(106, 118) }, Color.FromArgb(221, 248, 244), Color.Transparent, 0);
            Line(g, ox, oy, new PointF[] { P(113, 91), P(145, 91) }, Color.FromArgb(46, 125, 120), 2, false);
            Line(g, ox, oy, new PointF[] { P(113, 99), P(151, 99) }, Amber, 2, false);
            Line(g, ox, oy, new PointF[] { P(113, 107), P(137, 107) }, Color.FromArgb(46, 125, 120), 2, false);
            FillPolygon(g, ox, oy, new PointF[] { P(96, 126), P(166, 126), P(174, 132), P(91, 132) }, Color.FromArgb(101, 114, 122), Ink, 2);
            FillEllipse(g, Color.FromArgb(255, 247, 231), ox + 84, oy + 111, 15, 17, Ink, 2);

            Line(g, ox, oy, new PointF[] { P(57, 79), P(83, 102), P(111, 128 + typing) }, Ink, 5);
            Line(g, ox, oy, new PointF[] { P(58, 84), P(76, 115), P(127, 129 - typing) }, Ink, 5);
            FillEllipse(g, Color.FromArgb(255, 253, 248), ox + 107, oy + 125 + typing, 8, 8, Ink, 1);
            FillEllipse(g, Color.FromArgb(255, 253, 248), ox + 123, oy + 125 - typing, 8, 8, Ink, 1);
            DrawScarf(g, ox, oy, 57, 78, Amber, (float)Math.Sin(pulse * 2) * 1.5f);
            DrawHead(g, ox, oy, 52, 53 + breathe, 22, "focused");
        }

        private static void DrawFishTank(Graphics g, float ox, float oy, double pulse)
        {
            float handX = 106 + (float)Math.Sin(pulse * 1.7) * 7;
            float handY = 125 + (float)Math.Cos(pulse * 1.7) * 6;
            float fishX = 137 - (float)Math.Sin(pulse * 1.25) * 18;
            float fishY = 119 + (float)Math.Sin(pulse * 2.1) * 6;
            FillEllipse(g, Color.FromArgb(203, 211, 216), ox + 3, oy + 193, 180, 11);
            FillPolygon(g, ox, oy, new PointF[] { P(76, 60), P(179, 60), P(174, 180), P(81, 180) }, Color.FromArgb(233, 251, 252), Color.Transparent, 0);
            FillPolygon(g, ox, oy, new PointF[] { P(79, 77), P(177, 77), P(173, 177), P(82, 177) }, Color.FromArgb(191, 236, 239), Color.Transparent, 0);
            FillPolygon(g, ox, oy, new PointF[] { P(82, 164), P(104, 157), P(129, 166), P(151, 158), P(174, 165), P(173, 178), P(82, 178) }, Color.FromArgb(242, 211, 126), Color.Transparent, 0);
            Line(g, ox, oy, new PointF[] { P(103, 165), P(102, 137), P(94, 127) }, Color.FromArgb(46, 155, 120), 3);
            Line(g, ox, oy, new PointF[] { P(158, 164), P(159, 143), P(151, 134) }, Color.FromArgb(59, 170, 114), 3);
            DrawFish(g, ox, oy, fishX, fishY, 1, Color.FromArgb(255, 140, 85), false);
            DrawFish(g, ox, oy, 151 + (float)Math.Sin(pulse) * 8, 145, -1, Color.FromArgb(106, 143, 232), true);
            for (int index = 0; index < 3; index++)
            {
                float bx = new float[] { 117, 148, 165 }[index];
                float by = 155 - (float)((pulse * 13 + index * 19) % 67);
                using (Pen pen = new Pen(Color.FromArgb(74, 174, 184), 1)) g.DrawEllipse(pen, ox + bx - 3, oy + by - 3, 6, 6);
            }
            Line(g, ox, oy, new PointF[] { P(43, 89), P(46, 146), P(25, 195) }, Ink, 6);
            Line(g, ox, oy, new PointF[] { P(46, 146), P(63, 195) }, Ink, 6);
            Line(g, ox, oy, new PointF[] { P(19, 195), P(34, 195) }, Ink, 5);
            Line(g, ox, oy, new PointF[] { P(57, 195), P(72, 195) }, Ink, 5);
            Line(g, ox, oy, new PointF[] { P(44, 96), P(68, 75), P(84, 69) }, Ink, 5);
            Line(g, ox, oy, new PointF[] { P(46, 99), P(74, 105), P(91, 111), P(handX, handY) }, Ink, 5);
            FillEllipse(g, Color.FromArgb(255, 253, 248), ox + handX - 5, oy + handY - 5, 10, 10, Ink, 1);
            DrawScarf(g, ox, oy, 43, 89, Green, (float)Math.Sin(pulse) * 2);
            DrawHead(g, ox, oy, 32, 67 + (float)Math.Sin(pulse) * 1.2f, 21, "curious");
            Line(g, ox, oy, new PointF[] { P(76, 60), P(179, 60), P(174, 180), P(81, 180), P(76, 60) }, Color.FromArgb(61, 143, 152), 3, false);
            Line(g, ox, oy, new PointF[] { P(79, 77), P(177, 77) }, Color.FromArgb(74, 174, 184), 2);
        }

        private static void DrawExhausted(Graphics g, float ox, float oy, double pulse)
        {
            float breath = (float)Math.Sin(pulse * 2) * 2.2f;
            FillEllipse(g, Color.FromArgb(203, 211, 216), ox + 13, oy + 190, 161, 13);
            Line(g, ox, oy, new PointF[] { P(72, 126), P(53, 155), P(40, 193) }, Ink, 6);
            Line(g, ox, oy, new PointF[] { P(72, 126), P(99, 157), P(124, 193) }, Ink, 6);
            Line(g, ox, oy, new PointF[] { P(34, 193), P(49, 193) }, Ink, 5);
            Line(g, ox, oy, new PointF[] { P(117, 193), P(134, 193) }, Ink, 5);
            Line(g, ox, oy, new PointF[] { P(72, 126), P(104, 101 + breath) }, Ink, 7);
            Line(g, ox, oy, new PointF[] { P(101, 104 + breath), P(78, 132), P(54, 155) }, Ink, 5);
            Line(g, ox, oy, new PointF[] { P(106, 105 + breath), P(121, 133), P(99, 157) }, Ink, 5);
            DrawScarf(g, ox, oy, 105, 101 + breath, Green, 3 + breath);
            DrawHead(g, ox, oy, 128, 77 + breath, 23, "tired");
            for (int index = 0; index < 3; index++)
            {
                float x = new float[] { 145, 155, 116 }[index];
                float y = 44 + (float)((pulse * 11 + index * 17) % 42);
                FillPolygon(g, ox, oy, new PointF[] { P(x, y - 7), P(x - 4, y + 4), P(x, y + 6), P(x + 4, y + 4) }, Color.FromArgb(58, 184, 212), Color.FromArgb(37, 127, 152), 1);
            }
        }

        private static void DrawApproval(Graphics g, float ox, float oy, double pulse)
        {
            float wave = (float)Math.Sin(pulse * 4) * 8;
            float bob = (float)Math.Sin(pulse * 2) * 1.5f;
            FillEllipse(g, Color.FromArgb(203, 211, 216), ox + 21, oy + 192, 145, 11);
            Line(g, ox, oy, new PointF[] { P(88, 82 + bob), P(88, 141), P(57, 194) }, Ink, 7);
            Line(g, ox, oy, new PointF[] { P(88, 141), P(119, 194) }, Ink, 6);
            Line(g, ox, oy, new PointF[] { P(88, 91), P(54, 58 + wave) }, Ink, 5);
            Line(g, ox, oy, new PointF[] { P(88, 91), P(125, 58 - wave) }, Ink, 5);
            DrawScarf(g, ox, oy, 88, 82 + bob, Red, (float)Math.Sin(pulse * 3) * 3);
            DrawHead(g, ox, oy, 88, 55 + bob, 23, "surprised");
            DrawText(g, "!", AlertFont, Red, new RectangleF(ox + 143, oy + 25, 30, 50), StringAlignment.Center, StringAlignment.Center);
        }

        private static void DrawError(Graphics g, float ox, float oy, double pulse)
        {
            float droop = 2 + (float)Math.Sin(pulse * 1.5);
            FillEllipse(g, Color.FromArgb(203, 211, 216), ox + 10, oy + 190, 170, 12);
            Line(g, ox, oy, new PointF[] { P(54, 96 + droop), P(57, 151), P(31, 190) }, Ink, 7);
            Line(g, ox, oy, new PointF[] { P(57, 151), P(88, 190) }, Ink, 6);
            Line(g, ox, oy, new PointF[] { P(55, 105), P(83, 128), P(112, 143) }, Ink, 5);
            DrawScarf(g, ox, oy, 54, 96 + droop, Red, -2);
            DrawHead(g, ox, oy, 43, 74 + droop, 22, "sad");
            FillPolygon(g, ox, oy, new PointF[] { P(112, 116), P(171, 127), P(162, 165), P(105, 153) }, Color.FromArgb(52, 62, 68), Ink, 2);
            Line(g, ox, oy, new PointF[] { P(121, 129), P(150, 153) }, Red, 4);
            Line(g, ox, oy, new PointF[] { P(151, 135), P(122, 149) }, Red, 4);
        }

        private static void DrawHead(Graphics g, float ox, float oy, float cx, float cy, float radius, string expression)
        {
            FillEllipse(g, Color.FromArgb(255, 253, 248), ox + cx - radius, oy + cy - radius, radius * 2, radius * 2, Ink, 4);
            if (expression == "tired" || expression == "sad")
            {
                Line(g, ox, oy, new PointF[] { P(cx - 10, cy - 3), P(cx - 4, cy - 4) }, Ink, 2, false);
                Line(g, ox, oy, new PointF[] { P(cx + 4, cy - 4), P(cx + 10, cy - 3) }, Ink, 2, false);
            }
            else
            {
                FillEllipse(g, Ink, ox + cx - 10, oy + cy - 6, 4, 4);
                FillEllipse(g, Ink, ox + cx + 6, oy + cy - 6, 4, 4);
            }
            if (expression == "surprised")
                FillEllipse(g, Paper, ox + cx - 4, oy + cy + 6, 8, 9, Ink, 2);
            else if (expression == "tired")
                FillEllipse(g, Paper, ox + cx + 1, oy + cy + 5, 9, 8, Ink, 2);
            else
                Line(g, ox, oy, new PointF[] { P(cx + 1, cy + 10), P(cx + 9, cy + 10) }, Ink, 2, false);
        }

        private static void DrawScarf(Graphics g, float ox, float oy, float x, float y, Color color, float wave)
        {
            Line(g, ox, oy, new PointF[] { P(x - 8, y), P(x + 9, y) }, color, 4);
            Line(g, ox, oy, new PointF[] { P(x + 7, y + 1), P(x + 20, y + 7 + wave) }, color, 3);
        }

        private static void DrawFish(Graphics g, float ox, float oy, float x, float y, int direction, Color color, bool small)
        {
            float bw = small ? 11 : 15;
            float bh = small ? 6 : 8;
            FillPolygon(g, ox, oy, new PointF[] { P(x - direction * bw, y), P(x - direction * (bw + 8), y - bh), P(x - direction * (bw + 8), y + bh) }, color, Ink, 1);
            FillEllipse(g, color, ox + x - bw, oy + y - bh, bw * 2, bh * 2, Ink, 1);
            float eye = x + direction * (bw - 4);
            FillEllipse(g, Ink, ox + eye - 1.5f, oy + y - 2.5f, 3, 3);
        }

        private static void Line(Graphics g, float ox, float oy, PointF[] points, Color color, float width, bool smooth = true)
        {
            PointF[] moved = points.Select(point => new PointF(point.X + ox, point.Y + oy)).ToArray();
            if (color == Ink && width >= 4)
            {
                using (Pen outline = new Pen(Color.FromArgb(247, 249, 248), width + 3))
                {
                    outline.StartCap = outline.EndCap = LineCap.Round;
                    outline.LineJoin = LineJoin.Round;
                    g.DrawLines(outline, moved);
                }
            }
            using (Pen pen = new Pen(color, width))
            {
                pen.StartCap = pen.EndCap = LineCap.Round;
                pen.LineJoin = LineJoin.Round;
                g.DrawLines(pen, moved);
            }
        }

        private static void FillPolygon(Graphics g, float ox, float oy, PointF[] points, Color fill, Color outline, float width)
        {
            PointF[] moved = points.Select(point => new PointF(point.X + ox, point.Y + oy)).ToArray();
            using (Brush brush = new SolidBrush(fill)) g.FillPolygon(brush, moved);
            if (width > 0 && outline != Color.Transparent)
                using (Pen pen = new Pen(outline, width) { LineJoin = LineJoin.Round }) g.DrawPolygon(pen, moved);
        }

        private static void FillEllipse(Graphics g, Color fill, float x, float y, float width, float height)
        {
            using (Brush brush = new SolidBrush(fill)) g.FillEllipse(brush, x, y, width, height);
        }

        private static void FillEllipse(Graphics g, Color fill, float x, float y, float width, float height, Color outline, float outlineWidth)
        {
            FillEllipse(g, fill, x, y, width, height);
            using (Pen pen = new Pen(outline, outlineWidth)) g.DrawEllipse(pen, x, y, width, height);
        }

        private static PointF P(float x, float y) { return new PointF(x, y); }

        private static void RoundRect(Graphics g, Rectangle rect, int radius, Color fill, Color outline, float width)
        {
            RoundRect(g, new RectangleF(rect.X, rect.Y, rect.Width, rect.Height), radius, fill, outline, width);
        }

        private static void RoundRect(Graphics g, RectangleF rect, float radius, Color fill, Color outline, float width)
        {
            using (GraphicsPath path = new GraphicsPath())
            {
                float diameter = radius * 2;
                path.AddArc(rect.X, rect.Y, diameter, diameter, 180, 90);
                path.AddArc(rect.Right - diameter, rect.Y, diameter, diameter, 270, 90);
                path.AddArc(rect.Right - diameter, rect.Bottom - diameter, diameter, diameter, 0, 90);
                path.AddArc(rect.X, rect.Bottom - diameter, diameter, diameter, 90, 90);
                path.CloseFigure();
                using (Brush brush = new SolidBrush(fill)) g.FillPath(brush, path);
                if (width > 0 && outline != Color.Transparent)
                    using (Pen pen = new Pen(outline, width)) g.DrawPath(pen, path);
            }
        }

        private static void DrawText(Graphics g, string text, Font font, Color color, Rectangle rect, StringAlignment horizontal, StringAlignment vertical)
        {
            DrawText(g, text, font, color, new RectangleF(rect.X, rect.Y, rect.Width, rect.Height), horizontal, vertical);
        }

        private static void DrawText(Graphics g, string text, Font font, Color color, RectangleF rect, StringAlignment horizontal, StringAlignment vertical)
        {
            using (Brush brush = new SolidBrush(color))
            using (StringFormat format = new StringFormat { Alignment = horizontal, LineAlignment = vertical, Trimming = StringTrimming.EllipsisCharacter, FormatFlags = StringFormatFlags.NoWrap })
                g.DrawString(text ?? "", font, brush, rect, format);
        }

        private static string Truncate(string text, int limit)
        {
            if (String.IsNullOrWhiteSpace(text)) return "";
            string cleaned = String.Join(" ", text.Split((char[])null, StringSplitOptions.RemoveEmptyEntries));
            return cleaned.Length <= limit ? cleaned : cleaned.Substring(0, limit - 1) + "…";
        }

        public static string Elapsed(TaskSnapshot task)
        {
            if (task == null || task.StartedAt <= 0) return "--:--";
            double end = task.Status == TaskStatus.Running || task.Status == TaskStatus.Approval ? HookBridge.UnixNow() : Math.Max(task.UpdatedAt, task.StartedAt);
            int seconds = Math.Max(0, (int)(end - task.StartedAt));
            if (seconds >= 3600) return String.Format("{0:00}:{1:00}:{2:00}", seconds / 3600, (seconds / 60) % 60, seconds % 60);
            return String.Format("{0:00}:{1:00}", seconds / 60, seconds % 60);
        }
    }
}
