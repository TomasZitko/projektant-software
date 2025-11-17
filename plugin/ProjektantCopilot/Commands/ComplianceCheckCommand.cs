using System;
using System.Linq;
using System.Windows.Forms;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using ProjektantCopilot.Services;

namespace ProjektantCopilot.Commands
{
    /// <summary>
    /// External command to manually check compliance of selected elements.
    /// </summary>
    [Transaction(TransactionMode.Manual)]
    [Regeneration(RegenerationOption.Manual)]
    public class ComplianceCheckCommand : IExternalCommand
    {
        public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
        {
            UIApplication uiApp = commandData.Application;
            UIDocument uiDoc = uiApp.ActiveUIDocument;
            Document doc = uiDoc.Document;

            try
            {
                // Get selected elements
                var selection = uiDoc.Selection.GetElementIds();

                if (!selection.Any())
                {
                    TaskDialog.Show("Projektant Copilot", "Please select at least one element to check.");
                    return Result.Cancelled;
                }

                LogService.Info($"Checking compliance for {selection.Count} selected element(s)");

                int checkedCount = 0;
                int violationCount = 0;

                foreach (ElementId elemId in selection)
                {
                    Element elem = doc.GetElement(elemId);

                    if (elem == null)
                        continue;

                    // Extract context
                    var contextExtractor = new ContextExtractor();
                    var context = contextExtractor.ExtractContext(elem, doc);

                    if (context == null)
                    {
                        LogService.Warn($"Could not extract context for element {elemId}");
                        continue;
                    }

                    // Check compliance via API
                    var apiClient = new ApiClient();
                    var result = apiClient.CheckElementCompliance(context);

                    checkedCount++;

                    if (result != null && !result.Compliant)
                    {
                        violationCount += result.Violations.Count;

                        // Display violations
                        foreach (var violation in result.Violations)
                        {
                            LogService.Warn($"Violation: {violation.Message}");
                        }
                    }
                }

                // Show summary
                string summaryMessage = $"Checked {checkedCount} element(s).\n";
                if (violationCount > 0)
                {
                    summaryMessage += $"Found {violationCount} violation(s). See log for details.";
                }
                else
                {
                    summaryMessage += "All elements are compliant!";
                }

                TaskDialog.Show("Compliance Check Complete", summaryMessage);

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                LogService.Error($"Error during compliance check: {ex.Message}", ex);
                message = ex.Message;
                return Result.Failed;
            }
        }
    }
}
