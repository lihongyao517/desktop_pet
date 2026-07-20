using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;

namespace CodexDesktopPet
{
    internal sealed class CodexMonitor : IDisposable
    {
        private readonly object sync = new object();
        private readonly Dictionary<string, TaskSnapshot> tasks = new Dictionary<string, TaskSnapshot>();
        private readonly Dictionary<string, SessionLogParser> parsers = new Dictionary<string, SessionLogParser>(StringComparer.OrdinalIgnoreCase);
        private readonly AgentProcessMonitor processMonitor = new AgentProcessMonitor();
        private readonly ReviewStateStore reviewState = new ReviewStateStore(AppPaths.ReviewedTasksFile);
        private readonly Dictionary<string, long> stateTimes = new Dictionary<string, long>(StringComparer.OrdinalIgnoreCase);
        private Dictionary<string, string> titles = new Dictionary<string, string>();
        private HashSet<string> unreadIds;
        private long titleTime;
        private long unreadTime;
        private double unreadStateUpdatedAt;
        private DateTime lastAdapterCheck = DateTime.MinValue;
        private DateTime lastPrune = DateTime.MinValue;
        private bool claudeAdapterReady;
        private bool openCodeAdapterReady;
        private DateTime lastDiscovery = DateTime.MinValue;
        private DateTime lastFullDiscovery = DateTime.MinValue;
        private AggregateSnapshot current = new AggregateSnapshot();
        private Thread worker;
        private volatile bool stopping;

        public AggregateSnapshot Current
        {
            get { lock (sync) return current.Clone(); }
        }

        public void Start()
        {
            if (worker != null && worker.IsAlive) return;
            stopping = false;
            worker = new Thread(Run) { IsBackground = true, Name = "codex-monitor" };
            worker.Start();
        }

        public void Dispose()
        {
            stopping = true;
            if (worker != null && worker.IsAlive) worker.Join(1500);
        }

        public void MarkReviewed(TaskSnapshot task)
        {
            reviewState.MarkReviewed(task);
        }

        private void Run()
        {
            while (!stopping)
            {
                try
                {
                    AggregateSnapshot snapshot = Scan();
                    lock (sync) current = snapshot;
                }
                catch { }
                for (int index = 0; index < 4 && !stopping; index++) Thread.Sleep(50);
            }
        }

        private AggregateSnapshot Scan()
        {
            LoadTitles();
            LoadUnreadIds();
            ScanHookStates();
            ScanAgentProcesses();
            DiscoverSessions();
            foreach (SessionLogParser parser in parsers.Values.ToList()) Merge(parser.ReadUpdates());
            ApplyTitlesAndUnread();
            PruneHistory();
            return AggregateResolver.Resolve(tasks.Values, HookBridge.UnixNow());
        }

