using System;
using System.Collections.Generic;
using System.Linq;
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Architecture;
using ProjektantCopilot.Models;

namespace ProjektantCopilot.Services
{
    /// <summary>
    /// Extracts context and properties from Revit elements for compliance checking
    /// </summary>
    public class ContextExtractor
    {
        private readonly LogService _logger;

        public ContextExtractor(LogService logger)
        {
            _logger = logger;
        }

        /// <summary>
        /// Extract complete context from a Revit element
        /// </summary>
        public ElementContext Extract(Element elem, Document doc)
        {
            try
            {
                var context = new ElementContext
                {
                    ElementId = elem.Id.ToString(),
                    Category = elem.Category?.Name ?? "Unknown",
                    Location = ExtractLocation(elem),
                    ProjectInfo = ExtractProjectInfo(doc)
                };

                // Extract properties based on element type
                if (elem is Wall wall)
                {
                    ExtractWallContext(wall, doc, context);
                }
                else if (elem is FamilyInstance familyInstance)
                {
                    ExtractFamilyInstanceContext(familyInstance, doc, context);
                }
                else if (elem is Floor floor)
                {
                    ExtractFloorContext(floor, doc, context);
                }
                else if (elem is Ceiling ceiling)
                {
                    ExtractCeilingContext(ceiling, doc, context);
                }
                else
                {
                    ExtractGenericContext(elem, context);
                }

                return context;
            }
            catch (Exception ex)
            {
                _logger.Error($"Failed to extract context for element {elem.Id}: {ex.Message}");
                throw;
            }
        }

        private void ExtractWallContext(Wall wall, Document doc, ElementContext context)
        {
            context.ElementType = "Wall";

            // Basic wall properties
            var wallType = doc.GetElement(wall.GetTypeId()) as WallType;
            context.Properties["width_mm"] = wall.Width * 304.8; // feet to mm
            context.Properties["height_mm"] = GetWallHeight(wall) * 304.8;
            context.Properties["length_mm"] = wall.get_Parameter(BuiltInParameter.CURVE_ELEM_LENGTH)?.AsDouble() * 304.8 ?? 0;
            context.Properties["type_name"] = wallType?.Name ?? "Unknown";
            context.Properties["structural"] = wall.StructuralUsage != StructuralWallUsage.NonBearing;

            // Fire rating
            var fireRating = wall.get_Parameter(BuiltInParameter.DOOR_FIRE_RATING);
            if (fireRating != null && !string.IsNullOrEmpty(fireRating.AsString()))
            {
                context.Properties["fire_rating"] = fireRating.AsString();
            }

            // Get adjacent rooms for context
            var phase = doc.Phases.get_Item(doc.Phases.Size - 1) as Phase;
            var room1 = wall.get_Parameter(BuiltInParameter.WALL_ATTR_ROOM_BOUNDING)?.AsInteger() == 1
                ? doc.GetRoomAtPoint(GetWallMidpoint(wall), phase)
                : null;

            if (room1 != null)
            {
                context.Context["room_type"] = GetRoomFunction(room1);
                context.Context["room_name"] = room1.get_Parameter(BuiltInParameter.ROOM_NAME)?.AsString() ?? "Unknown";
                context.Context["room_number"] = room1.Number;
            }

            // Building type from project
            var buildingType = doc.ProjectInformation.LookupParameter("Building Type")?.AsString();
            if (!string.IsNullOrEmpty(buildingType))
            {
                context.Context["building_type"] = buildingType;
            }
        }

        private void ExtractFamilyInstanceContext(FamilyInstance instance, Document doc, ElementContext context)
        {
            var category = instance.Category?.Name ?? "Unknown";
            context.ElementType = category;

            // Basic properties
            var familySymbol = instance.Symbol;
            context.Properties["family_name"] = familySymbol?.Family?.Name ?? "Unknown";
            context.Properties["type_name"] = familySymbol?.Name ?? "Unknown";

            // Door-specific properties
            if (category == "Doors")
            {
                var width = instance.get_Parameter(BuiltInParameter.DOOR_WIDTH);
                var height = instance.get_Parameter(BuiltInParameter.DOOR_HEIGHT);

                if (width != null) context.Properties["width_mm"] = width.AsDouble() * 304.8;
                if (height != null) context.Properties["height_mm"] = height.AsDouble() * 304.8;

                var fireRating = instance.get_Parameter(BuiltInParameter.DOOR_FIRE_RATING);
                if (fireRating != null && !string.IsNullOrEmpty(fireRating.AsString()))
                {
                    context.Properties["fire_rating"] = fireRating.AsString();
                }

                // Get room that door belongs to
                var fromRoom = instance.FromRoom;
                var toRoom = instance.ToRoom;

                if (fromRoom != null)
                {
                    context.Context["from_room_type"] = GetRoomFunction(fromRoom);
                    context.Context["from_room_name"] = fromRoom.get_Parameter(BuiltInParameter.ROOM_NAME)?.AsString();
                }

                if (toRoom != null)
                {
                    context.Context["to_room_type"] = GetRoomFunction(toRoom);
                    context.Context["to_room_name"] = toRoom.get_Parameter(BuiltInParameter.ROOM_NAME)?.AsString();
                }
            }
            // Window-specific properties
            else if (category == "Windows")
            {
                var width = instance.get_Parameter(BuiltInParameter.WINDOW_WIDTH);
                var height = instance.get_Parameter(BuiltInParameter.WINDOW_HEIGHT);

                if (width != null) context.Properties["width_mm"] = width.AsDouble() * 304.8;
                if (height != null) context.Properties["height_mm"] = height.AsDouble() * 304.8;

                var sillHeight = instance.get_Parameter(BuiltInParameter.INSTANCE_SILL_HEIGHT_PARAM);
                if (sillHeight != null) context.Properties["sill_height_mm"] = sillHeight.AsDouble() * 304.8;
            }
        }

