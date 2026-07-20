using System;
using System.Media;
using System.Threading;

namespace CodexDesktopPet
{
    internal static class AudioAlerts
    {
        public static void Play(string kind)
        {
            ThreadPool.QueueUserWorkItem(delegate
            {
                uint[,] pattern = Pattern(kind);
                if (pattern == null)
                    return;
                try
                {
                    for (int index = 0; index < pattern.GetLength(0); index++)
                        WindowsIntegration.Beep(pattern[index, 0], pattern[index, 1]);
                }
                catch { SystemSounds.Exclamation.Play(); }
            });
        }

        private static uint[,] Pattern(string kind)
        {
            if (kind == "approval") return new uint[,] { { 880, 160 }, { 659, 130 }, { 880, 240 } };
            if (kind == "completed") return new uint[,] { { 523, 100 }, { 659, 110 }, { 784, 190 } };
            if (kind == "error") return new uint[,] { { 784, 140 }, { 587, 150 }, { 392, 260 } };
            if (kind == "test") return new uint[,] { { 523, 90 }, { 659, 90 }, { 784, 120 } };
            return null;
        }
    }
}
