using System;
using Autodesk.Revit.ApplicationServices;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using ProjektantCopilot.Commands;
using ProjektantCopilot.Services;

namespace ProjektantCopilot
{
    /// <summary>
    /// Main application class implementing IExternalApplication.
    /// Handles plugin startup, shutdown, and ribbon UI creation.
    /// </summary>
    [Transaction(TransactionMode.Manual)]
    [Regeneration(RegenerationOption.Manual)]
    public class App : IExternalApplication
    {
        private static AddInId _appId;
        private ComplianceUpdater _updater;

        public Result OnStartup(UIControlledApplication application)
        {
            try
            {
                // Initialize logging
                LogService.Initialize();
                LogService.Info("Projektant Copilot starting up...");

                // Store AddInId for later use
                _appId = application.ActiveAddInId;

                // Create ribbon panel
                CreateRibbonPanel(application);

                // Register updater for real-time monitoring
                _updater = new ComplianceUpdater(_appId);
                UpdaterRegistry.RegisterUpdater(_updater, true);

                // Register triggers (walls, doors, etc.)
                _updater.RegisterTriggers();

                LogService.Info("Projektant Copilot initialized successfully");
                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                LogService.Error($"Failed to initialize Projektant Copilot: {ex.Message}", ex);
                return Result.Failed;
            }
        }

        public Result OnShutdown(UIControlledApplication application)
        {
            try
            {
                // Unregister updater
                if (_updater != null)
                {
                    UpdaterRegistry.UnregisterUpdater(_updater.GetUpdaterId());
                }

                LogService.Info("Projektant Copilot shut down successfully");
                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                LogService.Error($"Error during shutdown: {ex.Message}", ex);
                return Result.Failed;
            }
        }

        private void CreateRibbonPanel(UIControlledApplication application)
        {
            // Create ribbon panel
            string tabName = "Projektant";
            try
            {
                application.CreateRibbonTab(tabName);
            }
            catch
            {
                // Tab already exists
            }

            RibbonPanel panel = application.CreateRibbonPanel(tabName, "Compliance");

            // Add Compliance Check button
            string assemblyPath = typeof(App).Assembly.Location;

            PushButtonData checkButtonData = new PushButtonData(
                "ComplianceCheck",
                "Check\nCompliance",
                assemblyPath,
                typeof(ComplianceCheckCommand).FullName
            );

            checkButtonData.ToolTip = "Check building code compliance for selected elements";
            checkButtonData.LongDescription = "Analyzes selected elements against Czech building codes (ČSN) and identifies violations.";

            PushButton checkButton = panel.AddItem(checkButtonData) as PushButton;

            // TODO: Set button icon
            // checkButton.LargeImage = LoadImage("path/to/icon32.png");

            LogService.Info("Ribbon panel created successfully");
        }

        public static AddInId GetAddInId()
        {
            return _appId;
        }
    }
}
