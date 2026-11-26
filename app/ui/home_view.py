"""
diff_and_compare_tool Home / Welcome Studio (White / Light Theme)
- Drag & Drop anywhere: "Drag folders or files here or click a session icon to begin:"
- Session launcher cards covering all 10 studio modes:
  Row 1 (Primary 5): Folder Compare, Folder Merge, Folder Sync, Text Compare, Text Merge
  Row 2 (Specialized 5): Table / CSV, Structured (JSON/YAML/XML), API Contract Audit, Image Diff, Hex & Binary
- Recent Comparisons list & Compare Clipboard action.
- Clean staged 'Select Left' pill (shown only when a Left target is staged).
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMessageBox, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from app.ui.styles.icons import (
    get_line_icon,
    get_line_pixmap,
    get_app_icon_pixmap,
    get_studio_badge_pixmap,
)
from app.core.shell_integration import get_left_path, set_left_path, clear_state
from app.core.session_manager import SessionManager


class SessionCard(QFrame):
    """Fluent Light studio card with duotone badge, title, and capability subtitle."""

    clicked = Signal(str)

    def __init__(
        self,
        mode_id: str,
        title: str,
        icon_name: str,
        icon_color: str,
        parent=None,
        subtitle: str = "",
    ):
        super().__init__(parent)
        self.mode_id = mode_id
        self.setObjectName("SessionCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(152, 142)

        self.setStyleSheet("""
            QFrame#SessionCard {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-bottom: 2px solid #cbd5e1;
                border-radius: 12px;
            }
            QFrame#SessionCard:hover {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #eff6ff);
                border: 1.5px solid #2563eb;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignCenter)

        lbl_icon = QLabel()
        lbl_icon.setAlignment(Qt.AlignCenter)
        lbl_icon.setStyleSheet("background: transparent; border: none; padding: 0px;")
        lbl_icon.setPixmap(get_studio_badge_pixmap(mode_id, size=48))
        layout.addWidget(lbl_icon)

        lbl_title = QLabel(title)
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setWordWrap(True)
        lbl_title.setStyleSheet("""
            QLabel {
                font-weight: 700;
                font-size: 12px;
                color: #0f172a;
                background: transparent;
                border: none;
                padding: 0px;
            }
        """)
        layout.addWidget(lbl_title)

        if subtitle:
            lbl_sub = QLabel(subtitle)
            lbl_sub.setAlignment(Qt.AlignCenter)
            lbl_sub.setStyleSheet(
                "font-size: 10px; font-weight: 500; color: #64748b; background: transparent; border: none;"
            )
            layout.addWidget(lbl_sub)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.mode_id)


