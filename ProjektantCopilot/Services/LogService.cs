using System;
using System.IO;
using Serilog;
using Serilog.Core;

namespace ProjektantCopilot.Services
{
    /// <summary>
    /// Logging service using Serilog
    /// </summary>
    public class LogService
    {
        private static Logger _logger;
        private static readonly object _lock = new object();

        public static void Initialize()
        {
            if (_logger != null)
                return;

            lock (_lock)
            {
                if (_logger != null)
                    return;

                var logPath = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                    "ProjektantCopilot",
                    "Logs",
                    "plugin-.txt"
                );

                _logger = new LoggerConfiguration()
                    .MinimumLevel.Debug()
                    .WriteTo.File(
                        logPath,
                        rollingInterval: RollingInterval.Day,
                        outputTemplate: "{Timestamp:yyyy-MM-dd HH:mm:ss.fff} [{Level:u3}] {Message:lj}{NewLine}{Exception}"
                    )
                    .WriteTo.Console(
                        outputTemplate: "{Timestamp:HH:mm:ss} [{Level:u3}] {Message:lj}{NewLine}{Exception}"
                    )
                    .CreateLogger();

                _logger.Information("ProjektantCopilot logging initialized");
            }
        }

        public void Debug(string message)
        {
            _logger?.Debug(message);
        }

        public void Info(string message)
        {
            _logger?.Information(message);
        }

        public void Warning(string message)
        {
            _logger?.Warning(message);
        }

        public void Error(string message)
        {
            _logger?.Error(message);
        }

        public void Error(string message, Exception ex)
        {
            _logger?.Error(ex, message);
        }

        public void Fatal(string message)
        {
            _logger?.Fatal(message);
        }

        public void Fatal(string message, Exception ex)
        {
            _logger?.Fatal(ex, message);
        }

        public static void Shutdown()
        {
            _logger?.Dispose();
            _logger = null;
        }
    }
}
