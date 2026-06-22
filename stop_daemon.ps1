# OptiMas Service Stopper
# Queries and terminates the hidden background Python processes for OptiMas.

Write-Output "=========================================================="
Write-Output "             OptiMas Background Service Stopper           "
Write-Output "=========================================================="
Write-Output ""

Write-Output "[*] Querying background Python processes..."

# Find Python processes running the specific daemon script or server command line
$processes = Get-CimInstance Win32_Process | Where-Object { 
    $_.Name -eq "python.exe" -and ($_.CommandLine -like "*optimas_daemon.py*" -or $_.CommandLine -like "*http.server 3000*")
}

if ($processes) {
    foreach ($proc in $processes) {
        Write-Output "[*] Stopping Process ID $($proc.ProcessId): $($proc.CommandLine)"
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Output "[+] SUCCESS! All OptiMas background services have been stopped."
} else {
    Write-Output "[-] No active OptiMas background processes were found running."
}

Write-Output ""
Start-Sleep -Seconds 3
