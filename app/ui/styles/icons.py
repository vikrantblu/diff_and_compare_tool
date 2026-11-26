"""
Modern Vector Line Icon Provider (Feather / Lucide style)
Renders high-DPI vector SVG line icons dynamically with theme-aware stroke colors.
"""

import os
import sys
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray, Qt

# SVG Path definitions (24x24 viewBox, stroke-width=2, linecap=round, linejoin=round)
SVG_ICONS = {
    "arrow-up": """<polyline points="18 15 12 9 6 15"></polyline>""",
    "arrow-down": """<polyline points="6 9 12 15 18 9"></polyline>""",
    "arrow-left": """<line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline>""",
    "arrow-right": """<line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline>""",
    "chevron-left": """<polyline points="15 18 9 12 15 6"></polyline>""",
    "chevron-right": """<polyline points="9 18 15 12 9 6"></polyline>""",
    "swap": """<polyline points="16 3 21 3 21 8"></polyline><line x1="4" y1="20" x2="21" y2="3"></line><polyline points="21 16 21 21 16 21"></polyline><line x1="15" y1="15" x2="21" y2="21"></line><line x1="4" y1="4" x2="9" y2="9"></line>""",
    "save": """<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline>""",
    "folder": """<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>""",
    "folder-open": """<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path><path d="M2 10h20"></path>""",
    "file-text": """<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline>""",
    "diff": """<rect x="2" y="3" width="9" height="18" rx="2"></rect><rect x="13" y="3" width="9" height="18" rx="2"></rect><line x1="6.5" y1="8" x2="6.5" y2="16"></line><line x1="17.5" y1="8" x2="17.5" y2="16"></line>""",
    "git-merge": """<circle cx="18" cy="18" r="3"></circle><circle cx="6" cy="6" r="3"></circle><path d="M6 21V9a9 9 0 0 0 9 9"></path>""",
    "git-commit": """<circle cx="12" cy="12" r="4"></circle><line x1="1.05" y1="12" x2="7" y2="12"></line><line x1="17.01" y1="12" x2="22.96" y2="12"></line>""",
    "check": """<polyline points="20 6 9 17 4 12"></polyline>""",
    "layers": """<polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline>""",
    "refresh": """<polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>""",
    "sun": """<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>""",
    "align-justify": """<line x1="21" y1="10" x2="3" y2="10"></line><line x1="21" y1="6" x2="3" y2="6"></line><line x1="21" y1="14" x2="3" y2="14"></line><line x1="21" y1="18" x2="3" y2="18"></line>""",
    "zap": """<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>""",
    "image": """<rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline>""",
    "table": """<path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18"></path>""",
    "cpu": """<rect x="4" y="4" width="16" height="16" rx="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="14" x2="23" y2="14"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="14" x2="4" y2="14"></line>""",
    "sparkles": """<path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"></path>""",
    "filter": """<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>""",
    "archive": """<polyline points="21 8 21 21 3 21 3 8"></polyline><rect x="1" y="3" width="22" height="5"></rect><line x1="10" y1="12" x2="14" y2="12"></line>""",
    "plus": """<line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line>""",
    "code": """<polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline>""",
    "sliders": """<line x1="4" y1="21" x2="4" y2="14"></line><line x1="4" y1="10" x2="4" y2="3"></line><line x1="12" y1="21" x2="12" y2="12"></line><line x1="12" y1="8" x2="12" y2="3"></line><line x1="20" y1="21" x2="20" y2="16"></line><line x1="20" y1="12" x2="20" y2="3"></line>""",
    "x": """<line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>""",
    "download": """<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line>""",
    "folder-compare": """<path d="M4 4h4l2 2h4a2 2 0 0 1 2 2v2H4a2 2 0 0 0-2 2v6"></path><path d="M8 10h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2z"></path><path d="M12 16h6"></path><path d="M15 13.5l2.5 2.5-2.5 2.5"></path>""",
    "folder-merge": """<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="2"></circle><path d="M9 17l3-2 3 2"></path>""",
    "folder-sync": """<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path><path d="M9 14a3 3 0 0 1 4.2-2.5"></path><polyline points="14 9 14 12 11 12"></polyline><path d="M15 14a3 3 0 0 1-4.2 2.5"></path><polyline points="10 19 10 16 13 16"></polyline>""",
    "text-compare": """<rect x="2" y="3" width="8" height="18" rx="1.5"></rect><rect x="14" y="3" width="8" height="18" rx="1.5"></rect><line x1="4.5" y1="8" x2="7.5" y2="8"></line><line x1="4.5" y1="12" x2="7.5" y2="12"></line><line x1="4.5" y1="16" x2="7.5" y2="16"></line><line x1="16.5" y1="8" x2="19.5" y2="8"></line><line x1="16.5" y1="12" x2="19.5" y2="12"></line><line x1="16.5" y1="16" x2="19.5" y2="16"></line>""",
    "text-merge": """<rect x="2" y="2.5" width="8" height="9" rx="1.5"></rect><rect x="14" y="2.5" width="8" height="9" rx="1.5"></rect><rect x="8" y="13" width="8" height="9" rx="1.5"></rect><path d="M6 11.5v1.5a1.5 1.5 0 0 0 1.5 1.5H8"></path><path d="M18 11.5v1.5a1.5 1.5 0 0 1-1.5 1.5H16"></path>""",
    "search": """<circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>""",
    "undo": """<polyline points="1 4 1 10 7 10"></polyline><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path>""",
    "redo": """<polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>""",
    "shield": """<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><polyline points="9 12 11 14 15 10"></polyline>""",
    "zoom-in": """<circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line><line x1="11" y1="8" x2="11" y2="14"></line><line x1="8" y1="11" x2="14" y2="11"></line>""",
    "zoom-out": """<circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line><line x1="8" y1="11" x2="14" y2="11"></line>""",
    "maximize": """<polyline points="15 3 21 3 21 9"></polyline><polyline points="9 21 3 21 3 15"></polyline><line x1="21" y1="3" x2="14" y2="10"></line><line x1="3" y1="21" x2="10" y2="14"></line>""",
    "clipboard": """<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path><rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect>""",
    "trash": """<polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>""",
    "copy": """<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>""",
    "edit": """<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>""",
    "wrap": """<polyline points="17 10 21 14 17 18"></polyline><path d="M3 6h18"></path><path d="M3 14h15a3 3 0 0 0 0-6"></path><path d="M3 18h7"></path>""",
    "eye": """<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>""",
    "hash": """<line x1="4" y1="9" x2="20" y2="9"></line><line x1="4" y1="15" x2="20" y2="15"></line><line x1="10" y1="3" x2="8" y2="21"></line><line x1="16" y1="3" x2="14" y2="21"></line>""",
    "lock": """<rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path>""",
    "unlock": """<rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 9.9-1"></path>""",
    "git-branch": """<line x1="6" y1="3" x2="6" y2="15"></line><circle cx="18" cy="6" r="3"></circle><circle cx="6" cy="18" r="3"></circle><path d="M18 9a9 9 0 0 1-9 9"></path>""",
    "terminal": """<polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line>""",
    "file-code": """<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><polyline points="10 13 8 15 10 17"></polyline><polyline points="14 13 16 15 14 17"></polyline>""",
    "list": """<line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line>""",
    "bell": """<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path>""",
    "command": """<path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H6a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 3 3 0 0 0-3-3z"></path>""",
    "globe": """<circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>""",
}