        private void ExtractFloorContext(Floor floor, Document doc, ElementContext context)
        {
            context.ElementType = "Floor";

            var floorType = doc.GetElement(floor.GetTypeId()) as FloorType;
            context.Properties["type_name"] = floorType?.Name ?? "Unknown";
            context.Properties["structural"] = floor.get_Parameter(BuiltInParameter.FLOOR_PARAM_IS_STRUCTURAL)?.AsInteger() == 1;

            // Area
            var area = floor.get_Parameter(BuiltInParameter.HOST_AREA_COMPUTED);
            if (area != null)
            {
                context.Properties["area_sqm"] = area.AsDouble() * 0.09290304; // sq ft to sq m
            }

            // Thickness
            var thickness = floorType?.get_Parameter(BuiltInParameter.FLOOR_ATTR_DEFAULT_THICKNESS_PARAM);
            if (thickness != null)
            {
                context.Properties["thickness_mm"] = thickness.AsDouble() * 304.8;
            }
        }

        private void ExtractCeilingContext(Ceiling ceiling, Document doc, ElementContext context)
        {
            context.ElementType = "Ceiling";

            var ceilingType = doc.GetElement(ceiling.GetTypeId());
            context.Properties["type_name"] = ceilingType?.Name ?? "Unknown";

            // Area
            var area = ceiling.get_Parameter(BuiltInParameter.HOST_AREA_COMPUTED);
            if (area != null)
            {
                context.Properties["area_sqm"] = area.AsDouble() * 0.09290304;
            }
        }

        private void ExtractGenericContext(Element elem, ElementContext context)
        {
            context.ElementType = elem.GetType().Name;

            var elemType = elem.Document.GetElement(elem.GetTypeId());
            if (elemType != null)
            {
                context.Properties["type_name"] = elemType.Name;
            }
        }

        private LocationInfo ExtractLocation(Element elem)
        {
            var location = elem.Location;

            if (location is LocationPoint locPoint)
            {
                var point = locPoint.Point;
                return new LocationInfo
                {
                    Level = elem.LevelId != ElementId.InvalidElementId
                        ? elem.Document.GetElement(elem.LevelId)?.Name
                        : null,
                    X = point.X,
                    Y = point.Y,
                    Z = point.Z
                };
            }
            else if (location is LocationCurve locCurve)
            {
                var midpoint = locCurve.Curve.Evaluate(0.5, true);
                return new LocationInfo
                {
                    Level = elem.LevelId != ElementId.InvalidElementId
                        ? elem.Document.GetElement(elem.LevelId)?.Name
                        : null,
                    X = midpoint.X,
                    Y = midpoint.Y,
                    Z = midpoint.Z
                };
            }

            return new LocationInfo();
        }

        private Models.ProjectInfo ExtractProjectInfo(Document doc)
        {
            var projectInfo = doc.ProjectInformation;

            return new Models.ProjectInfo
            {
                Name = projectInfo.Name,
                BuildingType = projectInfo.LookupParameter("Building Type")?.AsString() ?? "Unknown",
                ProjectNumber = projectInfo.Number,
                Author = projectInfo.Author
            };
        }

        private double GetWallHeight(Wall wall)
        {
            var heightParam = wall.get_Parameter(BuiltInParameter.WALL_USER_HEIGHT_PARAM);
            if (heightParam != null && heightParam.HasValue)
            {
                return heightParam.AsDouble();
            }

            // Fallback: calculate from base and top constraints
            var baseConstraint = wall.get_Parameter(BuiltInParameter.WALL_BASE_CONSTRAINT);
            var topConstraint = wall.get_Parameter(BuiltInParameter.WALL_HEIGHT_TYPE);

            if (baseConstraint != null && topConstraint != null)
            {
                var baseLevel = wall.Document.GetElement(baseConstraint.AsElementId()) as Level;
                var topLevel = wall.Document.GetElement(topConstraint.AsElementId()) as Level;

                if (baseLevel != null && topLevel != null)
                {
                    return topLevel.Elevation - baseLevel.Elevation;
                }
            }

            return 0;
        }

        private XYZ GetWallMidpoint(Wall wall)
        {
            var location = wall.Location as LocationCurve;
            return location?.Curve.Evaluate(0.5, true) ?? XYZ.Zero;
        }

        private string GetRoomFunction(Room room)
        {
            // Try to get room department or function
            var department = room.get_Parameter(BuiltInParameter.ROOM_DEPARTMENT)?.AsString();
            if (!string.IsNullOrEmpty(department))
            {
                return department;
            }

            // Fallback to room name analysis
            var name = room.get_Parameter(BuiltInParameter.ROOM_NAME)?.AsString()?.ToLower() ?? "";

            if (name.Contains("bathroom") || name.Contains("wc") || name.Contains("toilet"))
                return "Bathroom";
            if (name.Contains("kitchen"))
                return "Kitchen";
            if (name.Contains("bedroom") || name.Contains("bed"))
                return "Bedroom";
            if (name.Contains("living") || name.Contains("salon"))
                return "LivingRoom";
            if (name.Contains("office"))
                return "Office";
            if (name.Contains("corridor") || name.Contains("hall"))
                return "Corridor";
            if (name.Contains("storage") || name.Contains("closet"))
                return "Storage";

            return "General";
        }
    }
}
