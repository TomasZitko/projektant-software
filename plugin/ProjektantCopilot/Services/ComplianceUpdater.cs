using System;
using System.Collections.Generic;
using Autodesk.Revit.DB;
using ProjektantCopilot.Utils;

namespace ProjektantCopilot.Services
{
    /// <summary>
    /// IUpdater implementation for real-time compliance monitoring.
    /// Automatically checks elements when they are modified.
    /// </summary>
    public class ComplianceUpdater : IUpdater
    {
        private static AddInId _appId;
        private static UpdaterId _updaterId;
        private ApiClient _apiClient;
        private ContextExtractor _contextExtractor;

        public ComplianceUpdater(AddInId appId)
        {
            _appId = appId;
            _updaterId = new UpdaterId(_appId, new Guid("E7F9D2C1-4A5B-6C8E-9D0F-1A2B3C4D5E6F"));
            _apiClient = new ApiClient();
            _contextExtractor = new ContextExtractor();
        }

        public void Execute(UpdaterData data)
        {
            try
            {
                Document doc = data.GetDocument();

                // Check if real-time checking is enabled
                bool realtimeEnabled = SettingsManager.GetSetting("RealtimeCheckingEnabled", true);
                if (!realtimeEnabled)
                    return;

                // Process modified elements
                foreach (ElementId id in data.GetModifiedElementIds())
                {
                    Element elem = doc.GetElement(id);
                    if (IsRelevantElement(elem))
                    {
                        CheckElementAsync(elem, doc);
                    }
                }
            }
            catch (Exception ex)
            {
                LogService.Error($"Error in ComplianceUpdater.Execute: {ex.Message}", ex);
            }
        }

        private void CheckElementAsync(Element element, Document doc)
        {
            try
            {
                var context = _contextExtractor.ExtractContext(element, doc);
                if (context == null)
                    return;

                var result = _apiClient.CheckElementCompliance(context);

                if (result != null && !result.Compliant)
                {
                    // TODO: Show non-intrusive notification
                    LogService.Warn($"Compliance violation detected in {element.Category?.Name} (ID: {element.Id})");

                    foreach (var violation in result.Violations)
                    {
                        LogService.Warn($"  - {violation.Message}");
                    }
                }
            }
            catch (Exception ex)
            {
                LogService.Debug($"Failed to check element {element.Id}: {ex.Message}");
            }
        }

        private bool IsRelevantElement(Element elem)
        {
            if (elem == null)
                return false;

            // Check if element category is relevant for compliance checking
            var category = elem.Category;
            if (category == null)
                return false;

            BuiltInCategory bic = (BuiltInCategory)category.Id.IntegerValue;

            return bic == BuiltInCategory.OST_Walls ||
                   bic == BuiltInCategory.OST_Doors ||
                   bic == BuiltInCategory.OST_Windows ||
                   bic == BuiltInCategory.OST_Floors ||
                   bic == BuiltInCategory.OST_Rooms ||
                   bic == BuiltInCategory.OST_Stairs;
        }

        public void RegisterTriggers()
        {
            // Register for wall modifications
            UpdaterRegistry.AddTrigger(
                _updaterId,
                new ElementCategoryFilter(BuiltInCategory.OST_Walls),
                Element.GetChangeTypeAny()
            );

            // Register for door modifications
            UpdaterRegistry.AddTrigger(
                _updaterId,
                new ElementCategoryFilter(BuiltInCategory.OST_Doors),
                Element.GetChangeTypeAny()
            );

            LogService.Info("ComplianceUpdater triggers registered");
        }

        public string GetAdditionalInformation()
        {
            return "Checks building code compliance in real-time when elements are modified.";
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
            return "ProjektantCopilotComplianceUpdater";
        }
    }
}
