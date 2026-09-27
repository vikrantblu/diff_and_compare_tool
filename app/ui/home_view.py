"""
diff_and_compare_tool Home / Welcome Studio
Matches signature launch screen:
- Drag & Drop anywhere: "Drag folders or files here or click a session icon to begin:"
- Clean, uncrowded session launcher cards with high-DPI vector line icons:
  Row 1 (Primary 5 sessions):
    1. Folder Compare
    2. Folder Merge
    3. Folder Sync
    4. Text Compare
    5. Text Merge
  Row 2 (Specialized 3 sessions):
    6. Table / CSV Compare
    7. Image Diff Studio
    8. Hex & Binary Diff
- Clean, unobtrusive staged 'Select Left' pill (only displayed when a Left target is staged).
- Explorer context menu management is placed in Tools menu, keeping the Home canvas clean.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMessageBox, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from app.ui.styles.icons import get_line_icon, get_line_pixmap
from app.core.shell_integration import (
    get_left_path, set_left_path, clear_state,
    is_context_menu_installed, install_context_menu, uninstall_context_menu
)


class SessionCard(QFrame):
    """Clean, high-resolution session icon card."""

    clicked = Signal(str)

    def __init__(self, mode_id: str, title: str, icon_name: str, icon_color: str, parent=None):
        super().__init__(parent)
        self.mode_id = mode_id
        self.setObjectName("SessionCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(136, 132)

        self.setStyleSheet("""
            QFrame#SessionCard {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 12px;
            }
            QFrame#SessionCard:hover {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #eff6ff);
                border: 1.5px solid qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #0969da, stop:0.35 #60a5fa, stop:0.7 #a855f7, stop:1 #0969da);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        # High-DPI Vector Icon rendered natively at 52x52
        lbl_icon = QLabel()
        lbl_icon.setAlignment(Qt.AlignCenter)
        lbl_icon.setStyleSheet("background: transparent; border: none; padding: 0px;")
        lbl_icon.setPixmap(get_line_pixmap(icon_name, icon_color, size=52))
        layout.addWidget(lbl_icon)

        # Title Label
        lbl_title = QLabel(title)
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setWordWrap(True)
        lbl_title.setStyleSheet("""
            QLabel {
                font-weight: 700;
                font-size: 12px;
                color: #1e293b;
                background: transparent;
                border: none;
                padding: 0px;
            }
        """)
        layout.addWidget(lbl_title)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.mode_id)


class HomeView(QWidget):
    """Home / Welcome Studio comparison session dashboard."""

    sessionSelected = Signal(str)                          # mode_id
    compareFilesRequested = Signal(str, str)              # (left_path, right_path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 48, 40, 36)
        main_layout.setSpacing(24)
        main_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # 1. Clean Centered Prompt
        prompt_box = QWidget()
        p_layout = QVBoxLayout(prompt_box)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setSpacing(6)
        p_layout.setAlignment(Qt.AlignCenter)

        lbl_prompt = QLabel("Drag folders or files here\nor click a session icon to begin:")
        lbl_prompt.setAlignment(Qt.AlignCenter)
        lbl_prompt.setStyleSheet("font-size: 16px; font-weight: 600; color: #1e293b; border: none; line-height: 1.4;")
        p_layout.addWidget(lbl_prompt)

        main_layout.addWidget(prompt_box)

        # Spacer between prompt and cards
        main_layout.addSpacing(12)

        # 2. Row 1: Primary Sessions (5 cards)
        row1_widget = QWidget()
        row1_layout = QHBoxLayout(row1_widget)
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(16)
        row1_layout.setAlignment(Qt.AlignCenter)

        primary_sessions = [
            ("folder", "Folder Compare", "folder-compare", "#d97706"),
            ("folder_merge", "Folder Merge", "folder-merge", "#b45309"),
            ("folder_sync", "Folder Sync", "folder-sync", "#059669"),
            ("text", "Text Compare", "text-compare", "#0969da"),
            ("merge", "Text Merge", "text-merge", "#16a34a"),
        ]

        for mode_id, title, icon_name, icon_color in primary_sessions:
            card = SessionCard(mode_id, title, icon_name, icon_color)
            card.clicked.connect(self._on_card_clicked)
            row1_layout.addWidget(card)

        main_layout.addWidget(row1_widget)

        # 3. Row 2: Specialized Sessions (3 cards centered below Row 1)
        row2_widget = QWidget()
        row2_layout = QHBoxLayout(row2_widget)
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(16)
        row2_layout.setAlignment(Qt.AlignCenter)

        secondary_sessions = [
            ("table", "Table / CSV\nCompare", "table", "#0891b2"),
            ("image", "Image Diff\nStudio", "image", "#7c3aed"),
            ("hex", "Hex & Binary\nDiff", "cpu", "#475569"),
        ]

        for mode_id, title, icon_name, icon_color in secondary_sessions:
            card = SessionCard(mode_id, title, icon_name, icon_color)
            card.clicked.connect(self._on_card_clicked)
            row2_layout.addWidget(card)

        main_layout.addWidget(row2_widget)

        # 4. Staged Left Target Pill (Clean floating pill, shown ONLY when a Left target is staged)
        self.left_cache_card = QFrame()
        self.left_cache_card.setStyleSheet("""
            QFrame {
                background-color: #eff6ff;
                border: 1px solid #bfdbfe;
                border-radius: 8px;
                padding: 6px 14px;
            }
        """)
        lc_layout = QHBoxLayout(self.left_cache_card)
        lc_layout.setContentsMargins(12, 6, 12, 6)
        lc_layout.setSpacing(12)

        self.lbl_left_cache = QLabel()
        self.lbl_left_cache.setStyleSheet("color: #1e40af; font-weight: 600; font-size: 12px; border: none;")
        lc_layout.addWidget(self.lbl_left_cache, 1)

        self.btn_clear_left = QPushButton(" Clear Left Target")
        self.btn_clear_left.setIcon(get_line_icon("x", "#cf222e"))
        self.btn_clear_left.setFixedHeight(26)
        self.btn_clear_left.clicked.connect(self._clear_left)
        lc_layout.addWidget(self.btn_clear_left)

        main_layout.addSpacing(16)
        main_layout.addWidget(self.left_cache_card)

        # Refresh initial state
        self.refresh_state()

    def refresh_state(self):
        """Updates current Left target pill."""
        left = get_left_path()
        if left and os.path.exists(left):
            self.lbl_left_cache.setText(f"📌 Staged Left Target: {left}   (Select Right in Explorer or drop 2nd file to compare)")
            self.left_cache_card.setVisible(True)
        else:
            self.left_cache_card.setVisible(False)

    def _clear_left(self):
        clear_state()
        self.refresh_state()

    def _on_card_clicked(self, mode_id: str):
        self.sessionSelected.emit(mode_id)

    # Drag & Drop Support across entire Home canvas
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if not paths:
            return

        if len(paths) >= 2:
            self.compareFilesRequested.emit(paths[0], paths[1])
        elif len(paths) == 1:
            left = get_left_path()
            if left and os.path.exists(left) and os.path.abspath(left) != os.path.abspath(paths[0]):
                self.compareFilesRequested.emit(left, paths[0])
            else:
                set_left_path(paths[0])
                self.refresh_state()
                QMessageBox.information(
                    self, "Selected Left",
                    f"Selected as Left Target:\n{paths[0]}\n\nNow drag another file/folder here or select 'Select Right' in Windows Explorer."
                )
