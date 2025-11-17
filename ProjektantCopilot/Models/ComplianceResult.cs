using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace ProjektantCopilot.Models
{
    /// <summary>
    /// Represents the result of a compliance check from the backend API
    /// </summary>
    public class ComplianceResult
    {
        [JsonProperty("is_compliant")]
        public bool IsCompliant { get; set; }

        [JsonProperty("violations")]
        public List<Violation> Violations { get; set; }

        [JsonProperty("warnings")]
        public List<Warning> Warnings { get; set; }

        [JsonProperty("recommendations")]
        public List<string> Recommendations { get; set; }

        [JsonProperty("checked_at")]
        public DateTime CheckedAt { get; set; }

        [JsonProperty("check_id")]
        public string CheckId { get; set; }

        public ComplianceResult()
        {
            Violations = new List<Violation>();
            Warnings = new List<Warning>();
            Recommendations = new List<string>();
        }
    }

    public class Violation
    {
        [JsonProperty("code")]
        public string Code { get; set; }

        [JsonProperty("severity")]
        public string Severity { get; set; }

        [JsonProperty("message")]
        public string Message { get; set; }

        [JsonProperty("regulation")]
        public string Regulation { get; set; }

        [JsonProperty("regulation_text")]
        public string RegulationText { get; set; }

        [JsonProperty("suggested_fix")]
        public string SuggestedFix { get; set; }
    }

    public class Warning
    {
        [JsonProperty("code")]
        public string Code { get; set; }

        [JsonProperty("message")]
        public string Message { get; set; }

        [JsonProperty("details")]
        public string Details { get; set; }
    }
}
