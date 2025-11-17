using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace ProjektantCopilot.Models
{
    /// <summary>
    /// Represents the context of a Revit element for compliance checking
    /// </summary>
    public class ElementContext
    {
        [JsonProperty("element_id")]
        public string ElementId { get; set; }

        [JsonProperty("element_type")]
        public string ElementType { get; set; }

        [JsonProperty("category")]
        public string Category { get; set; }

        [JsonProperty("properties")]
        public Dictionary<string, object> Properties { get; set; }

        [JsonProperty("context")]
        public Dictionary<string, object> Context { get; set; }

        [JsonProperty("location")]
        public LocationInfo Location { get; set; }

        [JsonProperty("project_info")]
        public ProjectInfo ProjectInfo { get; set; }

        public ElementContext()
        {
            Properties = new Dictionary<string, object>();
            Context = new Dictionary<string, object>();
        }
    }

    public class LocationInfo
    {
        [JsonProperty("level")]
        public string Level { get; set; }

        [JsonProperty("x")]
        public double X { get; set; }

        [JsonProperty("y")]
        public double Y { get; set; }

        [JsonProperty("z")]
        public double Z { get; set; }
    }

    public class ProjectInfo
    {
        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("building_type")]
        public string BuildingType { get; set; }

        [JsonProperty("project_number")]
        public string ProjectNumber { get; set; }

        [JsonProperty("author")]
        public string Author { get; set; }
    }
}
