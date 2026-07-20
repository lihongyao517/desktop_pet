using System;

namespace CodexDesktopPet
{
    internal static class HookProgram
    {
        public static int Main(string[] args)
        {
            try
            {
                string provider = "codex";
                string inlineJson = null;
                for (int index = 0; index < args.Length - 1; index++)
                {
                    if (args[index] == "--provider") provider = args[index + 1];
                    if (args[index] == "--json") inlineJson = args[index + 1];
                }
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
                if (inlineJson != null)
                {
                    HookBridge.WriteState(JsonUtil.ParseObject(inlineJson), null, provider);
                    return 0;
                }
                return HookBridge.Run(Console.In, provider);
            }
            catch
            {
                return 0;
            }
        }
    }
}
