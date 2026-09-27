"""
Windows Explorer Shell Context Menu & Registry Integration
Provides Windows Explorer right-click options:
- "Compare with diff_and_compare_tool" (Direct comparison or paired comparison)
- "diff_and_compare_tool: Select Left" (Stores the file/folder in local app data as Left side)
- "diff_and_compare_tool: Select Right" (Launches comparison of Left vs Right)

Also provides:
- App Paths registration (`diff_and_compare.exe` accessible anywhere via Win+R, cmd, etc.)
- Windows Add/Remove Programs (Installed Apps) registration
- Dynamic `.reg` export and Shell notification
- Registers under HKEY_CURRENT_USER (no Administrator/UAC prompt required).
"""

import os
import sys
import json
import time
import winreg
import ctypes
from typing import Optional, Tuple


APP_NAME = "diff_and_compare"
APP_DISPLAY_NAME = "diff_and_compare_tool"
APP_VERSION = "1.0.0"
APP_PUBLISHER = "diff_and_compare_tool"
STATE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "diff_and_compare")
STATE_FILE = os.path.join(STATE_DIR, "shell_state.json")


def get_state_file_path() -> str:
    os.makedirs(STATE_DIR, exist_ok=True)
    return STATE_FILE


def get_left_path() -> Optional[str]:
    """Retrieves the cached Left path if it exists."""
    path = get_state_file_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("left_path")
    except Exception:
        return None


def set_left_path(path: str) -> None:
    """Saves the specified path as Left comparison target."""
    fpath = get_state_file_path()
    data = {
        "left_path": os.path.abspath(path),
        "timestamp": time.time(),
        "is_dir": os.path.isdir(path)
    }
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def clear_state() -> None:
    """Clears cached selection."""
    fpath = get_state_file_path()
    if os.path.exists(fpath):
        try:
            os.remove(fpath)
        except OSError:
            pass


def notify_shell() -> None:
    """Notifies Windows Explorer of shell/file association and environment updates."""
    try:
        # SHCNE_ASSOCCHANGED = 0x08000000, SHCNF_IDLIST = 0
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except Exception:
        pass


def get_executable_command(custom_exe: Optional[str] = None) -> str:
    """Returns the executable command prefix to run the app."""
    if custom_exe and os.path.isfile(custom_exe):
        return f'"{os.path.abspath(custom_exe)}"'

    # When frozen by PyInstaller, sys.executable points directly to diff_and_compare.exe
    if getattr(sys, "frozen", False):
        return f'"{os.path.abspath(sys.executable)}"'

    # Check repository dist output
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    exe_candidate = os.path.join(base_dir, "dist", "diff_and_compare", "diff_and_compare.exe")
    if os.path.isfile(exe_candidate):
        return f'"{exe_candidate}"'

    # Fallback to pythonw.exe or python.exe running main.py
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    if not os.path.isfile(pythonw):
        pythonw = sys.executable

    main_script = os.path.join(base_dir, "app", "main.py")
    return f'"{pythonw}" "{main_script}"'


def get_app_icon_path(custom_icon: Optional[str] = None) -> str:
    """Finds app icon (.ico or .exe) for Windows Explorer context menu."""
    if custom_icon and os.path.isfile(custom_icon):
        return os.path.abspath(custom_icon)

    if getattr(sys, "frozen", False):
        exe_path = os.path.abspath(sys.executable)
        exe_dir = os.path.dirname(exe_path)
        for cand in [
            os.path.join(exe_dir, "assets", "app_icon.ico"),
            os.path.join(exe_dir, "_internal", "assets", "app_icon.ico"),
            exe_path
        ]:
            if os.path.isfile(cand):
                return cand
        return exe_path

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for cand in [
        os.path.join(base_dir, "assets", "app_icon.ico"),
        os.path.join(base_dir, "dist", "diff_and_compare", "assets", "app_icon.ico"),
        os.path.join(base_dir, "dist", "diff_and_compare", "_internal", "assets", "app_icon.ico"),
        os.path.join(base_dir, "dist", "diff_and_compare", "diff_and_compare.exe"),
    ]:
        if os.path.isfile(cand):
            return cand
    return sys.executable


