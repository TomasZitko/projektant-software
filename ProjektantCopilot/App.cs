using System;
using System.Configuration;
using System.IO;
using System.Reflection;
using System.Windows.Media.Imaging;
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Events;
using Autodesk.Revit.UI;
using ProjektantCopilot.Commands;
using ProjektantCopilot.Services;
using ProjektantCopilot.UI;

namespace ProjektantCopilot
{
    public class App : IExternalApplication
    {
        private static UIControlledApplication _application;
        private static CompliancePanel _compliancePanel;
        private static DockablePane _dockablePane;

        // Services
        public static LogService Logger { get; private set; }
        public static ApiClient ApiClient { get; private set; }
        public static ContextExtractor ContextExtractor { get; private set; }

        public Result OnStartup(UIControlledApplication application)
        {
            try
            {
                _application = application;

                // Initialize logging
                LogService.Initialize();
                Logger = new LogService();
                Logger.Info("ProjektantCopilot plugin starting...");

                // Initialize services
                InitializeServices();

                // Create ribbon panel
                CreateRibbonPanel(application);

                // Register dockable panel
                RegisterDockablePanel(application);

                // Register document events
                application.ControlledApplication.DocumentOpened += OnDocumentOpened;
                application.ControlledApplication.DocumentClosing += OnDocumentClosing;

                Logger.Info("ProjektantCopilot plugin started successfully");

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                Logger?.Fatal("Failed to start ProjektantCopilot plugin", ex);
                TaskDialog.Show("Error", $"Failed to start ProjektantCopilot: {ex.Message}");
                return Result.Failed;
            }
        }

        public Result OnShutdown(UIControlledApplication application)
        {
            try
            {
                Logger.Info("ProjektantCopilot plugin shutting down...");

                // Unregister events
                application.ControlledApplication.DocumentOpened -= OnDocumentOpened;
                application.ControlledApplication.DocumentClosing -= OnDocumentClosing;

                // Cleanup
                LogService.Shutdown();

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                Logger?.Fatal("Error during plugin shutdown", ex);
                return Result.Failed;
            }
        }

        private void InitializeServices()
        {
            try
            {
                // Get configuration
                var backendUrl = ConfigurationManager.AppSettings["BackendUrl"] ?? "http://localhost:8000";
                var apiKey = ConfigurationManager.AppSettings["ApiKey"] ?? "";

                Logger.Info($"Initializing services with backend URL: {backendUrl}");

                // Initialize services
                ApiClient = new ApiClient(backendUrl, apiKey, Logger);
                ContextExtractor = new ContextExtractor(Logger);

                Logger.Info("Services initialized successfully");
            }
            catch (Exception ex)
            {
                Logger.Error("Failed to initialize services", ex);
                throw;
            }
        }

        private void CreateRibbonPanel(UIControlledApplication application)
        {
            try
            {
                // Create ribbon panel
                var ribbonPanel = application.CreateRibbonPanel("ProjektantCopilot");

                // Get assembly path
                var assemblyPath = Assembly.GetExecutingAssembly().Location;

                // Add compliance check button
                var checkButton = new PushButtonData(
                    "ComplianceCheck",
                    "Check\nCompliance",
                    assemblyPath,
                    typeof(ComplianceCheckCommand).FullName
                );

                checkButton.ToolTip = "Check selected elements for building code compliance";
                checkButton.LongDescription = "Analyzes the selected elements against building regulations and displays compliance status.";

                var checkPushButton = ribbonPanel.AddItem(checkButton) as PushButton;

                // Add panel button
                var panelButton = new PushButtonData(
                    "CompliancePanel",
                    "Show\nPanel",
                    assemblyPath,
                    typeof(ShowPanelCommand).FullName
                );

                panelButton.ToolTip = "Show compliance monitoring panel";
                panelButton.LongDescription = "Displays the dockable panel for real-time compliance monitoring.";

                ribbonPanel.AddItem(panelButton);

                // Add separator
                ribbonPanel.AddSeparator();

                // Add settings button
                var settingsButton = new PushButtonData(
                    "ComplianceSettings",
                    "Settings",
                    assemblyPath,
                    typeof(SettingsCommand).FullName
                );

                settingsButton.ToolTip = "Configure plugin settings";

                ribbonPanel.AddItem(settingsButton);

                Logger.Info("Ribbon panel created successfully");
            }
            catch (Exception ex)
            {
                Logger.Error("Failed to create ribbon panel", ex);
                throw;
            }
        }

