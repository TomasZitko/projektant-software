using Newtonsoft.Json;

namespace ProjektantCopilot.Models
{
    /// <summary>
    /// Context information for a building element to be checked.
    /// </summary>
    public class ElementContext
    {
        [JsonProperty("element_type")]
        public string ElementType { get; set; }

        [JsonProperty("properties")]
        public ElementProperties Properties { get; set; }

        [JsonProperty("context")]
        public SpatialContext Context { get; set; }
    }

    /// <summary>
    /// Physical properties of the element.
    /// </summary>
    public class ElementProperties
    {
        [JsonProperty("width_mm")]
        public double? WidthMm { get; set; }

        [JsonProperty("height_mm")]
        public double? HeightMm { get; set; }

        [JsonProperty("length_mm")]
        public double? LengthMm { get; set; }

        [JsonProperty("function")]
        public string Function { get; set; }
    }

    /// <summary>
    /// Spatial and semantic context of the element.
    /// </summary>
    public class SpatialContext
    {
        [JsonProperty("room_type")]
        public string RoomType { get; set; }

        [JsonProperty("building_type")]
        public string BuildingType { get; set; }

        [JsonProperty("occupancy")]
        public int? Occupancy { get; set; }

        [JsonProperty("floor_level")]
        public int? FloorLevel { get; set; }
    }
}
