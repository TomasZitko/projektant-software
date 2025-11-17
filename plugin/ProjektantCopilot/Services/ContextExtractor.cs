using System;
using System.Collections.Generic;
using Autodesk.Revit.DB;
using ProjektantCopilot.Models;
using ProjektantCopilot.Utils;

namespace ProjektantCopilot.Services
{
    /// <summary>
    /// Extracts context information from Revit elements.
    /// </summary>
    public class ContextExtractor
    {
        public ElementContext ExtractContext(Element element, Document doc)
        {
            if (element == null)
                return null;

            var context = new ElementContext
            {
                ElementType = element.Category?.Name ?? "Unknown",
                Properties = new ElementProperties(),
                Context = new SpatialContext()
            };

            // Extract properties based on element type
            if (element is Wall wall)
            {
                ExtractWallProperties(wall, context.Properties);
            }
            else if (element is FamilyInstance familyInstance)
            {
                ExtractFamilyInstanceProperties(familyInstance, context.Properties);
            }

            // Extract spatial context
            ExtractSpatialContext(element, doc, context.Context);

            return context;
        }

        private void ExtractWallProperties(Wall wall, ElementProperties properties)
        {
            // Convert from feet to millimeters
            properties.WidthMm = UnitConverter.FeetToMillimeters(wall.Width);

            var heightParam = wall.get_Parameter(BuiltInParameter.WALL_USER_HEIGHT_PARAM);
            if (heightParam != null)
            {
                properties.HeightMm = UnitConverter.FeetToMillimeters(heightParam.AsDouble());
            }

            properties.Function = wall.WallType?.Function.ToString();
        }

        private void ExtractFamilyInstanceProperties(FamilyInstance instance, ElementProperties properties)
        {
            // Get width parameter
            var widthParam = instance.LookupParameter("Width") ?? instance.LookupParameter("Šířka");
            if (widthParam != null)
            {
                properties.WidthMm = UnitConverter.FeetToMillimeters(widthParam.AsDouble());
            }

            // Get height parameter
            var heightParam = instance.LookupParameter("Height") ?? instance.LookupParameter("Výška");
            if (heightParam != null)
            {
                properties.HeightMm = UnitConverter.FeetToMillimeters(heightParam.AsDouble());
            }

            properties.Function = instance.Symbol?.FamilyName;
        }

        private void ExtractSpatialContext(Element element, Document doc, SpatialContext context)
        {
            // Try to find containing room
            try
            {
                var location = element.Location;
                if (location is LocationPoint locPoint)
                {
                    var room = doc.GetRoomAtPoint(locPoint.Point);
                    if (room != null)
                    {
                        context.RoomType = room.get_Parameter(BuiltInParameter.ROOM_NAME)?.AsString();
                    }
                }
            }
            catch (Exception ex)
            {
                LogService.Debug($"Could not extract spatial context: {ex.Message}");
            }

            // Get level information
            var levelParam = element.get_Parameter(BuiltInParameter.FAMILY_LEVEL_PARAM);
            if (levelParam != null)
            {
                var level = doc.GetElement(levelParam.AsElementId()) as Level;
                context.FloorLevel = GetFloorNumber(level);
            }

            // TODO: Extract building type from project information
            context.BuildingType = "Residential"; // Placeholder
        }

        private int GetFloorNumber(Level level)
        {
            if (level == null)
                return 0;

            // Try to parse floor number from level name
            string name = level.Name;
            if (int.TryParse(name, out int floorNum))
                return floorNum;

            // Look for common patterns
            if (name.Contains("1") || name.ToLower().Contains("first") || name.ToLower().Contains("ground"))
                return 1;
            if (name.Contains("2") || name.ToLower().Contains("second"))
                return 2;

            return 0;
        }
    }
}
