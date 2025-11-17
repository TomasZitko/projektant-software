using System;
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Events;

namespace ProjektantCopilot.Services
{
    /// <summary>
    /// Event handlers for document-level events.
    /// </summary>
    public class EventHandler
    {
        public void OnDocumentSaving(object sender, DocumentSavingEventArgs e)
        {
            try
            {
                LogService.Info($"Document saving: {e.Document.Title}");
                // TODO: Optionally run full compliance check before saving
            }
            catch (Exception ex)
            {
                LogService.Error($"Error in OnDocumentSaving: {ex.Message}", ex);
            }
        }

        public void OnDocumentOpened(object sender, DocumentOpenedEventArgs e)
        {
            try
            {
                LogService.Info($"Document opened: {e.Document.Title}");
                // TODO: Load cached compliance results
            }
            catch (Exception ex)
            {
                LogService.Error($"Error in OnDocumentOpened: {ex.Message}", ex);
            }
        }
    }
}
