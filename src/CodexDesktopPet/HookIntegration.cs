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

        public static string ClaudeSettingsFile
        {
            get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".claude", "settings.json"); }
        }

        public static string OpenCodePluginFile
        {
            get
            {
                return Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                    ".config", "opencode", "plugins", "codex-desktop-pet.js");
            }
        }

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

        public static bool IsClaudeInstalled()
        {
            return IsManagedHookFileInstalled(ClaudeSettingsFile, "claude");
        }

        public static string InstallClaude()
        {
            string helper = Path.Combine(AppPaths.ExecutableDirectory, "CodexDesktopPetHook.exe");
            return InstallClaude(ClaudeSettingsFile, helper);
        }

        internal static string InstallClaude(string path, string helper)
        {
            return InstallManagedHookFile(path, helper, "claude", new string[]
            {
                "SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest", "PostToolUse",
                "PostToolUseFailure", "PostToolBatch", "PermissionDenied", "SubagentStart", "SubagentStop",
                "TaskCreated", "TaskCompleted", "TeammateIdle", "PreCompact", "PostCompact", "Stop", "StopFailure", "SessionEnd"
            });
        }

        public static bool IsOpenCodeInstalled()
        {
            try { return File.Exists(OpenCodePluginFile) && File.ReadAllText(OpenCodePluginFile).Contains("CodexDesktopPet"); }
            catch { return false; }
        }

        public static string InstallOpenCode()
        {
            return InstallOpenCode(OpenCodePluginFile);
        }

        internal static string InstallOpenCode(string path)
        {
            string directory = Path.GetDirectoryName(path);
            Directory.CreateDirectory(directory);
            if (File.Exists(path))
                File.Copy(path, path + ".backup-" + DateTime.Now.ToString("yyyyMMdd-HHmmss"), true);
            string helper = JsonUtil.Serialize(Path.Combine(AppPaths.ExecutableDirectory, "CodexDesktopPetHook.exe"));
            string plugin = "// CodexDesktopPet integration\n" +
                "const bridge = " + helper + ";\n" +
                "export const CodexDesktopPet = async ({ $, directory }) => ({\n" +
                "  event: async ({ event }) => {\n" +
                "    const relevant = ['session.created', 'session.compacted', 'session.idle', 'session.status', 'session.error', 'permission.asked', 'permission.replied', 'tool.execute.before', 'tool.execute.after'];\n" +
                "    if (!relevant.includes(event.type)) return;\n" +
                "    const props = event.properties || {};\n" +
                "    const session = props.sessionID || props.sessionId || props.session_id || (props.info && props.info.id) || (props.session && props.session.id) || props.id || 'opencode';\n" +
                "    let status = 'running';\n" +
                "    let phase = 'OpenCode: ' + event.type;\n" +
                "    if (event.type === 'session.created') { status = 'idle'; phase = 'OpenCode 会话就绪'; }\n" +
                "    if (event.type === 'permission.asked') status = 'approval';\n" +
                "    if (event.type === 'session.idle') status = 'completed';\n" +
                "    if (event.type === 'session.error') status = 'error';\n" +
                "    if (event.type === 'session.status') {\n" +
                "      const rawStatus = props.status && (props.status.type || props.status);\n" +
                "      if (rawStatus === 'idle') status = 'completed';\n" +
                "      if (rawStatus === 'error') status = 'error';\n" +
                "    }\n" +
                "    const payload = { hook_event_name: event.type, session_id: session, cwd: directory, status, phase };\n" +
                "    await $`${bridge} --provider opencode --json ${JSON.stringify(payload)}`;\n" +
                "  }\n" +
                "});\n";
            File.WriteAllText(path, plugin, new UTF8Encoding(false));
            return path;
        }

        public static string InstallManagedHookFile(string path, string helper, string provider, string[] events)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            Dictionary<string, object> root;
            if (File.Exists(path))
            {
                root = JsonUtil.ParseObject(File.ReadAllText(path));
                if (root == null) throw new InvalidDataException("Hook 设置文件必须是 JSON 对象");
                File.Copy(path, path + ".backup-" + DateTime.Now.ToString("yyyyMMdd-HHmmss"), true);
            }
            else root = new Dictionary<string, object>();
            Dictionary<string, object> hooks = JsonUtil.Dictionary(JsonUtil.Get(root, "hooks"));
            if (hooks == null) { hooks = new Dictionary<string, object>(); root["hooks"] = hooks; }
            foreach (string eventName in events)
            {
                List<object> groups = CleanGroups(JsonUtil.Get(hooks, eventName));
                Dictionary<string, object> handler = new Dictionary<string, object>();
                handler["type"] = "command";
                handler["command"] = helper;
                handler["args"] = new object[] { "--provider", provider, "--hook" };
                handler["timeout"] = 5;
                handler["statusMessage"] = Marker + " (" + provider + ")";
                Dictionary<string, object> group = new Dictionary<string, object>();
                group["hooks"] = new object[] { handler };
                if (eventName == "SessionStart") group["matcher"] = "startup|resume|clear";
                groups.Add(group);
                hooks[eventName] = groups.ToArray();
            }
            JsonUtil.WriteAtomic(path, root);
            return path;
        }

        private static bool IsManagedHookFileInstalled(string path, string provider)
        {
            try
            {
                if (!File.Exists(path)) return false;
                string text = File.ReadAllText(path);
                return text.Contains(Marker + " (" + provider + ")");
            }
            catch { return false; }
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
