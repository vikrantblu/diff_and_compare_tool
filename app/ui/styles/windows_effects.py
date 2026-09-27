"""
Windows 11 Desktop Window Manager (DWM) Modern Backdrop Effects
Supports:
- Mica (DWMWA_SYSTEMBACKDROP_TYPE = 2)
- Acrylic (DWMWA_SYSTEMBACKDROP_TYPE = 3)
- Mica Alt (Tabbed Backdrop, DWMWA_SYSTEMBACKDROP_TYPE = 4)
- Immersive Dark/Light Mode synchronization (DWMWA_USE_IMMERSIVE_DARK_MODE = 20)
- Rounded Corner Preference (DWMWA_WINDOW_CORNER_PREFERENCE = 33)
"""

import sys
import ctypes
from typing import Optional


# DWM Window Attribute constants
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_SYSTEMBACKDROP_TYPE = 38

# Backdrop types
BACKDROP_AUTO = 0
BACKDROP_NONE = 1
BACKDROP_MICA = 2
BACKDROP_ACRYLIC = 3
BACKDROP_MICA_ALT = 4

# Corner preferences
CORNER_DEFAULT = 0
CORNER_DONOTROUND = 1
CORNER_ROUND = 2
CORNER_ROUNDSMALL = 3


def is_windows_11_or_greater() -> bool:
    """Checks if running on Windows 11 (build >= 22000)."""
    if sys.platform != "win32":
        return False
    try:
        ver = sys.getwindowsversion()
        return ver.major >= 10 and ver.build >= 22000
    except Exception:
        return False


def apply_windows_material(window_handle: int, backdrop_type: int = BACKDROP_MICA_ALT, dark_mode: bool = False) -> bool:
    """
    Applies modern Windows 11 DWM backdrop effects (Mica Alt or Acrylic) to a window HWND.
    Fails safely without exception on older Windows or unsupported platforms.
    """
    if not is_windows_11_or_greater() or not window_handle:
        return False

    try:
        dwmapi = ctypes.windll.dwmapi
        hwnd = ctypes.c_void_p(int(window_handle))

        # 1. Dark/Light mode synchronization
        dark_val = ctypes.c_int(1 if dark_mode else 0)
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            ctypes.c_uint(DWMWA_USE_IMMERSIVE_DARK_MODE),
            ctypes.byref(dark_val),
            ctypes.sizeof(dark_val)
        )

        # 2. Window Corner Preference (Rounded)
        corner_val = ctypes.c_int(CORNER_ROUND)
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            ctypes.c_uint(DWMWA_WINDOW_CORNER_PREFERENCE),
            ctypes.byref(corner_val),
            ctypes.sizeof(corner_val)
        )

        # 3. System Backdrop (Mica Alt / Acrylic)
        backdrop_val = ctypes.c_int(backdrop_type)
        hr = dwmapi.DwmSetWindowAttribute(
            hwnd,
            ctypes.c_uint(DWMWA_SYSTEMBACKDROP_TYPE),
            ctypes.byref(backdrop_val),
            ctypes.sizeof(backdrop_val)
        )
        return hr == 0
    except Exception:
        return False
