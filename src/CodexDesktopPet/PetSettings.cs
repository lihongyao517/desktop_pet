using System;
using System.Collections.Generic;
using System.IO;

namespace CodexDesktopPet
{
    internal sealed class PetSettings
    {
        public bool SoundEnabled = true;
        public bool AlwaysOnTop = true;
        public bool CompactMode;
        public int FullSceneOriginY = 55;
        public int ApprovalRepeatSeconds = 45;
        public int? WindowX;
        public int? WindowY;

        public static PetSettings Load()
        {
            PetSettings settings = new PetSettings();
            try
            {
                if (!File.Exists(AppPaths.SettingsFile))
                    return settings;
                Dictionary<string, object> data = JsonUtil.ParseObject(File.ReadAllText(AppPaths.SettingsFile));
                settings.SoundEnabled = JsonUtil.BoolValue(data, "sound_enabled", settings.SoundEnabled);
                settings.AlwaysOnTop = JsonUtil.BoolValue(data, "always_on_top", settings.AlwaysOnTop);
                settings.CompactMode = JsonUtil.BoolValue(data, "compact_mode", settings.CompactMode);
                settings.FullSceneOriginY = Math.Max(39, Math.Min(110, JsonUtil.IntValue(data, "full_scene_origin_y", 55)));
                settings.ApprovalRepeatSeconds = JsonUtil.IntValue(data, "approval_repeat_seconds", 45);
                if (JsonUtil.Get(data, "window_x") != null)
                    settings.WindowX = JsonUtil.IntValue(data, "window_x", 0);
                if (JsonUtil.Get(data, "window_y") != null)
                    settings.WindowY = JsonUtil.IntValue(data, "window_y", 0);
            }
            catch { }
            return settings;
        }

        public void Save()
        {
            Dictionary<string, object> data = new Dictionary<string, object>();
            data["sound_enabled"] = SoundEnabled;
            data["always_on_top"] = AlwaysOnTop;
            data["compact_mode"] = CompactMode;
            data["full_scene_origin_y"] = FullSceneOriginY;
            data["approval_repeat_seconds"] = ApprovalRepeatSeconds;
            data["window_x"] = WindowX;
            data["window_y"] = WindowY;
            JsonUtil.WriteAtomic(AppPaths.SettingsFile, data);
        }
    }
}
