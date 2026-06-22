# OptiMas Windows Service Installer
# Requires Administrator privileges
# Requires Python 3.10+ in PATH or venv

param(
    [switch]$Uninstall,
    [string]$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Multiple mirrors for NSSM
$NssmUrls = @(
    "https://github.com/kirill-kouznetsov/nssm/releases/download/2.24/nssm-2.24.zip",
    "https://nssm.cc/release/nssm-2.24.zip"
)
$NssmZip = Join-Path $ScriptDir "nssm.zip"
$NssmDir = Join-Path $ScriptDir "nssm"
$NssmExe = Join-Path $NssmDir "nssm-2.24\win64\nssm.exe"
$ServiceName = "OptiMasHybridEngine"
$ServiceDisplayName = "OptiMas Hybrid GPU Coordination Engine"
$DaemonScript = Join-Path $ScriptDir "optimas_daemon.py"

function Test-Admin {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-Python {
    if ($PythonPath -and (Test-Path $PythonPath)) {
        return $PythonPath
    }
    
    # Check if we're in a venv
    $venvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }
    
    # Try system Python
    try {
        return (Get-Command python -ErrorAction Stop).Source
    } catch {
        throw "Python not found. Please install Python 3.10+ or specify -PythonPath."
    }
}

if (-not (Test-Admin)) {
    Write-Host "ERROR: This script requires Administrator privileges. Please run as Administrator." -ForegroundColor Red
    exit 1
}

# Uninstall existing service
if ($Uninstall) {
    Write-Host "Uninstalling OptiMas service..." -ForegroundColor Yellow
    try {
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        & $NssmExe stop $ServiceName -ErrorAction SilentlyContinue
        & $NssmExe remove $ServiceName confirm 2>&1 | Out-Null
        Write-Host "Service uninstalled successfully." -ForegroundColor Green
    } catch {
        Write-Host "WARNING: Failed to cleanly remove service - it may not exist." -ForegroundColor Yellow
    }
    exit 0
}

# Check Python
$PythonExe = Get-Python
Write-Host "Using Python at: $PythonExe" -ForegroundColor Cyan

# Check daemon script
if (-not (Test-Path $DaemonScript)) {
    throw "Daemon script not found at: $DaemonScript"
}

# Download NSSM if needed
if (-not (Test-Path $NssmExe)) {
    Write-Host "Downloading NSSM..." -ForegroundColor Cyan
    $downloaded = $false
    
    foreach ($url in $NssmUrls) {
        try {
            Write-Host "  Trying: $url" -ForegroundColor Gray
            Invoke-WebRequest -Uri $url -OutFile $NssmZip -UseBasicParsing -ErrorAction Stop
            $downloaded = $true
            break
        } catch {
            Write-Host "  Failed: $_" -ForegroundColor Yellow
            continue
        }
    }
    
    if (-not $downloaded) {
        throw "Failed to download NSSM from all mirrors. Please download it manually from https://nssm.cc/"
    }
    
    Write-Host "Extracting NSSM..." -ForegroundColor Cyan
    Expand-Archive -Path $NssmZip -DestinationPath $NssmDir -Force
    Remove-Item $NssmZip -Force
}

# Create service
Write-Host "Installing OptiMas service..." -ForegroundColor Yellow

& $NssmExe install $ServiceName $PythonExe $DaemonScript
& $NssmExe set $ServiceName DisplayName $ServiceDisplayName
& $NssmExe set $ServiceName Description "OptiMas Hybrid GPU Coordination Engine - Latch between AMD RX 580 and NVIDIA GT 710"
& $NssmExe set $ServiceName Start SERVICE_AUTO_START
& $NssmExe set $ServiceName AppDirectory $ScriptDir
& $NssmExe set $ServiceName AppStdout (Join-Path $ScriptDir "logs\service_stdout.log")
& $NssmExe set $ServiceName AppStderr (Join-Path $ScriptDir "logs\service_stderr.log")
& $NssmExe set $ServiceName AppRotateFiles 1
& $NssmExe set $ServiceName AppRotateOnline 1
& $NssmExe set $ServiceName AppRotateSeconds 86400
& $NssmExe set $ServiceName AppRotateBytes 1048576
& $NssmExe set $ServiceName AppExit Default RESTART

# Create logs directory
$LogDir = Join-Path $ScriptDir "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# Start service
Write-Host "Starting OptiMas service..." -ForegroundColor Yellow
Start-Service -Name $ServiceName

Write-Host "`n✅ OptiMas service installed and started successfully!" -ForegroundColor Green
Write-Host "Service Name: $ServiceName"
Write-Host "Logs at: $LogDir"
Write-Host "`nTo manage service:"
Write-Host "  Start: Start-Service $ServiceName"
Write-Host "  Stop: Stop-Service $ServiceName"
Write-Host "  Uninstall: .\install_service.ps1 -Uninstall"
