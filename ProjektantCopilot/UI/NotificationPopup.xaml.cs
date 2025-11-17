using System;
using System.ComponentModel;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Windows;
using System.Windows.Forms;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Threading;
using Autodesk.Revit.DB;
using ProjektantCopilot.Models;

namespace ProjektantCopilot.UI
{
    public partial class NotificationPopup : Window, INotifyPropertyChanged
    {
        private readonly Element _element;
        private readonly ComplianceResult _result;
        private DispatcherTimer _autoCloseTimer;

        private string _title;
        private string _elementInfo;
        private string _message;
        private SolidColorBrush _statusColor;
        private SolidColorBrush _borderColor;
        private Visibility _detailsButtonVisibility;

        public NotificationPopup(Element element, ComplianceResult result)
        {
            InitializeComponent();
            DataContext = this;

            _element = element;
            _result = result;

            InitializeContent();
            PositionWindow();
            StartAutoCloseTimer();
        }

        private void InitializeContent()
        {
            // Set title and colors based on compliance result
            if (_result.IsCompliant)
            {
                Title = "Compliant";
                StatusColor = new SolidColorBrush(Colors.Green);
                BorderColor = new SolidColorBrush(Color.FromRgb(34, 197, 94)); // Green
                Message = "Element meets all compliance requirements.";
                DetailsButtonVisibility = Visibility.Collapsed;
            }
            else
            {
                Title = "Compliance Violation";
                StatusColor = new SolidColorBrush(Colors.Red);
                BorderColor = new SolidColorBrush(Color.FromRgb(239, 68, 68)); // Red

                var violations = string.Join("\n", _result.Violations.Select(v => $"• {v.Message}"));
                Message = $"Violations found:\n{violations}";
                DetailsButtonVisibility = Visibility.Visible;
            }

            // Element info
            var category = _element.Category?.Name ?? "Unknown";
            var name = _element.Name;
            ElementInfo = $"{category}: {name} (ID: {_element.Id})";
        }

        private void PositionWindow()
        {
            // Position at bottom-right of screen
            var screen = Screen.PrimaryScreen.WorkingArea;
            var screenWidth = screen.Width / 96.0 * SystemParameters.WorkArea.Width / Screen.PrimaryScreen.WorkingArea.Width;
            var screenHeight = screen.Height / 96.0 * SystemParameters.WorkArea.Height / Screen.PrimaryScreen.WorkingArea.Height;

            SlideFromX = screenWidth;
            SlideToX = screenWidth - Width - 20;

            Left = SlideFromX;
            Top = screenHeight - Height - 20;

            // Start slide-in animation
            var slideIn = (Storyboard)Resources["SlideIn"];
            slideIn.Begin(this);
        }

        private void StartAutoCloseTimer()
        {
            _autoCloseTimer = new DispatcherTimer
            {
                Interval = TimeSpan.FromSeconds(5)
            };
            _autoCloseTimer.Tick += (s, e) =>
            {
                _autoCloseTimer.Stop();
                CloseWithAnimation();
            };
            _autoCloseTimer.Start();
        }

        private void CloseWithAnimation()
        {
            var slideOut = (Storyboard)Resources["SlideOut"];
            slideOut.Completed += (s, e) => Close();
            slideOut.Begin(this);
        }

        private void CloseButton_Click(object sender, RoutedEventArgs e)
        {
            _autoCloseTimer?.Stop();
            CloseWithAnimation();
        }

        private void Border_MouseLeftButtonDown(object sender, System.Windows.Input.MouseButtonEventArgs e)
        {
            // Stop auto-close when user interacts
            _autoCloseTimer?.Stop();

            // Show details if there are violations
            if (!_result.IsCompliant)
            {
                ViewDetails_Click(sender, e);
            }
        }

        private void ViewDetails_Click(object sender, RoutedEventArgs e)
        {
            _autoCloseTimer?.Stop();

            // Show detailed dialog
            var detailsWindow = new ComplianceDetailsWindow(_element, _result);
            detailsWindow.ShowDialog();

            CloseWithAnimation();
        }

        // Properties for data binding
        public string Title
        {
            get => _title;
            set { _title = value; OnPropertyChanged(); }
        }

        public string ElementInfo
        {
            get => _elementInfo;
            set { _elementInfo = value; OnPropertyChanged(); }
        }

        public string Message
        {
            get => _message;
            set { _message = value; OnPropertyChanged(); }
        }

        public SolidColorBrush StatusColor
        {
            get => _statusColor;
            set { _statusColor = value; OnPropertyChanged(); }
        }

        public SolidColorBrush BorderColor
        {
            get => _borderColor;
            set { _borderColor = value; OnPropertyChanged(); }
        }

