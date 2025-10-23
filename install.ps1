# Qoder CLI Installation Script for Windows (PowerShell)
# Version 2.0.0

param(
    [switch]$Force = $false,
    [switch]$Verbose = $false,
    [switch]$Help = $false
)

# Show help message
function Show-Usage {
    Write-Host "Qoder CLI Installation Script for Windows" -ForegroundColor Green
    Write-Host ""
    Write-Host "USAGE:" -ForegroundColor Yellow
    Write-Host "  .\install.ps1"
    Write-Host "  .\install.ps1 -Force"
    Write-Host "  .\install.ps1 -Verbose"
    Write-Host ""
    Write-Host "OPTIONS:" -ForegroundColor Yellow
    Write-Host "  -Force                Force overwrite existing installation"
    Write-Host "  -Verbose              Show detailed installation information"
    Write-Host "  -Help                 Show this help message"
    Write-Host ""
    Write-Host "EXAMPLES:" -ForegroundColor Yellow
    Write-Host "  # Standard installation"
    Write-Host "  .\install.ps1"
    Write-Host ""
    Write-Host "  # Force reinstall with verbose output"
    Write-Host "  .\install.ps1 -Force -Verbose"
}

# Check if help is requested
if ($Help) {
    Show-Usage
    exit 0
}

# Global variables
$BASE_URL = "https://qoder-ide.oss-ap-southeast-1.aliyuncs.com/qodercli"
$INSTALL_DIR = Join-Path $env:USERPROFILE ".qoder"
$BIN_DIR = Join-Path $INSTALL_DIR "bin\qodercli"
$LOCAL_BIN_DIR = Join-Path $env:USERPROFILE ".local\bin"
$BIN_LINK = Join-Path $LOCAL_BIN_DIR "qodercli.exe"

# Verbose output function
function Write-VerboseOutput {
    param([string]$Message)
    if ($Verbose) {
        Write-Host "==> $Message" -ForegroundColor Cyan
    }
}

# Detect OS architecture
function Get-OSArch {
    $arch = $env:PROCESSOR_ARCHITECTURE
    if ($arch -eq "AMD64") {
        return "windows", "amd64"
    } elseif ($arch -eq "ARM64") {
        return "windows", "arm64"
    } else {
        return "windows", "386"
    }
}

# Download file with retry logic
function Invoke-Download {
    param(
        [string]$Url,
        [string]$Output
    )
    
    $maxRetries = 3
    $retryCount = 0
    
    while ($retryCount -lt $maxRetries) {
        if ($retryCount -gt 0) {
            Write-Warning "Retry attempt $retryCount/$maxRetries..."
            Start-Sleep -Seconds 2
        }
        
        try {
            Write-VerboseOutput "Downloading $Url"
            $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -Uri $Url -OutFile $Output -UseBasicParsing -TimeoutSec 300
            return
        } catch {
            Write-Warning "Download failed: $($_.Exception.Message)"
            Remove-Item $Output -Force -ErrorAction SilentlyContinue
            $retryCount++
        }
    }
    
    Write-Error "Failed to download $Url after $maxRetries attempts"
    exit 1
}

