"""
Modern Pane Header Widget (Light Theme)
Displays file paths, encoding, line counts, save action, and per-pane diff badges.
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from app.ui.styles.icons import get_line_icon
import os


class EditorHeader(QWidget):
    """Modern header strip placed above an editor pane."""

    fileOpened = Signal(str, str)
    saveRequested = Signal()

    def __init__(self, title: str = "Pane", default_path: str = "Untitled.txt", parent=None):
        super().__init__(parent)
        self.current_file_path = default_path
        self.is_dirty = False

        self.setObjectName("EditorHeader")
        self.setFixedHeight(40)
        self.setStyleSheet("""
            #EditorHeader {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f8fafc);
                border-bottom: 1.5px solid #cbd5e1;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(10)

        # Pane role title with crisp pill border
        is_left = "LEFT" in title.upper() or "MINE" in title.upper()
        pill_bg = "stop:0 #eff6ff, stop:1 #dbeafe" if is_left else "stop:0 #f0fdf4, stop:1 #dcfce7"
        pill_border = "#bfdbfe" if is_left else "#bbf7d0"
        pill_color = "#1d4ed8" if is_left else "#15803d"

        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setStyleSheet(f"""
            color: {pill_color};
            font-weight: 700;
            font-size: 11px;
            background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, {pill_bg});
            padding: 4px 10px;
            border-radius: 5px;
            border: 1px solid {pill_border};
        """)
        layout.addWidget(self.lbl_title)

        # File path label
        self.lbl_path = QLabel(os.path.basename(default_path))
        self.lbl_path.setToolTip(default_path)
        self.lbl_path.setStyleSheet("color: #0f172a; font-weight: 600; font-size: 12px; border: none; background: transparent;")
        layout.addWidget(self.lbl_path)

        # Diff metrics badge with crisp border
        self.lbl_badge = QLabel("")
        self.lbl_badge.setStyleSheet("font-size: 11px; padding: 2px 7px; border-radius: 4px; border: 1px solid #cbd5e1; background: #ffffff;")
        self.lbl_badge.setToolTip("Differences in this file: +added, -deleted, ~modified")
        self.lbl_badge.setVisible(False)
        layout.addWidget(self.lbl_badge)

        layout.addStretch()

        # Encoding / Line ending badge with border
        self.lbl_meta = QLabel("UTF-8 | LF")
        self.lbl_meta.setStyleSheet("""
            color: #475569;
            font-size: 11px;
            background: #f1f5f9;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            padding: 3px 8px;
            font-weight: 500;
        """)
        layout.addWidget(self.lbl_meta)

        # Browse button with line icon
        self.btn_browse = QPushButton(" Browse...")
        self.btn_browse.setIcon(get_line_icon("folder-open", "#1e293b"))
        self.btn_browse.setFixedHeight(28)
        self.btn_browse.clicked.connect(self._open_file_dialog)
        layout.addWidget(self.btn_browse)

        # Save button with line icon
        self.btn_save = QPushButton(" Save")
        self.btn_save.setIcon(get_line_icon("save", "#1e293b"))
        self.btn_save.setFixedHeight(28)
        self.btn_save.clicked.connect(self.saveRequested.emit)
        layout.addWidget(self.btn_save)

    def set_file_info(self, file_path: str, dirty: bool = False, display_title: str = None):
        self.current_file_path = file_path
        self.is_dirty = dirty
        name = display_title if display_title else (os.path.basename(file_path) if file_path else "Untitled")
        if dirty:
            name += " *"
        self.lbl_path.setText(name)
        self.lbl_path.setToolTip(display_title if display_title else file_path)

    def set_diff_stats(self, added: int, deleted: int, modified: int):
        parts = []
        if added > 0:
            parts.append(f"<span style='color: #1a7f37; font-weight: bold;'>+{added}</span>")
        if deleted > 0:
            parts.append(f"<span style='color: #cf222e; font-weight: bold;'>-{deleted}</span>")
        if modified > 0:
            parts.append(f"<span style='color: #0969da; font-weight: bold;'>~{modified}</span>")

        if parts:
            self.lbl_badge.setText(" ".join(parts))
            self.lbl_badge.setVisible(True)
        else:
            self.lbl_badge.setText("")
            self.lbl_badge.setVisible(False)

    def _open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open File for Comparison", "", "All Files (*.*);;Python Files (*.py);;Text Files (*.txt)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                self.set_file_info(file_path, dirty=False)
                self.fileOpened.emit(file_path, content)
            except Exception as e:
                print(f"Error opening file: {e}")