def get_line_icon(name: str, color: str = "#24292f", size: int = 16) -> QIcon:
    """Renders a crisp vector line icon as a QIcon."""
    inner = SVG_ICONS.get(name, SVG_ICONS["file-text"])
    svg_template = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round">{inner}</svg>'
    )

    renderer = QSvgRenderer(QByteArray(svg_template.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()

    return QIcon(pixmap)


def get_line_pixmap(name: str, color: str = "#24292f", size: int = 48) -> QPixmap:
    """Renders a high-DPI vector pixmap directly at the exact requested pixel size."""
    inner = SVG_ICONS.get(name, SVG_ICONS.get("file-text", ""))
    svg_template = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round">{inner}</svg>'
    )

    renderer = QSvgRenderer(QByteArray(svg_template.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()

    return pixmap


STUDIO_BADGE_THEMES = {
    "folder": ("folder-compare", "#b45309", "#fffbeb", "#fef3c7", "#fcd34d"),
    "folder_merge": ("folder-merge", "#c2410c", "#fff7ed", "#ffedd5", "#fdba74"),
    "folder_sync": ("folder-sync", "#047857", "#ecfdf5", "#d1fae5", "#6ee7b7"),
    "text": ("text-compare", "#0969da", "#eff6ff", "#dbeafe", "#93c5fd"),
    "merge": ("text-merge", "#15803d", "#f0fdf4", "#dcfce7", "#86efac"),
    "table": ("table", "#0e7490", "#ecfeff", "#cffafe", "#67e8f9"),
    "structured": ("code", "#be123c", "#fff1f2", "#ffe4e6", "#fda4af"),
    "contract": ("shield", "#1d4ed8", "#eef2ff", "#e0e7ff", "#a5b4fc"),
    "image": ("image", "#7c3aed", "#f5f3ff", "#ede9fe", "#c4b5fd"),
    "hex": ("cpu", "#334155", "#f8fafc", "#e2e8f0", "#cbd5e1"),
}


def get_studio_badge_pixmap(mode_id: str, size: int = 52) -> QPixmap:
    """Renders a Fluent Light duotone rounded-squircle badge for a studio mode."""
    icon_name, stroke_color, bg_top, bg_bottom, border_color = STUDIO_BADGE_THEMES.get(
        mode_id,
        ("diff", "#0969da", "#eff6ff", "#dbeafe", "#93c5fd"),
    )
    inner = SVG_ICONS.get(icon_name, SVG_ICONS["file-text"])
    grad_id = f"badgeGrad_{mode_id}"
    svg_template = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 40 40">'
        f'<defs><linearGradient id="{grad_id}" x1="0%" y1="0%" x2="0%" y2="100%">'
        f'<stop offset="0%" stop-color="{bg_top}"/><stop offset="100%" stop-color="{bg_bottom}"/>'
        f'</linearGradient></defs>'
        f'<rect x="1" y="1" width="38" height="38" rx="10" ry="10" '
        f'fill="url(#{grad_id})" stroke="{border_color}" stroke-width="1.25"/>'
        f'<g transform="translate(8,8)" fill="none" stroke="{stroke_color}" '
        f'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">{inner}</g>'
        f'</svg>'
    )

    renderer = QSvgRenderer(QByteArray(svg_template.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    return pixmap


def get_studio_badge_icon(mode_id: str, size: int = 20) -> QIcon:
    """Returns a QIcon wrapping the Fluent Light duotone badge for tabs and menus."""
    return QIcon(get_studio_badge_pixmap(mode_id, size=size))


def _find_asset(filename: str) -> str:
    """Resolves an asset inside assets/ across source tree and frozen PyInstaller bundles."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    cand = os.path.join(base_dir, "assets", filename)
    if os.path.isfile(cand):
        return cand
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = os.path.join(meipass, "assets", filename)
        if os.path.isfile(bundled):
            return bundled
    return ""


def get_app_icon() -> QIcon:
    """Returns the official diff_and_compare_tool application icon."""
    ico_path = _find_asset("app_icon.ico")
    if ico_path:
        return QIcon(ico_path)
    png_path = _find_asset("app_icon.png")
    if png_path:
        return QIcon(png_path)
    return get_line_icon("diff", "#0969da", 32)


def get_app_icon_pixmap(size: int = 64) -> QPixmap:
    """Returns a high-DPI pixmap of the application icon."""
    png_path = _find_asset("app_icon.png")
    if png_path:
        pm = QPixmap(png_path)
        return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return get_line_pixmap("diff", "#0969da", size)