# Check if command exists
function Test-Command {
    param([string]$Command)
    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

# Install binary
function Install-Binary {
    param(
        [string]$BinName,
        [string]$Version,
        [string]$SourceDir
    )
    
    $versionBin = Join-Path $BIN_DIR "qodercli-$Version.exe"
    
    if (Test-Path $versionBin -PathType Leaf) {
        if (-not $Force) {
            Write-Error "Version $Version already exists. Use -Force to overwrite."
            exit 1
        } else {
            Write-VerboseOutput "Overwriting existing version $Version"
        }
    }
    
    Write-VerboseOutput "Installing to $BIN_DIR"
    
    # Create BIN_DIR
    if (-not (Test-Path $BIN_DIR)) {
        try {
            New-Item -ItemType Directory -Path $BIN_DIR -Force | Out-Null
        } catch {
            Write-Error "Cannot create installation directory $BIN_DIR"
            exit 1
        }
    }
    
    # Copy binary
    $sourceBin = Join-Path $SourceDir $BinName
    try {
        Copy-Item $sourceBin $versionBin -Force
        Write-VerboseOutput "Installed to: $versionBin"
    } catch {
        Write-Error "Failed to copy binary to $versionBin"
        exit 1
    }
    
    # Set executable permission (not needed on Windows, but keeping for consistency)
    try {
        # On Windows, we ensure it's not read-only
        $file = Get-Item $versionBin
        $file.Attributes = $file.Attributes -band -bnot [System.IO.FileAttributes]::ReadOnly
    } catch {
        Write-Warning "Failed to set file attributes on $versionBin"
    }
    
    # Create installation source marker
    $sourceFile = Join-Path $BIN_DIR ".qodercli-install-resource"
    try {
        "powershell-script" | Out-File -FilePath $sourceFile -Encoding UTF8
        Write-VerboseOutput "Created install source marker: $sourceFile"
    } catch {
        Write-VerboseOutput "Warning: Failed to create install source marker"
    }
    
    # Create LOCAL_BIN_DIR
    if (-not (Test-Path $LOCAL_BIN_DIR)) {
        try {
            New-Item -ItemType Directory -Path $LOCAL_BIN_DIR -Force | Out-Null
        } catch {
            Write-Warning "Cannot create local bin directory $LOCAL_BIN_DIR"
            Write-Host "Binary installed at: $versionBin" -ForegroundColor Yellow
            Write-Host "You may need to manually create the directory and symlink" -ForegroundColor Yellow
            return
        }
    }
    
    # Remove existing link
    if (Test-Path $BIN_LINK) {
        Remove-Item $BIN_LINK -Force -ErrorAction SilentlyContinue
    }
    
    # Create symlink or copy
    try {
        # Try to create symbolic link (requires admin rights or Developer Mode)
        cmd /c mklink "$BIN_LINK" "$versionBin" 2>$null | Out-Null
        if (Test-Path $BIN_LINK) {
            Write-VerboseOutput "Created symlink: $BIN_LINK -> $versionBin"
        } else {
            throw "Symlink creation failed"
        }
    } catch {
        # Fallback to copy
        try {
            Copy-Item $versionBin $BIN_LINK -Force
            Write-VerboseOutput "Created copy: $BIN_LINK"
        } catch {
            Write-Warning "Failed to create binary link at $BIN_LINK"
            Write-Host "Binary available at: $versionBin" -ForegroundColor Yellow
            Write-Host "You may need to manually add $BIN_DIR to your PATH" -ForegroundColor Yellow
        }
    }
}

# Add to PATH
function Add-ToPath {
    $pathToAdd = $LOCAL_BIN_DIR
    $currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    
    if ($currentPath -like "*$pathToAdd*") {
        Write-VerboseOutput "$pathToAdd already in PATH"
        return
    }
    
    if ($currentPath) {
        $newPath = "$currentPath;$pathToAdd"
    } else {
        $newPath = $pathToAdd
    }
    
    try {
        [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
        Write-Host "==> Added $pathToAdd to PATH" -ForegroundColor Green
        Write-Host "==> Please restart your terminal or run 'refreshenv' to apply changes" -ForegroundColor Yellow
    } catch {
        Write-Warning "Failed to add $pathToAdd to PATH"
        Write-Host "Please manually add $pathToAdd to your PATH environment variable" -ForegroundColor Yellow
    }
}

# Main installation function
function Install-QoderCLI {
    Write-Host "Starting Qoder CLI installation..." -ForegroundColor Green
    
    # Create temporary directory
    $tmpDir = [System.IO.Path]::GetTempPath() + "qoder-install-" + [System.IO.Path]::GetRandomFileName()
    New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
    Write-VerboseOutput "Created temporary directory: $tmpDir"
    
    try {
        # Detect OS and architecture
        $os, $arch = Get-OSArch
        Write-VerboseOutput "Detected platform: $os/$arch"
        
        # Fetch manifest
        $manifestUrl = "$BASE_URL/channels/manifest.json"
        $manifestFile = Join-Path $tmpDir "qoder-manifest.json"
        
        Write-VerboseOutput "Fetching release information..."
        Invoke-Download $manifestUrl $manifestFile
        
        # Parse manifest
        $manifest = Get-Content $manifestFile | ConvertFrom-Json
        
        # Get latest version
        $version = $manifest.latest
        if (-not $version) {
            Write-Error "Cannot parse version from manifest"
            exit 1
        }
        Write-VerboseOutput "Latest version: $version"
        
        # Find matching file entry
        $entry = $manifest.files | Where-Object { $_.os -eq $os -and $_.arch -eq $arch }
        if (-not $entry) {
            Write-Error "No matching release found in manifest for $os/$arch"
            exit 1
        }
        Write-VerboseOutput "Found binary for $os/$arch"
        
        # Get download URL and checksum
        $downloadUrl = $entry.url
        $checksum = $entry.sha256
        
        if (-not $downloadUrl) {
            Write-Error "Missing download URL in manifest for $os/$arch"
            exit 1
        }
        
        Write-VerboseOutput "Downloading Qoder CLI $version..."
        
        $archiveFilename = Split-Path $downloadUrl -Leaf
        $archiveFile = Join-Path $tmpDir $archiveFilename
        
        # Check required extraction tool
        if ($archiveFilename -like "*.zip") {
            if (-not (Test-Command "Expand-Archive")) {
                Write-Error "Expand-Archive command not available"
                exit 1
            }
        } elseif ($archiveFilename -like "*.tar.gz" -or $archiveFilename -like "*.tgz") {
            Write-Error "Tar.gz extraction not supported in this script"
            exit 1
        } else {
            Write-Error "Unsupported archive format: $archiveFilename"
            exit 1
        }
        
        # Download file
        Invoke-Download $downloadUrl $archiveFile
        
        # Verify file was downloaded
        if (-not (Test-Path $archiveFile)) {
            Write-Error "Downloaded file $archiveFile not found"
            exit 1
        }
        
        $fileSize = (Get-Item $archiveFile).Length
        if ($fileSize -lt 1024) {
            Write-Error "Downloaded file is too small ($fileSize bytes), likely corrupted"
            exit 1
        }
        Write-VerboseOutput "Downloaded file size: $fileSize bytes"
        
        # Verify checksum
        if ($checksum) {
            Write-VerboseOutput "Verifying checksum..."
            $actualChecksum = Get-FileHash $archiveFile -Algorithm SHA256 | Select-Object -ExpandProperty Hash
            if ($actualChecksum -ne $checksum.ToUpper()) {
                Write-Error "Checksum verification failed"
                Write-Host "Expected: $checksum" -ForegroundColor Red
                Write-Host "Actual:   $actualChecksum" -ForegroundColor Red
                exit 1
            }
            Write-VerboseOutput "Checksum verified"
        }
        
        # Extract archive
        Write-VerboseOutput "Extracting archive..."
        $extractDir = Join-Path $tmpDir "extract"
        New-Item -ItemType Directory -Path $extractDir -Force | Out-Null
        
        if ($archiveFilename -like "*.zip") {
            Expand-Archive -Path $archiveFile -DestinationPath $extractDir -Force
        }
        
        $binName = "qodercli.exe"
        $extractedBin = Get-ChildItem -Path $extractDir -Recurse -Name $binName -ErrorAction SilentlyContinue
        if (-not $extractedBin) {
            Write-Error "Binary $binName not found in archive"
            exit 1
        }
        
        $extractedBinPath = Join-Path $extractDir $extractedBin
        $tempBinDir = Join-Path $tmpDir "bin"
        New-Item -ItemType Directory -Path $tempBinDir -Force | Out-Null
        Move-Item $extractedBinPath (Join-Path $tempBinDir $binName) -Force
        
        Install-Binary $binName $version $tempBinDir
        
        # Add to PATH
        Add-ToPath
        
        Write-Host ""
        Write-Host "🎉 Qoder CLI $version installed successfully!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Get started: qodercli --help" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Note: You may need to restart your terminal for the PATH changes to take effect." -ForegroundColor Yellow
        
    } finally {
        # Cleanup
        if (Test-Path $tmpDir) {
            Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

# Run installation
Install-QoderCLI