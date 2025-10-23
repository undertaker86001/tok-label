@echo off
setlocal enabledelayedexpansion

echo Qoder CLI Installation Script for Windows
echo.

REM Check if PowerShell is available
where powershell >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: PowerShell is required but not found.
    echo Please install PowerShell to continue.
    echo.
    pause
    exit /b 1
)

REM Check if running from the correct directory
if not exist "%~dp0install.ps1" (
    echo Error: install.ps1 not found in the current directory.
    echo Please run this script from the same directory as install.ps1
    echo.
    pause
    exit /b 1
)

REM Parse command line arguments
set FORCE=
set VERBOSE=

:parse_args
if "%1"=="" goto end_parse
if "%1"=="-h" goto show_help
if "%1"=="--help" goto show_help
if "%1"=="-force" set FORCE=-Force
if "%1"=="--force" set FORCE=-Force
if "%1"=="-verbose" set VERBOSE=-Verbose
if "%1"=="--verbose" set VERBOSE=-Verbose
shift
goto parse_args

:end_parse

REM Run the PowerShell installation script
echo Starting Qoder CLI installation...
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0install.ps1" %FORCE% %VERBOSE%
if %errorlevel% neq 0 (
    echo.
    echo Installation failed with error code %errorlevel%.
    echo.
    pause
    exit /b %errorlevel%
)

echo.
echo Installation completed successfully!
echo.
echo To use Qoder CLI, please restart your command prompt or PowerShell
echo to ensure PATH changes take effect.
echo.
echo Then run: qodercli --help
echo.
pause

exit /b 0

:show_help
echo Qoder CLI Installation Script for Windows
echo.
echo USAGE:
echo   install.bat
echo   install.bat --force
echo   install.bat --verbose
echo.
echo OPTIONS:
echo   --force                Force overwrite existing installation
echo   --verbose              Show detailed installation information
echo   -h, --help            Show this help message
echo.
echo EXAMPLES:
echo   REM Standard installation
echo   install.bat
echo.
echo   REM Force reinstall with verbose output
echo   install.bat --force --verbose
echo.
pause
exit /b 0