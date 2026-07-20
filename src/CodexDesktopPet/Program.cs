using System;
using System.Threading;
using System.Windows.Forms;

namespace CodexDesktopPet
{
    internal static class Program
    {
        private const string MutexName = "Local\\CodexDesktopPet.SingleInstance";
        private const string ShowEventName = "Local\\CodexDesktopPet.ShowWindow";

        [STAThread]
        public static int Main()
        {
            bool created;
            using (Mutex mutex = new Mutex(true, MutexName, out created))
            {
                if (!created)
                {
                    try { EventWaitHandle.OpenExisting(ShowEventName).Set(); }
                    catch { }
                    return 0;
                }
                using (EventWaitHandle showEvent = new EventWaitHandle(false, EventResetMode.AutoReset, ShowEventName))
                {
                    Application.EnableVisualStyles();
                    Application.SetCompatibleTextRenderingDefault(false);
                    Application.Run(new DesktopPetForm(showEvent));
                }
            }
            return 0;
        }
    }
}