        public Visibility DetailsButtonVisibility
        {
            get => _detailsButtonVisibility;
            set { _detailsButtonVisibility = value; OnPropertyChanged(); }
        }

        public double SlideFromX { get; set; }
        public double SlideToX { get; set; }

        public event PropertyChangedEventHandler PropertyChanged;

        protected void OnPropertyChanged([CallerMemberName] string propertyName = null)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
        }
    }

    /// <summary>
    /// Detailed compliance results window
    /// </summary>
    public class ComplianceDetailsWindow : Window
    {
        public ComplianceDetailsWindow(Element element, ComplianceResult result)
        {
            Title = "Compliance Details";
            Width = 600;
            Height = 400;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;

            var scrollViewer = new System.Windows.Controls.ScrollViewer
            {
                VerticalScrollBarVisibility = System.Windows.Controls.ScrollBarVisibility.Auto,
                Padding = new Thickness(15)
            };

            var stackPanel = new System.Windows.Controls.StackPanel();

            // Element info
            stackPanel.Children.Add(new System.Windows.Controls.TextBlock
            {
                Text = $"Element: {element.Category?.Name} - {element.Name}",
                FontWeight = FontWeights.Bold,
                FontSize = 16,
                Margin = new Thickness(0, 0, 0, 15)
            });

            // Violations
            if (result.Violations.Count > 0)
            {
                stackPanel.Children.Add(new System.Windows.Controls.TextBlock
                {
                    Text = "Violations:",
                    FontWeight = FontWeights.Bold,
                    FontSize = 14,
                    Foreground = new SolidColorBrush(Colors.Red),
                    Margin = new Thickness(0, 0, 0, 10)
                });

                foreach (var violation in result.Violations)
                {
                    var violationPanel = new System.Windows.Controls.Border
                    {
                        BorderBrush = new SolidColorBrush(Colors.Red),
                        BorderThickness = new Thickness(1),
                        Padding = new Thickness(10),
                        Margin = new Thickness(0, 0, 0, 10),
                        Background = new SolidColorBrush(Color.FromRgb(254, 242, 242))
                    };

                    var violationStack = new System.Windows.Controls.StackPanel();
                    violationStack.Children.Add(new System.Windows.Controls.TextBlock
                    {
                        Text = $"{violation.Code} - {violation.Severity}",
                        FontWeight = FontWeights.Bold
                    });
                    violationStack.Children.Add(new System.Windows.Controls.TextBlock
                    {
                        Text = violation.Message,
                        TextWrapping = TextWrapping.Wrap,
                        Margin = new Thickness(0, 5, 0, 0)
                    });

                    if (!string.IsNullOrEmpty(violation.Regulation))
                    {
                        violationStack.Children.Add(new System.Windows.Controls.TextBlock
                        {
                            Text = $"Regulation: {violation.Regulation}",
                            FontStyle = FontStyles.Italic,
                            Margin = new Thickness(0, 5, 0, 0)
                        });
                    }

                    if (!string.IsNullOrEmpty(violation.SuggestedFix))
                    {
                        violationStack.Children.Add(new System.Windows.Controls.TextBlock
                        {
                            Text = $"Suggested fix: {violation.SuggestedFix}",
                            Foreground = new SolidColorBrush(Colors.DarkGreen),
                            Margin = new Thickness(0, 5, 0, 0)
                        });
                    }

                    violationPanel.Child = violationStack;
                    stackPanel.Children.Add(violationPanel);
                }
            }

            // Warnings
            if (result.Warnings.Count > 0)
            {
                stackPanel.Children.Add(new System.Windows.Controls.TextBlock
                {
                    Text = "Warnings:",
                    FontWeight = FontWeights.Bold,
                    FontSize = 14,
                    Foreground = new SolidColorBrush(Colors.Orange),
                    Margin = new Thickness(0, 15, 0, 10)
                });

                foreach (var warning in result.Warnings)
                {
                    var warningPanel = new System.Windows.Controls.Border
                    {
                        BorderBrush = new SolidColorBrush(Colors.Orange),
                        BorderThickness = new Thickness(1),
                        Padding = new Thickness(10),
                        Margin = new Thickness(0, 0, 0, 10),
                        Background = new SolidColorBrush(Color.FromRgb(255, 251, 235))
                    };

                    var warningStack = new System.Windows.Controls.StackPanel();
                    warningStack.Children.Add(new System.Windows.Controls.TextBlock
                    {
                        Text = warning.Message,
                        TextWrapping = TextWrapping.Wrap
                    });

                    warningPanel.Child = warningStack;
                    stackPanel.Children.Add(warningPanel);
                }
            }

            scrollViewer.Content = stackPanel;
            Content = scrollViewer;
        }
    }
}
