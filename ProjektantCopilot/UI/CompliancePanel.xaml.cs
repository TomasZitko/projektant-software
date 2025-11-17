using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Autodesk.Revit.DB;
using ProjektantCopilot.Models;

namespace ProjektantCopilot.UI
{
    public partial class CompliancePanel : UserControl, INotifyPropertyChanged
    {
        private int _totalChecked;
        private int _compliantCount;
        private int _violationCount;
        private ObservableCollection<ComplianceResultViewModel> _results;

        public CompliancePanel()
        {
            InitializeComponent();
            DataContext = this;

            Results = new ObservableCollection<ComplianceResultViewModel>();
        }

        public int TotalChecked
        {
            get => _totalChecked;
            set { _totalChecked = value; OnPropertyChanged(); }
        }

        public int CompliantCount
        {
            get => _compliantCount;
            set { _compliantCount = value; OnPropertyChanged(); }
        }

        public int ViolationCount
        {
            get => _violationCount;
            set { _violationCount = value; OnPropertyChanged(); }
        }

        public ObservableCollection<ComplianceResultViewModel> Results
        {
            get => _results;
            set { _results = value; OnPropertyChanged(); }
        }

        public void AddResult(Element element, ComplianceResult result)
        {
            var viewModel = new ComplianceResultViewModel
            {
                Element = element,
                Result = result,
                ElementName = $"{element.Category?.Name}: {element.Name}",
                ElementId = $"ID: {element.Id}",
                Summary = result.IsCompliant
                    ? "Compliant - No violations"
                    : $"{result.Violations.Count} violation(s) found",
                StatusBrush = result.IsCompliant
                    ? new SolidColorBrush(Colors.Green)
                    : new SolidColorBrush(Colors.Red),
                SummaryBrush = result.IsCompliant
                    ? new SolidColorBrush(Color.FromRgb(22, 163, 74))
                    : new SolidColorBrush(Color.FromRgb(220, 38, 38)),
                BackgroundBrush = result.IsCompliant
                    ? new SolidColorBrush(Colors.White)
                    : new SolidColorBrush(Color.FromRgb(254, 242, 242))
            };

            Results.Insert(0, viewModel); // Add to top

            // Update stats
            TotalChecked = Results.Count;
            CompliantCount = Results.Count(r => r.Result.IsCompliant);
            ViolationCount = Results.Count(r => !r.Result.IsCompliant);
        }

        public void ClearResults()
        {
            Results.Clear();
            TotalChecked = 0;
            CompliantCount = 0;
            ViolationCount = 0;
        }

        private void ViewDetails_Click(object sender, RoutedEventArgs e)
        {
            var button = sender as Button;
            var viewModel = button?.Tag as ComplianceResultViewModel;

            if (viewModel != null)
            {
                var detailsWindow = new ComplianceDetailsWindow(viewModel.Element, viewModel.Result);
                detailsWindow.ShowDialog();
            }
        }

        private void CheckSelected_Click(object sender, RoutedEventArgs e)
        {
            // Trigger manual check command
            App.RunComplianceCheck();
        }

        private void CheckAll_Click(object sender, RoutedEventArgs e)
        {
            // Trigger check all command
            App.RunComplianceCheckAll();
        }

        private void Settings_Click(object sender, RoutedEventArgs e)
        {
            var settingsDialog = new SettingsDialog();
            settingsDialog.ShowDialog();
        }

        public event PropertyChangedEventHandler PropertyChanged;

        protected void OnPropertyChanged([CallerMemberName] string propertyName = null)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
        }
    }

    public class ComplianceResultViewModel
    {
        public Element Element { get; set; }
        public ComplianceResult Result { get; set; }
        public string ElementName { get; set; }
        public string ElementId { get; set; }
        public string Summary { get; set; }
        public Brush StatusBrush { get; set; }
        public Brush SummaryBrush { get; set; }
        public Brush BackgroundBrush { get; set; }
    }
}
