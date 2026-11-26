"""
Modern Pane Header Widget (White / Light Theme)
Displays file paths, real encoding & line-ending badges, save action, drag-and-drop, and per-pane diff badges.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox,
    QToolButton, QMenu
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from app.ui.styles.icons import get_line_icon
from app.core.file_io import read_text_file


class EditorHeader(QWidget):
    """Modern header strip placed above an editor pane."""

    fileOpened = Signal(str, str)
    saveRequested = Signal()
    readOnlyToggled = Signal(bool)
    encodingFormatChanged = Signal(str, str)  # (encoding, eol)

    SUPPORTED_ENCODINGS = ["UTF-8", "UTF-8 BOM", "UTF-16 LE", "UTF-16 BE", "Windows-1252"]
    SUPPORTED_EOLS = ["LF", "CRLF", "CR"]

    def __init__(self, title: str = "Pane", default_path: str = "Untitled.txt", parent=None):
        super().__init__(parent)
        self.current_file_path = default_path
        self.is_dirty = False
        self.encoding = "UTF-8"
        self.eol = "LF"
        self._display_title = None
        self.setAcceptDrops(True)

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

        # Encoding / Line ending interactive converter button
        self.btn_meta = QToolButton()
        self.btn_meta.setText("UTF-8 | LF")
        self.btn_meta.setPopupMode(QToolButton.InstantPopup)
        self.btn_meta.setToolTip("Click to convert Encoding or Line Endings (EOL) for saving")
        self.btn_meta.setStyleSheet("""
            QToolButton {
                color: #475569;
                font-size: 11px;
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 3px 8px;
                font-weight: 500;
            }
            QToolButton:hover { background: #e2e8f0; color: #0f172a; }
            QToolButton::menu-indicator { width: 0px; }
        """)
        self.meta_menu = QMenu(self.btn_meta)
        self.btn_meta.setMenu(self.meta_menu)
        self._rebuild_meta_menu()
        # Preserve attribute alias for callers referencing lbl_meta
        self.lbl_meta = self.btn_meta
        layout.addWidget(self.btn_meta)

        # Read-Only Lock Toggle Button
        self.btn_lock = QPushButton()
        self.btn_lock.setCheckable(True)
        self.btn_lock.setIcon(get_line_icon("unlock", "#475569"))
        self.btn_lock.setFixedSize(28, 28)
        self.btn_lock.setToolTip("Lock pane as Read-Only to protect baseline against edits or transfers")
        self.btn_lock.toggled.connect(self._on_lock_toggled)
        layout.addWidget(self.btn_lock)

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
        if display_title is not None:
            self._display_title = display_title
        elif not dirty:
            self._display_title = None
        name = display_title if display_title else (self._display_title or (os.path.basename(file_path) if file_path else "Untitled"))
        if dirty:
            name += " *"
        self.lbl_path.setText(name)
        self.lbl_path.setToolTip(display_title if display_title else file_path)

    def set_dirty(self, dirty: bool):
        if self.is_dirty != dirty:
            self.set_file_info(self.current_file_path, dirty=dirty, display_title=self._display_title)

    def set_encoding_info(self, encoding: str, eol: str):
        self.encoding = encoding or "UTF-8"
        self.eol = eol or "LF"
        self.btn_meta.setText(f"{self.encoding} | {self.eol}")
        self._rebuild_meta_menu()

    def _rebuild_meta_menu(self):
        self.meta_menu.clear()
        enc_sub = self.meta_menu.addMenu("Encoding")
        for enc in self.SUPPORTED_ENCODINGS:
            act = enc_sub.addAction(enc)
            act.setCheckable(True)
            act.setChecked(enc == self.encoding)
            act.triggered.connect(lambda _=False, e=enc: self._change_encoding(e))

        eol_sub = self.meta_menu.addMenu("Line Endings (EOL)")
        for eol in self.SUPPORTED_EOLS:
            act = eol_sub.addAction(eol)
            act.setCheckable(True)
            act.setChecked(eol == self.eol)
            act.triggered.connect(lambda _=False, el=eol: self._change_eol(el))

    def _change_encoding(self, new_enc: str):
        if new_enc != self.encoding:
            self.set_encoding_info(new_enc, self.eol)
            self.set_dirty(True)
            self.encodingFormatChanged.emit(self.encoding, self.eol)

    def _change_eol(self, new_eol: str):
        if new_eol != self.eol:
            self.set_encoding_info(self.encoding, new_eol)
            self.set_dirty(True)
            self.encodingFormatChanged.emit(self.encoding, self.eol)

    def set_read_only(self, locked: bool):
        self.btn_lock.setChecked(locked)

    def is_read_only(self) -> bool:
        return self.btn_lock.isChecked()

    def _on_lock_toggled(self, checked: bool):
        if checked:
            self.btn_lock.setIcon(get_line_icon("lock", "#b45309"))
            self.btn_lock.setStyleSheet("background: #fef3c7; border: 1px solid #f59e0b; border-radius: 5px;")
            self.btn_lock.setToolTip("Pane Locked (Read-Only) — click to unlock editing")
        else:
            self.btn_lock.setIcon(get_line_icon("unlock", "#475569"))
            self.btn_lock.setStyleSheet("")
            self.btn_lock.setToolTip("Lock pane as Read-Only to protect baseline against edits or transfers")
        self.readOnlyToggled.emit(checked)

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

    def load_local_file(self, file_path: str):
        try:
            content, enc, eol = read_text_file(file_path)
            self.set_file_info(file_path, dirty=False)
            self.set_encoding_info(enc, eol)
            self.fileOpened.emit(file_path, content)
        except Exception as e:
            QMessageBox.warning(self, "Error Opening File", f"Could not open file:\n{file_path}\n\n{e}")

    def _open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open File for Comparison", "", "All Files (*.*);;Python Files (*.py);;Text Files (*.txt)"
        )
        if file_path:
            self.load_local_file(file_path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
            if urls and os.path.isfile(urls[0]):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if urls and os.path.isfile(urls[0]):
            self.load_local_file(urls[0])
