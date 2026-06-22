# NVIDIA Driver Extractor & Custom Setup Script
# Requires Administrator privileges

param(
    [string]$DriverInstaller = "474.82-desktop-win10-win11-64bit-international-dch-whql.exe",
    [string]$ExtractPath = "nvidia_driver_extracted",
    [switch]$Install,
    [switch]$ExtractOnly
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallerPath = Join-Path $ScriptDir $DriverInstaller
$FullExtractPath = Join-Path $ScriptDir $ExtractPath

function Test-Admin {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host "ERROR: This script requires Administrator privileges. Please run as Administrator." -ForegroundColor Red
    exit 1
}

# Step 1: Extract driver
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  NVIDIA Driver Extractor" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

if (-not (Test-Path $InstallerPath)) {
    throw "Driver installer not found at: $InstallerPath"
}

Write-Host "Using driver installer: $InstallerPath" -ForegroundColor Yellow

# Try to find existing extract locations (NVIDIA uses temp dirs)
$possibleExtractPaths = @(
    $FullExtractPath,
    "C:\NVIDIA\DisplayDriver",
    "$env:TEMP\NVIDIA"
)

# Check if driver is already extracted somewhere
$foundExtractPath = $null
foreach ($path in $possibleExtractPaths) {
    if (Test-Path $path) {
        $setupExe = Get-ChildItem -Path $path -Recurse -Filter "setup.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($setupExe) {
            $foundExtractPath = $path
            Write-Host "Found already extracted driver at: $foundExtractPath" -ForegroundColor Green
            break
        }
    }
}

if (-not $foundExtractPath) {
    Write-Host "Extracting driver (this may take 5-10 minutes)..." -ForegroundColor Yellow
    
    # Clean target directory
    if (Test-Path $FullExtractPath) {
        Write-Host "Cleaning existing extraction directory..." -ForegroundColor Yellow
        Remove-Item $FullExtractPath -Recurse -Force -ErrorAction SilentlyContinue
    }
    
    # Start extraction
    $process = Start-Process -FilePath $InstallerPath -ArgumentList "-s -d `"$FullExtractPath`"" -PassThru -Wait
    
    # Wait and verify extraction
    Write-Host "Waiting for extraction to complete..." -ForegroundColor Gray
    Start-Sleep -Seconds 10
    
    # Verify extraction
    if (-not (Test-Path $FullExtractPath)) {
        Write-Host "Warning: Target path not found. Checking common NVIDIA temp locations..." -ForegroundColor Yellow
        
        # Check other common paths
        foreach ($path in $possibleExtractPaths) {
            if (Test-Path $path) {
                $setupExe = Get-ChildItem -Path $path -Recurse -Filter "setup.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($setupExe) {
                    $foundExtractPath = Split-Path -Parent $setupExe.FullName
                    Write-Host "Found extracted driver at: $foundExtractPath" -ForegroundColor Green
                    break
                }
            }
        }
    } else {
        $foundExtractPath = $FullExtractPath
    }
} else {
    $FullExtractPath = $foundExtractPath
}

if (-not $foundExtractPath -and -not (Test-Path $FullExtractPath)) {
    Write-Host "Warning: Could not verify extraction path. Continuing anyway..." -ForegroundColor Yellow
} else {
    Write-Host "Driver extracted successfully to: $FullExtractPath" -ForegroundColor Green
}

if ($ExtractOnly) {
    Write-Host "`n✅ Extraction complete. Skipping installation." -ForegroundColor Green
    exit 0
}

# Step 2: Installation
if ($Install) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  Installing NVIDIA Driver" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan

    # Find setup.exe in extracted files
    $SetupExe = Get-ChildItem -Path $FullExtractPath -Recurse -Filter "setup.exe" | Select-Object -First 1
    if (-not $SetupExe) {
        throw "setup.exe not found in extracted files"
    }

    Write-Host "Installing driver (this may take 10-30 minutes)..." -ForegroundColor Yellow
    Write-Host "Your screen may flicker multiple times during this process." -ForegroundColor Magenta

    # Install driver with clean install and DCH
    Start-Process -FilePath $SetupExe.FullName -ArgumentList "-s -clean" -Wait

    Write-Host "`n✅ Driver installation complete!" -ForegroundColor Green

    # Step 3: Post-install OptiMas setup
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  Running OptiMas Post-Install Setup" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan

    $OptiMasSetup = Join-Path $ScriptDir "post_driver_install.ps1"
    if (Test-Path $OptiMasSetup) {
        Write-Host "Running OptiMas post-install..." -ForegroundColor Yellow
        & powershell -ExecutionPolicy Bypass -File $OptiMasSetup
    } else {
        Write-Host "Warning: OptiMas post-install script not found." -ForegroundColor Yellow
    }
}

Write-Host "`n✅ All operations complete!" -ForegroundColor Green
Write-Host "Extracted files at: $FullExtractPath"
Write-Host "`nNext steps:"
Write-Host "1. If you didn't install automatically, run setup.exe from the extracted folder."
Write-Host "2. Then install OptiMas service: .\install_service.ps1"
