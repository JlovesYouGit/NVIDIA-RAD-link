# OptiMas Pagefile & Virtual Memory Optimizer
# This script configures the Windows Pagefile (Swap Bank) to maximize secondary memory buffers for hybrid GPU systems (AMD RX 580 + NVIDIA GT 710).
# NOTE: This script must be run as Administrator to apply changes.

Write-Output "=========================================================="
Write-Output "       OptiMas Swap Bank & Virtual Memory Optimizer       "
Write-Output "=========================================================="
Write-Output ""

# Check for Administrator Rights
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Warning "This script is NOT running with Administrative privileges!"
    Write-Output "To optimize your Pagefile and System Memory Cache, please run this script from an Elevated PowerShell prompt:"
    Write-Output "  1. Right-click Start -> Terminal (Admin) or PowerShell (Admin)"
    Write-Output "  2. Run: Set-ExecutionPolicy Bypass -Scope Process"
    Write-Output "  3. Execute: & 'e:\DOWNLOADs\NVIDIA\optimas\swap_optimizer.ps1'"
    Write-Output ""
    Write-Output "Press Enter to exit..."
    Read-Host
    Exit
}

Write-Output "[*] Running with Administrator rights."
Write-Output "[*] Analyzing system physical memory..."

# Get System Memory Details
$sysInfo = Get-CimInstance Win32_OperatingSystem
$physMemBytes = $sysInfo.TotalVisibleMemorySize * 1024
$physMemGB = [math]::Round($physMemBytes / 1GB, 2)
Write-Output "[+] Total Physical RAM: $physMemGB GB"

# Calculate Optimal Pagefile (Swap Bank) Sizes
# We recommend setting pagefile to 1.5x to 2x Physical RAM as a fixed size for multi-GPU buffers.
$minSizeMB = [int]($sysInfo.TotalVisibleMemorySize / 1024) * 1.5
$maxSizeMB = [int]($sysInfo.TotalVisibleMemorySize / 1024) * 2.0

Write-Output "[*] Recommended Virtual Swap Bank limits based on your hardware:"
Write-Output "    - Initial (Minimum) Size: $minSizeMB MB"
Write-Output "    - Maximum Size: $maxSizeMB MB"
Write-Output ""

# Query Current Pagefile Setup
Write-Output "[*] Querying current Windows Pagefile configurations..."
$pageFiles = Get-CimInstance Win32_PageFileSetting
if ($pageFiles) {
    foreach ($pf in $pageFiles) {
        Write-Output "    - Drive: $($pf.Name)"
        Write-Output "      Initial Size: $($pf.InitialSize) MB"
        Write-Output "      Maximum Size: $($pf.MaximumSize) MB"
    }
} else {
    Write-Output "    - No dedicated pagefile settings found (Windows is auto-managing)."
}
Write-Output ""

# Ask to apply Pagefile optimization
$confirm = Read-Host "Would you like to apply the OptiMas Swap Bank Pagefile configuration now? (Y/N)"
if ($confirm.ToUpper() -eq "Y") {
    Write-Output "[*] Disabling automatic pagefile management..."
    # Disable auto pagefile management
    $computerSystem = Get-CimInstance Win32_ComputerSystem
    $computerSystem | Set-CimInstance -Property @{AutomaticManagedPagefile = $False}
    
    Write-Output "[*] Configuring unified fixed-size pagefile on System Drive C: ($minSizeMB MB to $maxSizeMB MB)..."
    # Try to set pagefile on C:
    $targetDrive = "C:\pagefile.sys"
    
    # Check if target pagefile setting exists, if not, create it
    $existingPF = Get-CimInstance Win32_PageFileSetting | Where-Object { $_.Name -like "*C:*" }
    if ($existingPF) {
        $existingPF | Set-CimInstance -Property @{InitialSize = [int]$minSizeMB; MaximumSize = [int]$maxSizeMB}
    } else {
        # Delete automatic entry and create custom one
        Get-CimInstance Win32_PageFileSetting | Remove-CimInstance -ErrorAction SilentlyContinue
        New-CimInstance -ClassName Win32_PageFileSetting -Property @{Name = $targetDrive; InitialSize = [int]$minSizeMB; MaximumSize = [int]$maxSizeMB}
    }
    
    Write-Output "[+] Virtual memory pagefile successfully updated to optimized range."
} else {
    Write-Output "[-] Pagefile allocation skipped."
}

Write-Output ""
Write-Output "[*] Optimizing system performance registry keys for hybrid GPU processing..."

# Optimize Windows memory cache parameters for fast GPU memory mapping over PCIe
try {
    # 1. Enable Large System Cache (Optimizes memory throughput)
    Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management" -Name "LargeSystemCache" -Value 1
    Write-Output "[+] LargeSystemCache configured to 1 (Enabled)."
    
    # 2. Disable Paging Executive (Forces system drivers and kernel code to remain in physical RAM)
    Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management" -Name "DisablePagingExecutive" -Value 1
    Write-Output "[+] DisablePagingExecutive configured to 1 (RAM Lock Enabled)."
} catch {
    Write-Warning "[-] Failed to modify registry parameters: $($_.Exception.Message)"
}

Write-Output ""
Write-Output "=========================================================="
Write-Output "  Optimization complete! Please restart Windows for all  "
Write-Output "  memory and pagefile configurations to take full effect.  "
Write-Output "=========================================================="
Write-Output ""
Write-Output "Press Enter to exit..."
Read-Host
