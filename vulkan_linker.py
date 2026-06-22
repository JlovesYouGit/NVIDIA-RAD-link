import os
import sys
import json
import subprocess

DXVK_CONF_TEMPLATE = """# DXVK Custom Device Configuration for OptiMas Hybrid Setup
# Target Architecture Link: {role}
# Selected Vendor ID: {vendor_id} (0x10de for NVIDIA, 0x1002 for AMD)
# Selected Device ID: {device_id}

dxgi.customVendorId = {vendor_id}
dxgi.customDeviceId = {device_id}
dxvk.gplPipelineCache = True
dxvk.hud = fps,gpl
"""

def generate_dxvk_conf(target_dir, gpu_vendor="AMD"):
    """Generates a custom dxvk.conf in the game directory to force device selection."""
    if not os.path.exists(target_dir):
        return False, f"Directory '{target_dir}' does not exist."

    file_path = os.path.join(target_dir, "dxvk.conf")
    
    if gpu_vendor.upper() == "NVIDIA":
        # GeForce GT 710 (GK208) IDs
        vendor_id = "10de"
        device_id = "128b" # GK208 GT 710 Device ID
        role = "NVIDIA GeForce GT 710 (Kepler GK208 Agent Anchor)"
    else:
        # AMD Radeon RX 580 IDs
        vendor_id = "1002"
        device_id = "67df" # Polaris10 RX 580 Device ID
        role = "AMD Radeon RX 580 Series (Compute/Upscaler Engine)"

    content = DXVK_CONF_TEMPLATE.format(
        role=role,
        vendor_id=vendor_id,
        device_id=device_id
    )

    try:
        with open(file_path, "w") as f:
            f.write(content)
        return True, f"dxvk.conf successfully created at '{file_path}'"
    except Exception as e:
        return False, f"Failed to write dxvk.conf: {str(e)}"

def generate_launch_batch(target_exec, mode="vulkan-fsr-wrap"):
    """Generates a launch batch file (.bat) with proper environment overrides."""
    exec_dir = os.path.dirname(target_exec)
    exec_name = os.path.basename(target_exec)
    bat_path = os.path.join(exec_dir, "optimas_launch.bat")

    lines = [
        "@echo off",
        "echo ========================================================",
        "echo      OptiMas Hybrid Latch Launcher Starting...",
        "echo ========================================================",
        ""
    ]

    if mode == "cuda-zluda":
        lines.extend([
            "echo [OptiMas] Activating CUDA Intermediary Bridge via ZLUDA...",
            "echo [OptiMas] Exposing NVIDIA GT 710 driver and routing kernel runs to RX 580...",
            "set VK_LOADER_DRIVERS_SELECT=*amd*",
            "set CUDA_VISIBLE_DEVICES=0",
            "set ZLUDA_PATH=%~dp0",
            "# Injects ZLUDA custom driver configurations if present",
        ])
    else:
        # vulkan-fsr-wrap (Default)
        lines.extend([
            "echo [OptiMas] Activating Vulkan Forced Link & FSR Upscaler wrapper...",
            "echo [OptiMas] Anchor active via NVIDIA GT 710 and shaders rendering on RX 580...",
            "set VK_LOADER_DRIVERS_SELECT=*amd*",
            "set VK_ICD_FILENAMES=",
        ])

    lines.extend([
        f"echo [OptiMas] Launching: {exec_name}",
        "echo ========================================================",
        f'start "" "{exec_name}"',
        "exit"
    ])

    try:
        with open(bat_path, "w") as f:
            f.write("\n".join(lines))
        return True, f"Launcher batch created at '{bat_path}'"
    except Exception as e:
        return False, f"Failed to write launch batch: {str(e)}"

if __name__ == "__main__":
    # Self-test or CLI run
    print("OptiMas Vulkan Linker Module Active.")
    print("Usage: Call methods programmatically or use the dashboard to create game profiles.")
