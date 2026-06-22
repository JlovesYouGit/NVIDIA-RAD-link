# OptiMas Headless Background Launcher
# Starts both the daemon service (5050) and web dashboard (3000) in hidden windows.
# No terminal windows will remain open.

$cwd = "e:\DOWNLOADs\NVIDIA\optimas"

Write-Output "=========================================================="
Write-Output "       OptiMas Headless Background Service Launcher       "
Write-Output "=========================================================="
Write-Output ""

# Determine Python executable (local venv vs global system Python)
$pythonExe = "python"
$localVenv = Join-Path $cwd ".venv\Scripts\python.exe"
if (Test-Path $localVenv) {
    $pythonExe = $localVenv
    Write-Output "[+] Local Virtual Environment detected! Using .venv interpreter."
} else {
    Write-Output "[*] No local .venv found. Using global system Python."
}

# 1. Start the OptiMas Daemon API Service invisibly
Write-Output "[*] Starting OptiMas Daemon (port 5050) in hidden window..."
$daemonProc = Start-Process $pythonExe -ArgumentList "optimas_daemon.py" -WindowStyle Hidden -WorkingDirectory $cwd -PassThru

# 2. Start the HTTP Dashboard Web Server invisibly
Write-Output "[*] Starting Dashboard Web Server (port 3000) in hidden window..."
$serverProc = Start-Process $pythonExe -ArgumentList "-m http.server 3000" -WindowStyle Hidden -WorkingDirectory $cwd -PassThru

# Small delay to verify startup
Start-Sleep -Seconds 2

# Check if processes are active
$daemonActive = Get-Process -Id $daemonProc.Id -ErrorAction SilentlyContinue
$serverActive = Get-Process -Id $serverProc.Id -ErrorAction SilentlyContinue

Write-Output ""
if ($daemonActive -and $serverActive) {
    Write-Output "[+] SUCCESS! Both services are now running in the background."
    Write-Output "    - Dashboard available at: http://localhost:3000"
    Write-Output "    - Daemon API active on:   http://localhost:5050"
    Write-Output ""
    Write-Output "    No terminal windows are open. The services will run invisibly."
    Write-Output "    To stop the services, run: & '$cwd\stop_daemon.ps1'"
} else {
    Write-Warning "[-] Start detection incomplete. Please verify if Python is installed and configured on your environment PATH."
}
Write-Output ""
Start-Sleep -Seconds 3
