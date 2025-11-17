@echo off
REM Build script for ProjektantCopilot Revit Plugin

echo ================================
echo ProjektantCopilot Build Script
echo ================================
echo.

REM Set paths
set REVIT_ADDINS=%AppData%\Autodesk\Revit\Addins\2024
set PROJECT_DIR=%~dp0
set BUILD_CONFIG=Release

echo Project Directory: %PROJECT_DIR%
echo Target Directory: %REVIT_ADDINS%
echo Build Configuration: %BUILD_CONFIG%
echo.

REM Clean previous build
echo [1/4] Cleaning previous build...
dotnet clean
if errorlevel 1 (
    echo ERROR: Clean failed
    pause
    exit /b 1
)

REM Restore NuGet packages
echo.
echo [2/4] Restoring NuGet packages...
dotnet restore
if errorlevel 1 (
    echo ERROR: Restore failed
    pause
    exit /b 1
)

REM Build project
echo.
echo [3/4] Building project...
dotnet build -c %BUILD_CONFIG%
if errorlevel 1 (
    echo ERROR: Build failed
    pause
    exit /b 1
)

REM Install to Revit
echo.
echo [4/4] Installing to Revit addins folder...

REM Create addins directory if it doesn't exist
if not exist "%REVIT_ADDINS%" (
    echo Creating addins directory...
    mkdir "%REVIT_ADDINS%"
)

REM Copy files
echo Copying DLL...
copy /Y "bin\%BUILD_CONFIG%\ProjektantCopilot.dll" "%REVIT_ADDINS%\"

echo Copying manifest...
copy /Y "ProjektantCopilot.addin" "%REVIT_ADDINS%\"

echo Copying dependencies...
copy /Y "bin\%BUILD_CONFIG%\RestSharp.dll" "%REVIT_ADDINS%\"
copy /Y "bin\%BUILD_CONFIG%\Serilog.dll" "%REVIT_ADDINS%\"
copy /Y "bin\%BUILD_CONFIG%\Serilog.Sinks.*.dll" "%REVIT_ADDINS%\"
copy /Y "bin\%BUILD_CONFIG%\Newtonsoft.Json.dll" "%REVIT_ADDINS%\"

echo.
echo ================================
echo Build completed successfully!
echo ================================
echo.
echo Plugin files installed to: %REVIT_ADDINS%
echo.
echo Next steps:
echo 1. Close Revit if it's running
echo 2. Start Revit 2024
echo 3. Look for ProjektantCopilot tab in the ribbon
echo 4. Configure settings with your backend URL
echo.

pause
