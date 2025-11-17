using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using ProjektantCopilot.Models;
using ProjektantCopilot.UI;

namespace ProjektantCopilot.Services
{
    /// <summary>
    /// Real-time compliance updater that monitors element changes
    /// </summary>
    public class ComplianceUpdater : IUpdater
    {
        private static UpdaterId _updaterId;
        private static LogService _logger;
        private static ApiClient _apiClient;
        private static ContextExtractor _contextExtractor;
        private static bool _isEnabled = true;

        // Monitored categories
        private static readonly List<BuiltInCategory> MonitoredCategories = new List<BuiltInCategory>
        {
            BuiltInCategory.OST_Walls,
            BuiltInCategory.OST_Doors,
            BuiltInCategory.OST_Windows,
            BuiltInCategory.OST_Floors,
            BuiltInCategory.OST_Ceilings
        };

        public ComplianceUpdater(AddInId addInId, LogService logger, ApiClient apiClient, ContextExtractor contextExtractor)
        {
            _logger = logger;
            _apiClient = apiClient;
            _contextExtractor = contextExtractor;
            _updaterId = new UpdaterId(addInId, new Guid("A1B2C3D4-E5F6-4A5B-8C9D-0E1F2A3B4C5D"));
        }

        public void Execute(UpdaterData data)
        {
            try
            {
                if (!_isEnabled)
                    return;

                Document doc = data.GetDocument();
                _logger.Debug($"ComplianceUpdater triggered in document: {doc.Title}");

                // Process modified elements
                var modifiedIds = data.GetModifiedElementIds();
                if (modifiedIds.Count > 0)
                {
                    _logger.Info($"Processing {modifiedIds.Count} modified elements");
                    ProcessElements(doc, modifiedIds);
                }

                // Process added elements
                var addedIds = data.GetAddedElementIds();
                if (addedIds.Count > 0)
                {
                    _logger.Info($"Processing {addedIds.Count} added elements");
                    ProcessElements(doc, addedIds);
                }
            }
            catch (Exception ex)
            {
                _logger.Error("Error in ComplianceUpdater.Execute", ex);
            }
        }

        private void ProcessElements(Document doc, ICollection<ElementId> elementIds)
        {
            foreach (ElementId id in elementIds)
            {
                try
                {
                    Element elem = doc.GetElement(id);

                    if (elem == null || elem.Category == null)
                        continue;

                    // Check if this is a monitored category
                    var categoryName = elem.Category.Name;
                    if (!IsMonitoredElement(elem))
                        continue;

                    _logger.Debug($"Processing element: {id} ({categoryName})");

                    // Extract context
                    var context = _contextExtractor.Extract(elem, doc);

                    // Check compliance asynchronously
                    Task.Run(async () =>
                    {
                        try
                        {
                            var result = await _apiClient.CheckComplianceAsync(context);

                            // Show notification on UI thread
                            Application.Current?.Dispatcher.Invoke(() =>
                            {
                                ShowComplianceNotification(elem, result);
                            });
                        }
                        catch (Exception ex)
                        {
                            _logger.Error($"Failed to check compliance for element {id}", ex);
                        }
                    });
                }
                catch (Exception ex)
                {
                    _logger.Error($"Error processing element {id}", ex);
                }
            }
        }

        private bool IsMonitoredElement(Element elem)
        {
            if (elem.Category == null)
                return false;

            var categoryId = elem.Category.Id.IntegerValue;
            return MonitoredCategories.Any(cat => (int)cat == categoryId);
        }

        private void ShowComplianceNotification(Element elem, ComplianceResult result)
        {
            try
            {
                var notification = new NotificationPopup(elem, result);
                notification.Show();
            }
            catch (Exception ex)
            {
                _logger.Error("Failed to show notification", ex);
            }
        }

        public string GetAdditionalInformation()
        {
            return "Real-time compliance checker for building elements";
        }

        public ChangePriority GetChangePriority()
        {
            return ChangePriority.FloorsRoofsStructuralWalls;
        }

        public UpdaterId GetUpdaterId()
        {
            return _updaterId;
        }

        public string GetUpdaterName()
        {
            return "ProjektantCopilot Compliance Updater";
        }

        /// <summary>
        /// Register the updater with Revit
        /// </summary>
        public static void Register(Document doc, AddInId addInId, LogService logger, ApiClient apiClient, ContextExtractor contextExtractor)
        {
            try
            {
                var updater = new ComplianceUpdater(addInId, logger, apiClient, contextExtractor);

                UpdaterRegistry.RegisterUpdater(updater, doc);

                // Add triggers for each monitored category
                foreach (var category in MonitoredCategories)
                {
                    var filter = new ElementCategoryFilter(category);

                    // Trigger on geometry changes
                    UpdaterRegistry.AddTrigger(_updaterId, filter, Element.GetChangeTypeGeometry());

                    // Trigger on parameter changes
                    UpdaterRegistry.AddTrigger(_updaterId, filter, Element.GetChangeTypeParameter());

                    // Trigger on element addition
                    UpdaterRegistry.AddTrigger(_updaterId, filter, Element.GetChangeTypeElementAddition());
                }

                logger.Info("ComplianceUpdater registered successfully");
            }
            catch (Exception ex)
            {
                logger.Error("Failed to register ComplianceUpdater", ex);
                throw;
            }
        }

        /// <summary>
        /// Unregister the updater
        /// </summary>
        public static void Unregister()
        {
            try
            {
                if (UpdaterRegistry.IsUpdaterRegistered(_updaterId))
                {
                    UpdaterRegistry.UnregisterUpdater(_updaterId);
                    _logger?.Info("ComplianceUpdater unregistered successfully");
                }
            }
            catch (Exception ex)
            {
                _logger?.Error("Failed to unregister ComplianceUpdater", ex);
            }
        }

        /// <summary>
        /// Enable or disable the updater
        /// </summary>
        public static void SetEnabled(bool enabled)
        {
            _isEnabled = enabled;
            _logger?.Info($"ComplianceUpdater {(enabled ? "enabled" : "disabled")}");
        }

        /// <summary>
        /// Check if updater is enabled
        /// </summary>
        public static bool IsEnabled()
        {
            return _isEnabled;
        }
    }
}
