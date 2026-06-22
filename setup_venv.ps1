# OptiMas Python Virtual Environment (.venv) Installer
# Creates a dedicated virtual environment and installs premium library packages for GPU monitoring, compute, and API services.

$cwd = "e:\DOWNLOADs\NVIDIA\optimas"
$venvDir = Join-Path $cwd ".venv"
$requirementsPath = Join-Path $cwd "requirements.txt"

Write-Output "=========================================================="
Write-Output "         OptiMas Python venv & Library Installer          "
=========================================================="
Write-Output ""

# 1. Generate the Premium Requirements List
$requirementsContent = @"
# OptiMas Hybrid GPU Engine Library Requirements
# Core REST API & Web Server
FastAPI>=0.100.0
uvicorn>=0.22.0

# Hardware Diagnostics & Real-time Sensors
psutil>=5.9.0
gputil>=1.4.0
nvidia-ml-py>=12.535.0

# Windows System Integrations
pywin32>=306; sys_platform == 'win32'

# Numerical & Quantum Compute Acceleration
numpy>=1.24.0
scipy>=1.10.0
numba>=0.57.0
qiskit>=0.43.0
"@

Write-Output "[*] Generating requirements.txt..."
[System.IO.File]::WriteAllText($requirementsPath, $requirementsContent)

# 2. Create the Virtual Environment
Write-Output "[*] Creating Python Virtual Environment in $venvDir..."
if (Test-Path $venvDir) {
    Write-Output "[+] Virtual environment folder already exists. Skipping creation..."
} else {
    python -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "[-] Failed to create venv. Please ensure Python is installed and on your system PATH."
        Read-Host "Press Enter to exit..."
        Exit
    }
    Write-Output "[+] Virtual environment successfully created."
}

# 3. Upgrade pip and install packages
Write-Output ""
Write-Output "[*] Activating virtual environment and installing packages..."
$pipPath = Join-Path $venvDir "Scripts\pip.exe"
$pythonPath = Join-Path $venvDir "Scripts\python.exe"

# Run pip upgrade
Start-Process $pipPath -ArgumentList "install --upgrade pip" -NoNewWindow -Wait

# Run packages installation
Write-Output "[*] Installing premium packages (this may take a minute)..."
$installProc = Start-Process $pipPath -ArgumentList "install -r `"$requirementsPath`"" -NoNewWindow -PassThru -Wait

if ($installProc.ExitCode -eq 0) {
    Write-Output ""
    Write-Output "=========================================================="
    Write-Output "  SUCCESS! OptiMas venv is fully configured and ready."
    Write-Output "  All premium GPU monitoring and compute packages loaded."
    Write-Output "=========================================================="
} else {
    Write-Warning "[-] Installation completed with errors. Verify your internet connection or package compatibility."
}

Write-Output ""
Write-Output "Press Enter to exit..."
Read-Host
