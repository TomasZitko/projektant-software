using System;
using System.Threading.Tasks;
using RestSharp;
using Newtonsoft.Json;
using ProjektantCopilot.Models;

namespace ProjektantCopilot.Services
{
    /// <summary>
    /// API client for communicating with the compliance backend
    /// </summary>
    public class ApiClient
    {
        private readonly RestClient _client;
        private readonly LogService _logger;
        private readonly string _apiKey;

        public ApiClient(string baseUrl, string apiKey, LogService logger)
        {
            _logger = logger;
            _apiKey = apiKey;

            var options = new RestClientOptions(baseUrl)
            {
                ThrowOnAnyError = false,
                Timeout = TimeSpan.FromSeconds(30)
            };

            _client = new RestClient(options);
            _logger.Info($"ApiClient initialized with base URL: {baseUrl}");
        }

        /// <summary>
        /// Check compliance for a given element context
        /// </summary>
        public async Task<ComplianceResult> CheckComplianceAsync(ElementContext context)
        {
            try
            {
                _logger.Debug($"Checking compliance for element {context.ElementId} ({context.ElementType})");

                var request = new RestRequest("/api/v1/compliance/check", Method.Post);

                // Add headers
                if (!string.IsNullOrEmpty(_apiKey))
                {
                    request.AddHeader("Authorization", $"Bearer {_apiKey}");
                }
                request.AddHeader("Content-Type", "application/json");

                // Serialize and add body
                var jsonBody = JsonConvert.SerializeObject(context);
                request.AddStringBody(jsonBody, DataFormat.Json);

                // Execute request
                var response = await _client.ExecuteAsync(request);

                if (!response.IsSuccessful)
                {
                    var errorMessage = $"API request failed: {response.StatusCode} - {response.ErrorMessage ?? response.Content}";
                    _logger.Error(errorMessage);
                    throw new ApiException(errorMessage, response.StatusCode);
                }

                // Parse response
                var result = JsonConvert.DeserializeObject<ComplianceResult>(response.Content);

                _logger.Info($"Compliance check completed for element {context.ElementId}: " +
                            $"Compliant={result.IsCompliant}, Violations={result.Violations.Count}");

                return result;
            }
            catch (Exception ex)
            {
                _logger.Error($"Exception during compliance check for element {context.ElementId}", ex);
                throw;
            }
        }

        /// <summary>
        /// Batch check multiple elements at once
        /// </summary>
        public async Task<BatchComplianceResult> CheckComplianceBatchAsync(ElementContext[] contexts)
        {
            try
            {
                _logger.Debug($"Checking compliance for {contexts.Length} elements");

                var request = new RestRequest("/api/v1/compliance/check-batch", Method.Post);

                if (!string.IsNullOrEmpty(_apiKey))
                {
                    request.AddHeader("Authorization", $"Bearer {_apiKey}");
                }
                request.AddHeader("Content-Type", "application/json");

                var jsonBody = JsonConvert.SerializeObject(contexts);
                request.AddStringBody(jsonBody, DataFormat.Json);

                var response = await _client.ExecuteAsync(request);

                if (!response.IsSuccessful)
                {
                    var errorMessage = $"Batch API request failed: {response.StatusCode} - {response.ErrorMessage ?? response.Content}";
                    _logger.Error(errorMessage);
                    throw new ApiException(errorMessage, response.StatusCode);
                }

                var result = JsonConvert.DeserializeObject<BatchComplianceResult>(response.Content);

                _logger.Info($"Batch compliance check completed: {result.Results.Count} results");

                return result;
            }
            catch (Exception ex)
            {
                _logger.Error("Exception during batch compliance check", ex);
                throw;
            }
        }

        /// <summary>
        /// Get health status of the API
        /// </summary>
        public async Task<bool> CheckHealthAsync()
        {
            try
            {
                var request = new RestRequest("/health", Method.Get);
                var response = await _client.ExecuteAsync(request);

                var isHealthy = response.IsSuccessful;
                _logger.Debug($"API health check: {(isHealthy ? "Healthy" : "Unhealthy")}");

                return isHealthy;
            }
            catch (Exception ex)
            {
                _logger.Error("Exception during health check", ex);
                return false;
            }
        }
    }

    /// <summary>
    /// Batch compliance check result
    /// </summary>
    public class BatchComplianceResult
    {
        [JsonProperty("results")]
        public System.Collections.Generic.List<ComplianceResultWithId> Results { get; set; }

        public BatchComplianceResult()
        {
            Results = new System.Collections.Generic.List<ComplianceResultWithId>();
        }
    }

    public class ComplianceResultWithId
    {
        [JsonProperty("element_id")]
        public string ElementId { get; set; }

        [JsonProperty("result")]
        public ComplianceResult Result { get; set; }
    }

    /// <summary>
    /// Custom exception for API errors
    /// </summary>
    public class ApiException : Exception
    {
        public System.Net.HttpStatusCode? StatusCode { get; set; }

        public ApiException(string message) : base(message)
        {
        }

        public ApiException(string message, System.Net.HttpStatusCode? statusCode) : base(message)
        {
            StatusCode = statusCode;
        }

        public ApiException(string message, Exception innerException) : base(message, innerException)
        {
        }
    }
}
