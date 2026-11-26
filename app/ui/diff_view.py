"""
Modern 2-Way Side-by-Side File Comparison View (White / Light Theme)
Supports:
- Horizontal Alignment with spacer lines & moved-block ribbons.
- Real-time in-place editing with debounced reactive diff updates & unified undo/redo.
- Intraline character-level highlights + GitHub-Light syntax highlighting.
- Find & Replace bar (case-sensitive & regex) across both panes.
- Word wrap, visible whitespace, font zoom, encoding/EOL preservation, and Git hunk staging.
"""

import os
import re
from typing import List, Dict, Tuple, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSplitter,
    QLabel, QComboBox, QCheckBox, QMessageBox, QFileDialog, QSizePolicy,
    QToolButton, QMenu, QFrame, QLineEdit, QTextEdit, QApplication
)
from PySide6.QtCore import Qt, QTimer, Signal, QRegularExpression, QFileSystemWatcher
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor, QTextDocument, QColor

from app.ui.widgets.modern_editor import ModernCodeEditor
from app.ui.widgets.editor_header import EditorHeader
from app.ui.widgets.diff_connector import DiffConnectorWidget
from app.ui.widgets.line_details_panel import LineDetailsPanel
from app.core.diff_engine import DiffEngine, DiffChunk, AlignedDiffResult
from app.core.file_io import read_text_file, write_text_file, is_vfs_path, is_virtual_path, is_docx_path
from app.core.git_staging import GitStagingManager
from app.core.headless_reporter import HeadlessReporter
from app.ui.styles.icons import get_line_icon
from app.ui.dialogs.ai_summary_dialog import AISummaryDialog
from app.ui.dialogs.noise_filter_dialog import NoiseFilterDialog


