using System;
using System.Configuration;
using System.Threading.Tasks;
using System.Windows;
using ProjektantCopilot.Services;

namespace ProjektantCopilot.UI
{
    public partial class SettingsDialog : Window
    {
        private readonly LogService _logger;

        public SettingsDialog()
        {
            InitializeComponent();
            _logger = App.Logger;

            LoadSettings();
        }

        private void LoadSettings()
        {
            try
            {
                // Load from configuration
                var config = ConfigurationManager.OpenExeConfiguration(ConfigurationUserLevel.PerUserRoamingAndLocal);

                BackendUrlTextBox.Text = GetSetting("BackendUrl", "http://localhost:8000");
                // API key is not loaded for security reasons

                EnableMonitoringCheckBox.IsChecked = GetBoolSetting("EnableMonitoring", true);
                ShowNotificationsCheckBox.IsChecked = GetBoolSetting("ShowNotifications", true);
                NotifyOnlyViolationsCheckBox.IsChecked = GetBoolSetting("NotifyOnlyViolations", true);

                MonitorWallsCheckBox.IsChecked = GetBoolSetting("MonitorWalls", true);
                MonitorDoorsCheckBox.IsChecked = GetBoolSetting("MonitorDoors", true);
                MonitorWindowsCheckBox.IsChecked = GetBoolSetting("MonitorWindows", true);
                MonitorFloorsCheckBox.IsChecked = GetBoolSetting("MonitorFloors", true);
                MonitorCeilingsCheckBox.IsChecked = GetBoolSetting("MonitorCeilings", true);
            }
            catch (Exception ex)
            {
                _logger.Error("Failed to load settings", ex);
            }
        }

        private void SaveSettings()
        {
            try
            {
                SetSetting("BackendUrl", BackendUrlTextBox.Text);

                if (!string.IsNullOrEmpty(ApiKeyPasswordBox.Password))
                {
                    // In production, use secure storage (Windows Credential Manager)
                    SetSetting("ApiKey", ApiKeyPasswordBox.Password);
                }

                SetSetting("EnableMonitoring", EnableMonitoringCheckBox.IsChecked.ToString());
                SetSetting("ShowNotifications", ShowNotificationsCheckBox.IsChecked.ToString());
                SetSetting("NotifyOnlyViolations", NotifyOnlyViolationsCheckBox.IsChecked.ToString());

                SetSetting("MonitorWalls", MonitorWallsCheckBox.IsChecked.ToString());
                SetSetting("MonitorDoors", MonitorDoorsCheckBox.IsChecked.ToString());
                SetSetting("MonitorWindows", MonitorWindowsCheckBox.IsChecked.ToString());
                SetSetting("MonitorFloors", MonitorFloorsCheckBox.IsChecked.ToString());
                SetSetting("MonitorCeilings", MonitorCeilingsCheckBox.IsChecked.ToString());

                ConfigurationManager.RefreshSection("appSettings");

                _logger.Info("Settings saved successfully");
            }
            catch (Exception ex)
            {
                _logger.Error("Failed to save settings", ex);
                MessageBox.Show($"Failed to save settings: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private string GetSetting(string key, string defaultValue = "")
        {
            try
            {
                var value = ConfigurationManager.AppSettings[key];
                return string.IsNullOrEmpty(value) ? defaultValue : value;
            }
            catch
            {
                return defaultValue;
            }
        }

        private bool GetBoolSetting(string key, bool defaultValue = false)
        {
            try
            {
                var value = ConfigurationManager.AppSettings[key];
                return bool.TryParse(value, out var result) ? result : defaultValue;
            }
            catch
            {
                return defaultValue;
            }
        }

        private void SetSetting(string key, string value)
        {
            try
            {
                var config = ConfigurationManager.OpenExeConfiguration(ConfigurationUserLevel.PerUserRoamingAndLocal);

                if (config.AppSettings.Settings[key] == null)
                {
                    config.AppSettings.Settings.Add(key, value);
                }
                else
                {
                    config.AppSettings.Settings[key].Value = value;
                }

                config.Save(ConfigurationSaveMode.Modified);
            }
            catch (Exception ex)
            {
                _logger.Error($"Failed to set setting {key}", ex);
                throw;
            }
        }

        private async void TestConnection_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                var button = sender as System.Windows.Controls.Button;
                button.IsEnabled = false;
                button.Content = "Testing...";

                var url = BackendUrlTextBox.Text;
                var apiKey = ApiKeyPasswordBox.Password;

                if (string.IsNullOrWhiteSpace(url))
                {
                    MessageBox.Show("Please enter a backend URL.", "Validation Error", MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }

                // Create temporary API client
                var testClient = new ApiClient(url, apiKey, _logger);

                var isHealthy = await testClient.CheckHealthAsync();

                if (isHealthy)
                {
                    MessageBox.Show("Connection successful!", "Success", MessageBoxButton.OK, MessageBoxImage.Information);
                }
                else
                {
                    MessageBox.Show("Connection failed. Please check the URL and try again.", "Connection Failed", MessageBoxButton.OK, MessageBoxImage.Error);
                }

                button.IsEnabled = true;
                button.Content = "Test Connection";
            }
            catch (Exception ex)
            {
                _logger.Error("Connection test failed", ex);
                MessageBox.Show($"Connection test failed: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);

                var button = sender as System.Windows.Controls.Button;
                button.IsEnabled = true;
                button.Content = "Test Connection";
            }
        }

        private void EnableMonitoring_Changed(object sender, RoutedEventArgs e)
        {
            var isEnabled = EnableMonitoringCheckBox.IsChecked == true;
            ComplianceUpdater.SetEnabled(isEnabled);
        }

        private void Save_Click(object sender, RoutedEventArgs e)
        {
            SaveSettings();

            // Apply settings
            App.ApplySettings();

            DialogResult = true;
            Close();
        }

        private void Cancel_Click(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
            Close();
        }
    }
}
