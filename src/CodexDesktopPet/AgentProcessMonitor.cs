using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Management;

namespace CodexDesktopPet
{
    internal sealed class AgentProcessMonitor
    {
        private DateTime lastScan = DateTime.MinValue;
        private Dictionary<string, TaskSnapshot> last = new Dictionary<string, TaskSnapshot>();

        public Dictionary<string, TaskSnapshot> Scan()
        {
            if ((DateTime.UtcNow - lastScan).TotalSeconds < 1) return last;
            lastScan = DateTime.UtcNow;
            Dictionary<string, TaskSnapshot> current = new Dictionary<string, TaskSnapshot>();
            try
            {
                using (ManagementObjectSearcher searcher = new ManagementObjectSearcher("SELECT ProcessId, Name, CommandLine, CreationDate FROM Win32_Process"))
                using (ManagementObjectCollection processes = searcher.Get())
                {
                    foreach (ManagementObject process in processes)
                    {
                        string name = Convert.ToString(process["Name"] ?? "");
                        string command = Convert.ToString(process["CommandLine"] ?? "");
                        string provider = DetectProvider(name, command);
                        if (provider == null) continue;
                        uint pid = Convert.ToUInt32(process["ProcessId"]);
                        if (pid == (uint)Process.GetCurrentProcess().Id) continue;
                        string id = "process-" + provider + "-" + pid;
                        double now = HookBridge.UnixNow();
                        TaskSnapshot previous;
                        double started = ProcessCreationTime(process, now);
                        if (last.TryGetValue(id, out previous) && previous.StartedAt > 0)
                            started = previous.StartedAt;
                        current[id] = new TaskSnapshot
                        {
                            SessionId = id,
                            Provider = provider,
                            Source = "process",
                            Status = TaskStatus.Running,
                            Phase = "TUI 运行中",
                            Title = ProviderName(provider) + " CLI (PID " + pid + ")",
                            UpdatedAt = now,
                            StartedAt = started
                        };
                    }
                }
            }
            catch { }
            last = current;
            return current;
        }

        internal static string DetectProvider(string processName, string commandLine)
        {
            string value = ((processName ?? "") + " " + (commandLine ?? "")).ToLowerInvariant();
            string name = (processName ?? "").ToLowerInvariant();
            if (value.Contains("codexdesktoppet")) return null;
            if (name == "cmd.exe" || name == "powershell.exe" || name == "pwsh.exe" ||
                name == "npm.exe" || name == "npx.exe" || name == "conhost.exe") return null;
            if (value.Contains("claude-code") || value.Contains("@anthropic-ai") || name.StartsWith("claude")) return "claude";
            if (value.Contains("opencode") || name.StartsWith("opencode")) return "opencode";
            if (value.Contains("antigravity") || value.Contains("\\agy") || name.StartsWith("agy")) return "antigravity";
            if (value.Contains("gemini") || name.StartsWith("gemini")) return "gemini";
            if (value.Contains("aider") || name.StartsWith("aider")) return "aider";
            if (value.Contains("cursor-agent")) return "cursor";
            if (value.Contains("qwen-code") || name.StartsWith("qwen")) return "qwen";
            if (name.StartsWith("goose") || value.Contains("\\goose") || value.Contains("/goose")) return "goose";
            if (value.Contains("kimi-cli") || name.StartsWith("kimi")) return "kimi";
            return null;
        }

        private static double ProcessCreationTime(ManagementObject process, double fallback)
        {
            try
            {
                string raw = Convert.ToString(process["CreationDate"] ?? "");
                if (!String.IsNullOrEmpty(raw))
                {
                    DateTime created = ManagementDateTimeConverter.ToDateTime(raw).ToUniversalTime();
                    return (created - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds;
                }
            }
            catch { }
            return fallback;
        }

        internal static string ProviderName(string provider)
        {
            if (provider == "claude") return "Claude Code";
            if (provider == "opencode") return "OpenCode";
            if (provider == "antigravity") return "Antigravity";
            if (provider == "gemini") return "Gemini CLI";
            if (provider == "aider") return "Aider";
            if (provider == "cursor") return "Cursor Agent";
            if (provider == "qwen") return "Qwen Code";
            if (provider == "goose") return "Goose";
            if (provider == "kimi") return "Kimi CLI";
            return provider;
        }
    }
}
