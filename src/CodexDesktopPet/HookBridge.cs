using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;

namespace CodexDesktopPet
{
    internal static class HookBridge
    {
        private static readonly Dictionary<string, string[]> EventStates = new Dictionary<string, string[]>
        {
            { "SessionStart", new string[] { TaskStatus.Idle, "会话就绪" } },
            { "UserPromptSubmit", new string[] { TaskStatus.Running, "开始处理" } },
            { "SubagentStart", new string[] { TaskStatus.Running, "并行任务运行中" } },
            { "PermissionRequest", new string[] { TaskStatus.Approval, "等待权限批准" } },
            { "PostToolUse", new string[] { TaskStatus.Running, "继续执行" } },
            { "Stop", new string[] { TaskStatus.Completed, "本轮已完成" } }
        };

        public static int Run(TextReader input)
        {
            try
            {
                string raw = input.ReadToEnd().TrimStart('\uFEFF');
                if (String.IsNullOrWhiteSpace(raw)) return 0;
                Dictionary<string, object> payload = JsonUtil.ParseObject(raw);
                WriteState(payload, null);
            }
            catch { }
            return 0;
        }

        public static string WriteState(Dictionary<string, object> payload, string directory)
        {
            string eventName = JsonUtil.StringValue(payload, "hook_event_name", "");
            string[] mapped;
            if (!EventStates.TryGetValue(eventName, out mapped)) return null;
            string sessionId = JsonUtil.StringValue(payload, "session_id", "unknown-session");
            double now = UnixNow();
            Dictionary<string, object> state = new Dictionary<string, object>();
            state["schema"] = 1;
            state["session_id"] = sessionId;
            state["turn_id"] = JsonUtil.StringValue(payload, "turn_id", "");
            state["status"] = mapped[0];
            state["phase"] = mapped[1];
            state["cwd"] = JsonUtil.StringValue(payload, "cwd", "");
            state["updated_at"] = now;
            state["started_at"] = eventName == "UserPromptSubmit" ? now : 0;
            state["source"] = "hook";
            state["event"] = eventName;
            string targetDirectory = directory ?? AppPaths.TaskStateDirectory;
            Directory.CreateDirectory(targetDirectory);
            string safeName = Regex.Replace(sessionId, "[^A-Za-z0-9_.-]", "_");
            if (safeName.Length > 120) safeName = safeName.Substring(0, 120);
            if (safeName.Length == 0) safeName = "unknown-session";
            string path = Path.Combine(targetDirectory, safeName + ".json");
            JsonUtil.WriteAtomic(path, state);
            return path;
        }

        internal static double UnixNow()
        {
            return (DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds;
        }
    }
}