        private void LoadUnreadIds()
        {
            string path = Path.Combine(AppPaths.CodexHome, ".codex-global-state.json");
            long modified = LastWriteTicks(path);
            if (modified == 0 || modified == unreadTime) return;
            try
            {
                Dictionary<string, object> root = JsonUtil.ParseObject(File.ReadAllText(path));
                Dictionary<string, object> atoms = JsonUtil.Dictionary(JsonUtil.Get(root, "electron-persisted-atom-state"));
                Dictionary<string, object> byHost = JsonUtil.Dictionary(JsonUtil.Get(atoms, "unread-thread-ids-by-host-v1"));
                HashSet<string> loaded = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                foreach (object value in JsonUtil.Array(JsonUtil.Get(byHost, "local")))
                    if (value != null) loaded.Add(Convert.ToString(value, CultureInfo.InvariantCulture));
                unreadIds = loaded;
                unreadTime = modified;
                unreadStateUpdatedAt = (File.GetLastWriteTimeUtc(path) -
                    new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds;
            }
            catch { }
        }

        private void LoadTitles()
        {
            string path = Path.Combine(AppPaths.CodexHome, "session_index.jsonl");
            long modified = LastWriteTicks(path);
            if (modified == 0 || modified == titleTime) return;
            try
            {
                Dictionary<string, string> loaded = new Dictionary<string, string>();
                using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                using (StreamReader reader = new StreamReader(stream, Encoding.UTF8, true))
                {
                    string line;
                    while ((line = reader.ReadLine()) != null)
                    {
                        try
                        {
                            Dictionary<string, object> item = JsonUtil.ParseObject(line);
                            string id = JsonUtil.StringValue(item, "id", "");
                            string name = JsonUtil.StringValue(item, "thread_name", "").Trim();
                            if (id.Length > 0 && name.Length > 0) loaded[id] = name;
                        }
                        catch { }
                    }
                }
                titles = loaded;
                titleTime = modified;
            }
            catch { }
        }

        private void ScanHookStates()
        {
            if (!Directory.Exists(AppPaths.TaskStateDirectory)) return;
            string[] files;
            try { files = Directory.GetFiles(AppPaths.TaskStateDirectory, "*.json", SearchOption.TopDirectoryOnly); }
            catch { return; }
            foreach (string path in files)
            {
                long modified = LastWriteTicks(path);
                long previous;
                if (stateTimes.TryGetValue(path, out previous) && previous == modified) continue;
                stateTimes[path] = modified;
                try
                {
                    Dictionary<string, object> data = JsonUtil.ParseObject(File.ReadAllText(path));
                    TaskSnapshot snapshot = new TaskSnapshot();
                    snapshot.SessionId = JsonUtil.StringValue(data, "session_id", Path.GetFileNameWithoutExtension(path));
                    snapshot.Status = JsonUtil.StringValue(data, "status", TaskStatus.Idle);
                    snapshot.Phase = JsonUtil.StringValue(data, "phase", "会话就绪");
                    snapshot.Cwd = JsonUtil.StringValue(data, "cwd", "");
                    snapshot.Title = TitleFallback(snapshot.Cwd);
                    snapshot.TurnId = JsonUtil.StringValue(data, "turn_id", "");
                    snapshot.UpdatedAt = JsonUtil.DoubleValue(data, "updated_at", 0);
                    snapshot.StartedAt = JsonUtil.DoubleValue(data, "started_at", 0);
                    snapshot.Source = "hook";
                    snapshot.Provider = JsonUtil.StringValue(data, "provider", "codex");
                    Merge(snapshot);
                }
                catch { }
            }
        }

        private void DiscoverSessions()
        {
            DateTime now = DateTime.UtcNow;
            if ((now - lastDiscovery).TotalSeconds < 0.4) return;
            lastDiscovery = now;
            string sessions = Path.Combine(AppPaths.CodexHome, "sessions");
            if (!Directory.Exists(sessions)) return;
            List<string> candidates = new List<string>();
            try
            {
                DateTime today = DateTime.Now;
                string current = Path.Combine(sessions, today.ToString("yyyy"), today.ToString("MM"), today.ToString("dd"));
                if (Directory.Exists(current)) candidates.AddRange(Directory.GetFiles(current, "rollout-*.jsonl"));
                if (parsers.Count == 0 || (now - lastFullDiscovery).TotalSeconds >= 30)
                {
                    lastFullDiscovery = now;
                    candidates.AddRange(Directory.GetFiles(sessions, "rollout-*.jsonl", SearchOption.AllDirectories));
                }
            }
            catch { return; }
            foreach (string path in candidates.Distinct(StringComparer.OrdinalIgnoreCase)
                .OrderByDescending(LastWriteTicks).Take(80))
            {
                if (!parsers.ContainsKey(path)) parsers[path] = new SessionLogParser(path);
            }
        }

        private void Merge(TaskSnapshot incoming)
        {
            if (incoming == null || String.IsNullOrEmpty(incoming.SessionId)) return;
            TaskSnapshot previous;
            string key = TaskKey(incoming);
            if (!tasks.TryGetValue(key, out previous))
            {
                tasks[key] = incoming.Clone();
                return;
            }
            if (incoming.UpdatedAt < previous.UpdatedAt) return;
            TaskSnapshot merged = incoming.Clone();
            if (merged.StartedAt <= 0) merged.StartedAt = previous.StartedAt;
            if (merged.Title == "Codex 任务" && previous.Title != "Codex 任务") merged.Title = previous.Title;
            if (String.IsNullOrEmpty(merged.Cwd)) merged.Cwd = previous.Cwd;
            if (String.IsNullOrEmpty(merged.TurnId)) merged.TurnId = previous.TurnId;
            merged.Unread = previous.Unread;
            tasks[key] = merged;
        }

        private void ApplyTitlesAndUnread()
        {
            foreach (TaskSnapshot task in tasks.Values)
            {
                string title;
                if (task.Provider == "codex" && titles.TryGetValue(task.SessionId, out title)) task.Title = title;
                if (task.Status != TaskStatus.Completed) continue;
                if (reviewState.IsReviewed(task))
                {
                    task.Unread = false;
                    continue;
                }
                if (task.Provider != "codex")
                {
                    task.Unread = true;
                    continue;
                }
                if (unreadIds == null)
                {
                    task.Unread = true;
                    continue;
                }
                if (unreadIds.Contains(task.SessionId))
                {
                    task.Unread = true;
                    continue;
                }
                double now = HookBridge.UnixNow();
                bool statePredatesCompletion = unreadStateUpdatedAt + 1 < task.UpdatedAt;
                task.Unread = now - task.UpdatedAt <= 5 || statePredatesCompletion;
            }
        }

        private void ScanAgentProcesses()
        {
            if ((DateTime.UtcNow - lastAdapterCheck).TotalSeconds >= 5)
            {
                lastAdapterCheck = DateTime.UtcNow;
                claudeAdapterReady = HookIntegration.IsClaudeInstalled();
                openCodeAdapterReady = HookIntegration.IsOpenCodeInstalled();
            }
            Dictionary<string, TaskSnapshot> active = processMonitor.Scan();
            List<TaskSnapshot> accepted = active.Values.Where(task =>
                !(task.Provider == "claude" && claudeAdapterReady) &&
                !(task.Provider == "opencode" && openCodeAdapterReady)).ToList();
            HashSet<string> activeKeys = new HashSet<string>(accepted.Select(TaskKey), StringComparer.OrdinalIgnoreCase);
            foreach (string oldKey in tasks.Keys.Where(key => tasks[key].Source == "process" && !activeKeys.Contains(key)).ToList())
                tasks.Remove(oldKey);
            foreach (TaskSnapshot task in accepted) Merge(task);
        }

        private void PruneHistory()
        {
            DateTime now = DateTime.UtcNow;
            if ((now - lastPrune).TotalSeconds < 30) return;
            lastPrune = now;
            double current = HookBridge.UnixNow();
            foreach (string key in tasks.Keys.Where(key =>
                tasks[key].Source == "hook" &&
                tasks[key].Unread != true &&
                tasks[key].UpdatedAt > 0 &&
                current - tasks[key].UpdatedAt > 7 * 24 * 3600).ToList())
                tasks.Remove(key);
            foreach (string path in stateTimes.Keys.Where(path => !File.Exists(path)).ToList())
                stateTimes.Remove(path);
        }

        internal static string TaskKey(TaskSnapshot task)
        {
            return ReviewStateStore.Key(task == null ? "codex" : task.Provider, task == null ? "" : task.SessionId);
        }

        internal static string TitleFallback(string cwd)
        {
            try
            {
                if (!String.IsNullOrWhiteSpace(cwd))
                {
                    string name = Path.GetFileName(cwd.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
                    if (!String.IsNullOrEmpty(name)) return name;
                }
            }
            catch { }
            return "Codex 任务";
        }

        internal static long LastWriteTicks(string path)
        {
            try { return File.Exists(path) ? File.GetLastWriteTimeUtc(path).Ticks : 0; }
            catch { return 0; }
        }
    }

    internal sealed class SessionLogParser
    {
        private static readonly Regex SessionPattern = new Regex(
            "([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\\.jsonl$",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);
        private readonly string path;
        private long offset;
        private byte[] partial = new byte[0];
        private TaskSnapshot snapshot;

        public SessionLogParser(string path)
        {
            this.path = path;
            Match match = SessionPattern.Match(Path.GetFileName(path));
            snapshot = new TaskSnapshot
            {
                SessionId = match.Success ? match.Groups[1].Value : Path.GetFileNameWithoutExtension(path),
                Title = "Codex 任务",
                Source = "session-log"
                ,Provider = "codex"
            };
        }

        public TaskSnapshot ReadUpdates()
        {
            long length;
            try { length = new FileInfo(path).Length; }
            catch { return snapshot.Clone(); }
            if (length < offset) { offset = 0; partial = new byte[0]; }
            if (length == offset) return snapshot.Clone();
            bool discardFirst = false;
            long start = offset;
            if (offset == 0 && length > 2 * 1024 * 1024)
            {
                start = length - 2 * 1024 * 1024;
                discardFirst = true;
            }
            byte[] chunk;
            try
            {
                using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                {
                    stream.Seek(start, SeekOrigin.Begin);
                    chunk = new byte[stream.Length - start];
                    int total = 0;
                    while (total < chunk.Length)
                    {
                        int read = stream.Read(chunk, total, chunk.Length - total);
                        if (read <= 0) break;
                        total += read;
                    }
                    if (total != chunk.Length) Array.Resize(ref chunk, total);
                    offset = stream.Position;
                }
            }
            catch { return snapshot.Clone(); }

            byte[] data = new byte[partial.Length + chunk.Length];
            Buffer.BlockCopy(partial, 0, data, 0, partial.Length);
            Buffer.BlockCopy(chunk, 0, data, partial.Length, chunk.Length);
            int position = 0;
            if (discardFirst)
            {
                int newline = Array.IndexOf(data, (byte)'\n');
                position = newline < 0 ? data.Length : newline + 1;
            }
            while (position < data.Length)
            {
                int newline = Array.IndexOf(data, (byte)'\n', position);
                if (newline < 0) break;
                ConsumeLine(data, position, newline - position);
                position = newline + 1;
            }
            partial = new byte[data.Length - position];
            if (partial.Length > 0) Buffer.BlockCopy(data, position, partial, 0, partial.Length);
            return snapshot.Clone();
        }

        private void ConsumeLine(byte[] data, int start, int length)
        {
            if (length <= 0) return;
            try
            {
                string line = Encoding.UTF8.GetString(data, start, length).Trim().TrimStart('\uFEFF');
                if (line.Length == 0) return;
                Dictionary<string, object> record = JsonUtil.ParseObject(line);
                Consume(record);
            }
            catch { }
        }

        private void Consume(Dictionary<string, object> record)
        {
            string recordType = JsonUtil.StringValue(record, "type", "");
            Dictionary<string, object> payload = JsonUtil.Dictionary(JsonUtil.Get(record, "payload")) ?? new Dictionary<string, object>();
            double stamp = Timestamp(JsonUtil.Get(record, "timestamp"), HookBridge.UnixNow());
            if (recordType == "session_meta")
            {
                string id = JsonUtil.StringValue(payload, "session_id", JsonUtil.StringValue(payload, "id", snapshot.SessionId));
                string cwd = JsonUtil.StringValue(payload, "cwd", snapshot.Cwd);
                snapshot.SessionId = id;
                snapshot.Cwd = cwd;
                snapshot.Title = CodexMonitor.TitleFallback(cwd);
                return;
            }
            if (recordType == "event_msg")
            {
                string eventType = JsonUtil.StringValue(payload, "type", "");
                if (eventType == "task_started") Update(TaskStatus.Running, "开始处理", stamp, Timestamp(JsonUtil.Get(payload, "started_at"), stamp));
                else if (eventType == "user_message") Update(TaskStatus.Running, "开始处理", stamp, 0);
                else if (eventType == "agent_reasoning") Update(TaskStatus.Running, "正在分析", stamp, 0);
                else if (eventType == "agent_message") Update(TaskStatus.Running, JsonUtil.StringValue(payload, "phase", "") == "final_answer" ? "整理结果" : "正在汇报进度", stamp, 0);
                else if (eventType == "patch_apply_end") Update(TaskStatus.Running, "正在修改文件", stamp, 0);
                else if (eventType == "mcp_tool_call_end") Update(TaskStatus.Running, "正在使用工具", stamp, 0);
                else if (eventType == "web_search_end") Update(TaskStatus.Running, "正在检索资料", stamp, 0);
                else if (eventType == "context_compacted") Update(TaskStatus.Running, "正在整理上下文", stamp, 0);
                else if (eventType == "task_complete") Update(TaskStatus.Completed, "本轮已完成", stamp, 0);
                else if (eventType == "turn_aborted")
                {
                    string reason = JsonUtil.StringValue(payload, "reason", "").ToLowerInvariant();
                    bool failed = reason.Contains("error") || reason.Contains("fail") || reason.Contains("crash") || reason.Contains("panic");
                    Update(failed ? TaskStatus.Error : TaskStatus.Cancelled, failed ? "任务异常中止" : "任务已终止", stamp, 0);
                }
                snapshot.TurnId = JsonUtil.StringValue(payload, "turn_id", snapshot.TurnId);
                return;
            }
            if (recordType != "response_item") return;
            string itemType = JsonUtil.StringValue(payload, "type", "");
            if (itemType == "custom_tool_call" || itemType == "function_call")
                Update(TaskStatus.Running, ToolPhase(JsonUtil.StringValue(payload, "name", "")), stamp, 0);
            else if (itemType == "custom_tool_call_output" || itemType == "function_call_output")
                Update(TaskStatus.Running, "正在处理工具结果", stamp, 0);
        }

        private void Update(string status, string phase, double stamp, double started)
        {
            snapshot.Status = status;
            snapshot.Phase = phase;
            snapshot.UpdatedAt = Math.Max(snapshot.UpdatedAt, stamp);
            if (started > 0) snapshot.StartedAt = started;
            else if (status == TaskStatus.Running && snapshot.StartedAt <= 0) snapshot.StartedAt = stamp;
        }

        private static double Timestamp(object value, double fallback)
        {
            if (value == null) return fallback;
            try
            {
                if (!(value is string)) return Convert.ToDouble(value, CultureInfo.InvariantCulture);
                DateTime parsed;
                if (DateTime.TryParse(Convert.ToString(value), CultureInfo.InvariantCulture, DateTimeStyles.AdjustToUniversal, out parsed))
                    return (parsed.ToUniversalTime() - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds;
            }
            catch { }
            return fallback;
        }

        private static string ToolPhase(string name)
        {
            string lower = name.ToLowerInvariant();
            if (lower.Contains("apply_patch") || lower == "edit" || lower == "write") return "正在修改文件";
            if (lower.Contains("shell") || lower.Contains("exec")) return "正在执行命令";
            if (lower.Contains("web") || lower.Contains("search")) return "正在检索资料";
            if (lower.Contains("wait")) return "等待后台任务";
            return "正在使用工具";
        }
    }
}
