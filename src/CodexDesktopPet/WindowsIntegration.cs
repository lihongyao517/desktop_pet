using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

namespace CodexDesktopPet
{
    internal static class WindowsIntegration
    {
        private const uint ProcessQueryLimitedInformation = 0x1000;
        private const int SwRestore = 9;

        [DllImport("user32.dll")]
        private static extern bool EnumWindows(EnumWindowsProc callback, IntPtr parameter);

        [DllImport("user32.dll")]
        private static extern bool IsWindowVisible(IntPtr window);

        [DllImport("user32.dll")]
        private static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);

        [DllImport("user32.dll")]
        private static extern bool ShowWindow(IntPtr window, int command);

        [DllImport("user32.dll")]
        private static extern bool SetForegroundWindow(IntPtr window);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr OpenProcess(uint access, bool inherit, uint processId);

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern bool QueryFullProcessImageName(IntPtr process, int flags, StringBuilder path, ref int size);

        [DllImport("kernel32.dll")]
        private static extern bool CloseHandle(IntPtr handle);

        [DllImport("kernel32.dll")]
        internal static extern bool Beep(uint frequency, uint duration);

        [DllImport("user32.dll")]
        internal static extern bool SetProcessDPIAware();

        private delegate bool EnumWindowsProc(IntPtr window, IntPtr parameter);

        public static bool OpenCodex()
        {
            IntPtr found = IntPtr.Zero;
            EnumWindows(delegate(IntPtr window, IntPtr parameter)
            {
                if (!IsWindowVisible(window))
                    return true;
                uint processId;
                GetWindowThreadProcessId(window, out processId);
                IntPtr process = OpenProcess(ProcessQueryLimitedInformation, false, processId);
                if (process == IntPtr.Zero)
                    return true;
                try
                {
                    int size = 32768;
                    StringBuilder path = new StringBuilder(size);
                    if (QueryFullProcessImageName(process, 0, path, ref size))
                    {
                        string name = Path.GetFileName(path.ToString()).ToLowerInvariant();
                        if (name == "chatgpt.exe" || name == "codex.exe")
                        {
                            found = window;
                            return false;
                        }
                    }
                }
                finally { CloseHandle(process); }
                return true;
            }, IntPtr.Zero);

            if (found != IntPtr.Zero)
            {
                ShowWindow(found, SwRestore);
                SetForegroundWindow(found);
                return true;
            }
            return StartUri("codex://");
        }

        public static bool OpenCodexThread(string sessionId)
        {
            if (String.IsNullOrWhiteSpace(sessionId))
                return false;
            if (StartUri("codex://threads/" + Uri.EscapeDataString(sessionId)))
                return true;
            return OpenCodex();
        }

        private static bool StartUri(string uri)
        {
            try
            {
                Process.Start(new ProcessStartInfo(uri) { UseShellExecute = true });
                return true;
            }
            catch { return false; }
        }
    }
}