class DiffView(QWidget):
    """Production-grade 2-Way Diff View."""

    statusMessage = Signal(str)
    filesChanged = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.chunks: List[DiffChunk] = []
        self.current_diff_idx = -1
        self._raw_left = ""
        self._raw_right = ""
        self._is_sample_state = True
        self.active_noise_rules: List[Tuple[str, str]] = []
        self.manual_alignments: List[Tuple[int, int]] = []
        self._pending_alignment: Optional[Tuple[str, int]] = None
        self.undo_stack: List[Tuple[str, str, str]] = []
        self.redo_stack: List[Tuple[str, str, str]] = []
        self._find_matches: List[Tuple[str, int, int]] = []
        self._current_find_match_idx: int = -1
        self._view_rows: List[Tuple[Optional[int], str, Optional[int], str, bool, bool, str]] = []
        self._saving_paths: set = set()
        self._pending_reload_path: Optional[str] = None
        self._file_watcher = QFileSystemWatcher(self)
        self._file_watcher.fileChanged.connect(self._on_external_file_changed)

        from app.core.wal_journal import WALJournal
        self.wal = WALJournal()

        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.setInterval(3500)
        self._toast_timer.timeout.connect(self._hide_toast)

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
        self.left_editor.set_language_from_path("sample_local.py")
        self.right_editor.set_language_from_path("sample_remote.py")

        self.run_diff()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Primary Command Bar
        cmd_bar = QWidget()
        cmd_bar.setObjectName("DiffCmdBar")
        cmd_bar.setFixedHeight(44)
        cmd_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        cmd_bar.setStyleSheet("""
            #DiffCmdBar {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f8fafc);
                border-bottom: 1px solid #cbd5e1;
            }
        """)
        cmd_layout = QHBoxLayout(cmd_bar)
        cmd_layout.setContentsMargins(10, 6, 10, 6)
        cmd_layout.setSpacing(6)

        self.btn_prev = QPushButton(" Prev (F7)")
        self.btn_prev.setIcon(get_line_icon("arrow-up", "#1e293b"))
        self.btn_prev.setFixedHeight(30)
        self.btn_prev.setToolTip("Previous difference hunk (F7 / Shift+F8)")

        self.btn_next = QPushButton(" Next (F8)")
        self.btn_next.setIcon(get_line_icon("arrow-down", "#1e293b"))
        self.btn_next.setFixedHeight(30)
        self.btn_next.setToolTip("Next difference hunk (F8)")

        self.lbl_hunk_pos = QLabel("Hunk -/-")
        self.lbl_hunk_pos.setStyleSheet("color: #475569; font-size: 11px; font-weight: 600; padding: 0 4px; background: transparent; border: none;")

        cmd_layout.addWidget(self.btn_prev)
        cmd_layout.addWidget(self.btn_next)
        cmd_layout.addWidget(self.lbl_hunk_pos)

        self.btn_swap = QPushButton(" Swap")
        self.btn_swap.setIcon(get_line_icon("swap", "#1e293b"))
        self.btn_swap.setFixedHeight(30)
        self.btn_swap.setToolTip("Swap Left and Right viewports (Ctrl+U)")
        cmd_layout.addWidget(self.btn_swap)

        self.btn_undo = QPushButton(" Undo")
        self.btn_undo.setIcon(get_line_icon("undo", "#1e293b"))
        self.btn_undo.setFixedHeight(30)
        self.btn_undo.setEnabled(False)
        self.btn_undo.setToolTip("Undo last change (Ctrl+Z)")
        self.btn_undo.clicked.connect(self.undo)
        cmd_layout.addWidget(self.btn_undo)

        self.btn_redo = QPushButton(" Redo")
        self.btn_redo.setIcon(get_line_icon("redo", "#1e293b"))
        self.btn_redo.setFixedHeight(30)
        self.btn_redo.setEnabled(False)
        self.btn_redo.setToolTip("Redo last undone change (Ctrl+Y)")
        self.btn_redo.clicked.connect(self.redo)
        cmd_layout.addWidget(self.btn_redo)

        self.btn_find = QPushButton(" Find")
        self.btn_find.setIcon(get_line_icon("search", "#1e293b"))
        self.btn_find.setFixedHeight(30)
        self.btn_find.setToolTip("Find & Replace across both diff panes (Ctrl+F / Ctrl+H)")
        self.btn_find.clicked.connect(self.toggle_find_bar)
        cmd_layout.addWidget(self.btn_find)

        self.btn_noise = QPushButton(" Filters")
        self.btn_noise.setIcon(get_line_icon("filter", "#1e293b"))
        self.btn_noise.setFixedHeight(30)
        self.btn_noise.clicked.connect(self._open_noise_filters)
        cmd_layout.addWidget(self.btn_noise)

        self.btn_ai_summary = QPushButton(" AI Summary")
        self.btn_ai_summary.setIcon(get_line_icon("sparkles", "#0969da"))
        self.btn_ai_summary.setFixedHeight(30)
        self.btn_ai_summary.clicked.connect(self._open_ai_summary)
        cmd_layout.addWidget(self.btn_ai_summary)

        self.btn_export = QToolButton()
        self.btn_export.setText(" Export")
        self.btn_export.setIcon(get_line_icon("download", "#1e293b"))
        self.btn_export.setFixedHeight(30)
        self.btn_export.setPopupMode(QToolButton.InstantPopup)
        export_menu = QMenu(self.btn_export)
        export_menu.addAction(get_line_icon("file-text", "#1e293b"), "Export Unified .patch...", self._export_patch)
        export_menu.addAction(get_line_icon("file-code", "#0969da"), "Export Side-by-Side HTML Report...", self._export_html_report)
        export_menu.addSeparator()
        export_menu.addAction(get_line_icon("copy", "#1e293b"), "Copy Unified Diff to Clipboard", self._copy_unified_diff)
        self.btn_export.setMenu(export_menu)
        self.btn_export_patch = self.btn_export
        cmd_layout.addWidget(self.btn_export)

        # Git Actions ToolButton with dropdown menu
        self.btn_git = QToolButton()
        self.btn_git.setText(" Git")
        self.btn_git.setIcon(get_line_icon("git-commit", "#1e293b"))
        self.btn_git.setFixedHeight(30)
        self.btn_git.setPopupMode(QToolButton.InstantPopup)
        git_menu = QMenu(self.btn_git)
        git_menu.addAction(get_line_icon("search", "#0969da"), "Compare with Git HEAD", self.compare_with_git_head)
        git_menu.addSeparator()
        git_menu.addAction(get_line_icon("plus", "#16a34a"), "Stage Current Hunk (git apply --cached)", self.stage_current_hunk)
        git_menu.addAction(get_line_icon("undo", "#475569"), "Unstage Current Hunk", self.unstage_current_hunk)
        git_menu.addAction(get_line_icon("trash", "#cf222e"), "Discard Current Hunk (Revert)", self.discard_current_hunk)
        self.btn_git.setMenu(git_menu)
        cmd_layout.addWidget(self.btn_git)

        cmd_layout.addStretch()

        self.btn_clear_alignments = QPushButton("0 Alignments [✕]")
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
            QPushButton:hover { background-color: #dbeafe; }
        """)
        self.btn_clear_alignments.clicked.connect(self.clear_manual_alignments)
        self.btn_clear_alignments.setVisible(False)
        cmd_layout.addWidget(self.btn_clear_alignments)

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
        cmd_layout.addWidget(self.lbl_stats)

        main_layout.addWidget(cmd_bar, 0)

        # 1.2 Compact Secondary Options Strip (prevents toolbar clipping on 1280px screens)
        opt_bar = QFrame()
        opt_bar.setObjectName("DiffOptBar")
        opt_bar.setFixedHeight(34)
        opt_bar.setStyleSheet("""
            #DiffOptBar {
                background-color: #f8fafc;
                border-bottom: 1.5px solid #cbd5e1;
            }
        """)
        opt_layout = QHBoxLayout(opt_bar)
        opt_layout.setContentsMargins(10, 2, 10, 2)
        opt_layout.setSpacing(10)

        self.chk_aligned_view = QCheckBox("Aligned View")
        self.chk_aligned_view.setChecked(True)
        self.chk_aligned_view.setToolTip("Inserts blank spacer lines so matching blocks align horizontally")
        opt_layout.addWidget(self.chk_aligned_view)

        self.chk_ast = QCheckBox("AST Semantic")
        self.chk_ast.setChecked(True)
        self.chk_ast.setToolTip("Tree-sitter structural diffing: detects reordered functions & normalized docstrings")
        opt_layout.addWidget(self.chk_ast)

        self.combo_whitespace = QComboBox()
        self.combo_whitespace.setFixedHeight(26)
        self.combo_whitespace.addItems([
            "Compare Whitespace",
            "Ignore Leading/Trailing",
            "Ignore All Whitespace"
        ])
        opt_layout.addWidget(self.combo_whitespace)

        self.chk_ignore_case = QCheckBox("Ignore Case")
        opt_layout.addWidget(self.chk_ignore_case)

        self.chk_sync_scroll = QCheckBox("Sync Scroll")
        self.chk_sync_scroll.setChecked(True)
        opt_layout.addWidget(self.chk_sync_scroll)

        self.chk_word_wrap = QCheckBox("Word Wrap")
        self.chk_word_wrap.setChecked(False)
        opt_layout.addWidget(self.chk_word_wrap)

        self.chk_show_ws = QCheckBox("Show Spaces")
        self.chk_show_ws.setChecked(False)
        opt_layout.addWidget(self.chk_show_ws)

        self.combo_view_scope = QComboBox()
        self.combo_view_scope.setFixedHeight(26)
        self.combo_view_scope.addItems(["All Lines", "Diffs Only", "Context ±3", "Same Only"])
        self.combo_view_scope.setToolTip("Display scope filter (focus only changed lines, context ±3, or unchanged lines)")
        opt_layout.addWidget(self.combo_view_scope)

        self.chk_ignore_unimportant = QCheckBox("Ignore Unimportant")
        self.chk_ignore_unimportant.setChecked(True)
        self.chk_ignore_unimportant.setToolTip("Apply configured Noise & Custom Regex Unimportant Difference rules")
        opt_layout.addWidget(self.chk_ignore_unimportant)

        self.chk_line_details = QCheckBox("Line Details")
        self.chk_line_details.setChecked(True)
        self.chk_line_details.setToolTip("Show/hide bottom stacked character-by-character Line Details pane")
        opt_layout.addWidget(self.chk_line_details)

        opt_layout.addStretch()

        # Non-blocking inline toast status pill
        self.lbl_toast = QLabel("")
        self.lbl_toast.setStyleSheet("""
            background: #dafbe1;
            color: #116329;
            border: 1px solid #4ac26b;
            border-radius: 5px;
            padding: 2px 10px;
            font-size: 11px;
            font-weight: 600;
        """)
        self.lbl_toast.setVisible(False)
        opt_layout.addWidget(self.lbl_toast)

        # Font Zoom Controls
        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_out.setFixedSize(26, 24)
        self.btn_zoom_out.setToolTip("Zoom Out (Ctrl+-)")
        self.btn_zoom_out.clicked.connect(self._zoom_out)
        opt_layout.addWidget(self.btn_zoom_out)

        self.btn_zoom_reset = QPushButton("100%")
        self.btn_zoom_reset.setFixedHeight(24)
        self.btn_zoom_reset.setToolTip("Reset Editor Font Size (Ctrl+0)")
        self.btn_zoom_reset.clicked.connect(self._zoom_reset)
        opt_layout.addWidget(self.btn_zoom_reset)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setFixedSize(26, 24)
        self.btn_zoom_in.setToolTip("Zoom In (Ctrl++)")
        self.btn_zoom_in.clicked.connect(self._zoom_in)
        opt_layout.addWidget(self.btn_zoom_in)

        main_layout.addWidget(opt_bar, 0)

        # Manual Alignment Notification Banner
        self.banner_alignment = QFrame()
        self.banner_alignment.setFixedHeight(36)
        self.banner_alignment.setStyleSheet("QFrame { background-color: #eff6ff; border-bottom: 1.5px solid #93c5fd; padding: 0 12px; }")
        ba_layout = QHBoxLayout(self.banner_alignment)
        ba_layout.setContentsMargins(12, 0, 12, 0)
        ba_layout.setSpacing(10)

        self.lbl_align_banner = QLabel("Manual Alignment Mode")
        self.lbl_align_banner.setStyleSheet("font-size: 12px; font-weight: 600; color: #1e40af; border: none; background: transparent;")
        ba_layout.addWidget(self.lbl_align_banner, 1)

        btn_cancel_align = QPushButton("Cancel (Esc)")
        btn_cancel_align.setFixedHeight(24)
        btn_cancel_align.clicked.connect(self._cancel_alignment_mode)
        ba_layout.addWidget(btn_cancel_align)

        self.banner_alignment.setVisible(False)
        main_layout.addWidget(self.banner_alignment, 0)

        # 1.5 In-Editor Find & Replace Bar
        self.find_bar = QFrame()
        self.find_bar.setFixedHeight(40)
        self.find_bar.setStyleSheet("QFrame { background: #f8fafc; border-bottom: 1.5px solid #cbd5e1; padding: 0 10px; }")
        fb_layout = QHBoxLayout(self.find_bar)
        fb_layout.setContentsMargins(10, 4, 10, 4)
        fb_layout.setSpacing(6)

        self.txt_find = QLineEdit()
        self.txt_find.setPlaceholderText("Find in diff... (Enter=next, Shift+Enter=prev)")
        self.txt_find.setFixedHeight(28)
        self.txt_find.setFixedWidth(230)
        self.txt_find.setClearButtonEnabled(True)
        self.txt_find.textChanged.connect(self._on_find_text_changed)
        self.txt_find.returnPressed.connect(self.find_next)
        fb_layout.addWidget(self.txt_find)

        self.btn_find_prev = QPushButton("◀ Prev")
        self.btn_find_prev.setFixedHeight(26)
        self.btn_find_prev.setToolTip("Previous match (Shift+F3)")
        self.btn_find_prev.clicked.connect(self.find_prev)
        fb_layout.addWidget(self.btn_find_prev)

        self.btn_find_next = QPushButton("Next ▶")
        self.btn_find_next.setFixedHeight(26)
        self.btn_find_next.setToolTip("Next match (Enter / F3)")
        self.btn_find_next.clicked.connect(self.find_next)
        fb_layout.addWidget(self.btn_find_next)

        self.chk_find_case = QCheckBox("Aa")
        self.chk_find_case.setToolTip("Match Case")
        self.chk_find_case.toggled.connect(self._on_find_text_changed)
        fb_layout.addWidget(self.chk_find_case)

        self.chk_find_regex = QCheckBox(".*")
        self.chk_find_regex.setToolTip("Regular Expression")
        self.chk_find_regex.toggled.connect(self._on_find_text_changed)
        fb_layout.addWidget(self.chk_find_regex)

        self.txt_replace = QLineEdit()
        self.txt_replace.setPlaceholderText("Replace with...")
        self.txt_replace.setFixedHeight(28)
        self.txt_replace.setFixedWidth(160)
        fb_layout.addWidget(self.txt_replace)

        self.btn_replace_one = QPushButton("Replace")
        self.btn_replace_one.setFixedHeight(26)
        self.btn_replace_one.clicked.connect(self.replace_current_match)
        fb_layout.addWidget(self.btn_replace_one)

        self.btn_replace_all = QPushButton("Replace All")
        self.btn_replace_all.setFixedHeight(26)
        self.btn_replace_all.clicked.connect(self.replace_all_matches)
        fb_layout.addWidget(self.btn_replace_all)

        self.lbl_find_status = QLabel("0 matches")
        self.lbl_find_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b; padding-left: 4px; border: none; background: transparent;")
        fb_layout.addWidget(self.lbl_find_status)

        fb_layout.addStretch()

        btn_close_find = QPushButton("✕")
        btn_close_find.setFixedSize(24, 24)
        btn_close_find.setToolTip("Close Find Bar (Esc)")
        btn_close_find.clicked.connect(self.close_find_bar)
        fb_layout.addWidget(btn_close_find)

        self.find_bar.setVisible(False)
        main_layout.addWidget(self.find_bar, 0)

        # External File Modification Banner (non-blocking reload prompt)
        self.banner_reload = QFrame()
        self.banner_reload.setFixedHeight(36)
        self.banner_reload.setStyleSheet("QFrame { background-color: #fffbeb; border-bottom: 1.5px solid #fcd34d; padding: 0 12px; }")
        br_layout = QHBoxLayout(self.banner_reload)
        br_layout.setContentsMargins(12, 0, 12, 0)
        br_layout.setSpacing(8)
        self.lbl_reload_banner = QLabel("External modification detected on disk.")
        self.lbl_reload_banner.setStyleSheet("font-size: 12px; font-weight: 600; color: #92400e; border: none; background: transparent;")
        br_layout.addWidget(self.lbl_reload_banner, 1)
        btn_do_reload = QPushButton("Reload File")
        btn_do_reload.setFixedHeight(24)
        btn_do_reload.clicked.connect(self._reload_external_file)
        br_layout.addWidget(btn_do_reload)
        btn_dismiss_reload = QPushButton("Dismiss")
        btn_dismiss_reload.setFixedHeight(24)
        btn_dismiss_reload.clicked.connect(lambda: self.banner_reload.setVisible(False))
        br_layout.addWidget(btn_dismiss_reload)
        self.banner_reload.setVisible(False)
        main_layout.addWidget(self.banner_reload, 0)

        # 2. Comparison Splitter
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        left_container = QWidget()
        l_layout = QVBoxLayout(left_container)
        l_layout.setContentsMargins(0, 0, 0, 0)
        l_layout.setSpacing(0)
        self.left_header = EditorHeader(title="Mine / Left", default_path="local_file.py")
        self.left_editor = ModernCodeEditor()
        l_layout.addWidget(self.left_header)
        l_layout.addWidget(self.left_editor)

        right_container = QWidget()
        r_layout = QVBoxLayout(right_container)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(0)
        self.right_header = EditorHeader(title="Theirs / Right", default_path="remote_file.py")
        self.right_editor = ModernCodeEditor()
        r_layout.addWidget(self.right_header)
        r_layout.addWidget(self.right_editor)

        self.connector = DiffConnectorWidget(self.left_editor, self.right_editor)

        self.splitter.addWidget(left_container)
        self.splitter.addWidget(self.connector)
        self.splitter.addWidget(right_container)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setCollapsible(2, False)
        self.splitter.setSizes([600, 38, 600])

        main_layout.addWidget(self.splitter, 1)

        # 3. Synchronized Bottom Line Details Panel (character-by-character inspector)
        self.line_details = LineDetailsPanel()
        main_layout.addWidget(self.line_details, 0)

    def setup_connections(self):
        self.left_editor.liveTextChanged.connect(self._on_left_live_edit)
        self.right_editor.liveTextChanged.connect(self._on_right_live_edit)
        self.left_editor.cursorPositionChanged.connect(lambda: self._update_line_details_from_editor("left"))
        self.right_editor.cursorPositionChanged.connect(lambda: self._update_line_details_from_editor("right"))

        self.left_editor.scrolled.connect(self._on_left_scrolled)
        self.right_editor.scrolled.connect(self._on_right_scrolled)

        self.chk_aligned_view.toggled.connect(self.run_diff)
        self.chk_ast.toggled.connect(self.run_diff)
        self.combo_whitespace.currentIndexChanged.connect(self.run_diff)
        self.chk_ignore_case.toggled.connect(self.run_diff)
        self.combo_view_scope.currentIndexChanged.connect(self.run_diff)
        self.chk_ignore_unimportant.toggled.connect(self.run_diff)
        self.chk_line_details.toggled.connect(self.line_details.setVisible)
        self.chk_word_wrap.toggled.connect(self._on_word_wrap_toggled)
        self.chk_show_ws.toggled.connect(self._on_show_ws_toggled)

        self.btn_next.clicked.connect(self.jump_next)
        self.btn_prev.clicked.connect(self.jump_prev)
        self.btn_swap.clicked.connect(self.swap_sides)

        self.left_header.fileOpened.connect(self._on_left_file_opened)
        self.right_header.fileOpened.connect(self._on_right_file_opened)
        self.left_header.readOnlyToggled.connect(lambda locked: self._apply_read_only_state())
        self.right_header.readOnlyToggled.connect(lambda locked: self._apply_read_only_state())
        self.left_header.encodingFormatChanged.connect(lambda e, l: self._show_toast(f"Left save format: {e} | {l}"))
        self.right_header.encodingFormatChanged.connect(lambda e, l: self._show_toast(f"Right save format: {e} | {l}"))
        self.left_editor.fileDropped.connect(self.left_header.load_local_file)
        self.right_editor.fileDropped.connect(self.right_header.load_local_file)
        self.left_header.saveRequested.connect(lambda: self._save_editor(self.left_editor, self.left_header))
        self.right_header.saveRequested.connect(lambda: self._save_editor(self.right_editor, self.right_header))

        self.connector.transferLeftToRight.connect(self.transfer_left_to_right)
        self.connector.transferRightToLeft.connect(self.transfer_right_to_left)
        self.connector.stageHunkRequested.connect(self.stage_hunk)
        self.connector.discardHunkRequested.connect(self.discard_hunk)
        self.connector.unstageHunkRequested.connect(self.unstage_hunk)

        self.left_editor.alignWithRequested.connect(lambda line: self._start_alignment_mode('left', line))
        self.right_editor.alignWithRequested.connect(lambda line: self._start_alignment_mode('right', line))
        self.left_editor.alignmentTargetClicked.connect(lambda line: self._on_editor_line_clicked('left', line))
        self.right_editor.alignmentTargetClicked.connect(lambda line: self._on_editor_line_clicked('right', line))
        self.left_editor.clearAlignmentRequested.connect(self.clear_manual_alignments)
        self.right_editor.clearAlignmentRequested.connect(self.clear_manual_alignments)

        self.splitter.splitterMoved.connect(lambda: self.connector.update())

    def setup_shortcuts(self):
        QShortcut(QKeySequence("F7"), self, self.jump_prev)
        QShortcut(QKeySequence("F8"), self, self.jump_next)
        QShortcut(QKeySequence("Shift+F8"), self, self.jump_prev)
        QShortcut(QKeySequence("Ctrl+Down"), self, self.jump_next)
        QShortcut(QKeySequence("Ctrl+Up"), self, self.jump_prev)
        QShortcut(QKeySequence("Ctrl+U"), self, self.swap_sides)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_focused_editor)
        QShortcut(QKeySequence.Undo, self, self.undo)
        QShortcut(QKeySequence.Redo, self, self.redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, self.redo)
        QShortcut(QKeySequence("Ctrl+F"), self, self.open_find_bar)
        QShortcut(QKeySequence("Ctrl+H"), self, self.open_find_bar)
        QShortcut(QKeySequence("F3"), self, self.find_next)
        QShortcut(QKeySequence("Shift+F3"), self, self.find_prev)
        QShortcut(QKeySequence("Ctrl++"), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+="), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self._zoom_reset)
        QShortcut(QKeySequence("Escape"), self, self._on_escape_pressed)

    def _show_toast(self, msg: str, is_error: bool = False):
        if is_error:
            self.lbl_toast.setStyleSheet("background: #ffebe9; color: #cf222e; border: 1px solid #ff8182; border-radius: 5px; padding: 2px 10px; font-size: 11px; font-weight: 600;")
        else:
            self.lbl_toast.setStyleSheet("background: #dafbe1; color: #116329; border: 1px solid #4ac26b; border-radius: 5px; padding: 2px 10px; font-size: 11px; font-weight: 600;")
        self.lbl_toast.setText(msg)
        self.lbl_toast.setVisible(True)
        self._toast_timer.start()
        self.statusMessage.emit(msg)

    def _hide_toast(self):
        self.lbl_toast.setVisible(False)

    def _on_word_wrap_toggled(self, checked: bool):
        self.left_editor.set_word_wrap(checked)
        self.right_editor.set_word_wrap(checked)
        self.connector.update()

    def _on_show_ws_toggled(self, checked: bool):
        self.left_editor.set_show_whitespace(checked)
        self.right_editor.set_show_whitespace(checked)

    def _zoom_in(self):
        self.left_editor.zoom_in()
        self.right_editor.zoom_in()
        self._update_zoom_label()

    def _zoom_out(self):
        self.left_editor.zoom_out()
        self.right_editor.zoom_out()
        self._update_zoom_label()

    def _zoom_reset(self):
        self.left_editor.reset_zoom()
        self.right_editor.reset_zoom()
        self._update_zoom_label()

    def _update_zoom_label(self):
        pct = int(round((self.left_editor._font_size / ModernCodeEditor.DEFAULT_FONT_SIZE) * 100))
        self.btn_zoom_reset.setText(f"{pct}%")
        self.connector.update()

    def has_unsaved_changes(self) -> bool:
        return bool(self.left_header.is_dirty or self.right_header.is_dirty)

    def load_files(self, left_path: str = "", right_path: str = "", left_title: Optional[str] = None, right_title: Optional[str] = None):
        """Loads left and/or right files (including ArchiveVFS virtual paths and .docx) with encoding & EOL detection."""
        if left_path and (is_virtual_path(left_path) or os.path.exists(left_path)):
            try:
                content, enc, eol = read_text_file(left_path)
                self._raw_left = content
                self.left_header.set_file_info(left_path, dirty=False, display_title=left_title)
                self.left_header.set_encoding_info(enc, eol)
                self.left_editor.set_language_from_path(left_path)
                self.left_header.set_read_only(is_docx_path(left_path))
                self._is_sample_state = False
            except Exception as e:
                self._show_toast(f"Left read error: {e}", is_error=True)

        if right_path and (is_virtual_path(right_path) or os.path.exists(right_path)):
            try:
                content, enc, eol = read_text_file(right_path)
                self._raw_right = content
                self.right_header.set_file_info(right_path, dirty=False, display_title=right_title)
                self.right_header.set_encoding_info(enc, eol)
                self.right_editor.set_language_from_path(right_path)
                self.right_header.set_read_only(is_docx_path(right_path))
                self._is_sample_state = False
            except Exception as e:
                self._show_toast(f"Right read error: {e}", is_error=True)

        if left_path or right_path:
            self.manual_alignments = []
            self._pending_alignment = None
            self.banner_alignment.setVisible(False)
            self.banner_reload.setVisible(False)
            self._update_alignments_button()
            self.undo_stack.clear()
            self.redo_stack.clear()
            self._update_undo_redo_actions()
            self._update_watched_files()
            self.run_diff()
            if is_docx_path(left_path) or is_docx_path(right_path):
                self._show_toast("Extracted text from Word .docx (Read-Only)")
            self.filesChanged.emit(self.left_header.current_file_path, self.right_header.current_file_path)

    def _apply_read_only_state(self):
        scope = self.combo_view_scope.currentText() if hasattr(self, "combo_view_scope") else "All Lines"
        is_filtered = self.chk_aligned_view.isChecked() and scope != "All Lines"
        self.left_editor.setReadOnly(is_filtered or self.left_header.is_read_only())
        self.right_editor.setReadOnly(is_filtered or self.right_header.is_read_only())

    def _update_watched_files(self):
        watched = self._file_watcher.files()
        if watched:
            self._file_watcher.removePaths(watched)
        for p in (self.left_header.current_file_path, self.right_header.current_file_path):
            if p and not is_vfs_path(p) and not p.startswith("sample") and not p.startswith("local_") and not p.startswith("remote_") and os.path.isfile(p):
                self._file_watcher.addPath(p)

    def _on_external_file_changed(self, path: str):
        norm = os.path.normpath(path)
        if norm in self._saving_paths:
            self._saving_paths.discard(norm)
            if os.path.isfile(path) and path not in self._file_watcher.files():
                self._file_watcher.addPath(path)
            return
        if os.path.isfile(path) and path not in self._file_watcher.files():
            self._file_watcher.addPath(path)
        self._pending_reload_path = path
        self.lbl_reload_banner.setText(
            f"External change detected in '{os.path.basename(path)}' — reload updated content from disk?"
        )
        self.banner_reload.setVisible(True)

    def _reload_external_file(self):
        self.banner_reload.setVisible(False)
        target = self._pending_reload_path
        self._pending_reload_path = None
        if not target or not os.path.isfile(target):
            return
        norm_t = os.path.normpath(target)
        reloaded = False
        lp = self.left_header.current_file_path or ""
        rp = self.right_header.current_file_path or ""
        if lp and os.path.normpath(lp) == norm_t:
            self.load_files(left_path=lp)
            reloaded = True
        if rp and os.path.normpath(rp) == norm_t:
            self.load_files(right_path=rp)
            reloaded = True
        if reloaded:
            self._show_toast(f"Reloaded: {os.path.basename(target)}")

    def _update_line_details_from_editor(self, side: str):
        if not hasattr(self, "line_details") or not self._view_rows:
            return
        editor = self.left_editor if side == "left" else self.right_editor
        row_idx = editor.textCursor().blockNumber() + editor.get_window_start()
        if 0 <= row_idx < len(self._view_rows):
            l_no, l_txt, r_no, r_txt, l_sp, r_sp, tag = self._view_rows[row_idx]
            self.line_details.update_pair(l_no, l_txt, r_no, r_txt, l_sp, r_sp, tag)

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
        new_left = self.left_editor.get_clean_text()
        if new_left == self._raw_left:
            return
        self._push_undo("Edit Left")
        self._is_sample_state = False
        self._raw_left = new_left
        self.left_header.set_dirty(True)
        if hasattr(self, "wal") and self.wal:
            self.wal.checkpoint("left", self.left_header.current_file_path or "untitled_left", self._raw_left, is_dirty=True)
        self.run_diff(editing_editor=self.left_editor)

    def _on_right_live_edit(self):
        new_right = self.right_editor.get_clean_text()
        if new_right == self._raw_right:
            return
        self._push_undo("Edit Right")
        self._is_sample_state = False
        self._raw_right = new_right
        self.right_header.set_dirty(True)
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
            eff_rules = self.active_noise_rules if (not hasattr(self, "chk_ignore_unimportant") or self.chk_ignore_unimportant.isChecked()) else []
            result: AlignedDiffResult = DiffEngine.build_aligned_diff(
                left_text, right_text,
                ignore_whitespace=ws_mode,
                ignore_case=ignore_case,
                regex_rules=eff_rules,
                ast_semantic=is_ast,
                language=lang,
                manual_alignments=self.manual_alignments
            )
            n_rows = len(result.left_display_lines)
            row_chunk_idx = [-1] * n_rows
            for c_idx, ch in enumerate(result.chunks):
                if ch.tag != 'equal':
                    for i in range(ch.left_start, min(ch.left_end, n_rows)):
                        row_chunk_idx[i] = c_idx
                if ch.tag == 'insert':
                    add_count += 1
                elif ch.tag == 'delete':
                    del_count += 1
                elif ch.tag == 'replace':
                    mod_count += 1
                elif ch.tag == 'moved':
                    moved_count += 1

            scope = self.combo_view_scope.currentText() if hasattr(self, "combo_view_scope") else "All Lines"
            if scope == "All Lines":
                keep_indices = list(range(n_rows))
            else:
                keep_mask = [False] * n_rows
                if scope == "Diffs Only":
                    for r in range(n_rows):
                        keep_mask[r] = (row_chunk_idx[r] != -1)
                elif scope == "Same Only":
                    for r in range(n_rows):
                        keep_mask[r] = (row_chunk_idx[r] == -1)
                elif scope == "Context ±3":
                    for r in range(n_rows):
                        if row_chunk_idx[r] != -1:
                            for ctx in range(max(0, r - 3), min(n_rows, r + 4)):
                                keep_mask[ctx] = True
                keep_indices = [r for r in range(n_rows) if keep_mask[r]]

            if scope == "All Lines":
                self.chunks = result.chunks
                disp_ld = result.left_display_lines
                disp_rd = result.right_display_lines
                disp_ls = set(result.left_spacers)
                disp_rs = set(result.right_spacers)
                disp_ln = dict(result.left_line_numbers)
                disp_rn = dict(result.right_line_numbers)
                orig_to_disp = {r: r for r in range(n_rows)}
            else:
                disp_ld, disp_rd = [], []
                disp_ls, disp_rs = set(), set()
                disp_ln, disp_rn = {}, {}
                orig_to_disp = {}
                prev_r = -1
                for r in keep_indices:
                    if prev_r != -1 and r > prev_r + 1:
                        sep_idx = len(disp_ld)
                        marker = f"··· ({r - prev_r - 1} hidden line(s)) ···"
                        disp_ld.append(marker)
                        disp_rd.append(marker)
                        disp_ls.add(sep_idx)
                        disp_rs.add(sep_idx)
                    d_idx = len(disp_ld)
                    orig_to_disp[r] = d_idx
                    disp_ld.append(result.left_display_lines[r])
                    disp_rd.append(result.right_display_lines[r])
                    if r in result.left_spacers:
                        disp_ls.add(d_idx)
                    if r in result.right_spacers:
                        disp_rs.add(d_idx)
                    if r in result.left_line_numbers:
                        disp_ln[d_idx] = result.left_line_numbers[r]
                    if r in result.right_line_numbers:
                        disp_rn[d_idx] = result.right_line_numbers[r]
                    prev_r = r

                remapped_chunks: List[DiffChunk] = []
                for ch in result.chunks:
                    if ch.tag == 'equal':
                        continue
                    mapped_rows = [orig_to_disp[r] for r in range(ch.left_start, ch.left_end) if r in orig_to_disp]
                    if not mapped_rows:
                        continue
                    d_start, d_end = mapped_rows[0], mapped_rows[-1] + 1
                    new_l_spans = {orig_to_disp[ch.left_start + k] - d_start: sp for k, sp in ch.left_char_spans.items() if (ch.left_start + k) in orig_to_disp}
                    new_r_spans = {orig_to_disp[ch.right_start + k] - d_start: sp for k, sp in ch.right_char_spans.items() if (ch.right_start + k) in orig_to_disp}
                    remapped_chunks.append(DiffChunk(
                        tag=ch.tag,
                        left_start=d_start, left_end=d_end,
                        right_start=d_start, right_end=d_end,
                        left_char_spans=new_l_spans,
                        right_char_spans=new_r_spans,
                        is_moved=ch.is_moved,
                        moved_to_line=ch.moved_to_line,
                        semantic_match_info=ch.semantic_match_info,
                        raw_left_start=ch.raw_left_start, raw_left_end=ch.raw_left_end,
                        raw_right_start=ch.raw_right_start, raw_right_end=ch.raw_right_end,
                    ))
                self.chunks = remapped_chunks

            if editing_editor != self.left_editor or scope != "All Lines":
                self.left_editor.set_aligned_lines(disp_ld, disp_ls, disp_ln)
            else:
                self.left_editor.spacer_lines = disp_ls
                self.left_editor.real_line_numbers = disp_ln
                self.left_editor.gutter.update()

            if editing_editor != self.right_editor or scope != "All Lines":
                self.right_editor.set_aligned_lines(disp_rd, disp_rs, disp_rn)
            else:
                self.right_editor.spacer_lines = disp_rs
                self.right_editor.real_line_numbers = disp_rn
                self.right_editor.gutter.update()

            disp_tags = ["equal"] * len(disp_ld)
            for chunk in self.chunks:
                if chunk.tag == 'equal':
                    continue
                for r in range(chunk.left_start, min(chunk.left_end, len(disp_tags))):
                    disp_tags[r] = chunk.tag
                if chunk.tag == 'replace':
                    for i in range(chunk.left_start, chunk.left_end):
                        is_left_spacer = i in disp_ls
                        is_right_spacer = i in disp_rs
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
                    for i in range(chunk.left_start, chunk.left_end):
                        left_decorations[i] = "#cf222e"
                        left_tick_info[i] = ("#cf222e", "Deletion")

                elif chunk.tag == 'insert':
                    for j in range(chunk.right_start, chunk.right_end):
                        right_decorations[j] = "#1a7f37"
                        right_tick_info[j] = ("#1a7f37", "Addition")

                elif chunk.tag == 'moved':
                    info = chunk.semantic_match_info or "Moved Block"
                    for i in range(chunk.left_start, chunk.left_end):
                        if i not in disp_ls:
                            left_decorations[i] = "#8250df"
                            left_tick_info[i] = ("#8250df", info)
                    for j in range(chunk.right_start, chunk.right_end):
                        if j not in disp_rs:
                            right_decorations[j] = "#8250df"
                            right_tick_info[j] = ("#8250df", info)

            self._view_rows = [
                (
                    disp_ln.get(i),
                    disp_ld[i] if i < len(disp_ld) else "",
                    disp_rn.get(i),
                    disp_rd[i] if i < len(disp_rd) else "",
                    i in disp_ls,
                    i in disp_rs,
                    disp_tags[i],
                )
                for i in range(max(len(disp_ld), len(disp_rd)))
            ]
        else:
            eff_rules = self.active_noise_rules if (not hasattr(self, "chk_ignore_unimportant") or self.chk_ignore_unimportant.isChecked()) else []
            self.chunks, left_lines, right_lines = DiffEngine.compute_2way_diff(
                left_text, right_text,
                ignore_whitespace=ws_mode,
                ignore_case=ignore_case,
                regex_rules=eff_rules,
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
                    for k, spans in chunk.left_char_spans.items():
                        left_char_decorations[chunk.left_start + k] = [(s.start, s.end, "#0969da") for s in spans]
                    for k, spans in chunk.right_char_spans.items():
                        right_char_decorations[chunk.right_start + k] = [(s.start, s.end, "#0969da") for s in spans]
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

        self.left_editor.apply_diff_decorations(left_decorations, left_char_decorations, tick_info=left_tick_info)
        self.right_editor.apply_diff_decorations(right_decorations, right_char_decorations, tick_info=right_tick_info)
        self.connector.set_chunks(self.chunks)

        diff_chunks = [i for i, c in enumerate(self.chunks) if c.tag != 'equal']
        if not diff_chunks:
            self.current_diff_idx = -1
            self.lbl_hunk_pos.setText("Hunk 0/0")
            self.connector.set_active_chunk(-1)
        else:
            if self.current_diff_idx >= len(diff_chunks):
                self.current_diff_idx = len(diff_chunks) - 1
            pos_str = str(self.current_diff_idx + 1) if self.current_diff_idx >= 0 else "-"
            self.lbl_hunk_pos.setText(f"Hunk {pos_str}/{len(diff_chunks)}")

        total_diffs = add_count + del_count + mod_count + moved_count
        moved_badge = f"  <span style='color: #8250df; font-weight: bold;'>• {moved_count} Moved</span>" if moved_count > 0 else ""
        self.lbl_stats.setText(
            f"{total_diffs} Differences  |  "
            f"<span style='color: #1a7f37; font-weight: bold;'>+{add_count}</span>  "
            f"<span style='color: #cf222e; font-weight: bold;'>-{del_count}</span>  "
            f"<span style='color: #0969da; font-weight: bold;'>~{mod_count}</span>"
            f"{moved_badge}"
        )
        self.left_header.set_diff_stats(0, del_count, mod_count)
        self.right_header.set_diff_stats(add_count, 0, mod_count)

        if not is_aligned:
            max_un = max(len(left_lines), len(right_lines))
            self._view_rows = [
                (
                    i + 1 if i < len(left_lines) else None,
                    left_lines[i] if i < len(left_lines) else "",
                    i + 1 if i < len(right_lines) else None,
                    right_lines[i] if i < len(right_lines) else "",
                    i >= len(left_lines),
                    i >= len(right_lines),
                    "equal",
                )
                for i in range(max_un)
            ]

        self._apply_read_only_state()
        self._update_line_details_from_editor("right" if editing_editor == self.right_editor else "left")

        if hasattr(self, "find_bar") and self.find_bar.isVisible() and self.txt_find.text():
            self._on_find_text_changed()

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
            self._show_toast(f"Patch exported: {os.path.basename(file)}")

    def _export_html_report(self):
        file, _ = QFileDialog.getSaveFileName(self, "Export Side-by-Side HTML Report", "diff_report.html", "HTML Files (*.html);;All Files (*.*)")
        if file:
            left_name = self.left_header.current_file_path or "Left"
            right_name = self.right_header.current_file_path or "Right"
            ws_mode = ["none", "leading_trailing", "all"][self.combo_whitespace.currentIndex()]
            eff_rules = self.active_noise_rules if self.chk_ignore_unimportant.isChecked() else []
            HeadlessReporter.generate_side_by_side_html_report(
                self._raw_left,
                self._raw_right,
                left_label=left_name,
                right_label=right_name,
                output_file=file,
                ignore_whitespace=ws_mode,
                ignore_case=self.chk_ignore_case.isChecked(),
                regex_rules=eff_rules,
            )
            self._show_toast(f"HTML report exported: {os.path.basename(file)}")

    def _copy_unified_diff(self):
        left_name = self.left_header.current_file_path or "a/file"
        right_name = self.right_header.current_file_path or "b/file"
        patch_content = DiffEngine.generate_unified_patch(self._raw_left, self._raw_right, left_name, right_name)
        QApplication.clipboard().setText(patch_content)
        self._show_toast("Unified diff copied to clipboard")

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
        self.lbl_hunk_pos.setText(f"Hunk {self.current_diff_idx + 1}/{len(diff_chunks)}")

    def jump_prev(self):
        diff_chunks = [i for i, c in enumerate(self.chunks) if c.tag != 'equal']
        if not diff_chunks:
            return
        self.current_diff_idx = (self.current_diff_idx - 1 + len(diff_chunks)) % len(diff_chunks)
        self._scroll_to_chunk(diff_chunks[self.current_diff_idx])
        self.lbl_hunk_pos.setText(f"Hunk {self.current_diff_idx + 1}/{len(diff_chunks)}")

    def _scroll_to_chunk(self, chunk_idx: int):
        chunk = self.chunks[chunk_idx]
        target_line = chunk.left_start
        self.left_editor.jump_to_line(target_line)
        self.right_editor.jump_to_line(chunk.right_start)
        self.connector.set_active_chunk(chunk_idx)

    def _start_alignment_mode(self, side: str, line: int):
        self._pending_alignment = (side, line)
        target_side = "Right" if side == "left" else "Left"
        self.lbl_align_banner.setText(
            f"Manual Alignment Active: Click any line in the {target_side} pane to align with {side.capitalize()} Line {line}. (Esc to cancel)"
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
            self.btn_clear_alignments.setText(f"{count} Alignment{'s' if count > 1 else ''} [✕]")
            self.btn_clear_alignments.setVisible(True)
        else:
            self.btn_clear_alignments.setVisible(False)

    def _push_undo(self, desc: str = "Edit"):
        self.undo_stack.append((self._raw_left, self._raw_right, desc))
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self._update_undo_redo_actions()

    def undo(self):
        if not self.undo_stack:
            return
        prev_left, prev_right, desc = self.undo_stack.pop()
        self.redo_stack.append((self._raw_left, self._raw_right, desc))
        self._raw_left = prev_left
        self._raw_right = prev_right
        self._update_undo_redo_actions()
        self.run_diff()

    def redo(self):
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
            self.btn_undo.setToolTip(f"Undo {self.undo_stack[-1][2]} (Ctrl+Z)" if has_undo else "Nothing to undo (Ctrl+Z)")
        if hasattr(self, 'btn_redo'):
            self.btn_redo.setEnabled(has_redo)
            self.btn_redo.setToolTip(f"Redo {self.redo_stack[-1][2]} (Ctrl+Y)" if has_redo else "Nothing to redo (Ctrl+Y)")

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
        use_regex = self.chk_find_regex.isChecked() if hasattr(self, 'chk_find_regex') else False
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

        regex_obj = None
        if use_regex:
            opts = QRegularExpression.NoPatternOption if case_sensitive else QRegularExpression.CaseInsensitiveOption
            regex_obj = QRegularExpression(query, opts)
            if not regex_obj.isValid():
                self.lbl_find_status.setText("Invalid regex")
                return

        def collect_matches(editor: ModernCodeEditor, side: str):
            doc = editor.document()
            cursor = QTextCursor(doc)
            while True:
                if regex_obj is not None:
                    cursor = doc.find(regex_obj, cursor, flags)
                else:
                    cursor = doc.find(query, cursor, flags)
                if cursor.isNull():
                    break
                self._find_matches.append((side, cursor.selectionStart(), cursor.selectionEnd()))

        collect_matches(self.left_editor, "left")
        collect_matches(self.right_editor, "right")

        total = len(self._find_matches)
        if total > 0:
            self._current_find_match_idx = 0
            self._jump_to_current_match()
        else:
            self.left_editor.clear_search_selections()
            self.right_editor.clear_search_selections()
            if hasattr(self, 'lbl_find_status'):
                self.lbl_find_status.setText("No matches")

    def _refresh_search_highlights(self):
        left_sels: List[QTextEdit.ExtraSelection] = []
        right_sels: List[QTextEdit.ExtraSelection] = []

        for idx, (side, start, end) in enumerate(self._find_matches):
            editor = self.left_editor if side == "left" else self.right_editor
            cursor = QTextCursor(editor.document())
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            # Highlight active match in vivid amber/orange, others in soft yellow
            sel.format.setBackground(QColor("#fb923c" if idx == self._current_find_match_idx else "#fef08a"))
            if side == "left":
                left_sels.append(sel)
            else:
                right_sels.append(sel)

        self.left_editor.set_search_selections(left_sels)
        self.right_editor.set_search_selections(right_sels)

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
        self._refresh_search_highlights()
        side, start, end = self._find_matches[self._current_find_match_idx]
        editor = self.left_editor if side == "left" else self.right_editor
        cursor = QTextCursor(editor.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        editor.setTextCursor(cursor)
        editor.centerCursor()

        if hasattr(self, 'lbl_find_status'):
            self.lbl_find_status.setText(f"{self._current_find_match_idx + 1} of {len(self._find_matches)} matches")

    def replace_current_match(self):
        if not self._find_matches or self._current_find_match_idx < 0:
            return
        side, start, end = self._find_matches[self._current_find_match_idx]
        editor = self.left_editor if side == "left" else self.right_editor
        cursor = QTextCursor(editor.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.insertText(self.txt_replace.text())
        if side == "left":
            self._on_left_live_edit()
        else:
            self._on_right_live_edit()

    def replace_all_matches(self):
        query = self.txt_find.text()
        if not query or not self._find_matches:
            return
        repl = self.txt_replace.text()
        case_sensitive = self.chk_find_case.isChecked()
        use_regex = self.chk_find_regex.isChecked()
        flags = 0 if case_sensitive else re.IGNORECASE

        self._push_undo("Replace All")
        self._is_sample_state = False
        pattern = query if use_regex else re.escape(query)
        try:
            self._raw_left = re.sub(pattern, repl, self._raw_left, flags=flags)
            self._raw_right = re.sub(pattern, repl, self._raw_right, flags=flags)
        except re.error as e:
            self._show_toast(f"Invalid regex: {e}", is_error=True)
            return
        self.left_header.set_dirty(True)
        self.right_header.set_dirty(True)
        self.run_diff()
        self._on_find_text_changed()

    def swap_sides(self):
        self._push_undo("Swap Sides")
        self._raw_left, self._raw_right = self._raw_right, self._raw_left
        left_path = self.left_header.current_file_path
        right_path = self.right_header.current_file_path
        left_dirty, right_dirty = self.left_header.is_dirty, self.right_header.is_dirty
        left_enc, left_eol = self.left_header.encoding, self.left_header.eol
        right_enc, right_eol = self.right_header.encoding, self.right_header.eol

        self.left_header.set_file_info(right_path, dirty=right_dirty)
        self.left_header.set_encoding_info(right_enc, right_eol)
        self.right_header.set_file_info(left_path, dirty=left_dirty)
        self.right_header.set_encoding_info(left_enc, left_eol)
        self.left_editor.set_language_from_path(right_path)
        self.right_editor.set_language_from_path(left_path)

        if self.manual_alignments:
            self.manual_alignments = [(r, l) for l, r in self.manual_alignments]
        self._pending_alignment = None
        self.banner_alignment.setVisible(False)
        self._update_alignments_button()
        self.run_diff()

    def _raw_bounds_for_chunk(self, c: DiffChunk) -> Tuple[int, int, int, int]:
        l1 = c.raw_left_start if c.raw_left_start is not None else c.left_start
        l2 = c.raw_left_end if c.raw_left_end is not None else c.left_end
        r1 = c.raw_right_start if c.raw_right_start is not None else c.right_start
        r2 = c.raw_right_end if c.raw_right_end is not None else c.right_end
        return l1, l2, r1, r2

    def transfer_left_to_right(self, chunk_idx: int):
        if chunk_idx < 0 or chunk_idx >= len(self.chunks):
            return
        if self.right_header.is_read_only():
            self._show_toast("Right pane is locked (Read-Only)", is_error=True)
            return
        c = self.chunks[chunk_idx]
        l1, l2, r1, r2 = self._raw_bounds_for_chunk(c)
        left_raw = self._raw_left.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        right_raw = self._raw_right.replace('\r\n', '\n').replace('\r', '\n').split('\n')

        self._push_undo(f"Transfer Hunk {chunk_idx + 1} to Right")
        self._is_sample_state = False
        right_raw[r1:r2] = left_raw[l1:l2]
        self._raw_right = '\n'.join(right_raw)
        self.right_header.set_dirty(True)
        if hasattr(self, "wal") and self.wal:
            self.wal.checkpoint("right", self.right_header.current_file_path or "untitled_right", self._raw_right, is_dirty=True)
        self.run_diff()

    def transfer_right_to_left(self, chunk_idx: int):
        if chunk_idx < 0 or chunk_idx >= len(self.chunks):
            return
        if self.left_header.is_read_only():
            self._show_toast("Left pane is locked (Read-Only)", is_error=True)
            return
        c = self.chunks[chunk_idx]
        l1, l2, r1, r2 = self._raw_bounds_for_chunk(c)
        left_raw = self._raw_left.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        right_raw = self._raw_right.replace('\r\n', '\n').replace('\r', '\n').split('\n')

        self._push_undo(f"Transfer Hunk {chunk_idx + 1} to Left")
        self._is_sample_state = False
        left_raw[l1:l2] = right_raw[r1:r2]
        self._raw_left = '\n'.join(left_raw)
        self.left_header.set_dirty(True)
        if hasattr(self, "wal") and self.wal:
            self.wal.checkpoint("left", self.left_header.current_file_path or "untitled_left", self._raw_left, is_dirty=True)
        self.run_diff()

    def _on_left_file_opened(self, path, content):
        self._raw_left = content
        self._is_sample_state = False
        self.left_header.set_file_info(path, dirty=False)
        self.left_editor.set_language_from_path(path)
        self.left_header.set_read_only(is_docx_path(path))
        self.manual_alignments = []
        self._pending_alignment = None
        self.banner_alignment.setVisible(False)
        self.banner_reload.setVisible(False)
        self._update_alignments_button()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._update_undo_redo_actions()
        self._update_watched_files()
        self.run_diff()
        if is_docx_path(path):
            self._show_toast("Extracted text from Word .docx (Read-Only)")
        self.filesChanged.emit(self.left_header.current_file_path, self.right_header.current_file_path)

    def _on_right_file_opened(self, path, content):
        self._raw_right = content
        self._is_sample_state = False
        self.right_header.set_file_info(path, dirty=False)
        self.right_editor.set_language_from_path(path)
        self.right_header.set_read_only(is_docx_path(path))
        self.manual_alignments = []
        self._pending_alignment = None
        self.banner_alignment.setVisible(False)
        self.banner_reload.setVisible(False)
        self._update_alignments_button()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._update_undo_redo_actions()
        self._update_watched_files()
        self.run_diff()
        if is_docx_path(path):
            self._show_toast("Extracted text from Word .docx (Read-Only)")
        self.filesChanged.emit(self.left_header.current_file_path, self.right_header.current_file_path)

    def _save_focused_editor(self):
        if self.right_editor.hasFocus():
            self._save_editor(self.right_editor, self.right_header)
        else:
            self._save_editor(self.left_editor, self.left_header)

    def _save_editor(self, editor: ModernCodeEditor, header: EditorHeader):
        path = header.current_file_path
        if not path or path.startswith("sample") or path.startswith("local_") or path.startswith("remote_") or is_vfs_path(path):
            suggested = "" if is_vfs_path(path) else (path or "")
            path, _ = QFileDialog.getSaveFileName(self, "Save File", suggested, "All Files (*.*)")
            if not path:
                return

        try:
            self._saving_paths.add(os.path.normpath(path))
            clean_content = self._raw_left if editor == self.left_editor else self._raw_right
            write_text_file(path, clean_content, encoding_label=header.encoding, eol_label=header.eol)
            header.set_file_info(path, dirty=False)
            editor.set_language_from_path(path)
            self._update_watched_files()
            if hasattr(self, "wal") and self.wal:
                pane = "left" if editor == self.left_editor else "right"
                self.wal.commit_save(pane, path)
            self._show_toast(f"Saved: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error Saving", f"Could not save file:\n{e}")

    def _get_working_git_file(self) -> Tuple[Optional[str], str]:
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

        working_content, enc, eol = read_text_file(target_path)
        self._is_sample_state = False
        self._raw_left = head_content
        self._raw_right = working_content
        self.left_header.set_file_info(target_path, dirty=False, display_title=f"{os.path.basename(target_path)} (Git HEAD)")
        self.left_header.set_encoding_info(enc, eol)
        self.right_header.set_file_info(target_path, dirty=False)
        self.right_header.set_encoding_info(enc, eol)
        self.left_editor.set_language_from_path(target_path)
        self.right_editor.set_language_from_path(target_path)
        self.run_diff()
        self._show_toast(f"Loaded Git HEAD vs Working Copy for {os.path.basename(target_path)}")

    def _resolve_chunk_idx(self, chunk_idx: int) -> Optional[int]:
        if 0 <= chunk_idx < len(self.chunks) and self.chunks[chunk_idx].tag != 'equal':
            return chunk_idx
        diff_chunks = [i for i, c in enumerate(self.chunks) if c.tag != 'equal']
        if 0 <= self.current_diff_idx < len(diff_chunks):
            return diff_chunks[self.current_diff_idx]
        return None

    def _to_raw_chunk(self, chunk: DiffChunk) -> DiffChunk:
        l1, l2, r1, r2 = self._raw_bounds_for_chunk(chunk)
        return DiffChunk(
            tag=chunk.tag,
            left_start=l1, left_end=l2,
            right_start=r1, right_end=r2
        )

    def stage_current_hunk(self):
        self.stage_hunk(-1)

    def unstage_current_hunk(self):
        self.unstage_hunk(-1)

    def discard_current_hunk(self):
        self.discard_hunk(-1)

    def stage_hunk(self, chunk_idx: int):
        resolved = self._resolve_chunk_idx(chunk_idx)
        if resolved is None:
            self._show_toast("No diff hunk selected to stage.", is_error=True)
            return

        target_path, _ = self._get_working_git_file()
        if not target_path:
            QMessageBox.warning(self, "Git Staging", "The opened file is not inside a Git repository.")
            return

        raw_chunk = self._to_raw_chunk(self.chunks[resolved])
        left_lines = self._raw_left.splitlines()
        right_lines = self._raw_right.splitlines()

        ok, msg = GitStagingManager.stage_hunk(target_path, raw_chunk, left_lines, right_lines)
        if ok:
            self._show_toast(f"Hunk staged to Git index")
        else:
            QMessageBox.warning(self, "Staging Failed", f"Could not stage hunk:\n{msg}")

    def unstage_hunk(self, chunk_idx: int):
        resolved = self._resolve_chunk_idx(chunk_idx)
        if resolved is None:
            return

        target_path, _ = self._get_working_git_file()
        if not target_path:
            return

        raw_chunk = self._to_raw_chunk(self.chunks[resolved])
        left_lines = self._raw_left.splitlines()
        right_lines = self._raw_right.splitlines()

        ok, msg = GitStagingManager.unstage_hunk(target_path, raw_chunk, left_lines, right_lines)
        if ok:
            self._show_toast("Hunk unstaged from Git index")
        else:
            QMessageBox.warning(self, "Unstage Failed", f"Could not unstage hunk:\n{msg}")

    def discard_hunk(self, chunk_idx: int):
        resolved = self._resolve_chunk_idx(chunk_idx)
        if resolved is None:
            return

        reply = QMessageBox.question(
            self,
            "Discard Hunk Changes",
            f"Are you sure you want to discard changes in this hunk?\nThis will revert working copy modifications for this block.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        target_path, _ = self._get_working_git_file()
        if not target_path:
            return

        raw_chunk = self._to_raw_chunk(self.chunks[resolved])
        left_lines = self._raw_left.splitlines()
        right_lines = self._raw_right.splitlines()

        ok, msg = GitStagingManager.discard_hunk(target_path, raw_chunk, left_lines, right_lines)
        if ok:
            if os.path.exists(target_path):
                content, enc, eol = read_text_file(target_path)
                self._raw_right = content
                self.right_header.set_file_info(target_path, dirty=False)
                self.right_header.set_encoding_info(enc, eol)
                self.run_diff()
            self._show_toast("Hunk discarded and reverted")
        else:
            QMessageBox.warning(self, "Discard Failed", f"Could not discard hunk:\n{msg}")
