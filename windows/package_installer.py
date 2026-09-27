"""
Package Installer & Distribution Generator for diff_and_compare_tool
Creates:
1. dist/diff_and_compare_installer/ (Ready-to-deploy folder with 1-click Install.cmd & scripts)
2. dist/diff_and_compare_tool-v1.0.0-windows-x64.zip (Distribution archive for end users)
3. Compiles Inno Setup .exe if ISCC compiler is installed on host.
"""

import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"
APP_DIST_DIR = DIST_DIR / "diff_and_compare"
PACKAGE_DIR = DIST_DIR / "diff_and_compare_installer"
WINDOWS_DIR = REPO_ROOT / "windows"
ASSETS_DIR = REPO_ROOT / "assets"
VERSION = "1.0.0"
ZIP_NAME = f"diff_and_compare_tool-v{VERSION}-windows-x64.zip"


def ensure_build():
    """Ensures dist/diff_and_compare exists and contains diff_and_compare.exe."""
    exe_path = APP_DIST_DIR / "diff_and_compare.exe"
    if not exe_path.is_file():
        print(f"[Package] {exe_path} not found. Running build.py...")
        subprocess.check_call([sys.executable, str(REPO_ROOT / "build.py")])
    if not exe_path.is_file():
        raise RuntimeError("Build failed: diff_and_compare.exe was not created.")


def assemble_package():
    """Assembles dist/diff_and_compare_installer folder."""
    print(f"[Package] Creating installer directory: {PACKAGE_DIR}")
    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Copy application files from dist/diff_and_compare
    print(f"[Package] Copying binaries from {APP_DIST_DIR}...")
    for item in APP_DIST_DIR.iterdir():
        dest = PACKAGE_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    # 2. Ensure assets folder exists with icons
    target_assets = PACKAGE_DIR / "assets"
    target_assets.mkdir(exist_ok=True)
    if ASSETS_DIR.exists():
        for icon in ASSETS_DIR.iterdir():
            if icon.is_file():
                shutil.copy2(icon, target_assets / icon.name)

    # 3. Copy installer and uninstaller scripts
    files_to_copy = [
        "Install.cmd",
        "Install-DiffAndCompare.ps1",
        "Uninstall.cmd",
        "Uninstall-DiffAndCompare.ps1",
        "Register-All.reg",
        "Unregister-All.reg",
        "diff_and_compare.iss"
    ]
    for fn in files_to_copy:
        src = WINDOWS_DIR / fn
        if src.is_file():
            shutil.copy2(src, PACKAGE_DIR / fn)

    # 4. Generate README_INSTALL.txt
    readme_text = f"""========================================================================
diff_and_compare_tool v{VERSION} - Windows Installation Package
========================================================================

HOW TO INSTALL:
---------------
Method 1 (Recommended - 1-Click):
  Double-click "Install.cmd"
  - Installs to %LOCALAPPDATA%\\Programs\\diff_and_compare_tool (no Admin rights required).
  - Registers Windows Explorer right-click context menu:
      "Compare with diff_and_compare_tool"
      "diff_and_compare_tool: Select Left"
      "diff_and_compare_tool: Select Right"
  - Registers Windows App Paths (launch via Win+R or Command Prompt: 'diff_and_compare').
  - Adds to User PATH.
  - Registers in Windows Settings "Installed Apps" / "Add or Remove Programs".
  - Creates Start Menu & Desktop shortcuts.

Method 2 (PowerShell):
  Run in PowerShell:
  .\\Install-DiffAndCompare.ps1

Method 3 (Portable / Manual Registry):
  Double-click "Register-All.reg" or run:
  .\\diff_and_compare.exe --install-all

HOW TO UNINSTALL:
-----------------
- Double-click "Uninstall.cmd" or run "uninstall.cmd" in the installed folder.
- Or use Windows Settings -> Installed Apps -> diff_and_compare_tool -> Uninstall.
- Or double-click "Unregister-All.reg".
========================================================================
"""
    (PACKAGE_DIR / "README_INSTALL.txt").write_text(readme_text, encoding="utf-8")
    print(f"[Package] Assembly completed: {PACKAGE_DIR}")


def create_zip():
    """Compresses the installer folder into a clean .zip distribution."""
    zip_path = DIST_DIR / ZIP_NAME
    print(f"[Package] Generating release archive: {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(PACKAGE_DIR):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(DIST_DIR)
                zf.write(full_path, rel_path)
    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"[Package] Release archive created successfully: {zip_path} ({size_mb:.1f} MB)")


def try_compile_inno():
    """Attempts to compile with Inno Setup if ISCC.exe is detected."""
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    iscc_paths = [
        os.path.join(localappdata, "Programs", "Inno Setup 6", "ISCC.exe"),
        os.path.join(prog_files_x86, "Inno Setup 6", "ISCC.exe"),
        os.path.join(prog_files, "Inno Setup 6", "ISCC.exe"),
        shutil.which("iscc")
    ]
    iscc_exe = next((p for p in iscc_paths if p and os.path.isfile(p)), None)
    if iscc_exe:
        print(f"[Package] Inno Setup compiler detected at: {iscc_exe}")
        iss_path = WINDOWS_DIR / "diff_and_compare.iss"
        print(f"[Package] Compiling installer executable: {iss_path}...")
        try:
            subprocess.check_call([iscc_exe, str(iss_path)])
            print("[Package] Inno Setup installer compiled: dist/Setup_diff_and_compare_tool.exe")
        except Exception as e:
            print(f"[Package] Inno Setup compilation warning: {e}")
    else:
        print("[Package] Inno Setup compiler (ISCC.exe) not found. Skipping .iss compilation.")
        print("[Package] (The standalone 1-click Install.cmd and PowerShell installer are ready!)")


def main():
    print("==========================================================")
    print("  Building diff_and_compare_tool Installable Distribution")
    print("==========================================================")
    ensure_build()
    assemble_package()
    create_zip()
    try_compile_inno()
    print("==========================================================")
    print("  Package Creation Complete!")
    print(f"  Installer folder:  {PACKAGE_DIR}")
    print(f"  Release Zip:       {DIST_DIR / ZIP_NAME}")
    print("==========================================================")


if __name__ == "__main__":
    main()
