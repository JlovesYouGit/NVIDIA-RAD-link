# NVIDIA Driver Tool Quick Guide

## Prerequisites

Install **7-Zip** from https://www.7-zip.org/ and add it to your PATH.


## Usage

### 1. Extract Only
Extracts the driver without modifying:
```powershell
python nvidia_driver_tool.py --extract-only
```

### 2. Extract, Modify, Repack
Full workflow:
```powershell
python nvidia_driver_tool.py
```
- It extracts the driver
- Pauses so you can modify files in `driver_extracted/`
- Then repacks it as `custom_nvidia_driver.exe`

### 3. Repack Only
If you already have modified files:
```powershell
python nvidia_driver_tool.py --repack-only
```


## What to Modify

After extraction, edit files in `driver_extracted/`:
- Configuration files (`.cfg`, `.inf`)
- Replace DLLs or drivers
- Modify setup behavior


## Installing the Custom Driver

1. After repacking, run `custom_nvidia_driver.exe`
2. Or run `setup.exe` directly from the `driver_extracted/` folder!
