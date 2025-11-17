using System;
using System.Net.Http;
using System.Threading;
using RestSharp;
using Newtonsoft.Json;
using ProjektantCopilot.Models;
using ProjektantCopilot.Utils;

namespace ProjektantCopilot.Services
{
    /// <summary>
    /// API client for communicating with the backend compliance service.
    /// Features:
    /// - Exponential backoff retry logic (1s, 2s, 4s)
    /// - Timeout configuration
    /// - Circuit breaker pattern
    /// - Comprehensive error handling
    /// </summary>
    public class ApiClient
    {
        private readonly RestClient _client;
        private readonly string _baseUrl;
        private readonly int _maxRetries = 3;
        private readonly int _timeoutMs = 10000; // 10 seconds

        // Circuit breaker state
        private int _consecutiveFailures = 0;
        private readonly int _circuitBreakerThreshold = 5;
        private DateTime _circuitBreakerResetTime = DateTime.MinValue;
        private bool _isCircuitOpen =>
            _consecutiveFailures >= _circuitBreakerThreshold &&
            DateTime.UtcNow < _circuitBreakerResetTime;

        public ApiClient()
        {
            _baseUrl = SettingsManager.GetSetting("ApiBaseUrl", "http://localhost:8000");

            var options = new RestClientOptions(_baseUrl)
            {
                MaxTimeout = _timeoutMs,
                ThrowOnAnyError = false
            };

            _client = new RestClient(options);
        }

        /// <summary>
        /// Check element compliance against building codes.
        /// Includes retry logic with exponential backoff (1s, 2s, 4s).
        /// </summary>
        public ComplianceResult CheckElementCompliance(ElementContext context)
        {
            // Check circuit breaker
            if (_isCircuitOpen)
            {
                LogService.Warn($"Circuit breaker is open. Backend unavailable until {_circuitBreakerResetTime:HH:mm:ss}");
                throw new Exception("Service temporarily unavailable. Too many consecutive failures. Please try again later.");
            }

            Exception lastException = null;

            for (int attempt = 0; attempt < _maxRetries; attempt++)
            {
                try
                {
                    var request = new RestRequest("/api/v1/compliance/check", Method.Post);
                    request.AddJsonBody(context);

                    if (attempt > 0)
                    {
                        LogService.Info($"Retry attempt {attempt + 1}/{_maxRetries} for {context.ElementType}");
                    }
                    else
                    {
                        LogService.Info($"Sending compliance check request for {context.ElementType}");
                    }

                    var response = _client.Execute<ComplianceResult>(request);

                    if (response.IsSuccessful && response.Data != null)
                    {
                        // Success - reset circuit breaker
                        _consecutiveFailures = 0;

                        LogService.Info($"Compliance check completed: {(response.Data.Compliant ? "Compliant" : "Violations found")}");
                        return response.Data;
                    }

                    // Handle HTTP errors
                    if (response.StatusCode == System.Net.HttpStatusCode.NotFound)
                    {
                        throw new Exception("Backend API endpoint not found. Please check the API URL configuration.");
                    }

                    if (response.StatusCode == System.Net.HttpStatusCode.ServiceUnavailable)
                    {
                        LogService.Warn("Backend service unavailable. Retrying...");
                        lastException = new Exception("Backend service temporarily unavailable.");
                    }
                    else if (!string.IsNullOrEmpty(response.ErrorMessage))
                    {
                        LogService.Error($"API request failed: {response.ErrorMessage}");
                        lastException = new Exception($"API error: {response.ErrorMessage}");
                    }
                    else
                    {
                        LogService.Error($"API request failed with status {response.StatusCode}");
                        lastException = new Exception($"API returned status {response.StatusCode}");
                    }
                }
                catch (Exception ex)
                {
                    LogService.Error($"Request attempt {attempt + 1} failed: {ex.Message}");
                    lastException = ex;

                    // Don't retry on configuration errors
                    if (ex.Message.Contains("endpoint not found") ||
                        ex.Message.Contains("configuration"))
                    {
                        throw;
                    }
                }

                // Exponential backoff: 1s, 2s, 4s
                if (attempt < _maxRetries - 1)
                {
                    int delayMs = (int)Math.Pow(2, attempt) * 1000; // 1000, 2000, 4000
                    LogService.Debug($"Waiting {delayMs}ms before retry...");
                    Thread.Sleep(delayMs);
                }
            }

            // All retries failed - trigger circuit breaker
            _consecutiveFailures++;
            if (_consecutiveFailures >= _circuitBreakerThreshold)
            {
                _circuitBreakerResetTime = DateTime.UtcNow.AddMinutes(5);
                LogService.Error($"Circuit breaker opened after {_consecutiveFailures} consecutive failures. Will retry at {_circuitBreakerResetTime:HH:mm:ss}");
            }

            // Throw the last exception
            LogService.Error($"All {_maxRetries} retry attempts failed for {context.ElementType}");
            throw new Exception($"Failed to check compliance after {_maxRetries} attempts. Last error: {lastException?.Message ?? "Unknown error"}");
        }

        /// <summary>
        /// Test connection to backend API.
        /// </summary>
        public bool TestConnection()
        {
            try
            {
                var request = new RestRequest("/health", Method.Get);
                var response = _client.Execute(request);

                if (response.IsSuccessful)
                {
                    LogService.Info("Backend API connection test successful");
                    _consecutiveFailures = 0; // Reset on successful connection
                    return true;
                }

                LogService.Warn($"Backend API connection test failed: {response.StatusCode}");
                return false;
            }
            catch (Exception ex)
            {
                LogService.Error($"Backend API connection test failed: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Get the current circuit breaker status.
        /// </summary>
        public string GetCircuitBreakerStatus()
        {
            if (_isCircuitOpen)
            {
                return $"OPEN (resets at {_circuitBreakerResetTime:HH:mm:ss})";
            }
            else if (_consecutiveFailures > 0)
            {
                return $"CLOSED ({_consecutiveFailures}/{_circuitBreakerThreshold} failures)";
            }
            return "CLOSED (healthy)";
        }

        /// <summary>
        /// Manually reset the circuit breaker.
        /// </summary>
        public void ResetCircuitBreaker()
        {
            _consecutiveFailures = 0;
            _circuitBreakerResetTime = DateTime.MinValue;
            LogService.Info("Circuit breaker manually reset");
        }
    }
}
