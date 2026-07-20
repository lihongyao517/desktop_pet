using System;

namespace CodexDesktopPet
{
    internal static class HookProgram
    {
        public static int Main(string[] args)
        {
            try
            {
                foreach (string argument in args)
                {
                    if (argument == "--install-hooks")
                    {
                        Console.WriteLine(HookIntegration.Install(null));
                        return 0;
                    }
                    if (argument == "--uninstall-hooks")
                    {
                        Console.WriteLine(HookIntegration.Uninstall());
                        return 0;
                    }
                }
                return HookBridge.Run(Console.In);
            }
            catch
            {
                return 0;
            }
        }
    }
}
