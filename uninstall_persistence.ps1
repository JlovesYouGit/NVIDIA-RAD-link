# OptiMas Persistence Uninstaller
# Removes the hidden startup wrapper to prevent OptiMas starting automatically at boot.

$startupFolder = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$vbsPath = Join-Path $startupFolder "OptiMas_Startup.vbs"

Write-Output "=========================================================="
Write-Output "            OptiMas Persistence Uninstaller               "
=========================================================="
Write-Output ""

if (Test-Path $vbsPath) {
    Write-Output "[*] Removing startup shortcut from Windows Startup folder..."
    Remove-Item $vbsPath -Force
    Write-Output "[+] SUCCESS! Startup persistence has been removed."
} else {
    Write-Output "[-] Startup persistence was not active (no shortcut found)."
}

Write-Output ""
Start-Sleep -Seconds 3