class HomeView(QWidget):
    """Home / Welcome Studio comparison session dashboard."""

    sessionSelected = Signal(str)                          # mode_id
    compareFilesRequested = Signal(str, str)               # (left_path, right_path)
    clipboardCompareRequested = Signal()
    gitChangesRequested = Signal()
    remoteProfilesRequested = Signal()

    _DROP_HINT_DEFAULT_QSS = (
        "QFrame#DropHintFrame { background: #f8fafc; border: 1.5px dashed #cbd5e1; border-radius: 10px; padding: 4px 12px; }"
    )
    _DROP_HINT_ACTIVE_QSS = (
        "QFrame#DropHintFrame { background: #eff6ff; border: 2px dashed #0969da; border-radius: 10px; padding: 4px 12px; }"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(36, 22, 36, 18)
        main_layout.setSpacing(14)
        main_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # 1. Branded Studio Header Card
        hero_card = QFrame()
        hero_card.setObjectName("HomeHeroCard")
        hero_card.setMaximumWidth(816)
        hero_card.setStyleSheet("""
            QFrame#HomeHeroCard {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 #ffffff, stop:0.65 #f8fafc, stop:1 #eff6ff);
                border: 1px solid #cbd5e1;
                border-radius: 14px;
            }
        """)
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(18, 14, 18, 14)
        hero_layout.setSpacing(16)

        lbl_logo = QLabel()
        lbl_logo.setFixedSize(56, 56)
        lbl_logo.setAlignment(Qt.AlignCenter)
        lbl_logo.setStyleSheet("background: transparent; border: none;")
        lbl_logo.setPixmap(get_app_icon_pixmap(56))
        hero_layout.addWidget(lbl_logo)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(3)

        lbl_brand = QLabel("Diff & Compare Studio")
        lbl_brand.setStyleSheet(
            "font-size: 19px; font-weight: 800; color: #0f172a; background: transparent; border: none;"
        )
        title_col.addWidget(lbl_brand)

        lbl_tagline = QLabel("Multi-Format Diff, 3-Way Merge, Folder Sync & Remote VFS Workbench")
        lbl_tagline.setStyleSheet(
            "font-size: 12px; font-weight: 500; color: #475569; background: transparent; border: none;"
        )
        title_col.addWidget(lbl_tagline)

        pills_row = QHBoxLayout()
        pills_row.setContentsMargins(0, 4, 0, 0)
        pills_row.setSpacing(6)
        for badge_txt, bg, fg, bd in [
            ("Fluent Light", "#eff6ff", "#0969da", "#bfdbfe"),
            ("10 Studios", "#f0fdf4", "#15803d", "#bbf7d0"),
            ("SFTP · S3 · FTP", "#ecfeff", "#0e7490", "#a5f3fc"),
            ("Command Palette Ctrl+K", "#f8fafc", "#334155", "#cbd5e1"),
        ]:
            pill = QLabel(badge_txt)
            pill.setStyleSheet(
                f"background: {bg}; color: {fg}; border: 1px solid {bd}; "
                f"border-radius: 9px; padding: 2px 8px; font-size: 10.5px; font-weight: 600;"
            )
            pills_row.addWidget(pill)
        pills_row.addStretch()
        title_col.addLayout(pills_row)
        hero_layout.addLayout(title_col, 1)

        main_layout.addWidget(hero_card, 0, Qt.AlignHCenter)

        # Interactive Drag & Drop Cue Strip
        self.drop_hint_frame = QFrame()
        self.drop_hint_frame.setObjectName("DropHintFrame")
        self.drop_hint_frame.setMaximumWidth(816)
        self.drop_hint_frame.setStyleSheet(self._DROP_HINT_DEFAULT_QSS)
        dh_layout = QHBoxLayout(self.drop_hint_frame)
        dh_layout.setContentsMargins(12, 6, 12, 6)
        dh_layout.setAlignment(Qt.AlignCenter)
        lbl_prompt = QLabel("Drag folders or files anywhere here to compare immediately, or choose a studio below:")
        lbl_prompt.setAlignment(Qt.AlignCenter)
        lbl_prompt.setStyleSheet("font-size: 12.5px; font-weight: 600; color: #334155; border: none; background: transparent;")
        dh_layout.addWidget(lbl_prompt)
        main_layout.addWidget(self.drop_hint_frame, 0, Qt.AlignHCenter)

        # 2. Row 1: Primary Sessions (5 cards)
        row1_widget = QWidget()
        row1_layout = QHBoxLayout(row1_widget)
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(14)
        row1_layout.setAlignment(Qt.AlignCenter)

        primary_sessions = [
            ("folder", "Folder Compare", "folder-compare", "#d97706", "2-Way · ZIP · Remote"),
            ("folder_merge", "Folder Merge", "folder-merge", "#b45309", "3-Way Ancestor"),
            ("folder_sync", "Folder Sync", "folder-sync", "#059669", "Mirror & Bi-Dir"),
            ("text", "Text Compare", "text-compare", "#0969da", "Myers · AST · DOCX"),
            ("merge", "Text Merge", "text-merge", "#16a34a", "3-Way Conflicts"),
        ]

        for mode_id, title, icon_name, icon_color, subtitle in primary_sessions:
            card = SessionCard(mode_id, title, icon_name, icon_color, subtitle=subtitle)
            card.clicked.connect(self._on_card_clicked)
            row1_layout.addWidget(card)

        main_layout.addWidget(row1_widget)

        # 3. Row 2: Specialized Sessions (5 cards)
        row2_widget = QWidget()
        row2_layout = QHBoxLayout(row2_widget)
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(14)
        row2_layout.setAlignment(Qt.AlignCenter)

        secondary_sessions = [
            ("table", "Table / CSV\nCompare", "table", "#0891b2", "CSV · Excel · Parquet"),
            ("structured", "JSON / YAML\nXML Tree", "code", "#cf222e", "JSONPath · XPath"),
            ("contract", "API Contract\nAudit", "shield", "#0969da", "OpenAPI · GraphQL"),
            ("image", "Image & PDF\nDiff Studio", "image", "#7c3aed", "RGBA · PDF Overlay"),
            ("hex", "Hex & Binary\nDiff", "cpu", "#475569", "Virtual Multi-GB"),
        ]

        for mode_id, title, icon_name, icon_color, subtitle in secondary_sessions:
            card = SessionCard(mode_id, title, icon_name, icon_color, subtitle=subtitle)
            card.clicked.connect(self._on_card_clicked)
            row2_layout.addWidget(card)

        main_layout.addWidget(row2_widget)

        # Quick Actions: Compare Clipboard, Git Working Changes & Remote Profiles
        qa_row = QHBoxLayout()
        qa_row.setAlignment(Qt.AlignCenter)
        qa_row.setSpacing(10)
        self.btn_compare_clipboard = QPushButton(" Compare Clipboard vs Text Studio")
        self.btn_compare_clipboard.setIcon(get_line_icon("clipboard", "#0969da"))
        self.btn_compare_clipboard.setFixedHeight(32)
        self.btn_compare_clipboard.clicked.connect(self.clipboardCompareRequested.emit)
        qa_row.addWidget(self.btn_compare_clipboard)

        self.btn_git_changes = QPushButton(" Browse Git Changes (Ctrl+G)")
        self.btn_git_changes.setIcon(get_line_icon("git-branch", "#1a7f37"))
        self.btn_git_changes.setFixedHeight(32)
        self.btn_git_changes.clicked.connect(self.gitChangesRequested.emit)
        qa_row.addWidget(self.btn_git_changes)

        self.btn_remote_profiles = QPushButton(" Remote Profiles (SFTP/S3/FTP)")
        self.btn_remote_profiles.setIcon(get_line_icon("globe", "#0891b2"))
        self.btn_remote_profiles.setFixedHeight(32)
        self.btn_remote_profiles.clicked.connect(self.remoteProfilesRequested.emit)
        qa_row.addWidget(self.btn_remote_profiles)
        main_layout.addLayout(qa_row)

        # 4. Staged Left Target Pill (shown only when a Left target is staged)
        self.left_cache_card = QFrame()
        self.left_cache_card.setStyleSheet("""
            QFrame {
                background-color: #eff6ff;
                border: 1px solid #bfdbfe;
                border-radius: 8px;
                padding: 4px 12px;
            }
        """)
        lc_layout = QHBoxLayout(self.left_cache_card)
        lc_layout.setContentsMargins(10, 4, 10, 4)
        lc_layout.setSpacing(12)

        self.lbl_left_cache = QLabel()
        self.lbl_left_cache.setStyleSheet("color: #1e40af; font-weight: 600; font-size: 12px; border: none; background: transparent;")
        lc_layout.addWidget(self.lbl_left_cache, 1)

        self.btn_clear_left = QPushButton(" Clear Left Target")
        self.btn_clear_left.setIcon(get_line_icon("x", "#cf222e"))
        self.btn_clear_left.setFixedHeight(26)
        self.btn_clear_left.clicked.connect(self._clear_left)
        lc_layout.addWidget(self.btn_clear_left)

        main_layout.addWidget(self.left_cache_card)

        # 5. Recent Comparisons Panel
        self.recent_frame = QFrame()
        self.recent_frame.setMaximumWidth(816)
        self.recent_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 12px;
                padding: 8px 14px;
            }
        """)
        rf_layout = QVBoxLayout(self.recent_frame)
        rf_layout.setContentsMargins(8, 6, 8, 6)
        rf_layout.setSpacing(6)

        rf_head = QHBoxLayout()
        lbl_rec = QLabel("Recent Comparisons")
        lbl_rec.setStyleSheet("font-weight: 700; font-size: 12px; color: #334155; border: none; background: transparent;")
        rf_head.addWidget(lbl_rec)
        rf_head.addStretch()

        self.btn_clear_recent = QPushButton("Clear")
        self.btn_clear_recent.setFixedHeight(22)
        self.btn_clear_recent.clicked.connect(self._clear_recent)
        rf_head.addWidget(self.btn_clear_recent)
        rf_layout.addLayout(rf_head)

        self.list_recent = QListWidget()
        self.list_recent.setMaximumHeight(124)
        self.list_recent.itemDoubleClicked.connect(self._on_recent_clicked)
        rf_layout.addWidget(self.list_recent)

        main_layout.addWidget(self.recent_frame, 0, Qt.AlignHCenter)

        self.refresh_state()

    def refresh_state(self):
        """Updates staged Left target pill and recent comparisons list."""
        left = get_left_path()
        if left and os.path.exists(left):
            self.lbl_left_cache.setText(f"Staged Left Target: {left}   (Select Right in Explorer or drop 2nd file to compare)")
            self.left_cache_card.setVisible(True)
        else:
            self.left_cache_card.setVisible(False)

        self.list_recent.clear()
        recents = SessionManager.get_recent_comparisons(limit=8)
        diff_icon = get_line_icon("diff", "#0969da", size=14)
        for rec in recents:
            lp = rec.get("left_path", "")
            rp = rec.get("right_path", "")
            if lp and rp:
                label = f"{os.path.basename(lp)}  ↔  {os.path.basename(rp)}   ({lp}  |  {rp})"
                item = QListWidgetItem(diff_icon, label)
                item.setData(Qt.UserRole, (lp, rp))
                self.list_recent.addItem(item)
        self.recent_frame.setVisible(self.list_recent.count() > 0)

    def _clear_left(self):
        clear_state()
        self.refresh_state()

    def _clear_recent(self):
        SessionManager.clear_recent_comparisons()
        self.refresh_state()

    def _on_recent_clicked(self, item: QListWidgetItem):
        pair = item.data(Qt.UserRole)
        if pair:
            self.compareFilesRequested.emit(pair[0], pair[1])

    def _on_card_clicked(self, mode_id: str):
        self.sessionSelected.emit(mode_id)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            self.drop_hint_frame.setStyleSheet(self._DROP_HINT_ACTIVE_QSS)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.drop_hint_frame.setStyleSheet(self._DROP_HINT_DEFAULT_QSS)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        self.drop_hint_frame.setStyleSheet(self._DROP_HINT_DEFAULT_QSS)
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
