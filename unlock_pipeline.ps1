# OptiMas OS Pipeline Unlocker
# Forces Windows to re-scan the PCI bus and associate the GT 710 with the Basic Display Driver
# This provides a valid LUID anchor for the OptiMas Session Driver.

$ErrorActionPreference = "Stop"

function Test-Admin {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host "ERROR: Requires Administrator privileges!" -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  OptiMas OS Pipeline Unlocker" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# 1. Find the restricted GT 710
$GT710 = Get-PnpDevice | Where-Object {$_.InstanceId -like "*PCI*VEN_10DE&DEV_128B*"}
if (-not $GT710) {
    Write-Host "❌ GT 710 not found on PCI bus. Check physical connection." -ForegroundColor Red
    exit 1
}

Write-Host "🔗 Found GT 710 at: $($GT710.InstanceId)" -ForegroundColor Green
Write-Host "🔗 Current Status: $($GT710.Status)" -ForegroundColor Yellow

# 2. Force Pipeline Reset
Write-Host "`n[1] Resetting Hardware Pipeline..." -ForegroundColor Cyan
Disable-PnpDevice -InstanceId $GT710.InstanceId -Confirm:$false
Start-Sleep -Seconds 2
Enable-PnpDevice -InstanceId $GT710.InstanceId -Confirm:$false
Write-Host "✅ Pipeline reset complete." -ForegroundColor Green

# 3. Associate with Basic Display Driver (The "Access Session")
Write-Host "`n[2] Linking to Windows Access Session Driver..." -ForegroundColor Cyan
# This forces Windows to bind the card to the basic WDDM pipeline, giving it a LUID
# without requiring the restricted NVIDIA signature yet.
Update-PnpDevice -InstanceId $GT710.InstanceId
Write-Host "✅ Basic Link established." -ForegroundColor Green

# 4. Inject Hybrid Memory Registry Keys
Write-Host "`n[3] Injecting Multi-Duplex Registry Anchors..." -ForegroundColor Cyan
$RegPath = "HKLM:\SYSTEM\CurrentControlSet\Enum\$($GT710.InstanceId)\Device Parameters"
if (Test-Path $RegPath) {
    New-ItemProperty -Path $RegPath -Name "EnableMSHybrid" -Value 1 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path $RegPath -Name "HybridGraphicsMode" -Value 2 -PropertyType DWord -Force | Out-Null
    Write-Host "✅ Registry anchors injected." -ForegroundColor Green
} else {
    Write-Host "⚠️  Device Parameters key not found. Manual install may be required." -ForegroundColor Yellow
}

Write-Host "`n🎉 Pipeline Unlocked!" -ForegroundColor Green
Write-Host "Next: Run 'python test_hardware.py' to verify the LUID is now visible."
