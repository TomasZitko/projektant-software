using Newtonsoft.Json;

namespace ProjektantCopilot.Models
{
    /// <summary>
    /// Health check response from API.
    /// </summary>
    public class HealthResponse
    {
        [JsonProperty("status")]
        public string Status { get; set; }

        [JsonProperty("app_name")]
        public string AppName { get; set; }

        [JsonProperty("version")]
        public string Version { get; set; }
    }
}