        private void RegisterDockablePanel(UIControlledApplication application)
        {
            try
            {
                // Create compliance panel
                _compliancePanel = new CompliancePanel();

                // Register dockable pane
                var panelId = new DockablePaneId(new Guid("A1B2C3D4-E5F6-4A5B-8C9D-0E1F2A3B4C5E"));

                application.RegisterDockablePane(
                    panelId,
                    "Compliance Monitor",
                    _compliancePanel
                );

                Logger.Info("Dockable panel registered successfully");
            }
            catch (Exception ex)
            {
                Logger.Error("Failed to register dockable panel", ex);
                throw;
            }
        }

        private void OnDocumentOpened(object sender, DocumentOpenedEventArgs e)
        {
            try
            {
                var doc = e.Document;
                Logger.Info($"Document opened: {doc.Title}");

                // Check if monitoring is enabled
                var enableMonitoring = bool.TryParse(
                    ConfigurationManager.AppSettings["EnableMonitoring"],
                    out var result) ? result : true;

                if (enableMonitoring)
                {
                    // Register compliance updater for this document
                    ComplianceUpdater.Register(doc, _application.ActiveAddInId, Logger, ApiClient, ContextExtractor);
                    Logger.Info("Compliance updater registered for document");
                }
            }
            catch (Exception ex)
            {
                Logger.Error("Error in DocumentOpened event", ex);
            }
        }

        private void OnDocumentClosing(object sender, DocumentClosingEventArgs e)
        {
            try
            {
                var doc = e.Document;
                Logger.Info($"Document closing: {doc.Title}");

                // Unregister compliance updater
                ComplianceUpdater.Unregister();
            }
            catch (Exception ex)
            {
                Logger.Error("Error in DocumentClosing event", ex);
            }
        }

        /// <summary>
        /// Show the compliance panel
        /// </summary>
        public static void ShowCompliancePanel()
        {
            try
            {
                var panelId = new DockablePaneId(new Guid("A1B2C3D4-E5F6-4A5B-8C9D-0E1F2A3B4C5E"));
                var pane = _application.GetDockablePane(panelId);

                if (pane != null && !pane.IsShown())
                {
                    pane.Show();
                }
            }
            catch (Exception ex)
            {
                Logger?.Error("Failed to show compliance panel", ex);
            }
        }

        /// <summary>
        /// Run compliance check on selected elements
        /// </summary>
        public static void RunComplianceCheck()
        {
            try
            {
                var uiDoc = _application.ActiveUIDocument;
                if (uiDoc != null)
                {
                    var command = new ComplianceCheckCommand();
                    // Note: This requires being called from within a command context
                    Logger.Info("Compliance check requested");
                }
            }
            catch (Exception ex)
            {
                Logger?.Error("Failed to run compliance check", ex);
            }
        }

        /// <summary>
        /// Run compliance check on all monitored elements
        /// </summary>
        public static void RunComplianceCheckAll()
        {
            Logger.Info("Check all compliance requested");
            // Implementation similar to RunComplianceCheck but for all elements
        }

        /// <summary>
        /// Apply settings changes
        /// </summary>
        public static void ApplySettings()
        {
            try
            {
                Logger.Info("Applying settings...");

                // Reload configuration
                var backendUrl = ConfigurationManager.AppSettings["BackendUrl"] ?? "http://localhost:8000";
                var apiKey = ConfigurationManager.AppSettings["ApiKey"] ?? "";

                // Recreate API client with new settings
                ApiClient = new ApiClient(backendUrl, apiKey, Logger);

                // Update monitoring state
                var enableMonitoring = bool.TryParse(
                    ConfigurationManager.AppSettings["EnableMonitoring"],
                    out var result) ? result : true;

                ComplianceUpdater.SetEnabled(enableMonitoring);

                Logger.Info("Settings applied successfully");
            }
            catch (Exception ex)
            {
                Logger.Error("Failed to apply settings", ex);
            }
        }

        /// <summary>
        /// Get the compliance panel instance
        /// </summary>
        public static CompliancePanel GetCompliancePanel()
        {
            return _compliancePanel;
        }
    }

    /// <summary>
    /// Command to show the compliance panel
    /// </summary>
    [Autodesk.Revit.Attributes.Transaction(Autodesk.Revit.Attributes.TransactionMode.Manual)]
    public class ShowPanelCommand : IExternalCommand
    {
        public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
        {
            App.ShowCompliancePanel();
            return Result.Succeeded;
        }
    }

    /// <summary>
    /// Command to show settings dialog
    /// </summary>
    [Autodesk.Revit.Attributes.Transaction(Autodesk.Revit.Attributes.TransactionMode.Manual)]
    public class SettingsCommand : IExternalCommand
    {
        public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
        {
            var settingsDialog = new SettingsDialog();
            settingsDialog.ShowDialog();
            return Result.Succeeded;
        }
    }
}
