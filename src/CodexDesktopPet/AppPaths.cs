using System;
using System.IO;

namespace CodexDesktopPet
{
    internal static class AppPaths
    {
        public static string DataDirectory
        {
            get
            {
                string overridden = Environment.GetEnvironmentVariable("CODEX_DESKTOP_PET_HOME");
                if (!String.IsNullOrWhiteSpace(overridden))
                    return Path.GetFullPath(Environment.ExpandEnvironmentVariables(overridden));
                return Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "CodexDesktopPet");
            }
        }

        public static string CodexHome
        {
            get
            {
                string overridden = Environment.GetEnvironmentVariable("CODEX_HOME");
                if (!String.IsNullOrWhiteSpace(overridden))
                    return Path.GetFullPath(Environment.ExpandEnvironmentVariables(overridden));
                return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".codex");
            }
        }

        public static string SettingsFile { get { return Path.Combine(DataDirectory, "settings.json"); } }
        public static string TaskStateDirectory { get { return Path.Combine(DataDirectory, "tasks"); } }
        public static string HooksFile { get { return Path.Combine(CodexHome, "hooks.json"); } }

        public static string StartupFile
        {
            get
            {
                return Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.Startup),
                    "CodexDesktopPet.vbs");
            }
        }

        public static string ExecutableDirectory
        {
            get { return AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar); }
        }

        public static string IconFile
        {
            get { return Path.Combine(ExecutableDirectory, "CodexDesktopPet.ico"); }
        }
    }
}
