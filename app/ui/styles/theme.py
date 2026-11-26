"""
Modern Windows 11 / Fluent Light (White) Theme QSS Palette
Features:
- Crisp, high-contrast structural borders with depth and elevation.
- Radiant Shimmering Gradient Borders on active tabs, hover states, and focused inputs.
- Windows 11 Fluent typography and balanced, non-cramped spacing.
"""

import os
import sys


def _resolve_checkmark_asset() -> str:
    """Resolves checkmark.png path both in source checkout and frozen PyInstaller bundles."""
    local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "checkmark.png")
    if os.path.isfile(local_path):
        return local_path.replace("\\", "/")
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = os.path.join(meipass, "app", "ui", "styles", "assets", "checkmark.png")
        if os.path.isfile(bundled):
            return bundled.replace("\\", "/")
        alt = os.path.join(meipass, "assets", "checkmark.png")
        if os.path.isfile(alt):
            return alt.replace("\\", "/")
    return local_path.replace("\\", "/")


_CHECKMARK_ASSET = _resolve_checkmark_asset()

MODERN_LIGHT_QSS = """
/* Global Window & Typography (Modern Windows 11 White / Light Mode) */
QWidget {
    background-color: #ffffff;
    color: #0f172a;
    font-family: "Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
    font-size: 12px;
    selection-background-color: #b6e3ff;
    selection-color: #0969da;
}

QMainWindow, QDialog {
    background-color: #f8fafc;
    color: #0f172a;
}

QMenuBar {
    background-color: #ffffff;
    color: #0f172a;
    border-bottom: 1px solid #e2e8f0;
    padding: 2px 4px;
}

QMenuBar::item {
    padding: 4px 10px;
    border-radius: 4px;
    background: transparent;
}

QMenuBar::item:selected {
    background-color: #eff6ff;
    color: #0969da;
}

QMenu {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px 0px;
    font-size: 12px;
}

QMenu::item {
    padding: 6px 22px 6px 12px;
}

QMenu::item:selected {
    background-color: #eff6ff;
    color: #0969da;
}

QMenu::separator {
    height: 1px;
    background: #e2e8f0;
    margin: 4px 8px;
}

/* Tab Widget Shell */
QTabWidget::pane {
    border: 1px solid #cbd5e1;
    background-color: #ffffff;
    top: -1px;
}

QTabWidget::tab-bar {
    left: 4px;
}

/* Tab Bar & Individual Tabs */
QTabBar {
    background-color: #f1f5f9;
    border-bottom: 2px solid #cbd5e1;
}

QTabBar::tab {
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f8fafc);
    color: #475569;
    padding: 7px 14px;
    margin-right: 3px;
    margin-top: 3px;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    border: 1px solid #cbd5e1;
    border-bottom: 1px solid #cbd5e1;
    font-weight: 600;
    font-size: 12px;
}

/* Hover Tab with Shimmer Highlight */
QTabBar::tab:hover {
    background: #ffffff;
    color: #0f172a;
    border: 1px solid qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #93c5fd, stop:0.5 #3b82f6, stop:1 #93c5fd);
    border-bottom: 1px solid #cbd5e1;
}

/* Active Selected Tab with Luminous Shimmer Border Accent */
QTabBar::tab:selected {
    background: #ffffff;
    color: #0969da;
    border: 1px solid #cbd5e1;
    border-bottom: 2px solid #ffffff;
    border-top: 3px solid qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
        stop:0 #0969da, stop:0.25 #58a6ff, stop:0.5 #c084fc, stop:0.75 #58a6ff, stop:1 #0969da);
    font-weight: 700;
    margin-top: 1px;
}

/* Tab Close Button */
QTabBar::close-button {
    subcontrol-position: right;
    margin-left: 6px;
    padding: 2px;
    border-radius: 4px;
}

QTabBar::close-button:hover {
    background-color: #fee2e2;
    border: 1px solid #fca5a5;
}

/* Toolbar & Command Bar */
QToolBar {
    background-color: #f8fafc;
    border-bottom: 1px solid #cbd5e1;
    padding: 6px;
    spacing: 8px;
}

/* Modern Elevated Buttons with Shimmer Borders */
QPushButton, QToolButton {
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f8fafc);
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-top: 1px solid #e2e8f0;
    border-bottom: 1.5px solid #94a3b8;
    border-radius: 6px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 500;
    min-height: 22px;
}

QToolButton::menu-indicator {
    image: none;
}

QPushButton:hover, QToolButton:hover {
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #eff6ff);
    color: #0969da;
    border: 1px solid qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
        stop:0 #0969da, stop:0.35 #60a5fa, stop:0.7 #a855f7, stop:1 #0969da);
    font-weight: 600;
}

QPushButton:pressed, QToolButton:pressed {
    background-color: #dbeafe;
    border: 1.5px solid #0969da;
    color: #1d4ed8;
}

QPushButton:checked, QToolButton:checked {
    background: #eff6ff;
    color: #0969da;
    border: 1.5px solid #2563eb;
    font-weight: 600;
}

QPushButton:disabled, QToolButton:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border: 1px solid #e2e8f0;
}

/* Primary Accent Button (Save, Resolve, Compare) */
QPushButton#PrimaryButton {
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #2563eb, stop:1 #1d4ed8);
    color: #ffffff;
    border: 1px solid #1d4ed8;
    border-radius: 6px;
    font-weight: 600;
    padding: 5px 14px;
}

QPushButton#PrimaryButton:hover {
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #1d4ed8, stop:1 #1e40af);
    border: 1px solid #60a5fa;
    color: #ffffff;
}

QPushButton#PrimaryButton:pressed {
    background-color: #1e3a8a;
    border: 1.5px solid #60a5fa;
    color: #ffffff;
}

QPushButton#PrimaryButton:disabled {
    background: #cbd5e1;
    color: #64748b;
    border: 1px solid #cbd5e1;
}

/* Splitter */
QSplitter::handle {
    background-color: #e2e8f0;
}

QSplitter::handle:hover {
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #8b5cf6);
}

/* Tree, Table & List Views with Proper Framing */
QTreeWidget, QTreeView, QListWidget, QTableWidget, QTableView {
    background-color: #ffffff;
    alternate-background-color: #f8fafc;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    outline: none;
    font-size: 12px;
    gridline-color: #e2e8f0;
}

QTreeWidget::item, QTreeView::item, QTableWidget::item, QTableView::item {
    padding: 4px;
    border-bottom: 1px solid #f1f5f9;
}

QTreeWidget::item:hover, QTreeView::item:hover, QListWidget::item:hover {
    background-color: #f8fafc;
}

QTreeWidget::item:selected, QTreeView::item:selected, QListWidget::item:selected {
    background-color: #eff6ff;
    color: #0969da;
}

QHeaderView::section {
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f8fafc);
    color: #475569;
    padding: 6px 10px;
    border: none;
    border-right: 1px solid #cbd5e1;
    border-bottom: 1px solid #cbd5e1;
    font-weight: 600;
    font-size: 11px;
}

/* Text Editors */
QPlainTextEdit, QTextEdit {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    selection-background-color: #b6e3ff;
    selection-color: #0969da;
}

/* Inputs, Combos & SpinBoxes with Shimmer Focus */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-bottom: 1.5px solid #94a3b8;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1.5px solid qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
        stop:0 #2563eb, stop:0.5 #60a5fa, stop:1 #2563eb);
    background-color: #ffffff;
}

QComboBox::drop-down {
    border: none;
    padding-right: 6px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    selection-background-color: #eff6ff;
    selection-color: #0969da;
}

/* Checkboxes */
QCheckBox {
    spacing: 7px;
    color: #1e293b;
    font-weight: 500;
    font-size: 12px;
    background: transparent;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1.5px solid #94a3b8;
    border-radius: 4px;
    background-color: #ffffff;
}

QCheckBox::indicator:hover {
    border: 1.5px solid #2563eb;
    background-color: #eff6ff;
}

QCheckBox::indicator:checked {
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #2563eb, stop:1 #1d4ed8);
    border: 1.5px solid #1d4ed8;
    image: url("__CHECKMARK_ASSET__");
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    background-color: #f1f5f9;
    color: #0f172a;
    text-align: center;
    font-size: 11px;
    font-weight: 600;
}

QProgressBar::chunk {
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #0969da);
    border-radius: 3px;
}

/* Sleek Scrollbars with Soft Framing */
QScrollBar:vertical {
    border: none;
    background: #f8fafc;
    width: 12px;
    margin: 0px;
    border-left: 1px solid #e2e8f0;
}

QScrollBar::handle:vertical {
    background: #cbd5e1;
    min-height: 24px;
    border-radius: 5px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #f8fafc;
    height: 12px;
    margin: 0px;
    border-top: 1px solid #e2e8f0;
}

QScrollBar::handle:horizontal {
    background: #cbd5e1;
    min-width: 24px;
    border-radius: 5px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background: #94a3b8;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Status Bar with Elevated Top Border */
QStatusBar {
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #f8fafc, stop:1 #f1f5f9);
    color: #475569;
    border-top: 1px solid #cbd5e1;
    font-size: 11px;
    font-weight: 500;
}

QStatusBar QLabel {
    color: #475569;
    padding: 0 8px;
    background: transparent;
}

/* Tooltips */
QToolTip {
    background-color: #0f172a;
    color: #ffffff;
    border: 1px solid #334155;
    border-radius: 5px;
    padding: 6px 10px;
    font-size: 12px;
}
"""

MODERN_LIGHT_QSS = MODERN_LIGHT_QSS.replace("__CHECKMARK_ASSET__", _CHECKMARK_ASSET)
