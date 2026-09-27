import os
import platform
import subprocess
import sys
import argparse


def build():
    parser = argparse.ArgumentParser(description="Build diff_and_compare binary")
    parser.add_argument(
        "--target-arch",
        choices=["x64", "x86_64", "arm64", "win-arm64", "native"],
        default="native",
        help="Target CPU architecture (default: native host architecture)"
    )
    parser.add_argument(
        "--package",
        action="store_true",
        help="Assemble complete installable package folder and distribution ZIP"
    )
    args = parser.parse_args()

    host_arch = platform.machine().lower()
    target = args.target_arch
    if target == "native":
        target = "arm64" if "arm" in host_arch or "aarch64" in host_arch else "x64"

    print(f"Building diff_and_compare executable for target architecture: {target.upper()} (Host: {host_arch})...")

    excludes = [
        "PyQt6", "PyQt5", "tkinter",
        "kivy", "kivymd", "pygame", "yt_dlp",
        "scipy", "torch", "torchvision", "torchaudio",
        "matplotlib", "pandas", "IPython", "jupyter"
    ]

    hidden_imports = [
        "tree_sitter",
        "tree_sitter_python",
        "tree_sitter_javascript",
        "blake3",
        "pyarrow",
        "pyarrow.parquet",
        "fitz",
        "jsonpath_ng",
        "openpyxl"
    ]

    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", f"diff_and_compare_{target}",
        "--icon", "assets/app_icon.ico",
        "--add-data", "assets;assets"
    ]

    for ex in excludes:
        cmd.extend(["--exclude-module", ex])

    for hi in hidden_imports:
        cmd.extend(["--hidden-import", hi])

    cmd.append("app/main.py")

    print("PyInstaller command:", " ".join(cmd))
    try:
        subprocess.check_call(cmd)
        print(f"Build complete for {target}. Artifacts located in 'dist/diff_and_compare_{target}'.")
    except Exception as e:
        print(f"Build execution: {e}")

    if args.package:
        # Ensure dist/diff_and_compare points to the built target
        dist_base = os.path.join("dist", "diff_and_compare")
        target_dir = os.path.join("dist", f"diff_and_compare_{target}")
        if os.path.isdir(target_dir) and not os.path.isdir(dist_base):
            import shutil
            shutil.copytree(target_dir, dist_base)

        from windows.package_installer import main as run_packager
        run_packager()


if __name__ == "__main__":
    build()
