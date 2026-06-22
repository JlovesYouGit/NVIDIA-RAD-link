#!/usr/bin/env python3
"""
NVIDIA Driver Extractor & Repacker
Allows extracting, modifying, and repacking NVIDIA driver installers
"""

import os
import sys
import shutil
import subprocess
import tempfile
import json
from pathlib import Path


def is_7zip_available():
    """Check if 7-Zip is installed and available in PATH"""
    try:
        result = subprocess.run(
            ["7z", "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def extract_driver(installer_path, extract_to):
    """Extract NVIDIA driver installer using 7-Zip"""
    print(f"\n📦 Extracting driver: {installer_path}")
    print(f"   To: {extract_to}")
    
    if not is_7zip_available():
        print("❌ 7-Zip not found! Please install it from https://www.7-zip.org/")
        return False
    
    # Clean destination if it exists
    if os.path.exists(extract_to):
        print("   Cleaning existing extraction directory...")
        shutil.rmtree(extract_to)
    os.makedirs(extract_to, exist_ok=True)
    
    # Extract using 7-Zip
    cmd = [
        "7z", "x",
        f"-o{extract_to}",
        installer_path,
        "-y"
    ]
    
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"❌ Extraction failed with code: {result.returncode}")
        return False
    
    print("✅ Driver extracted successfully!")
    return True


def modify_driver(extract_dir):
    """Modify extracted driver files (customize this function!)"""
    print(f"\n🛠️  Modifying driver in: {extract_dir}")
    
    # Example modifications - customize this!
    config_file = Path(extract_dir) / "setup.cfg"
    
    # If you want to modify something specific, do it here
    # For example, modify a configuration file or replace a DLL
    print("   Example: You can edit files in the extraction directory now")
    print("   Press Enter when you're ready to repack, or Ctrl+C to cancel...")
    input()
    
    return True


def repack_driver(extract_dir, output_path):
    """Repack driver (create self-extracting installer)"""
    print(f"\n📦 Repacking driver from: {extract_dir}")
    print(f"   To: {output_path}")
    
    # For repacking, we can create a simple zip or use 7-Zip SFX
    # This creates a 7-Zip SFX installer
    
    if not is_7zip_available():
        print("❌ 7-Zip not found for repacking!")
        return False
    
    # Create config.txt for 7-Zip SFX
    sfx_config = """
;!@Install@!UTF-8!
Title="NVIDIA Driver"
BeginPrompt="This will install the NVIDIA driver. Continue?"
RunProgram="setup.exe"
;!@InstallEnd@!
"""
    
    config_path = Path(extract_dir) / "sfx_config.txt"
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(sfx_config)
    
    # First create a 7z archive
    temp_7z = output_path.replace(".exe", ".7z")
    cmd_archive = [
        "7z", "a",
        "-t7z",
        "-m0=lzma2",
        "-mx=9",
        temp_7z,
        f"{extract_dir}\\*"
    ]
    
    result = subprocess.run(cmd_archive, check=False)
    if result.returncode != 0:
        print(f"❌ Failed to create 7z archive!")
        return False
    
    # Now create SFX
    cmd_sfx = [
        "copy", "/b",
        r"C:\Program Files\7-Zip\7zS.sfx" + "+" + config_path + "+" + temp_7z,
        output_path
    ]
    
    # Alternatively, if 7zS.sfx is not available, just zip it
    try:
        result = subprocess.run(cmd_sfx, shell=True, check=False)
        if result.returncode == 0:
            print("✅ Driver repacked as self-extracting installer!")
            # Cleanup
            os.remove(temp_7z)
            os.remove(config_path)
            return True
    except:
        pass
    
    print("⚠️ SFX creation failed. Creating regular ZIP instead...")
    shutil.copy(temp_7z, output_path.replace(".exe", ".zip"))
    os.remove(temp_7z)
    os.remove(config_path)
    print(f"✅ Created ZIP: {output_path.replace('.exe', '.zip')}")
    return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="NVIDIA Driver Extractor & Repacker")
    parser.add_argument(
        "installer",
        nargs="?",
        default="474.82-desktop-win10-win11-64bit-international-dch-whql.exe",
        help="Path to NVIDIA driver installer"
    )
    parser.add_argument(
        "--extract",
        help="Extract driver to this directory",
        default="driver_extracted"
    )
    parser.add_argument(
        "--repack",
        help="Repack extracted driver to this path",
        default="custom_nvidia_driver.exe"
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Only extract, don't modify or repack"
    )
    parser.add_argument(
        "--repack-only",
        action="store_true",
        help="Only repack from existing extraction directory"
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("  NVIDIA Driver Extractor & Repacker")
    print("="*60)
    
    script_dir = Path(__file__).parent
    installer_path = script_dir / args.installer
    
    if not args.repack_only and not os.path.exists(installer_path):
        print(f"\n❌ Driver installer not found at: {installer_path}")
        print("   Please place the driver installer in the same directory as this script!")
        return 1
    
    extract_dir = script_dir / args.extract
    repack_path = script_dir / args.repack
    
    success = True
    
    if not args.repack_only:
        if not extract_driver(str(installer_path), str(extract_dir)):
            return 1
        
        if args.extract_only:
            print("\n✅ Extraction complete!")
            print(f"   Files at: {extract_dir}")
            return 0
    
    if not args.extract_only:
        if not os.path.exists(extract_dir):
            print(f"\n❌ Extraction directory not found at: {extract_dir}")
            return 1
        
        if not args.repack_only:
            modify_driver(str(extract_dir))
        
        if not repack_driver(str(extract_dir), str(repack_path)):
            return 1
    
    print("\n✅ All operations complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
