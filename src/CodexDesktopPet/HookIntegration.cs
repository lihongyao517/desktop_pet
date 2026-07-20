using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;

namespace CodexDesktopPet
{
    internal static class HookIntegration
    {
        public const string Marker = "Codex Desktop Pet status bridge";
        private const string LegacyMarker = "Codex Traffic Light status bridge";
        public static readonly string[] Events = new string[]
        {
            "SessionStart", "UserPromptSubmit", "PermissionRequest", "PostToolUse", "SubagentStart", "Stop"
        };

        public static bool IsInstalled()
        {
            try
            {
                if (!File.Exists(AppPaths.HooksFile)) return false;
                Dictionary<string, object> root = JsonUtil.ParseObject(File.ReadAllText(AppPaths.HooksFile));
                Dictionary<string, object> hooks = JsonUtil.Dictionary(JsonUtil.Get(root, "hooks"));
                if (hooks == null) return false;
                return Events.All(name => ContainsOurs(JsonUtil.Get(hooks, name)));
            }
            catch { return false; }
        }

        public static string Install(string commandOverride)
        {
            string path = AppPaths.HooksFile;
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            Dictionary<string, object> root;
            if (File.Exists(path))
            {
                root = JsonUtil.ParseObject(File.ReadAllText(path));
                if (root == null) throw new InvalidDataException("hooks.json 必须是 JSON 对象");
                File.Copy(path, path + ".backup-" + DateTime.Now.ToString("yyyyMMdd-HHmmss"), true);
            }
            else
            {
                root = new Dictionary<string, object>();
                root["description"] = "User-level Codex lifecycle hooks.";
            }

            Dictionary<string, object> hooks = JsonUtil.Dictionary(JsonUtil.Get(root, "hooks"));
            if (hooks == null)
            {
                hooks = new Dictionary<string, object>();
                root["hooks"] = hooks;
            }

            string command = commandOverride;
            if (String.IsNullOrEmpty(command))
            {
                string helper = Path.Combine(AppPaths.ExecutableDirectory, "CodexDesktopPetHook.exe");
                command = "\"" + helper + "\" --hook";
            }
            foreach (string eventName in Events)
            {
                List<object> groups = CleanGroups(JsonUtil.Get(hooks, eventName));
                Dictionary<string, object> handler = new Dictionary<string, object>();
                handler["type"] = "command";
                handler["command"] = command;
                handler["commandWindows"] = command;
                handler["timeout"] = 5;
                handler["statusMessage"] = Marker;
                Dictionary<string, object> group = new Dictionary<string, object>();
                group["hooks"] = new object[] { handler };
                if (eventName == "SessionStart") group["matcher"] = "startup|resume|clear";
                groups.Add(group);
                hooks[eventName] = groups.ToArray();
            }
            JsonUtil.WriteAtomic(path, root);
            return path;
        }

        public static string Uninstall()
        {
            string path = AppPaths.HooksFile;
            if (!File.Exists(path)) return path;
            Dictionary<string, object> root = JsonUtil.ParseObject(File.ReadAllText(path));
            Dictionary<string, object> hooks = JsonUtil.Dictionary(JsonUtil.Get(root, "hooks"));
            if (hooks == null) return path;
            File.Copy(path, path + ".backup-" + DateTime.Now.ToString("yyyyMMdd-HHmmss"), true);
            foreach (string key in hooks.Keys.ToList())
            {
                List<object> groups = CleanGroups(hooks[key]);
                if (groups.Count == 0) hooks.Remove(key);
                else hooks[key] = groups.ToArray();
            }
            JsonUtil.WriteAtomic(path, root);
            return path;
        }

        private static bool ContainsOurs(object groupsValue)
        {
            foreach (object groupValue in JsonUtil.Array(groupsValue))
            {
                Dictionary<string, object> group = JsonUtil.Dictionary(groupValue);
                if (group == null) continue;
                foreach (object handlerValue in JsonUtil.Array(JsonUtil.Get(group, "hooks")))
                    if (IsOurs(JsonUtil.Dictionary(handlerValue))) return true;
            }
            return false;
        }

        private static List<object> CleanGroups(object groupsValue)
        {
            List<object> cleaned = new List<object>();
            foreach (object groupValue in JsonUtil.Array(groupsValue))
            {
                Dictionary<string, object> group = JsonUtil.Dictionary(groupValue);
                if (group == null) { cleaned.Add(groupValue); continue; }
                object hooksValue = JsonUtil.Get(group, "hooks");
                List<object> handlers = JsonUtil.Array(hooksValue)
                    .Where(value => !IsOurs(JsonUtil.Dictionary(value))).ToList();
                if (handlers.Count == 0) continue;
                Dictionary<string, object> copy = new Dictionary<string, object>(group);
                copy["hooks"] = handlers.ToArray();
                cleaned.Add(copy);
            }
            return cleaned;
        }

        private static bool IsOurs(Dictionary<string, object> handler)
        {
            if (handler == null) return false;
            string status = JsonUtil.StringValue(handler, "statusMessage", "") + " " + JsonUtil.StringValue(handler, "status_message", "");
            string command = JsonUtil.StringValue(handler, "commandWindows", "") + " " + JsonUtil.StringValue(handler, "command", "");
            return status.Contains(Marker) || status.Contains(LegacyMarker) ||
                command.IndexOf("CodexDesktopPetHook", StringComparison.OrdinalIgnoreCase) >= 0 ||
                command.IndexOf("CodexTrafficLightHook", StringComparison.OrdinalIgnoreCase) >= 0 ||
                command.IndexOf("hook_main.py", StringComparison.OrdinalIgnoreCase) >= 0;
        }
    }
}
