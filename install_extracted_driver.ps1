# Direct NVIDIA Driver Installer
# Uses already extracted driver!
# Just runs setup.exe directly!

param(
    [switch]$CleanInstall,
    [switch]$NoRestart
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DriverDir = Join-Path $ScriptDir "driver_extracted"
$SetupPath = Join-Path $DriverDir "setup.exe"

function Test-Admin {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host "ERROR: This script requires Administrator privileges! Please run as Administrator!" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $SetupPath)) {
    Write-Host "ERROR: setup.exe not found at $SetupPath!" -ForegroundColor Red
    Write-Host "   Make sure the driver is extracted first!" -ForegroundColor Yellow
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  OptiMas NVIDIA Driver Installer" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Using driver from: $DriverDir" -ForegroundColor Green
Write-Host "Setup: $SetupPath`n" -ForegroundColor Green

# Build arguments
$Args = @("-s") # -s = silent
if ($CleanInstall) {
    Write-Host "Performing CLEAN install (removes old drivers first)" -ForegroundColor Yellow
    $Args += "-clean"
}

if ($NoRestart) {
    Write-Host "Will NOT auto-restart if needed" -ForegroundColor Yellow
    $Args += "-noreboot"
}

Write-Host "`nStarting NVIDIA Driver Installation NOW!`n" -ForegroundColor Magenta
Write-Host "   This can take 10-30 minutes! Your screen will flicker!" -ForegroundColor Cyan
Write-Host "   Press Ctrl+C to cancel, or wait...`n" -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Start installation
Start-Process -FilePath $SetupPath -ArgumentList $Args -Wait

Write-Host "`n✅ NVIDIA Driver install complete!`n" -ForegroundColor Green

Write-Host "Next steps (optional):" -ForegroundColor Cyan
Write-Host "  1. Restart your PC if needed!"
Write-Host "  2. Run .\install_service.ps1 to install OptiMas as a Windows service!"
