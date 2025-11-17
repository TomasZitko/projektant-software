# ProjektantCopilot - Revit Plugin

Production-grade Autodesk Revit 2024 plugin for real-time building code compliance monitoring.

## Features

- **Real-time Monitoring**: Automatically checks elements as you create or modify them
- **Monitored Elements**: Walls, Doors, Windows, Floors, Ceilings
- **Smart Notifications**: Toast notifications with compliance status
- **Detailed Reports**: Comprehensive violation details with suggested fixes
- **Dockable Panel**: Track all compliance checks in one place
- **Manual Checks**: Run compliance checks on selected or all elements

## Architecture

```
ProjektantCopilot/
├── App.cs                          # Main IExternalApplication entry point
├── Commands/
│   └── ComplianceCheckCommand.cs   # Manual compliance check command
├── Services/
│   ├── ApiClient.cs                # REST API client (RestSharp)
│   ├── ComplianceUpdater.cs        # IUpdater for real-time monitoring
│   ├── ContextExtractor.cs         # Extract element data
│   └── LogService.cs               # Logging (Serilog)
├── Models/
│   ├── ElementContext.cs           # Element context DTO
│   └── ComplianceResult.cs         # Compliance result DTO
└── UI/
    ├── CompliancePanel.xaml        # Dockable panel
    ├── NotificationPopup.xaml      # Toast notification
    └── SettingsDialog.xaml         # Settings dialog
```

## Prerequisites

- **Revit 2024** or later
- **.NET Framework 4.8**
- **Backend API** running (see backend setup)
- **Visual Studio 2019/2022** (for development)

## Installation

### Option 1: Pre-built Binary

1. Download the latest release from GitHub
2. Extract the ZIP file
3. Copy `ProjektantCopilot.dll` and `ProjektantCopilot.addin` to:
   ```
   %AppData%\Autodesk\Revit\Addins\2024\
   ```
4. Copy all dependency DLLs to the same folder
5. Restart Revit

### Option 2: Build from Source

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-org/projektant-software.git
   cd projektant-software/ProjektantCopilot
   ```

2. **Update Revit API paths** in `ProjektantCopilot.csproj`:
   ```xml
   <Reference Include="RevitAPI">
     <HintPath>C:\Program Files\Autodesk\Revit 2024\RevitAPI.dll</HintPath>
   </Reference>
   ```

3. **Restore NuGet packages**:
   ```bash
   dotnet restore
   ```

4. **Build the project**:
   ```bash
   dotnet build -c Release
   ```

5. **Install** (automatic via post-build event or manual):
   ```bash
   copy bin\Release\*.dll "%AppData%\Autodesk\Revit\Addins\2024\"
   copy bin\Release\*.addin "%AppData%\Autodesk\Revit\Addins\2024\"
   ```

6. **Restart Revit**

## Configuration

### First-time Setup

1. Launch Revit
2. Look for **ProjektantCopilot** tab in the ribbon
3. Click **Settings** button
4. Configure:
   - **Backend URL**: `http://localhost:8000` (or your backend URL)
   - **API Key**: Your API key (if required)
   - **Monitoring**: Enable real-time monitoring
   - **Categories**: Select which elements to monitor
   - **Notifications**: Configure toast notifications

5. Click **Test Connection** to verify
6. Click **Save**

### Configuration File

Settings are stored in:
```
%AppData%\Local\<AppName>\user.config
```

You can also manually edit `App.config`:
```xml
<appSettings>
  <add key="BackendUrl" value="http://localhost:8000" />
  <add key="ApiKey" value="your-api-key" />
  <add key="EnableMonitoring" value="true" />
  <add key="ShowNotifications" value="true" />
  <add key="NotifyOnlyViolations" value="true" />
  <add key="MonitorWalls" value="true" />
  <add key="MonitorDoors" value="true" />
  <add key="MonitorWindows" value="true" />
  <add key="MonitorFloors" value="true" />
  <add key="MonitorCeilings" value="true" />
</appSettings>
```

## Usage

### Real-time Monitoring

1. Open a Revit project
2. Enable monitoring in Settings
3. Create or modify elements (walls, doors, etc.)
4. Watch for toast notifications in bottom-right corner:
   - **Green**: Compliant ✓
   - **Red**: Violations found ✗

### Manual Compliance Check

1. **Check Selected Elements**:
   - Select one or more elements
   - Click **Check Compliance** in ribbon
   - View results in notification

2. **Check All Elements**:
   - Click **Check Compliance** without selection
   - Choose "Check All"
   - View summary report

### Compliance Panel

1. Click **Show Panel** in ribbon
2. Dockable panel appears on the right
3. View all compliance checks:
   - Total checked
   - Compliant count
   - Violation count
   - Detailed list of results

4. Click **View Details** on any result for full information

### Understanding Results

**Compliant Element**:
```
✓ Wall: Basic Wall - Generic 200mm (ID: 12345)
  Compliant - No violations
```