# Registry targets for context menu
REG_TARGETS = [
    r"Software\Classes\*\shell",                       # All files
    r"Software\Classes\Directory\shell",               # All directories/folders
    r"Software\Classes\Directory\Background\shell",    # Explorer empty space
]

MENU_ITEMS = [
    {
        "key_name": "DiffAndCompareToolCompare",
        "title": "Compare with diff_and_compare_tool",
        "flag": "--compare"
    },
    {
        "key_name": "DiffAndCompareToolSelectLeft",
        "title": "diff_and_compare_tool: Select Left",
        "flag": "--select-left"
    },
    {
        "key_name": "DiffAndCompareToolSelectRight",
        "title": "diff_and_compare_tool: Select Right",
        "flag": "--select-right"
    }
]

LEGACY_KEYS = [
    "DiffAndCompareSelectLeft",
    "DiffAndCompareSelectRight",
    "DiffAndCompareCompare",
    "BeyondCompareCompare",
    "BeyondCompareSelectLeft",
    "BeyondCompareSelectRight"
]


def install_context_menu(target_exe: Optional[str] = None, icon_path: Optional[str] = None) -> Tuple[bool, str]:
    """
    Registers 'Compare with diff_and_compare_tool', 'diff_and_compare_tool: Select Left',
    and 'diff_and_compare_tool: Select Right' in the Windows Explorer context menu.
    Requires no Administrator privileges (installs in HKCU).
    """
    cmd_prefix = get_executable_command(target_exe)
    resolved_icon = get_app_icon_path(icon_path)

    try:
        # First remove legacy keys to avoid duplicate/stale entries
        for target_root in REG_TARGETS:
            for old_key in LEGACY_KEYS:
                full_old_path = f"{target_root}\\{old_key}"
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{full_old_path}\\command")
                except FileNotFoundError:
                    pass
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, full_old_path)
                except FileNotFoundError:
                    pass

        # Install current branded menu items
        for target_root in REG_TARGETS:
            for item in MENU_ITEMS:
                full_key_path = f"{target_root}\\{item['key_name']}"

                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, full_key_path) as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, item["title"])
                    if resolved_icon:
                        winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, resolved_icon)

                # Command subkey
                cmd_key_path = f"{full_key_path}\\command"
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_key_path) as cmd_key:
                    # %1 passes selected file or folder path
                    # %V passes background folder for Directory\Background
                    arg_macro = "%V" if "Background" in target_root else "%1"
                    full_cmd = f'{cmd_prefix} {item["flag"]} "{arg_macro}"'
                    winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, full_cmd)

        notify_shell()
        return True, "Context menu successfully installed into Windows Explorer!"
    except Exception as e:
        return False, f"Failed to register context menu: {e}"


def uninstall_context_menu() -> Tuple[bool, str]:
    """Removes all registered context menu keys (including legacy keys) from HKCU."""
    all_key_names = [item["key_name"] for item in MENU_ITEMS] + LEGACY_KEYS
    try:
        for target_root in REG_TARGETS:
            for key_name in all_key_names:
                full_key_path = f"{target_root}\\{key_name}"
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{full_key_path}\\command")
                except FileNotFoundError:
                    pass
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, full_key_path)
                except FileNotFoundError:
                    pass
        notify_shell()
        return True, "Context menu successfully removed from Windows Explorer."
    except Exception as e:
        return False, f"Failed to remove context menu: {e}"


def is_context_menu_installed() -> bool:
    """Checks if the context menu items exist in the registry."""
    for key_name in ["DiffAndCompareToolCompare", "DiffAndCompareToolSelectLeft", "BeyondCompareCompare", "DiffAndCompareSelectLeft"]:
        test_key = rf"Software\Classes\*\shell\{key_name}\command"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, test_key):
                return True
        except FileNotFoundError:
            pass
    return False


