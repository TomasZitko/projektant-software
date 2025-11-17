using System;
using System.IO;
using Serilog;

namespace ProjektantCopilot.Services
{
    /// <summary>
    /// Logging service using Serilog.
    /// </summary>
    public static class LogService
    {
        private static ILogger _logger;

        public static void Initialize()
        {
            string logFolder = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "ProjektantCopilot",
                "Logs"
            );

            Directory.CreateDirectory(logFolder);

            string logFile = Path.Combine(logFolder, "log-.txt");

            _logger = new LoggerConfiguration()
                .MinimumLevel.Debug()
                .WriteTo.File(
                    logFile,
                    rollingInterval: RollingInterval.Day,
                    retainedFileCountLimit: 7,
                    outputTemplate: "{Timestamp:yyyy-MM-dd HH:mm:ss.fff zzz} [{Level:u3}] {Message:lj}{NewLine}{Exception}"
                )
                .CreateLogger();

            Info("Logging initialized");
        }

        public static void Info(string message)
        {
            _logger?.Information(message);
        }

        public static void Warn(string message)
        {
            _logger?.Warning(message);
        }

        public static void Error(string message, Exception ex = null)
        {
            if (ex != null)
            {
                _logger?.Error(ex, message);
            }
            else
            {
                _logger?.Error(message);
            }
        }

        public static void Debug(string message)
        {
            _logger?.Debug(message);
        }
    }
}
