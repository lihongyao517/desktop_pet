using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;

namespace CodexDesktopPet
{
    internal sealed class ReviewStateStore
    {
        private readonly object sync = new object();
        private readonly string path;
        private readonly Dictionary<string, double> reviewed =
            new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);

        public ReviewStateStore(string path)
        {
            this.path = path;
            Load();
        }

        public bool IsReviewed(TaskSnapshot task)
        {
            if (task == null || task.Status != TaskStatus.Completed) return false;
            lock (sync)
            {
                double stamp;
                return reviewed.TryGetValue(Key(task.Provider, task.SessionId), out stamp) &&
                    stamp + 0.001 >= task.UpdatedAt;
            }
        }

        public void MarkReviewed(TaskSnapshot task)
        {
            if (task == null || task.Status != TaskStatus.Completed) return;
            lock (sync)
            {
                string key = Key(task.Provider, task.SessionId);
                double stamp = task.UpdatedAt > 0 ? task.UpdatedAt : HookBridge.UnixNow();
                double previous;
                if (!reviewed.TryGetValue(key, out previous) || stamp > previous)
                    reviewed[key] = stamp;
                Save();
            }
        }

        internal static string Key(string provider, string sessionId)
        {
            return (String.IsNullOrWhiteSpace(provider) ? "codex" : provider) + "|" + (sessionId ?? "");
        }

        private void Load()
        {
            try
            {
                if (!File.Exists(path)) return;
                Dictionary<string, object> root = JsonUtil.ParseObject(File.ReadAllText(path));
                Dictionary<string, object> values = JsonUtil.Dictionary(JsonUtil.Get(root, "reviewed"));
                if (values == null) return;
                foreach (KeyValuePair<string, object> pair in values)
                {
                    try { reviewed[pair.Key] = Convert.ToDouble(pair.Value, CultureInfo.InvariantCulture); }
                    catch { }
                }
            }
            catch { }
        }

        private void Save()
        {
            try
            {
                Dictionary<string, object> values = reviewed
                    .OrderByDescending(pair => pair.Value)
                    .Take(500)
                    .ToDictionary(pair => pair.Key, pair => (object)pair.Value, StringComparer.OrdinalIgnoreCase);
                Dictionary<string, object> root = new Dictionary<string, object>();
                root["schema"] = 1;
                root["reviewed"] = values;
                JsonUtil.WriteAtomic(path, root);
            }
            catch { }
        }
    }
}
