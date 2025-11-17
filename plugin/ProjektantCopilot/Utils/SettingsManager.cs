using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;

namespace ProjektantCopilot.Utils
{
    /// <summary>
    /// Manages plugin settings persistence.
    /// </summary>
    public static class SettingsManager
    {
        private static readonly string SettingsFolder = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "ProjektantCopilot"
        );

        private static readonly string SettingsFile = Path.Combine(SettingsFolder, "settings.json");
        private static Dictionary<string, object> _settings;

        static SettingsManager()
        {
            LoadSettings();
        }

        private static void LoadSettings()
        {
            try
            {
                if (File.Exists(SettingsFile))
                {
                    string json = File.ReadAllText(SettingsFile);
                    _settings = JsonConvert.DeserializeObject<Dictionary<string, object>>(json);
                }
                else
                {
                    _settings = new Dictionary<string, object>();
                    SetDefaultSettings();
                }
            }
            catch (Exception ex)
            {
                Services.LogService.Error($"Failed to load settings: {ex.Message}", ex);
                _settings = new Dictionary<string, object>();
                SetDefaultSettings();
            }
        }

        private static void SetDefaultSettings()
        {
            _settings["ApiBaseUrl"] = "http://localhost:8000";
            _settings["RealtimeCheckingEnabled"] = true;
            _settings["NotificationsEnabled"] = true;
            SaveSettings();
        }

        private static void SaveSettings()
        {
            try
            {
                Directory.CreateDirectory(SettingsFolder);
                string json = JsonConvert.SerializeObject(_settings, Formatting.Indented);
                File.WriteAllText(SettingsFile, json);
            }
            catch (Exception ex)
            {
                Services.LogService.Error($"Failed to save settings: {ex.Message}", ex);
            }
        }

        public static T GetSetting<T>(string key, T defaultValue)
        {
            if (_settings.ContainsKey(key))
            {
                try
                {
                    return (T)Convert.ChangeType(_settings[key], typeof(T));
                }
                catch
                {
                    return defaultValue;
                }
            }
            return defaultValue;
        }

        public static void SetSetting<T>(string key, T value)
        {
            _settings[key] = value;
            SaveSettings();
        }
    }
}
