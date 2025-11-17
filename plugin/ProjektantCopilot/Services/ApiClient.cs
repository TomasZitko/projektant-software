using System;
using System.Net.Http;
using RestSharp;
using Newtonsoft.Json;
using ProjektantCopilot.Models;
using ProjektantCopilot.Utils;

namespace ProjektantCopilot.Services
{
    /// <summary>
    /// API client for communicating with the backend compliance service.
    /// </summary>
    public class ApiClient
    {
        private readonly RestClient _client;
        private readonly string _baseUrl;

        public ApiClient()
        {
            _baseUrl = SettingsManager.GetSetting("ApiBaseUrl", "http://localhost:8000");
            _client = new RestClient(_baseUrl);
        }

        /// <summary>
        /// Check element compliance against building codes.
        /// </summary>
        public ComplianceResult CheckElementCompliance(ElementContext context)
        {
            try
            {
                var request = new RestRequest("/api/v1/compliance/check", Method.Post);
                request.AddJsonBody(context);

                LogService.Info($"Sending compliance check request for {context.ElementType}");

                var response = _client.Execute<ComplianceResult>(request);

                if (!response.IsSuccessful)
                {
                    LogService.Error($"API request failed: {response.ErrorMessage}");

                    if (response.StatusCode == System.Net.HttpStatusCode.NotFound)
                    {
                        throw new Exception("Backend API not available. Please ensure the server is running.");
                    }

                    throw new Exception($"API error: {response.ErrorMessage}");
                }

                LogService.Info($"Compliance check completed: {(response.Data.Compliant ? "Compliant" : "Violations found")}");

                return response.Data;
            }
            catch (Exception ex)
            {
                LogService.Error($"Failed to check compliance: {ex.Message}", ex);
                throw;
            }
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
                return response.IsSuccessful;
            }
            catch
            {
                return false;
            }
        }
    }
}
