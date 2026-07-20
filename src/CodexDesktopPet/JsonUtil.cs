using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;

namespace CodexDesktopPet
{
    internal static class JsonUtil
    {
        private static readonly JavaScriptSerializer Serializer = new JavaScriptSerializer
        {
            MaxJsonLength = Int32.MaxValue,
            RecursionLimit = 100
        };

        public static Dictionary<string, object> ParseObject(string json)
        {
            object parsed = Serializer.DeserializeObject(json.TrimStart('\uFEFF'));
            return parsed as Dictionary<string, object>;
        }

        public static string Serialize(object value)
        {
            return Serializer.Serialize(value);
        }

        public static Dictionary<string, object> Dictionary(object value)
        {
            return value as Dictionary<string, object>;
        }

        public static object[] Array(object value)
        {
            object[] array = value as object[];
            if (array != null)
                return array;
            ArrayList list = value as ArrayList;
            return list == null ? new object[0] : list.ToArray();
        }

        public static object Get(Dictionary<string, object> data, string key)
        {
            object value;
            return data != null && data.TryGetValue(key, out value) ? value : null;
        }

        public static string StringValue(Dictionary<string, object> data, string key, string fallback)
        {
            object value = Get(data, key);
            return value == null ? fallback : Convert.ToString(value, CultureInfo.InvariantCulture);
        }

        public static bool BoolValue(Dictionary<string, object> data, string key, bool fallback)
        {
            object value = Get(data, key);
            if (value == null)
                return fallback;
            bool result;
            return Boolean.TryParse(Convert.ToString(value, CultureInfo.InvariantCulture), out result)
                ? result
                : fallback;
        }

        public static int IntValue(Dictionary<string, object> data, string key, int fallback)
        {
            object value = Get(data, key);
            if (value == null)
                return fallback;
            try { return Convert.ToInt32(value, CultureInfo.InvariantCulture); }
            catch { return fallback; }
        }

        public static double DoubleValue(Dictionary<string, object> data, string key, double fallback)
        {
            object value = Get(data, key);
            if (value == null)
                return fallback;
            try { return Convert.ToDouble(value, CultureInfo.InvariantCulture); }
            catch { return fallback; }
        }

        public static void WriteAtomic(string path, object value)
        {
            string directory = Path.GetDirectoryName(path);
            if (!Directory.Exists(directory))
                Directory.CreateDirectory(directory);
            string temporary = Path.Combine(
                directory,
                "." + Path.GetFileName(path) + "." + System.Diagnostics.Process.GetCurrentProcess().Id + ".tmp");
            File.WriteAllText(temporary, Serialize(value), new UTF8Encoding(false));
            if (File.Exists(path))
                File.Replace(temporary, path, null);
            else
                File.Move(temporary, path);
        }
    }
}
