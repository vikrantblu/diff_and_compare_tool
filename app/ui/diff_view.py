"""
Modern 2-Way Side-by-Side File Comparison View
Supports:
- Horizontal Alignment with spacer lines.
- Real-time in-place editing with debounced reactive diff updates.
- Intraline character-level highlights via non-destructive ExtraSelections.
- Seamless synchronized scrolling.
- Fixed-height top toolbar (eliminates unwanted vertical spacing).
"""

import os
import sys
from typing import List, Dict, Tuple, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSplitter,
    QLabel, QComboBox, QCheckBox, QMessageBox, QFileDialog, QSizePolicy,
    QToolButton, QMenu, QFrame, QLineEdit, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor, QTextDocument, QPen, QColor, QTextFormat

from app.ui.widgets.modern_editor import ModernCodeEditor
from app.ui.widgets.editor_header import EditorHeader
from app.ui.widgets.diff_connector import DiffConnectorWidget
from app.core.diff_engine import DiffEngine, DiffChunk, AlignedDiffResult
from app.core.git_staging import GitStagingManager
from app.ui.styles.icons import get_line_icon
from app.ui.dialogs.ai_summary_dialog import AISummaryDialog
from app.ui.dialogs.noise_filter_dialog import NoiseFilterDialog


class DiffView(QWidget):
    """Production-grade 2-Way Diff View."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.chunks: List[DiffChunk] = []
        self.current_diff_idx = -1
        self._raw_left = ""
        self._raw_right = ""
        self.active_noise_rules: List[Tuple[str, str]] = []
        self.manual_alignments: List[Tuple[int, int]] = []
        self._pending_alignment: Optional[Tuple[str, int]] = None
        self.undo_stack: List[Tuple[str, str, str]] = []
        self.redo_stack: List[Tuple[str, str, str]] = []
        self._find_matches: List[Tuple[str, int, int]] = []
        self._current_find_match_idx: int = -1

        from app.core.wal_journal import WALJournal
        self.wal = WALJournal()

        self.setup_ui()
        self.setup_connections()
        self.setup_shortcuts()

        # Realistic modern diff sample
        sample_left = (
            "import os\n"
            "import sys\n"
            "\n"
            "def calculate_tax(income, rate=0.20):\n"
            "    # Standard tax formula (legacy)\n"
            "    tax_amount = income * rate\n"
            "    return tax_amount\n"
            "\n"
            "def process_user_data(user_id):\n"
            "    print(f'Fetching user: {user_id}')\n"
            "    status = 'active'\n"
            "    return status\n"
        )
        sample_right = (
            "import os\n"
            "import sys\n"
            "import logging\n"
            "\n"
            "def calculate_tax(income, rate=0.25):\n"
            "    # Modern optimized tax calculation\n"
            "    tax_amount = income * rate * 0.95\n"
            "    return round(tax_amount, 2)\n"
            "\n"
            "def process_user_data(user_id, role='user'):\n"
            "    logging.info(f'Processing account {user_id} with role {role}')\n"
            "    status = 'active'\n"
            "    return status\n"
            "\n"
            "# New feature addition\n"
            "def audit_trail():\n"
            "    return True\n"
        )

        self._raw_left = sample_left
        self._raw_right = sample_right
        self.left_header.set_file_info("sample_local.py")
        self.right_header.set_file_info("sample_remote.py")

        self.run_diff()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Compact Top Command Toolbar with Elevated Styling & Proper Borders
        cmd_bar = QWidget()
        cmd_bar.setObjectName("DiffCmdBar")
        cmd_bar.setFixedHeight(46)
        cmd_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        cmd_bar.setStyleSheet("""
            #DiffCmdBar {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f8fafc);
                border-bottom: 1.5px solid #cbd5e1;
            }
        """)
        cmd_layout = QHBoxLayout(cmd_bar)
        cmd_layout.setContentsMargins(10, 6, 10, 6)
        cmd_layout.setSpacing(8)

        # Navigation with crisp vector line icons
        self.btn_prev = QPushButton(" Prev (F7)")
        self.btn_prev.setIcon(get_line_icon("arrow-up", "#1e293b"))
        self.btn_prev.setFixedHeight(30)

        self.btn_next = QPushButton(" Next (F8)")
        self.btn_next.setIcon(get_line_icon("arrow-down", "#1e293b"))
        self.btn_next.setFixedHeight(30)
        cmd_layout.addWidget(self.btn_prev)
        cmd_layout.addWidget(self.btn_next)

        # Swap sides with line icon
        self.btn_swap = QPushButton(" Swap (Ctrl+U)")
        self.btn_swap.setIcon(get_line_icon("swap", "#1e293b"))
        self.btn_swap.setFixedHeight(30)
        self.btn_swap.setToolTip("Swap Left and Right viewports without reloading or losing undo history (Ctrl+U)")
        cmd_layout.addWidget(self.btn_swap)

        # Undo / Redo with crisp line icons
        self.btn_undo = QPushButton(" Undo (Ctrl+Z)")
        self.btn_undo.setIcon(get_line_icon("undo", "#1e293b"))
        self.btn_undo.setFixedHeight(30)
        self.btn_undo.setEnabled(False)
        self.btn_undo.setToolTip("Undo last accepted chunk transfer or change (Ctrl+Z)")
        self.btn_undo.clicked.connect(self.undo)
        cmd_layout.addWidget(self.btn_undo)

        self.btn_redo = QPushButton(" Redo (Ctrl+Y)")
        self.btn_redo.setIcon(get_line_icon("redo", "#1e293b"))
        self.btn_redo.setFixedHeight(30)
        self.btn_redo.setEnabled(False)
        self.btn_redo.setToolTip("Redo last undone change (Ctrl+Y)")
        self.btn_redo.clicked.connect(self.redo)
        cmd_layout.addWidget(self.btn_redo)

        # In-Editor Find
        self.btn_find = QPushButton(" Find (Ctrl+F)")
        self.btn_find.setIcon(get_line_icon("search", "#1e293b"))
        self.btn_find.setFixedHeight(30)
        self.btn_find.setToolTip("Open in-editor Find bar across both diff panes (Ctrl+F)")
        self.btn_find.clicked.connect(self.toggle_find_bar)
        cmd_layout.addWidget(self.btn_find)

        cmd_layout.addSpacing(6)

        # Aligned View Toggle (Horizontal Spacer Lines)
        self.chk_aligned_view = QCheckBox("Aligned View (Spacers)")
        self.chk_aligned_view.setChecked(True)
        self.chk_aligned_view.setToolTip("Inserts blank spacer lines so matching blocks align horizontally")
        cmd_layout.addWidget(self.chk_aligned_view)

        # AST Semantic Diff Toggle (Tree-sitter AST Structural understanding)
        self.chk_ast = QCheckBox("AST Semantic")
        self.chk_ast.setChecked(True)
        self.chk_ast.setToolTip("Tree-sitter structural diffing: detects reordered functions & normalized docstrings")
        cmd_layout.addWidget(self.chk_ast)

        # Whitespace mode
        self.combo_whitespace = QComboBox()
        self.combo_whitespace.setFixedHeight(30)
        self.combo_whitespace.addItems([
            "Compare Whitespace",
            "Ignore Leading/Trailing",
            "Ignore All Whitespace"
        ])
        cmd_layout.addWidget(self.combo_whitespace)

        # Ignore Case
        self.chk_ignore_case = QCheckBox("Ignore Case")
        cmd_layout.addWidget(self.chk_ignore_case)

        # Sync Scroll
        self.chk_sync_scroll = QCheckBox("Sync Scrolling")
        self.chk_sync_scroll.setChecked(True)
        cmd_layout.addWidget(self.chk_sync_scroll)

        cmd_layout.addSpacing(6)

        # Noise & Regex filter button
        self.btn_noise = QPushButton(" Filters")
        self.btn_noise.setIcon(get_line_icon("filter", "#1e293b"))
        self.btn_noise.setFixedHeight(30)
        self.btn_noise.clicked.connect(self._open_noise_filters)
        cmd_layout.addWidget(self.btn_noise)

        # AI Summary button
        self.btn_ai_summary = QPushButton(" AI Summary")
        self.btn_ai_summary.setIcon(get_line_icon("sparkles", "#0969da"))
        self.btn_ai_summary.setFixedHeight(30)
        self.btn_ai_summary.clicked.connect(self._open_ai_summary)
        cmd_layout.addWidget(self.btn_ai_summary)

        # Export .patch button
        self.btn_export_patch = QPushButton(" Export .patch")
        self.btn_export_patch.setIcon(get_line_icon("file-text", "#1e293b"))
        self.btn_export_patch.setFixedHeight(30)
        self.btn_export_patch.clicked.connect(self._export_patch)
        cmd_layout.addWidget(self.btn_export_patch)

        # Git Actions ToolButton with dropdown menu
        self.btn_git = QToolButton()
        self.btn_git.setText(" Git")
        self.btn_git.setIcon(get_line_icon("git-commit", "#1e293b"))
        self.btn_git.setFixedHeight(30)
        self.btn_git.setPopupMode(QToolButton.InstantPopup)
        self.btn_git.setStyleSheet("""
            QToolButton {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: #ffffff;
                color: #1e293b;
                padding: 4px 10px;
                font-weight: 500;
            }
            QToolButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }
            QToolButton::menu-indicator {
                image: none;
            }
        """)
        git_menu = QMenu(self.btn_git)
        git_menu.setStyleSheet("""
            QMenu {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 0px;
                font-size: 12px;
            }
            QMenu::item {
                padding: 6px 20px 6px 12px;
            }
            QMenu::item:selected {
                background: #f1f5f9;
                color: #0969da;
            }
        """)
        git_menu.addAction("🔍  Compare with Git HEAD", self.compare_with_git_head)
        git_menu.addSeparator()
        git_menu.addAction("➕  Stage Current Hunk (git apply --cached)", lambda: self.stage_hunk(self.current_diff_idx))
        git_menu.addAction("↺  Unstage Current Hunk", lambda: self.unstage_hunk(self.current_diff_idx))
        git_menu.addAction("🗑  Discard Current Hunk (Revert)", lambda: self.discard_hunk(self.current_diff_idx))
        self.btn_git.setMenu(git_menu)
        cmd_layout.addWidget(self.btn_git)

        cmd_layout.addStretch()

        # Stats Badge with Crisp Pill Border
        self.lbl_stats = QLabel("Calculating...")
        self.lbl_stats.setFixedHeight(30)
        self.lbl_stats.setStyleSheet("""
            background-color: #ffffff;
            color: #0f172a;
            padding: 4px 12px;
            border-radius: 6px;
            border: 1px solid #cbd5e1;
            font-size: 11px;
            font-weight: 600;
        """)
        # Manual Alignment Badge / Clear Button
        self.btn_clear_alignments = QPushButton("📌 0 Alignments [✕]")
        self.btn_clear_alignments.setFixedHeight(30)
        self.btn_clear_alignments.setStyleSheet("""
            QPushButton {
                background-color: #eff6ff;
                color: #1d4ed8;
                border: 1px solid #93c5fd;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #dbeafe;
            }
        """)
        self.btn_clear_alignments.clicked.connect(self.clear_manual_alignments)
        self.btn_clear_alignments.setVisible(False)
        cmd_layout.addWidget(self.btn_clear_alignments)

        cmd_layout.addWidget(self.lbl_stats)

        main_layout.addWidget(cmd_bar, 0)  # Stretch 0 = fixed to its size

        # Manual Alignment Action Notification Banner
        self.banner_alignment = QFrame()
        self.banner_alignment.setFixedHeight(36)
        self.banner_alignment.setStyleSheet("""
            QFrame {
                background-color: #eff6ff;
                border-bottom: 1.5px solid #93c5fd;
                padding: 0 12px;
            }
        """)
        ba_layout = QHBoxLayout(self.banner_alignment)
        ba_layout.setContentsMargins(12, 0, 12, 0)
        ba_layout.setSpacing(10)

        self.lbl_align_banner = QLabel("🎯 Manual Alignment Mode")
        self.lbl_align_banner.setStyleSheet("font-size: 12px; font-weight: 600; color: #1e40af;")
        ba_layout.addWidget(self.lbl_align_banner, 1)

        btn_cancel_align = QPushButton("Cancel (Esc)")
        btn_cancel_align.setFixedHeight(24)
        btn_cancel_align.setStyleSheet("""
            QPushButton {
                background: #ffffff;
                color: #475569;
                font-size: 11px;
                border-radius: 4px;
                padding: 0 8px;
                border: 1px solid #cbd5e1;
            }
            QPushButton:hover {
                background: #f1f5f9;
            }
        """)
        btn_cancel_align.clicked.connect(self._cancel_alignment_mode)
        ba_layout.addWidget(btn_cancel_align)

        self.banner_alignment.setVisible(False)
        main_layout.addWidget(self.banner_alignment, 0)

        # 1.5 In-Editor Find Bar (Docked right below command bar)
        self.find_bar = QFrame()
        self.find_bar.setFixedHeight(38)
        self.find_bar.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border-bottom: 1.5px solid #cbd5e1;
                padding: 0 10px;
            }
        """)
        fb_layout = QHBoxLayout(self.find_bar)
        fb_layout.setContentsMargins(10, 4, 10, 4)
        fb_layout.setSpacing(8)

        lbl_find_icon = QLabel("🔍")
        lbl_find_icon.setStyleSheet("font-size: 13px; background: transparent; border: none;")
        fb_layout.addWidget(lbl_find_icon)

        self.txt_find = QLineEdit()
        self.txt_find.setPlaceholderText("Find in diff... (Enter for next, Shift+Enter for prev)")
        self.txt_find.setFixedHeight(28)
        self.txt_find.setFixedWidth(280)
        self.txt_find.setClearButtonEnabled(True)
        self.txt_find.setStyleSheet("""
            QLineEdit {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 0 8px;
                font-size: 12px;
                color: #0f172a;
            }
            QLineEdit:focus {
                border: 1.5px solid #0969da;
            }
        """)
        self.txt_find.textChanged.connect(self._on_find_text_changed)
        self.txt_find.returnPressed.connect(self.find_next)
        fb_layout.addWidget(self.txt_find)

        self.btn_find_prev = QPushButton("◀ Prev")
        self.btn_find_prev.setFixedHeight(26)
        self.btn_find_prev.setStyleSheet("QPushButton { font-size: 11px; padding: 0 8px; }")
        self.btn_find_prev.setToolTip("Previous match (Shift+Enter / Shift+F3)")
        self.btn_find_prev.clicked.connect(self.find_prev)
        fb_layout.addWidget(self.btn_find_prev)

        self.btn_find_next = QPushButton("Next ▶")
        self.btn_find_next.setFixedHeight(26)
        self.btn_find_next.setStyleSheet("QPushButton { font-size: 11px; padding: 0 8px; }")
        self.btn_find_next.setToolTip("Next match (Enter / F3)")
        self.btn_find_next.clicked.connect(self.find_next)
        fb_layout.addWidget(self.btn_find_next)

        self.chk_find_case = QCheckBox("Aa (Match Case)")
        self.chk_find_case.setStyleSheet("font-size: 11px; color: #475569;")
        self.chk_find_case.toggled.connect(self._on_find_text_changed)
        fb_layout.addWidget(self.chk_find_case)

        self.lbl_find_status = QLabel("0 matches")
        self.lbl_find_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b; padding-left: 6px;")
        fb_layout.addWidget(self.lbl_find_status)

        fb_layout.addStretch()

        btn_close_find = QPushButton("✕")
        btn_close_find.setFixedHeight(24)
        btn_close_find.setFixedWidth(24)
        btn_close_find.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #64748b;
                font-size: 13px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #e2e8f0;
                color: #0f172a;
            }
        """)
        btn_close_find.setToolTip("Close Find Bar (Esc)")
        btn_close_find.clicked.connect(self.close_find_bar)
        fb_layout.addWidget(btn_close_find)

        self.find_bar.setVisible(False)
        main_layout.addWidget(self.find_bar, 0)

        # 2. Comparison Splitter (TAKES 100% OF REMAINING VERTICAL HEIGHT)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Left Pane
        left_container = QWidget()
        l_layout = QVBoxLayout(left_container)
        l_layout.setContentsMargins(0, 0, 0, 0)
        l_layout.setSpacing(0)
        self.left_header = EditorHeader(title="Mine / Left", default_path="local_file.py")
        self.left_editor = ModernCodeEditor()
        l_layout.addWidget(self.left_header)
        l_layout.addWidget(self.left_editor)

        # Right Pane
        right_container = QWidget()
        r_layout = QVBoxLayout(right_container)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(0)
        self.right_header = EditorHeader(title="Theirs / Right", default_path="remote_file.py")
        self.right_editor = ModernCodeEditor()
        r_layout.addWidget(self.right_header)
        r_layout.addWidget(self.right_editor)

        # Middle Connector
        self.connector = DiffConnectorWidget(self.left_editor, self.right_editor)

        self.splitter.addWidget(left_container)
        self.splitter.addWidget(self.connector)
        self.splitter.addWidget(right_container)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setCollapsible(2, False)
        self.splitter.setSizes([600, 38, 600])

        main_layout.addWidget(self.splitter, 1)  # STRETCH FACTOR 1 = Fills entire window!

    def setup_connections(self):
        # Debounced live typing
        self.left_editor.liveTextChanged.connect(self._on_left_live_edit)
        self.right_editor.liveTextChanged.connect(self._on_right_live_edit)

        # Synchronized scrolling
        self.left_editor.scrolled.connect(self._on_left_scrolled)
        self.right_editor.scrolled.connect(self._on_right_scrolled)

        # Options
        self.chk_aligned_view.toggled.connect(self.run_diff)
        self.chk_ast.toggled.connect(self.run_diff)
        self.combo_whitespace.currentIndexChanged.connect(self.run_diff)
        self.chk_ignore_case.toggled.connect(self.run_diff)

        # Buttons
        self.btn_next.clicked.connect(self.jump_next)
        self.btn_prev.clicked.connect(self.jump_prev)
        self.btn_swap.clicked.connect(self.swap_sides)

        # File loading / saving
        self.left_header.fileOpened.connect(self._on_left_file_opened)
        self.right_header.fileOpened.connect(self._on_right_file_opened)
        self.left_header.saveRequested.connect(lambda: self._save_editor(self.left_editor, self.left_header))
        self.right_header.saveRequested.connect(lambda: self._save_editor(self.right_editor, self.right_header))

        # Chunk transfers
        self.connector.transferLeftToRight.connect(self.transfer_left_to_right)
        self.connector.transferRightToLeft.connect(self.transfer_right_to_left)
        self.connector.stageHunkRequested.connect(self.stage_hunk)
        self.connector.discardHunkRequested.connect(self.discard_hunk)
        self.connector.unstageHunkRequested.connect(self.unstage_hunk)

        # Manual Alignment Connections
        self.left_editor.alignWithRequested.connect(lambda line: self._start_alignment_mode('left', line))
        self.right_editor.alignWithRequested.connect(lambda line: self._start_alignment_mode('right', line))
        self.left_editor.alignmentTargetClicked.connect(lambda line: self._on_editor_line_clicked('left', line))
        self.right_editor.alignmentTargetClicked.connect(lambda line: self._on_editor_line_clicked('right', line))
        self.left_editor.clearAlignmentRequested.connect(self.clear_manual_alignments)
        self.right_editor.clearAlignmentRequested.connect(self.clear_manual_alignments)

        self.splitter.splitterMoved.connect(lambda: self.connector.update())

    def setup_shortcuts(self):
        QShortcut(QKeySequence("F8"), self, self.jump_next)
        QShortcut(QKeySequence("Shift+F8"), self, self.jump_prev)
        QShortcut(QKeySequence("Ctrl+Down"), self, self.jump_next)
        QShortcut(QKeySequence("Ctrl+Up"), self, self.jump_prev)
        QShortcut(QKeySequence("Ctrl+U"), self, self.swap_sides)
        QShortcut(QKeySequence.Undo, self, self.undo)
        QShortcut(QKeySequence.Redo, self, self.redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, self.redo)
        QShortcut(QKeySequence("Ctrl+F"), self, self.open_find_bar)
        QShortcut(QKeySequence("F3"), self, self.find_next)
        QShortcut(QKeySequence("Shift+F3"), self, self.find_prev)
        QShortcut(QKeySequence("Escape"), self, self._on_escape_pressed)

    def _on_escape_pressed(self):
        if hasattr(self, 'find_bar') and self.find_bar.isVisible():
            self.close_find_bar()
        elif hasattr(self, 'banner_alignment') and self.banner_alignment.isVisible():
            self._cancel_alignment_mode()

    def _on_left_scrolled(self, val):
        if self.chk_sync_scroll.isChecked():
            self.right_editor.set_sync_scroll_value(val)
        self.connector.update()

    def _on_right_scrolled(self, val):
        if self.chk_sync_scroll.isChecked():
            self.left_editor.set_sync_scroll_value(val)
        self.connector.update()

    def _on_left_live_edit(self):
        self._raw_left = self.left_editor.get_clean_text()
        if hasattr(self, "wal") and self.wal:
            self.wal.checkpoint("left", self.left_header.current_file_path or "untitled_left", self._raw_left, is_dirty=True)
        self.run_diff(editing_editor=self.left_editor)

    def _on_right_live_edit(self):
        self._raw_right = self.right_editor.get_clean_text()
        if hasattr(self, "wal") and self.wal:
            self.wal.checkpoint("right", self.right_header.current_file_path or "untitled_right", self._raw_right, is_dirty=True)
        self.run_diff(editing_editor=self.right_editor)

    def run_diff(self, editing_editor=None):
        """Calculates diffs and applies highlights and alignment without resetting active editor cursor."""
        ws_idx = self.combo_whitespace.currentIndex()
        ws_mode = ["none", "leading_trailing", "all"][ws_idx]
        ignore_case = self.chk_ignore_case.isChecked()
        is_aligned = self.chk_aligned_view.isChecked()
        is_ast = self.chk_ast.isChecked()

        left_text = self._raw_left
        right_text = self._raw_right

        left_decorations: Dict[int, str] = {}
        right_decorations: Dict[int, str] = {}
        left_char_decorations: Dict[int, List[Tuple[int, int, str]]] = {}
        right_char_decorations: Dict[int, List[Tuple[int, int, str]]] = {}
        left_tick_info: Dict[int, Tuple[str, str]] = {}
        right_tick_info: Dict[int, Tuple[str, str]] = {}

        left_path = self.left_header.current_file_path or ""
        right_path = self.right_header.current_file_path or ""
        ext = os.path.splitext(left_path or right_path)[1].lower()
        lang = "javascript" if ext in (".js", ".jsx", ".ts", ".tsx") else "python"

        add_count = 0
        del_count = 0
        mod_count = 0
        moved_count = 0

        if is_aligned:
            # Aligned Spacer Mode
            result: AlignedDiffResult = DiffEngine.build_aligned_diff(
                left_text, right_text,
                ignore_whitespace=ws_mode,
                ignore_case=ignore_case,
                regex_rules=self.active_noise_rules,
                ast_semantic=is_ast,
                language=lang,
                manual_alignments=self.manual_alignments
            )
            self.chunks = result.chunks

            # Do NOT touch the text buffer of the editor currently being typed in!
            if editing_editor != self.left_editor:
                self.left_editor.set_aligned_lines(
                    result.left_display_lines, result.left_spacers, result.left_line_numbers
                )
            else:
                self.left_editor.spacer_lines = set(result.left_spacers)
                self.left_editor.real_line_numbers = dict(result.left_line_numbers)
                self.left_editor.gutter.update()

            if editing_editor != self.right_editor:
                self.right_editor.set_aligned_lines(
                    result.right_display_lines, result.right_spacers, result.right_line_numbers
                )
            else:
                self.right_editor.spacer_lines = set(result.right_spacers)
                self.right_editor.real_line_numbers = dict(result.right_line_numbers)
                self.right_editor.gutter.update()

            for chunk in self.chunks:
                if chunk.tag == 'equal':
                    continue

                if chunk.tag == 'replace':
                    mod_count += 1
                    for i in range(chunk.left_start, chunk.left_end):
                        is_left_spacer = i in result.left_spacers
                        is_right_spacer = i in result.right_spacers
                        if is_left_spacer and not is_right_spacer:
                            right_decorations[i] = "#1a7f37"
                            right_tick_info[i] = ("#1a7f37", "Addition")
                        elif is_right_spacer and not is_left_spacer:
                            left_decorations[i] = "#cf222e"
                            left_tick_info[i] = ("#cf222e", "Deletion")
                        else:
                            left_decorations[i] = "#0969da"
                            right_decorations[i] = "#0969da"
                            left_tick_info[i] = ("#0969da", "Modification")
                            right_tick_info[i] = ("#0969da", "Modification")

                    for k, spans in chunk.left_char_spans.items():
                        line_idx = chunk.left_start + k
                        left_char_decorations[line_idx] = [(s.start, s.end, "#0969da") for s in spans]
                    for k, spans in chunk.right_char_spans.items():
                        line_idx = chunk.right_start + k
                        right_char_decorations[line_idx] = [(s.start, s.end, "#0969da") for s in spans]

                elif chunk.tag == 'delete':
                    del_count += 1
                    for i in range(chunk.left_start, chunk.left_end):
                        left_decorations[i] = "#cf222e"
                        left_tick_info[i] = ("#cf222e", "Deletion")

                elif chunk.tag == 'insert':
                    add_count += 1
                    for j in range(chunk.right_start, chunk.right_end):
                        right_decorations[j] = "#1a7f37"
                        right_tick_info[j] = ("#1a7f37", "Addition")

                elif chunk.tag == 'moved':
                    moved_count += 1
                    info = chunk.semantic_match_info or "Moved Block"
                    for i in range(chunk.left_start, chunk.left_end):
                        left_decorations[i] = "#8250df"
                        left_tick_info[i] = ("#8250df", info)
                    for j in range(chunk.right_start, chunk.right_end):
                        right_decorations[j] = "#8250df"
                        right_tick_info[j] = ("#8250df", info)
        else:
            # Raw Unpadded View
            self.chunks, left_lines, right_lines = DiffEngine.compute_2way_diff(
                left_text, right_text,
                ignore_whitespace=ws_mode,
                ignore_case=ignore_case,
                regex_rules=self.active_noise_rules,
                ast_semantic=is_ast,
                language=lang
            )
            if editing_editor != self.left_editor:
                self.left_editor.set_aligned_lines(left_lines, set(), {})
            if editing_editor != self.right_editor:
                self.right_editor.set_aligned_lines(right_lines, set(), {})

            for chunk in self.chunks:
                if chunk.tag == 'equal':
                    continue
                if chunk.tag == 'replace':
                    mod_count += 1
                    for i in range(chunk.left_start, chunk.left_end):
                        left_decorations[i] = "#0969da"
                        left_tick_info[i] = ("#0969da", "Modification")
                    for j in range(chunk.right_start, chunk.right_end):
                        right_decorations[j] = "#0969da"
                        right_tick_info[j] = ("#0969da", "Modification")
                elif chunk.tag == 'delete':
                    del_count += 1
                    for i in range(chunk.left_start, chunk.left_end):
                        left_decorations[i] = "#cf222e"
                        left_tick_info[i] = ("#cf222e", "Deletion")
                elif chunk.tag == 'insert':
                    add_count += 1
                    for j in range(chunk.right_start, chunk.right_end):
                        right_decorations[j] = "#1a7f37"
                        right_tick_info[j] = ("#1a7f37", "Addition")
                elif chunk.tag == 'moved':
                    moved_count += 1
                    info = chunk.semantic_match_info or "Moved Block"
                    for i in range(chunk.left_start, chunk.left_end):
                        left_decorations[i] = "#8250df"
                        left_tick_info[i] = ("#8250df", info)
                    for j in range(chunk.right_start, chunk.right_end):
                        right_decorations[j] = "#8250df"
                        right_tick_info[j] = ("#8250df", info)

        # Apply decorations non-destructively via ExtraSelections (never resets cursor)
        self.left_editor.apply_diff_decorations(left_decorations, left_char_decorations, tick_info=left_tick_info)
        self.right_editor.apply_diff_decorations(right_decorations, right_char_decorations, tick_info=right_tick_info)

        self.connector.set_chunks(self.chunks)

        total_diffs = add_count + del_count + mod_count + moved_count
        moved_badge = f"  <span style='color: #8250df; font-weight: bold;'>💜 {moved_count} Moved</span>" if moved_count > 0 else ""
        self.lbl_stats.setText(
            f"{total_diffs} Differences  |  "
            f"<span style='color: #1a7f37; font-weight: bold;'>+{add_count}</span>  "
            f"<span style='color: #cf222e; font-weight: bold;'>-{del_count}</span>  "
            f"<span style='color: #0969da; font-weight: bold;'>~{mod_count}</span>"
            f"{moved_badge}"
        )
        self.left_header.set_diff_stats(0, del_count, mod_count)
        self.right_header.set_diff_stats(add_count, 0, mod_count)

    def _open_ai_summary(self):
        left_name = self.left_header.current_file_path or "Left"
        right_name = self.right_header.current_file_path or "Right"
        dialog = AISummaryDialog(
            self,
            chunks=self.chunks,
            left_raw=self._raw_left.splitlines(),
            right_raw=self._raw_right.splitlines(),
            left_name=left_name,
            right_name=right_name
        )
        dialog.exec()

    def _export_patch(self):
        file, _ = QFileDialog.getSaveFileName(self, "Export Unified Diff Patch", "changes.patch", "Patch Files (*.patch *.diff);;All Files (*.*)")
        if file:
            left_name = self.left_header.current_file_path or "a/file"
            right_name = self.right_header.current_file_path or "b/file"
            patch_content = DiffEngine.generate_unified_patch(
                self._raw_left, self._raw_right, left_name, right_name
            )
            with open(file, "w", encoding="utf-8") as f:
                f.write(patch_content)
            QMessageBox.information(self, "Patch Exported", f"Successfully exported patch to:\n{file}")

    def _open_noise_filters(self):
        dialog = NoiseFilterDialog(self, active_rules=self.active_noise_rules)
        if dialog.exec():
            self.active_noise_rules = dialog.get_rules()
            self.run_diff()

    def jump_next(self):
        diff_chunks = [i for i, c in enumerate(self.chunks) if c.tag != 'equal']
        if not diff_chunks:
            return
        self.current_diff_idx = (self.current_diff_idx + 1) % len(diff_chunks)
        self._scroll_to_chunk(diff_chunks[self.current_diff_idx])

    def jump_prev(self):
        diff_chunks = [i for i, c in enumerate(self.chunks) if c.tag != 'equal']
        if not diff_chunks:
            return
        self.current_diff_idx = (self.current_diff_idx - 1 + len(diff_chunks)) % len(diff_chunks)
        self._scroll_to_chunk(diff_chunks[self.current_diff_idx])

    def _scroll_to_chunk(self, chunk_idx: int):
        chunk = self.chunks[chunk_idx]
        target_line = chunk.left_start if chunk.left_start < self.left_editor.blockCount() else 0
        block = self.left_editor.document().findBlockByNumber(target_line)
        if block.isValid():
            cursor = QTextCursor(block)
            self.left_editor.setTextCursor(cursor)
            self.left_editor.centerCursor()

    def _start_alignment_mode(self, side: str, line: int):
        self._pending_alignment = (side, line)
        target_side = "Right" if side == "left" else "Left"
        self.lbl_align_banner.setText(
            f"🎯 Manual Alignment Active: Click any line in the {target_side} pane to align with {side.capitalize()} Line {line}. (Press Esc to cancel)"
        )
        self.banner_alignment.setVisible(True)

    def _cancel_alignment_mode(self):
        self._pending_alignment = None
        self.banner_alignment.setVisible(False)

    def _on_editor_line_clicked(self, side: str, line: int):
        if not self._pending_alignment:
            return
        source_side, source_line = self._pending_alignment
        if source_side == side:
            # Clicked on same side, switch source anchor line
            self._start_alignment_mode(side, line)
            return

        if source_side == "left":
            self.manual_alignments.append((source_line, line))
        else:
            self.manual_alignments.append((line, source_line))

        self._pending_alignment = None
        self.banner_alignment.setVisible(False)
        self._update_alignments_button()
        self.run_diff()

    def clear_manual_alignments(self):
        self.manual_alignments = []
        self._pending_alignment = None
        self.banner_alignment.setVisible(False)
        self._update_alignments_button()
        self.run_diff()

    def _update_alignments_button(self):
        count = len(self.manual_alignments)
        if count > 0:
            self.btn_clear_alignments.setText(f"📌 {count} Manual Alignment{'s' if count > 1 else ''} [✕]")
            self.btn_clear_alignments.setVisible(True)
        else:
            self.btn_clear_alignments.setVisible(False)

    def _push_undo(self, desc: str = "Edit"):
        """Pushes current raw buffers to undo stack before any mutating operation."""
        self.undo_stack.append((self._raw_left, self._raw_right, desc))
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self._update_undo_redo_actions()

    def undo(self):
        """Undoes last accepted chunk transfer or buffer change."""
        if not self.undo_stack:
            return
        prev_left, prev_right, desc = self.undo_stack.pop()
        self.redo_stack.append((self._raw_left, self._raw_right, desc))
        self._raw_left = prev_left
        self._raw_right = prev_right
        self._update_undo_redo_actions()
        self.run_diff()

    def redo(self):
        """Redoes last undone change."""
        if not self.redo_stack:
            return
        next_left, next_right, desc = self.redo_stack.pop()
        self.undo_stack.append((self._raw_left, self._raw_right, desc))
        self._raw_left = next_left
        self._raw_right = next_right
        self._update_undo_redo_actions()
        self.run_diff()

    def _update_undo_redo_actions(self):
        has_undo = len(self.undo_stack) > 0
        has_redo = len(self.redo_stack) > 0
        if hasattr(self, 'btn_undo'):
            self.btn_undo.setEnabled(has_undo)
            if has_undo:
                self.btn_undo.setToolTip(f"Undo {self.undo_stack[-1][2]} (Ctrl+Z)")
            else:
                self.btn_undo.setToolTip("Nothing to undo (Ctrl+Z)")
        if hasattr(self, 'btn_redo'):
            self.btn_redo.setEnabled(has_redo)
            if has_redo:
                self.btn_redo.setToolTip(f"Redo {self.redo_stack[-1][2]} (Ctrl+Y)")
            else:
                self.btn_redo.setToolTip("Nothing to redo (Ctrl+Y)")

    def toggle_find_bar(self):
        if hasattr(self, 'find_bar') and self.find_bar.isVisible():
            self.close_find_bar()
        else:
            self.open_find_bar()

    def open_find_bar(self):
        if not hasattr(self, 'find_bar'):
            return
        self.find_bar.setVisible(True)
        self.txt_find.setFocus()
        self.txt_find.selectAll()
        if self.txt_find.text():
            self._on_find_text_changed()

    def close_find_bar(self):
        if hasattr(self, 'find_bar'):
            self.find_bar.setVisible(False)
        self.left_editor.clear_search_selections()
        self.right_editor.clear_search_selections()
        self._find_matches = []
        self._current_find_match_idx = -1
        self.left_editor.setFocus()

    def _on_find_text_changed(self):
        query = self.txt_find.text() if hasattr(self, 'txt_find') else ""
        case_sensitive = self.chk_find_case.isChecked() if hasattr(self, 'chk_find_case') else False
        self._find_matches = []
        self._current_find_match_idx = -1

        if not query:
            self.left_editor.clear_search_selections()
            self.right_editor.clear_search_selections()
            if hasattr(self, 'lbl_find_status'):
                self.lbl_find_status.setText("0 matches")
            return

        flags = QTextDocument.FindFlag(0)
        if case_sensitive:
            flags |= QTextDocument.FindCaseSensitively

        def collect_matches(editor: ModernCodeEditor, side: str):
            doc = editor.document()
            selections = []
            cursor = QTextCursor(doc)
            while True:
                cursor = doc.find(query, cursor, flags)
                if cursor.isNull():
                    break
                pos = cursor.position()
                self._find_matches.append((side, pos - len(query), pos))
                sel = QTextEdit.ExtraSelection()
                sel.format.setBackground(QColor("#fef08a"))
                sel.cursor = cursor
                selections.append(sel)
            editor.set_search_selections(selections)

        collect_matches(self.left_editor, "left")
        collect_matches(self.right_editor, "right")

        total = len(self._find_matches)
        if total > 0:
            self._current_find_match_idx = 0
            self._jump_to_current_match()
        elif hasattr(self, 'lbl_find_status'):
            self.lbl_find_status.setText("No matches")

    def find_next(self):
        if not self._find_matches:
            return
        self._current_find_match_idx = (self._current_find_match_idx + 1) % len(self._find_matches)
        self._jump_to_current_match()

    def find_prev(self):
        if not self._find_matches:
            return
        self._current_find_match_idx = (self._current_find_match_idx - 1 + len(self._find_matches)) % len(self._find_matches)
        self._jump_to_current_match()

    def _jump_to_current_match(self):
        if not self._find_matches or self._current_find_match_idx < 0:
            return
        side, start, end = self._find_matches[self._current_find_match_idx]
        editor = self.left_editor if side == "left" else self.right_editor
        cursor = QTextCursor(editor.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        editor.setTextCursor(cursor)
        editor.centerCursor()

        if hasattr(self, 'lbl_find_status'):
            self.lbl_find_status.setText(f"{self._current_find_match_idx + 1} of {len(self._find_matches)} matches")

    def swap_sides(self):
        self._push_undo("Swap Sides")
        self._raw_left, self._raw_right = self._raw_right, self._raw_left
        left_path = self.left_header.current_file_path
        right_path = self.right_header.current_file_path
        self.left_header.set_file_info(right_path)
        self.right_header.set_file_info(left_path)
        if self.manual_alignments:
            self.manual_alignments = [(r, l) for l, r in self.manual_alignments]
        self._pending_alignment = None
        self.banner_alignment.setVisible(False)
        self._update_alignments_button()
        self.run_diff()

    def transfer_left_to_right(self, chunk_idx: int):
        if chunk_idx >= len(self.chunks):
            return
        chunks, left_raw, right_raw = DiffEngine.compute_2way_diff(self._raw_left, self._raw_right)
        if chunk_idx < len(chunks):
            self._push_undo(f"Transfer Hunk {chunk_idx + 1} to Right")
            c = chunks[chunk_idx]
            right_raw[c.right_start:c.right_end] = left_raw[c.left_start:c.left_end]
            self._raw_right = '\n'.join(right_raw)
            self.run_diff()

    def transfer_right_to_left(self, chunk_idx: int):
        if chunk_idx >= len(self.chunks):
            return
        chunks, left_raw, right_raw = DiffEngine.compute_2way_diff(self._raw_left, self._raw_right)
        if chunk_idx < len(chunks):
            self._push_undo(f"Transfer Hunk {chunk_idx + 1} to Left")
            c = chunks[chunk_idx]
            left_raw[c.left_start:c.left_end] = right_raw[c.right_start:c.right_end]
            self._raw_left = '\n'.join(left_raw)
            self.run_diff()

    def _on_left_file_opened(self, path, content):
        self._raw_left = content
        self.left_header.set_file_info(path, dirty=False)
        self.manual_alignments = []
        self._pending_alignment = None
        self.banner_alignment.setVisible(False)
        self._update_alignments_button()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._update_undo_redo_actions()
        self.run_diff()

    def _on_right_file_opened(self, path, content):
        self._raw_right = content
        self.right_header.set_file_info(path, dirty=False)
        self.manual_alignments = []
        self._pending_alignment = None
        self.banner_alignment.setVisible(False)
        self._update_alignments_button()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._update_undo_redo_actions()
        self.run_diff()

    def _save_editor(self, editor: ModernCodeEditor, header: EditorHeader):
        path = header.current_file_path
        if not path or path.startswith("sample") or path.startswith("local_"):
            path, _ = QFileDialog.getSaveFileName(self, "Save File", path, "All Files (*.*)")
            if not path:
                return

        try:
            clean_content = editor.get_clean_text()
            with open(path, 'w', encoding='utf-8') as f:
                f.write(clean_content)
            header.set_file_info(path, dirty=False)
            if hasattr(self, "wal") and self.wal:
                pane = "left" if editor == self.left_editor else "right"
                self.wal.commit_save(pane, path)
            QMessageBox.information(self, "Saved", f"File saved cleanly to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error Saving", f"Could not save file:\n{e}")

    def _get_working_git_file(self) -> Tuple[Optional[str], str]:
        """Returns (file_path, 'right' or 'left') for the file tracked by Git."""
        right_p = self.right_header.current_file_path
        if right_p and GitStagingManager.is_git_tracked(right_p):
            return right_p, "right"
        left_p = self.left_header.current_file_path
        if left_p and GitStagingManager.is_git_tracked(left_p):
            return left_p, "left"
        if right_p and GitStagingManager.find_git_root(right_p):
            return right_p, "right"
        if left_p and GitStagingManager.find_git_root(left_p):
            return left_p, "left"
        return None, ""

    def compare_with_git_head(self):
        """Loads Git HEAD on the Left and working copy on the Right."""
        target_path, _ = self._get_working_git_file()
        if not target_path:
            target_path = self.right_header.current_file_path or self.left_header.current_file_path
            if not target_path or not os.path.exists(target_path):
                QMessageBox.warning(self, "Git Compare", "Please open a file from a Git repository first.")
                return

        head_content = GitStagingManager.get_git_head_content(target_path)
        if head_content is None:
            QMessageBox.warning(self, "Git Compare", f"Could not find committed version of '{os.path.basename(target_path)}' in Git HEAD.")
            return

        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            working_content = f.read()

        self._raw_left = head_content
        self._raw_right = working_content
        self.left_header.set_file_info(f"{os.path.basename(target_path)} (Git HEAD)")
        self.left_header.current_file_path = target_path
        self.right_header.set_file_info(target_path)
        self.run_diff()
        QMessageBox.information(self, "Git Compare", f"Loaded Git HEAD on the Left and current working copy on the Right for:\n{target_path}")

    def stage_hunk(self, chunk_idx: int):
        if chunk_idx < 0 or chunk_idx >= len(self.chunks):
            diff_chunks = [i for i, c in enumerate(self.chunks) if c.tag != 'equal']
            if self.current_diff_idx >= 0 and self.current_diff_idx < len(diff_chunks):
                chunk_idx = diff_chunks[self.current_diff_idx]
            else:
                QMessageBox.information(self, "Git Staging", "No diff hunk selected. Click on a diff block to stage.")
                return

        chunk = self.chunks[chunk_idx]
        if chunk.tag == 'equal':
            return

        target_path, _ = self._get_working_git_file()
        if not target_path:
            QMessageBox.warning(self, "Git Staging", "The opened file is not inside a Git repository.")
            return

        left_lines = self._raw_left.splitlines()
        right_lines = self._raw_right.splitlines()

        ok, msg = GitStagingManager.stage_hunk(target_path, chunk, left_lines, right_lines)
        if ok:
            QMessageBox.information(self, "Hunk Staged", f"✓ Hunk {chunk_idx + 1} staged to Git index successfully!")
        else:
            QMessageBox.warning(self, "Staging Failed", f"Could not stage hunk:\n{msg}")

    def unstage_hunk(self, chunk_idx: int):
        if chunk_idx < 0 or chunk_idx >= len(self.chunks):
            diff_chunks = [i for i, c in enumerate(self.chunks) if c.tag != 'equal']
            if self.current_diff_idx >= 0 and self.current_diff_idx < len(diff_chunks):
                chunk_idx = diff_chunks[self.current_diff_idx]
            else:
                return

        chunk = self.chunks[chunk_idx]
        if chunk.tag == 'equal':
            return

        target_path, _ = self._get_working_git_file()
        if not target_path:
            return

        left_lines = self._raw_left.splitlines()
        right_lines = self._raw_right.splitlines()

        ok, msg = GitStagingManager.unstage_hunk(target_path, chunk, left_lines, right_lines)
        if ok:
            QMessageBox.information(self, "Hunk Unstaged", f"✓ Hunk {chunk_idx + 1} unstaged from Git index.")
        else:
            QMessageBox.warning(self, "Unstage Failed", f"Could not unstage hunk:\n{msg}")

    def discard_hunk(self, chunk_idx: int):
        if chunk_idx < 0 or chunk_idx >= len(self.chunks):
            diff_chunks = [i for i, c in enumerate(self.chunks) if c.tag != 'equal']
            if self.current_diff_idx >= 0 and self.current_diff_idx < len(diff_chunks):
                chunk_idx = diff_chunks[self.current_diff_idx]
            else:
                return

        chunk = self.chunks[chunk_idx]
        if chunk.tag == 'equal':
            return

        reply = QMessageBox.question(
            self,
            "Discard Hunk Changes",
            f"Are you sure you want to discard changes in Hunk {chunk_idx + 1}?\nThis will revert working copy modifications for this block.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        target_path, _ = self._get_working_git_file()
        if not target_path:
            return

        left_lines = self._raw_left.splitlines()
        right_lines = self._raw_right.splitlines()

        ok, msg = GitStagingManager.discard_hunk(target_path, chunk, left_lines, right_lines)
        if ok:
            if os.path.exists(target_path):
                with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                    self._raw_right = f.read()
                self.run_diff()
            QMessageBox.information(self, "Hunk Discarded", f"✓ Hunk {chunk_idx + 1} discarded and reverted.")
        else:
            QMessageBox.warning(self, "Discard Failed", f"Could not discard hunk:\n{msg}")