def install_app_paths(target_exe: Optional[str] = None) -> Tuple[bool, str]:
    """
    Registers the application executable under App Paths in HKCU.
    Allows running 'diff_and_compare' or 'diff_and_compare_tool' from Win+R, CMD, or PowerShell.
    """
    if target_exe:
        resolved_exe = os.path.abspath(target_exe)
    elif getattr(sys, "frozen", False):
        resolved_exe = os.path.abspath(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        resolved_exe = os.path.join(base_dir, "dist", "diff_and_compare", "diff_and_compare.exe")

    if not os.path.isfile(resolved_exe):
        return False, f"Executable not found at: {resolved_exe}"

    install_dir = os.path.dirname(resolved_exe)
    app_names = ["diff_and_compare.exe", "diff_and_compare_tool.exe"]

    try:
        for app in app_names:
            key_path = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{app}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, resolved_exe)
                winreg.SetValueEx(key, "Path", 0, winreg.REG_SZ, install_dir)
        return True, "App Paths successfully registered in Windows Registry!"
    except Exception as e:
        return False, f"Failed to register App Paths: {e}"


def uninstall_app_paths() -> Tuple[bool, str]:
    """Removes App Paths registration from HKCU."""
    app_names = ["diff_and_compare.exe", "diff_and_compare_tool.exe"]
    try:
        for app in app_names:
            key_path = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{app}"
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
            except FileNotFoundError:
                pass
        return True, "App Paths successfully removed from Windows Registry."
    except Exception as e:
        return False, f"Failed to remove App Paths: {e}"


def install_uninstall_entry(install_dir: Optional[str] = None, target_exe: Optional[str] = None, version: str = APP_VERSION) -> Tuple[bool, str]:
    r"""
    Registers diff_and_compare_tool in Windows 'Installed Apps' / 'Add or Remove Programs'
    under HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\diff_and_compare_tool.
    """
    if target_exe:
        resolved_exe = os.path.abspath(target_exe)
    elif getattr(sys, "frozen", False):
        resolved_exe = os.path.abspath(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        resolved_exe = os.path.join(base_dir, "dist", "diff_and_compare", "diff_and_compare.exe")

    if not install_dir:
        install_dir = os.path.dirname(resolved_exe)

    uninstall_script = os.path.join(install_dir, "uninstall.ps1")
    uninstall_cmd = os.path.join(install_dir, "uninstall.cmd")
    uninstall_string = f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{uninstall_script}"'
    if os.path.isfile(uninstall_cmd):
        uninstall_string = f'"{uninstall_cmd}"'

    # Compute estimated size in KB
    size_kb = 400000
    if os.path.isdir(install_dir):
        try:
            total_bytes = sum(
                os.path.getsize(os.path.join(dp, f))
                for dp, dn, filenames in os.walk(install_dir)
                for f in filenames
            )
            size_kb = total_bytes // 1024
        except Exception:
            pass

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\diff_and_compare_tool"
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_DISPLAY_NAME)
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, version)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, APP_PUBLISHER)
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, f'"{resolved_exe}",0')
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, install_dir)
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, uninstall_string)
            winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{uninstall_script}" -Silent')
            winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, size_kb)
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        return True, "Installed Apps uninstall entry registered in Windows Registry!"
    except Exception as e:
        return False, f"Failed to register uninstall entry: {e}"


def uninstall_uninstall_entry() -> Tuple[bool, str]:
    """Removes the Uninstall entry from HKCU."""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\diff_and_compare_tool"
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
        return True, "Uninstall entry removed from Windows Registry."
    except FileNotFoundError:
        return True, "Uninstall entry was not present."
    except Exception as e:
        return False, f"Failed to remove uninstall entry: {e}"


def install_all(target_exe: Optional[str] = None, icon_path: Optional[str] = None, install_dir: Optional[str] = None, version: str = APP_VERSION) -> Tuple[bool, str]:
    """Registers Context Menu, App Paths, and Add/Remove Programs entry."""
    ok1, msg1 = install_context_menu(target_exe, icon_path)
    ok2, msg2 = install_app_paths(target_exe)
    ok3, msg3 = install_uninstall_entry(install_dir, target_exe, version)

    if ok1 and ok2 and ok3:
        return True, "All Windows Registry entries successfully configured (Context Menus, App Paths, Installed Apps)."
    errors = [m for ok, m in [(ok1, msg1), (ok2, msg2), (ok3, msg3)] if not ok]
    return False, "Registry setup warnings: " + "; ".join(errors)


