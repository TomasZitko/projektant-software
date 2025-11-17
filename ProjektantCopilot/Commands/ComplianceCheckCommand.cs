using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using Autodesk.Revit.UI.Selection;
using ProjektantCopilot.Models;
using ProjektantCopilot.Services;
using ProjektantCopilot.UI;

namespace ProjektantCopilot.Commands
{
    [Transaction(TransactionMode.Manual)]
    [Regeneration(RegenerationOption.Manual)]
    public class ComplianceCheckCommand : IExternalCommand
    {
        public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
        {
            try
            {
                UIApplication uiApp = commandData.Application;
                UIDocument uiDoc = uiApp.ActiveUIDocument;
                Document doc = uiDoc.Document;

                var logger = App.Logger;
                var apiClient = App.ApiClient;
                var contextExtractor = App.ContextExtractor;

                logger.Info("ComplianceCheckCommand executed");

                // Get selected elements
                var selection = uiDoc.Selection;
                var selectedIds = selection.GetElementIds();

                if (selectedIds.Count == 0)
                {
                    // No selection - ask user to select or check all
                    TaskDialog dialog = new TaskDialog("Compliance Check");
                    dialog.MainInstruction = "No elements selected";
                    dialog.MainContent = "Would you like to select elements or check all monitored elements in the project?";
                    dialog.AddCommandLink(TaskDialogCommandLinkId.CommandLink1, "Select Elements", "Pick specific elements to check");
                    dialog.AddCommandLink(TaskDialogCommandLinkId.CommandLink2, "Check All", "Check all walls, doors, windows, floors, and ceilings");
                    dialog.CommonButtons = TaskDialogCommonButtons.Cancel;

                    var result = dialog.Show();

                    if (result == TaskDialogResult.CommandLink1)
                    {
                        // Let user select elements
                        try
                        {
                            var pickedRefs = selection.PickObjects(ObjectType.Element, "Select elements to check for compliance");
                            selectedIds = pickedRefs.Select(r => r.ElementId).ToList();
                        }
                        catch (Autodesk.Revit.Exceptions.OperationCanceledException)
                        {
                            return Result.Cancelled;
                        }
                    }
                    else if (result == TaskDialogResult.CommandLink2)
                    {
                        // Get all monitored elements
                        selectedIds = GetAllMonitoredElements(doc);
                    }
                    else
                    {
                        return Result.Cancelled;
                    }
                }

                if (selectedIds.Count == 0)
                {
                    TaskDialog.Show("No Elements", "No elements found to check.");
                    return Result.Cancelled;
                }

                // Show progress dialog
                var progressDialog = new TaskDialog("Compliance Check")
                {
                    MainInstruction = "Checking compliance...",
                    MainContent = $"Processing {selectedIds.Count} element(s)",
                    CommonButtons = TaskDialogCommonButtons.None,
                    AllowCancellation = false
                };

                // Process elements in background
                Task.Run(async () =>
                {
                    try
                    {
                        var contexts = new List<ElementContext>();

                        foreach (var id in selectedIds)
                        {
                            var elem = doc.GetElement(id);
                            if (elem != null && elem.Category != null)
                            {
                                var context = contextExtractor.Extract(elem, doc);
                                contexts.Add(context);
                            }
                        }

                        logger.Info($"Checking compliance for {contexts.Count} elements");

                        // Batch check if multiple elements
                        if (contexts.Count > 1)
                        {
                            var batchResult = await apiClient.CheckComplianceBatchAsync(contexts.ToArray());

                            // Show results on UI thread
                            Application.Current?.Dispatcher.Invoke(() =>
                            {
                                ShowBatchResults(batchResult, doc);
                            });
                        }
                        else if (contexts.Count == 1)
                        {
                            var result = await apiClient.CheckComplianceAsync(contexts[0]);
                            var elem = doc.GetElement(new ElementId(int.Parse(contexts[0].ElementId)));

                            // Show results on UI thread
                            Application.Current?.Dispatcher.Invoke(() =>
                            {
                                var notification = new NotificationPopup(elem, result);
                                notification.Show();
                            });
                        }
                    }
                    catch (Exception ex)
                    {
                        logger.Error("Error during compliance check", ex);

                        Application.Current?.Dispatcher.Invoke(() =>
                        {
                            TaskDialog.Show("Error", $"Failed to check compliance: {ex.Message}");
                        });
                    }
                });

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                message = ex.Message;
                return Result.Failed;
            }
        }

        private ICollection<ElementId> GetAllMonitoredElements(Document doc)
        {
            var collector = new FilteredElementCollector(doc);

            var categories = new List<BuiltInCategory>
            {
                BuiltInCategory.OST_Walls,
                BuiltInCategory.OST_Doors,
                BuiltInCategory.OST_Windows,
                BuiltInCategory.OST_Floors,
                BuiltInCategory.OST_Ceilings
            };

            var filters = categories.Select(cat => new ElementCategoryFilter(cat) as ElementFilter).ToList();
            var multiFilter = new LogicalOrFilter(filters);

            return collector.WherePasses(multiFilter).WhereElementIsNotElementType().ToElementIds();
        }

        private void ShowBatchResults(BatchComplianceResult batchResult, Document doc)
        {
            var compliantCount = batchResult.Results.Count(r => r.Result.IsCompliant);
            var violationCount = batchResult.Results.Count(r => !r.Result.IsCompliant);

            var summary = $"Compliant: {compliantCount}\n" +
                         $"Violations: {violationCount}\n\n";

            if (violationCount > 0)
            {
                summary += "Elements with violations:\n";

                foreach (var item in batchResult.Results.Where(r => !r.Result.IsCompliant))
                {
                    var elem = doc.GetElement(new ElementId(int.Parse(item.ElementId)));
                    var elemName = elem?.Name ?? "Unknown";
                    var violationsSummary = string.Join(", ", item.Result.Violations.Select(v => v.Code));

                    summary += $"- {elemName} ({item.ElementId}): {violationsSummary}\n";
                }
            }

            TaskDialog dialog = new TaskDialog("Compliance Check Results");
            dialog.MainInstruction = $"Checked {batchResult.Results.Count} elements";
            dialog.MainContent = summary;
            dialog.CommonButtons = TaskDialogCommonButtons.Close;

            if (violationCount > 0)
            {
                dialog.AddCommandLink(TaskDialogCommandLinkId.CommandLink1, "View Details", "Open compliance panel for detailed results");
            }

            var result = dialog.Show();

            if (result == TaskDialogResult.CommandLink1)
            {
                // Open compliance panel
                App.ShowCompliancePanel();
            }
        }
    }
}
