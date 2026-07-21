using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace CodexDesktopPet
{
    internal static class TestProgram
    {
        private static int passed;
        private static int failed;

        public static int Main()
        {
            Run("Aggregate priority", TestAggregatePriority);
            Run("Unread completion lifecycle", TestUnreadCompletion);
            Run("Completion review persistence", TestCompletionReview);
            Run("Multi-agent task identity", TestMultiAgentIdentity);
            Run("Bottom-right anchor", TestBottomAnchor);
            Run("Left-edge expansion anchor", TestHorizontalAnchor);
            Run("Hook state bridge", TestHookBridge);
            Run("Hook install preservation", TestHookIntegration);
            Run("Session log lifecycle", TestSessionLogLifecycle);
            Run("Claude and OpenCode adapters", TestAgentAdapters);
            Run("CLI provider detection", TestProviderDetection);
            Console.WriteLine("C# tests: {0} passed, {1} failed", passed, failed);
            return failed == 0 ? 0 : 1;
        }

        private static void TestAggregatePriority()
        {
            List<TaskSnapshot> tasks = new List<TaskSnapshot>
            {
                Task("cancelled", TaskStatus.Cancelled, 999),
                Task("error", TaskStatus.Error, 998),
                Task("running", TaskStatus.Running, 997)
            };
            AggregateSnapshot result = AggregateResolver.Resolve(tasks, 1000);
            Equal(TaskStatus.Running, result.Status);
            Equal("running", result.Selected.SessionId);
            Equal("running,error,cancelled", String.Join(",", result.VisibleTasks.Select(item => item.SessionId).ToArray()));
        }

        private static void TestUnreadCompletion()
        {
            TaskSnapshot completed = Task("done", TaskStatus.Completed, 1);
            completed.Unread = true;
            AggregateSnapshot unread = AggregateResolver.Resolve(new TaskSnapshot[] { completed }, 100000);
            Equal(TaskStatus.Completed, unread.Status);
            Equal("任务完成，待检查", PetRenderer.StatusName(unread.Status));
            Equal("待检查", PetRenderer.TaskStatusName(unread.Status));
            completed.Unread = false;
            AggregateSnapshot read = AggregateResolver.Resolve(new TaskSnapshot[] { completed }, 100000);
            Equal(TaskStatus.Idle, read.Status);
            Equal(0, read.VisibleTasks.Count);
        }

        private static void TestCompletionReview()
        {
            string directory = TemporaryDirectory();
            try
            {
                string path = Path.Combine(directory, "reviewed.json");
                TaskSnapshot task = Task("same-session", TaskStatus.Completed, 100);
                task.Provider = "claude";
                ReviewStateStore first = new ReviewStateStore(path);
                True(!first.IsReviewed(task));
                first.MarkReviewed(task);
                True(first.IsReviewed(task));
                ReviewStateStore reloaded = new ReviewStateStore(path);
                True(reloaded.IsReviewed(task));
                task.UpdatedAt = 101;
                True(!reloaded.IsReviewed(task));
            }
            finally { Directory.Delete(directory, true); }
        }

        private static void TestMultiAgentIdentity()
        {
            TaskSnapshot codex = Task("same-session", TaskStatus.Running, 1);
            TaskSnapshot claude = Task("same-session", TaskStatus.Running, 1);
            claude.Provider = "claude";
            True(CodexMonitor.TaskKey(codex) != CodexMonitor.TaskKey(claude));
        }

        private static void TestBottomAnchor()
        {
            int compactY = 1080 - 48 - 250;
            int anchor = compactY + 39;
            int windowY;
            int originY;
            LayoutMath.FitExpandedVertically(anchor, 0, 1080 - 48, 320, out windowY, out originY);
            Equal(712, windowY);
            Equal(109, originY);
            Equal(anchor, windowY + originY);
        }

        private static void TestHorizontalAnchor()
        {
            bool leftEdge = LayoutMath.ChooseBubbleOnRight(
                20, 0, 1920, PetRenderer.FullSize.Width,
                PetRenderer.FullOriginX, PetRenderer.FullOriginXWithRightBubble);
            True(leftEdge);
            int leftWindow = LayoutMath.Clamp(
                20 - PetRenderer.FullSceneOriginX(leftEdge),
                0, 1920 - PetRenderer.FullSize.Width);
            Equal(20, leftWindow + PetRenderer.FullSceneOriginX(leftEdge));

            bool rightEdge = LayoutMath.ChooseBubbleOnRight(
                1720, 0, 1920, PetRenderer.FullSize.Width,
                PetRenderer.FullOriginX, PetRenderer.FullOriginXWithRightBubble);
            True(!rightEdge);
            int rightWindow = LayoutMath.Clamp(
                1720 - PetRenderer.FullSceneOriginX(rightEdge),
                0, 1920 - PetRenderer.FullSize.Width);
            Equal(1720, rightWindow + PetRenderer.FullSceneOriginX(rightEdge));
        }

        private static void TestHookBridge()
        {
            string directory = TemporaryDirectory();
            try
            {
                Dictionary<string, object> payload = new Dictionary<string, object>();
                payload["hook_event_name"] = "UserPromptSubmit";
                payload["session_id"] = "session-a";
                payload["cwd"] = "C:\\work";
                string path = HookBridge.WriteState(payload, directory, "claude");
                Dictionary<string, object> data = JsonUtil.ParseObject(File.ReadAllText(path));
                Equal(TaskStatus.Running, JsonUtil.StringValue(data, "status", ""));
                Equal("session-a", JsonUtil.StringValue(data, "session_id", ""));
                payload["hook_event_name"] = "StopFailure";
                path = HookBridge.WriteState(payload, directory, "claude");
                data = JsonUtil.ParseObject(File.ReadAllText(path));
                Equal(TaskStatus.Error, JsonUtil.StringValue(data, "status", ""));
                payload["hook_event_name"] = "Stop";
                path = HookBridge.WriteState(payload, directory, "claude");
                payload["hook_event_name"] = "SessionEnd";
                HookBridge.WriteState(payload, directory, "claude");
                data = JsonUtil.ParseObject(File.ReadAllText(path));
                Equal(TaskStatus.Completed, JsonUtil.StringValue(data, "status", ""));
            }
            finally { Directory.Delete(directory, true); }
        }

        private static void TestHookIntegration()
        {
            string directory = TemporaryDirectory();
            string previous = Environment.GetEnvironmentVariable("CODEX_HOME");
            try
            {
                Environment.SetEnvironmentVariable("CODEX_HOME", directory);
                Dictionary<string, object> existingHandler = new Dictionary<string, object>();
                existingHandler["type"] = "command";
                existingHandler["command"] = "existing-tool";
                Dictionary<string, object> existingGroup = new Dictionary<string, object>();
                existingGroup["hooks"] = new object[] { existingHandler };
                Dictionary<string, object> hooks = new Dictionary<string, object>();
                hooks["Stop"] = new object[] { existingGroup };
                Dictionary<string, object> root = new Dictionary<string, object>();
                root["hooks"] = hooks;
                File.WriteAllText(Path.Combine(directory, "hooks.json"), JsonUtil.Serialize(root));
                HookIntegration.Install("\"C:\\monitor.exe\" --hook");
                True(HookIntegration.IsInstalled());
                string installed = File.ReadAllText(Path.Combine(directory, "hooks.json"));
                True(installed.Contains("existing-tool"));
                HookIntegration.Uninstall();
                string removed = File.ReadAllText(Path.Combine(directory, "hooks.json"));
                True(removed.Contains("existing-tool"));
                True(!removed.Contains(HookIntegration.Marker));
            }
            finally
            {
                Environment.SetEnvironmentVariable("CODEX_HOME", previous);
                Directory.Delete(directory, true);
            }
        }

        private static void TestSessionLogLifecycle()
        {
            string directory = TemporaryDirectory();
            try
            {
                string path = Path.Combine(directory, "rollout-019f79ea-498f-7442-8fd4-3df934234cf6.jsonl");
                File.WriteAllText(path,
                    "{\"timestamp\":1,\"type\":\"event_msg\",\"payload\":{\"type\":\"task_started\"}}\n");
                SessionLogParser parser = new SessionLogParser(path);
                Equal(TaskStatus.Running, parser.ReadUpdates().Status);
                File.AppendAllText(path,
                    "{\"timestamp\":2,\"type\":\"event_msg\",\"payload\":{\"type\":\"task_complete\"}}\n");
                Equal(TaskStatus.Completed, parser.ReadUpdates().Status);
            }
            finally { Directory.Delete(directory, true); }
        }

        private static void TestAgentAdapters()
        {
            string directory = TemporaryDirectory();
            try
            {
                string claude = Path.Combine(directory, "claude-settings.json");
                File.WriteAllText(claude, "{\"env\":{\"KEEP\":\"1\"}}");
                HookIntegration.InstallClaude(claude, "C:\\CodexDesktopPetHook.exe");
                string claudeText = File.ReadAllText(claude);
                True(claudeText.Contains("Codex Desktop Pet status bridge (claude)"));
                True(claudeText.Contains("KEEP"));
                string plugin = HookIntegration.InstallOpenCode(Path.Combine(directory, "codex-desktop-pet.js"));
                True(File.ReadAllText(plugin).Contains("session.idle"));
                True(File.ReadAllText(plugin).Contains("session.status"));
                True(File.ReadAllText(plugin).Contains("relevant.includes"));
                True(File.ReadAllText(plugin).Contains("--provider opencode"));
            }
            finally { Directory.Delete(directory, true); }
        }

        private static void TestProviderDetection()
        {
            Equal("claude", AgentProcessMonitor.DetectProvider("node.exe", "@anthropic-ai\\claude-code\\cli.js"));
            Equal("opencode", AgentProcessMonitor.DetectProvider("opencode.exe", "opencode"));
            Equal("antigravity", AgentProcessMonitor.DetectProvider("agy.exe", "agy"));
            Equal("qwen", AgentProcessMonitor.DetectProvider("node.exe", "qwen-code\\bin\\cli.js"));
            Equal("goose", AgentProcessMonitor.DetectProvider("goose.exe", "goose"));
            Equal("kimi", AgentProcessMonitor.DetectProvider("node.exe", "kimi-cli\bin\run.js"));
            Equal(null, AgentProcessMonitor.DetectProvider("cmd.exe", "cmd /c claude"));
            Equal(null, AgentProcessMonitor.DetectProvider("python.exe", "python helper.py"));
        }

        private static TaskSnapshot Task(string id, string status, double updated)
        {
            return new TaskSnapshot { SessionId = id, Status = status, UpdatedAt = updated };
        }

        private static string TemporaryDirectory()
        {
            string path = Path.Combine(Path.GetTempPath(), "CodexDesktopPet.Tests." + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(path);
            return path;
        }

        private static void Run(string name, Action test)
        {
            try { test(); passed++; Console.WriteLine("PASS  " + name); }
            catch (Exception error) { failed++; Console.WriteLine("FAIL  {0}: {1}", name, error.Message); }
        }

        private static void Equal(object expected, object actual)
        {
            if (!Object.Equals(expected, actual)) throw new Exception("expected " + expected + ", got " + actual);
        }

        private static void True(bool value)
        {
            if (!value) throw new Exception("expected true");
        }
    }
}