**Non-compliant Element**:
```
✗ Wall: Fire Wall - 300mm (ID: 67890)
  2 violation(s) found:
  • FIRE_RATING_INSUFFICIENT - Critical
    Fire rating must be at least EI90 for this wall type
    Regulation: ČSN 73 0802, §4.2.1
    Suggested fix: Change wall type to EI90 rated wall
```

## API Integration

### Request Format

The plugin sends POST requests to `/api/v1/compliance/check`:

```json
{
  "element_id": "12345",
  "element_type": "Wall",
  "category": "Walls",
  "properties": {
    "width_mm": 300,
    "height_mm": 3000,
    "fire_rating": "EI60",
    "structural": true
  },
  "context": {
    "room_type": "Bedroom",
    "room_name": "Room 101",
    "building_type": "Residential"
  },
  "location": {
    "level": "Level 1",
    "x": 10.5,
    "y": 20.3,
    "z": 0.0
  },
  "project_info": {
    "name": "Office Building",
    "building_type": "Commercial",
    "project_number": "2024-001"
  }
}
```

### Response Format

Expected response:

```json
{
  "is_compliant": false,
  "violations": [
    {
      "code": "FIRE_RATING_INSUFFICIENT",
      "severity": "Critical",
      "message": "Fire rating must be at least EI90",
      "regulation": "ČSN 73 0802, §4.2.1",
      "regulation_text": "Fire separation walls...",
      "suggested_fix": "Change to EI90 rated wall"
    }
  ],
  "warnings": [],
  "recommendations": [
    "Consider adding acoustic insulation"
  ],
  "checked_at": "2024-01-15T10:30:00Z",
  "check_id": "check_123456"
}
```

## Troubleshooting

### Plugin doesn't appear in Revit

1. Check Revit version (must be 2024)
2. Verify files in `%AppData%\Autodesk\Revit\Addins\2024\`
3. Check Revit error log: `%AppData%\Autodesk\Revit\Autodesk Revit 2024\Journals\`
4. Look for error messages in journal file

### Connection errors

1. Verify backend is running: `curl http://localhost:8000/health`
2. Check firewall settings
3. Test connection in Settings dialog
4. Review logs in `%AppData%\ProjektantCopilot\Logs\`

### Monitoring not working

1. Open Settings
2. Verify "Enable real-time monitoring" is checked
3. Check monitored categories are selected
4. Look for errors in log file

### View Logs

Logs are stored in:
```
%AppData%\ProjektantCopilot\Logs\plugin-YYYY-MM-DD.txt
```

Example:
```
2024-01-15 10:30:15.123 [INF] ProjektantCopilot logging initialized
2024-01-15 10:30:15.456 [INF] Services initialized successfully
2024-01-15 10:30:20.789 [INF] ComplianceUpdater triggered in document: Office Building
2024-01-15 10:30:20.890 [INF] Processing 1 modified elements
2024-01-15 10:30:21.234 [INF] Compliance check completed for element 12345: Compliant=false, Violations=2
```

## Development

### Building

```bash
# Debug build
dotnet build

# Release build
dotnet build -c Release

# Clean
dotnet clean
```

### Testing

1. Build the plugin
2. Launch Revit 2024
3. Open a test project
4. Create/modify elements
5. Verify in logs:
   ```
   tail -f "%AppData%\ProjektantCopilot\Logs\plugin-*.txt"
   ```

### Debugging

1. Set Revit.exe as startup program in Visual Studio:
   - Project Properties → Debug
   - Start external program: `C:\Program Files\Autodesk\Revit 2024\Revit.exe`

2. Set breakpoints
3. Press F5
4. Revit launches with debugger attached

## Known Limitations

- **Revit 2024 only** (can be adapted for other versions)
- **Windows only** (.NET Framework)
- **Single document** at a time (multi-document support planned)
- **Network required** for API calls (offline mode planned)

## Performance

- **Updater overhead**: <50ms per element change
- **API calls**: Asynchronous, non-blocking
- **Memory usage**: ~50MB base + ~10MB per 1000 elements cached
- **Log file rotation**: Daily, max 31 days

## Security

- **API keys**: Stored in user config (consider Windows Credential Manager)
- **HTTPS**: Recommended for production
- **Input validation**: All element data validated before API calls
- **Error handling**: Exceptions logged, never crash Revit

## Support

- **Documentation**: https://docs.projektant.io
- **Issues**: https://github.com/your-org/projektant-software/issues
- **Email**: support@projektant.io

## License

Proprietary - Copyright © 2024 Projektant Software

## Version History

### v1.0.0 (2024-01-15)
- Initial release
- Real-time monitoring for walls, doors, windows, floors, ceilings
- Toast notifications
- Dockable compliance panel
- Settings dialog
- Manual compliance checks

---

**Built with ❤️ by the Projektant team**
