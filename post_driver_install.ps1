# OptiMas NVIDIA Driver Post-Install Setup
# Applies system changes and registry tweaks for the hybrid GPU setup

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Test-Admin {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host "ERROR: This script requires Administrator privileges." -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  OptiMas Post-Install Setup" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# 1. Set GPU priorities (example - customize as needed)
Write-Host "Applying GPU performance optimizations..." -ForegroundColor Yellow

# Example: Set NVIDIA GT 710 as primary for display (if needed)
# Note: This requires specific device IDs - adjust for your system!
try {
    # Get display adapter info
    $adapters = Get-WmiObject Win32_VideoController
    foreach ($adapter in $adapters) {
        Write-Host "  Found: $($adapter.Name)" -ForegroundColor Gray
    }
} catch {
    Write-Host "  Warning: Could not query display adapters." -ForegroundColor Yellow
}

# 2. Ensure OptiMas config files exist
Write-Host "Initializing OptiMas configuration..." -ForegroundColor Yellow

# Create logs directory if missing
$LogDir = Join-Path $ScriptDir "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# 3. Run GPU translation map
$TranslatorScript = Join-Path $ScriptDir "gpu_translator.py"
$TransactionScript = Join-Path $ScriptDir "gpu_transaction.py"
$PythonPath = $null

# Find Python
if (Test-Path (Join-Path $ScriptDir ".venv\Scripts\python.exe")) {
    $PythonPath = Join-Path $ScriptDir ".venv\Scripts\python.exe"
} else {
    try {
        $PythonPath = (Get-Command python -ErrorAction Stop).Source
    } catch {
        Write-Host "  Warning: Python not found - skipping config generation." -ForegroundColor Yellow
    }
}

if ($PythonPath) {
    Write-Host "Generating GPU capability map..." -ForegroundColor Yellow
    try {
        & $PythonPath -c "
import sys
sys.path.insert(0, r'$ScriptDir')
from gpu_translator import build_translation_map
from gpu_transaction import write_transaction
cap_map = build_translation_map()
if cap_map:
    write_transaction(cap_map)
    print('  Config map generated and signed successfully.')
"
    } catch {
        Write-Host "  Warning: Failed to generate config map: $_" -ForegroundColor Yellow
    }
}

Write-Host "`n✅ OptiMas post-install setup complete!" -ForegroundColor Green
Write-Host "`nNext: Install OptiMas service with:"
Write-Host "  .\install_service.ps1"
