using System;
using System.IO;
using System.Text;

namespace CodexDesktopPet
{
    internal static class StartupIntegration
    {
        public static bool IsEnabled
        {
            get { return File.Exists(AppPaths.StartupFile); }
        }

        public static void SetEnabled(bool enabled)
        {
            string legacy = Path.Combine(Path.GetDirectoryName(AppPaths.StartupFile), "CodexTrafficLight.vbs");
            if (!enabled)
            {
                if (File.Exists(AppPaths.StartupFile)) File.Delete(AppPaths.StartupFile);
                if (File.Exists(legacy)) File.Delete(legacy);
                return;
            }
            if (File.Exists(legacy)) File.Delete(legacy);
            Directory.CreateDirectory(Path.GetDirectoryName(AppPaths.StartupFile));
            string executable = System.Diagnostics.Process.GetCurrentProcess().MainModule.FileName.Replace("\"", "\"\"");
            string content = "Set shell = CreateObject(\"WScript.Shell\")\r\n" +
                "shell.Run \"\"\"" + executable + "\"\"\", 0, False\r\n";
            File.WriteAllText(AppPaths.StartupFile, content, new UTF8Encoding(true));
        }
    }
}
