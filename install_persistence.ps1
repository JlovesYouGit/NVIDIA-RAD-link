# OptiMas Persistence Installer
# Configures the hidden background processes to launch automatically at Windows boot/logon.

$cwd = "e:\DOWNLOADs\NVIDIA\optimas"
$startupFolder = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$vbsPath = Join-Path $startupFolder "OptiMas_Startup.vbs"

Write-Output "=========================================================="
Write-Output "             OptiMas Persistence Auto-Installer           "
Write-Output "=========================================================="
Write-Output ""

Write-Output "[*] Target Workspace: $cwd"
Write-Output "[*] Startup Folder:   $startupFolder"
Write-Output ""

# Create a VBScript wrapper to launch the PowerShell script completely hidden at logon.
# Using VBScript guarantees that absolutely NO command prompt or console window pops up at boot.
$vbsContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & "$cwd\launch_hidden.ps1" & """", 0, False
"@

try {
    Write-Output "[*] Generating hidden boot wrapper in Windows Startup folder..."
    [System.IO.File]::WriteAllText($vbsPath, $vbsContent)
    
    Write-Output "[+] SUCCESS! OptiMas has been registered for persistence."
    Write-Output "    - The background engine will now automatically start at system logon."
    Write-Output "    - It will run 100% invisibly in the background with no terminal windows."
    Write-Output ""
    Write-Output "    To remove this startup persistence, you can run:"
    Write-Output "    Remove-Item '$vbsPath' -Force"
} catch {
    Write-Warning "[-] Failed to install startup persistence: $($_.Exception.Message)"
}

Write-Output ""
Write-Output "Press Enter to exit..."
Read-Host
