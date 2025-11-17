using System.Collections.Generic;
using Newtonsoft.Json;

namespace ProjektantCopilot.Models
{
    /// <summary>
    /// Result of a compliance check from the backend API.
    /// </summary>
    public class ComplianceResult
    {
        [JsonProperty("compliant")]
        public bool Compliant { get; set; }

        [JsonProperty("violations")]
        public List<ComplianceViolation> Violations { get; set; }

        [JsonProperty("recommendations")]
        public List<string> Recommendations { get; set; }

        [JsonProperty("checked_at")]
        public string CheckedAt { get; set; }
    }

    /// <summary>
    /// A single compliance violation.
    /// </summary>
    public class ComplianceViolation
    {
        [JsonProperty("rule_id")]
        public string RuleId { get; set; }

        [JsonProperty("severity")]
        public string Severity { get; set; }

        [JsonProperty("message")]
        public string Message { get; set; }

        [JsonProperty("required_value")]
        public double? RequiredValue { get; set; }

        [JsonProperty("actual_value")]
        public double? ActualValue { get; set; }

        [JsonProperty("code_reference")]
        public string CodeReference { get; set; }

        [JsonProperty("confidence_score")]
        public double ConfidenceScore { get; set; }
    }
}