def uninstall_all() -> Tuple[bool, str]:
    """Removes all Context Menus, App Paths, and Uninstall entries from Registry."""
    ok1, msg1 = uninstall_context_menu()
    ok2, msg2 = uninstall_app_paths()
    ok3, msg3 = uninstall_uninstall_entry()
    return True, "All Windows Registry entries successfully removed."


def generate_reg_content(target_exe: Optional[str] = None, icon_path: Optional[str] = None, install_dir: Optional[str] = None) -> str:
    """Generates standard Windows Registry Editor Version 5.00 (.reg) text."""
    if target_exe:
        resolved_exe = os.path.abspath(target_exe)
    elif getattr(sys, "frozen", False):
        resolved_exe = os.path.abspath(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        resolved_exe = os.path.join(base_dir, "dist", "diff_and_compare", "diff_and_compare.exe")

    resolved_icon = get_app_icon_path(icon_path)
    if not install_dir:
        install_dir = os.path.dirname(resolved_exe)

    # In .reg files, backslashes must be doubled
    reg_exe = resolved_exe.replace("\\", "\\\\")
    reg_icon = resolved_icon.replace("\\", "\\\\")
    reg_dir = install_dir.replace("\\", "\\\\")

    content = f"""Windows Registry Editor Version 5.00

; ========================================================
; diff_and_compare_tool - Complete Windows Registry Configuration
; Generated automatically for: {resolved_exe}
; ========================================================

; ---------------------------------------------
; 1. Explorer Context Menu: All Files (*)
; ---------------------------------------------
[HKEY_CURRENT_USER\\Software\\Classes\\*\\shell\\DiffAndCompareToolCompare]
@="Compare with diff_and_compare_tool"
"Icon"="\\"{reg_icon}\\""

[HKEY_CURRENT_USER\\Software\\Classes\\*\\shell\\DiffAndCompareToolCompare\\command]
@="\\"\\"{reg_exe}\\" --compare \\"%1\\"\\""

[HKEY_CURRENT_USER\\Software\\Classes\\*\\shell\\DiffAndCompareToolSelectLeft]
@="diff_and_compare_tool: Select Left"
"Icon"="\\"{reg_icon}\\""

[HKEY_CURRENT_USER\\Software\\Classes\\*\\shell\\DiffAndCompareToolSelectLeft\\command]
@="\\"\\"{reg_exe}\\" --select-left \\"%1\\"\\""

[HKEY_CURRENT_USER\\Software\\Classes\\*\\shell\\DiffAndCompareToolSelectRight]
@="diff_and_compare_tool: Select Right"
"Icon"="\\"{reg_icon}\\""

[HKEY_CURRENT_USER\\Software\\Classes\\*\\shell\\DiffAndCompareToolSelectRight\\command]
@="\\"\\"{reg_exe}\\" --select-right \\"%1\\"\\""

; ---------------------------------------------
; 2. Explorer Context Menu: Directories / Folders
; ---------------------------------------------
[HKEY_CURRENT_USER\\Software\\Classes\\Directory\\shell\\DiffAndCompareToolCompare]
@="Compare with diff_and_compare_tool"
"Icon"="\\"{reg_icon}\\""

[HKEY_CURRENT_USER\\Software\\Classes\\Directory\\shell\\DiffAndCompareToolCompare\\command]
@="\\"\\"{reg_exe}\\" --compare \\"%1\\"\\""

[HKEY_CURRENT_USER\\Software\\Classes\\Directory\\shell\\DiffAndCompareToolSelectLeft]
@="diff_and_compare_tool: Select Left"
"Icon"="\\"{reg_icon}\\""

[HKEY_CURRENT_USER\\Software\\Classes\\Directory\\shell\\DiffAndCompareToolSelectLeft\\command]
@="\\"\\"{reg_exe}\\" --select-left \\"%1\\"\\""

[HKEY_CURRENT_USER\\Software\\Classes\\Directory\\shell\\DiffAndCompareToolSelectRight]
@="diff_and_compare_tool: Select Right"
"Icon"="\\"{reg_icon}\\""

[HKEY_CURRENT_USER\\Software\\Classes\\Directory\\shell\\DiffAndCompareToolSelectRight\\command]
@="\\"\\"{reg_exe}\\" --select-right \\"%1\\"\\""

; ---------------------------------------------
; 3. Explorer Context Menu: Directory Background (Empty Space)
; ---------------------------------------------
[HKEY_CURRENT_USER\\Software\\Classes\\Directory\\Background\\shell\\DiffAndCompareToolCompare]
@="Compare with diff_and_compare_tool"
"Icon"="\\"{reg_icon}\\""

[HKEY_CURRENT_USER\\Software\\Classes\\Directory\\Background\\shell\\DiffAndCompareToolCompare\\command]
@="\\"\\"{reg_exe}\\" --compare \\"%V\\"\\""

; ---------------------------------------------
; 4. Windows App Paths (Win+R / CMD launch)
; ---------------------------------------------
[HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\diff_and_compare.exe]
@="\\"{reg_exe}\\""
"Path"="\\"{reg_dir}\\""

[HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\diff_and_compare_tool.exe]
@="\\"{reg_exe}\\""
"Path"="\\"{reg_dir}\\""

; ---------------------------------------------
; 5. Windows Add/Remove Programs (Installed Apps)
; ---------------------------------------------
[HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\\\Uninstall\\diff_and_compare_tool]
"DisplayName"="{APP_DISPLAY_NAME}"
"DisplayVersion"="{APP_VERSION}"
"Publisher"="{APP_PUBLISHER}"
"DisplayIcon"="\\"{reg_exe}\\",0"
"InstallLocation"="\\"{reg_dir}\\""
"UninstallString"="powershell.exe -NoProfile -ExecutionPolicy Bypass -File \\"{reg_dir}\\\\uninstall.ps1\\""
"QuietUninstallString"="powershell.exe -NoProfile -ExecutionPolicy Bypass -File \\"{reg_dir}\\\\uninstall.ps1\\" -Silent"
"NoModify"=dword:00000001
"NoRepair"=dword:00000001
"EstimatedSize"=dword:00065000
"""
    return content


def export_reg_file(file_path: str, target_exe: Optional[str] = None, icon_path: Optional[str] = None, install_dir: Optional[str] = None) -> Tuple[bool, str]:
    """Exports a .reg file for importing into Windows Registry."""
    try:
        content = generate_reg_content(target_exe, icon_path, install_dir)
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True, f"Registry file successfully exported to: {file_path}"
    except Exception as e:
        return False, f"Failed to export registry file: {e}"


def show_native_notification(title: str, message: str):
    """Displays a native Windows message box or notification."""
    try:
        # MB_OK | MB_ICONINFORMATION = 0x40
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x40 | 0x10000)
    except Exception:
        print(f"[{title}] {message}")


if __name__ == "__main__":
    if "--install-all" in sys.argv:
        ok, msg = install_all()
        print(msg)
    elif "--uninstall-all" in sys.argv:
        ok, msg = uninstall_all()
        print(msg)
    elif "--install" in sys.argv or "--install-shell" in sys.argv:
        ok, msg = install_context_menu()
        print(msg)
    elif "--uninstall" in sys.argv or "--uninstall-shell" in sys.argv:
        ok, msg = uninstall_context_menu()
        print(msg)
    elif "--status" in sys.argv:
        print("Context Menu Installed:", is_context_menu_installed())
    elif "--export-reg" in sys.argv:
        idx = sys.argv.index("--export-reg")
        out = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "Register-DiffAndCompare.reg"
        ok, msg = export_reg_file(out)
        print(msg)
