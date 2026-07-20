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
            { "SubagentStop", new string[] { TaskStatus.Running, "子 Agent 已完成" } },
            { "PermissionRequest", new string[] { TaskStatus.Approval, "等待权限批准" } },
            { "PermissionDenied", new string[] { TaskStatus.Error, "权限被拒绝" } },
            { "PreToolUse", new string[] { TaskStatus.Running, "调用工具" } },
            { "PostToolUse", new string[] { TaskStatus.Running, "继续执行" } },
            { "PostToolUseFailure", new string[] { TaskStatus.Error, "工具执行失败" } },
            { "PostToolBatch", new string[] { TaskStatus.Running, "处理工具结果" } },
            { "TaskCreated", new string[] { TaskStatus.Running, "创建子任务" } },
            { "TaskCompleted", new string[] { TaskStatus.Running, "子任务已完成" } },
            { "TeammateIdle", new string[] { TaskStatus.Running, "协作者待命" } },
            { "PreCompact", new string[] { TaskStatus.Running, "整理上下文" } },
            { "PostCompact", new string[] { TaskStatus.Running, "上下文已整理" } },
            { "Stop", new string[] { TaskStatus.Completed, "本轮已完成" } },
            { "StopFailure", new string[] { TaskStatus.Error, "任务失败" } },
            { "SessionEnd", new string[] { TaskStatus.Cancelled, "会话已关闭" } }
        };

        public static int Run(TextReader input, string provider)
        {
            try
            {
                string raw = input.ReadToEnd().TrimStart('\uFEFF');
                if (String.IsNullOrWhiteSpace(raw)) return 0;
                Dictionary<string, object> payload = JsonUtil.ParseObject(raw);
                WriteState(payload, null, provider);
            }
            catch { }
            return 0;
        }

        public static string WriteState(Dictionary<string, object> payload, string directory, string provider)
        {
            string eventName = JsonUtil.StringValue(payload, "hook_event_name", "");
            string[] mapped;
            if (!EventStates.TryGetValue(eventName, out mapped))
            {
                string explicitStatus = JsonUtil.StringValue(payload, "status", "");
                if (String.IsNullOrEmpty(explicitStatus)) return null;
                mapped = new string[] { explicitStatus, JsonUtil.StringValue(payload, "phase", eventName) };
            }
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
            state["provider"] = String.IsNullOrEmpty(provider) ? "codex" : provider;
            state["event"] = eventName;
            string targetDirectory = directory ?? AppPaths.TaskStateDirectory;
            Directory.CreateDirectory(targetDirectory);
            string stateId = state["provider"].ToString() == "codex" ? sessionId : state["provider"] + "-" + sessionId;
            string safeName = Regex.Replace(stateId, "[^A-Za-z0-9_.-]", "_");
            if (safeName.Length > 120) safeName = safeName.Substring(0, 120);
            if (safeName.Length == 0) safeName = "unknown-session";
            string path = Path.Combine(targetDirectory, safeName + ".json");
            if (eventName == "SessionEnd" && File.Exists(path))
            {
                try
                {
                    Dictionary<string, object> previous = JsonUtil.ParseObject(File.ReadAllText(path));
                    string previousStatus = JsonUtil.StringValue(previous, "status", TaskStatus.Idle);
                    if (previousStatus != TaskStatus.Running && previousStatus != TaskStatus.Approval)
                        return path;
                }
                catch { }
            }
            JsonUtil.WriteAtomic(path, state);
            return path;
        }

        internal static double UnixNow()
        {
            return (DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds;
        }
    }
}
