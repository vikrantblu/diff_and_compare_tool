"""
diff_and_compare_tool Dual-Tree Folder & Virtual Archive Comparison Studio
Matches diff_and_compare_tool's signature Folder Compare interface:
- Top Ribbon:
  - 'Home', 'Sessions'
  - View Filters: '* All', '≠ Diffs', '= Same' (Instant in-memory filtering)
  - 'Rules' (Size & Timestamp, Byte-by-Byte Hash, Rules-Based)
  - 'Expand All', 'Collapse All', 'Refresh', 'Swap'
  - Filename / Wildcard Filters: e.g. '-kb_*.*', '*.py'
- Smart Subfolder Matcher Banner:
  - Detects if a subfolder on one side matches the opposite root, offering a 1-click direct compare.
- Side-by-Side Synchronized Dual Folder Trees:
  - Left Tree (Name, Size, Modified)
  - Center Gutter (Comparison status icons: ≠ diff in red, ← left orphan, → right orphan, = match)
  - Right Tree (Name, Size, Modified)
  - Synchronized scrolling and O(1) branch expand/collapse.
  - No ghost expand arrows on spacer nodes.
  - Folders first, files second.
  - Right-click context menus: "Set as Base Folder", "Open in Explorer", "Copy Path".
- Bottom Session Log Bar with background worker progress and cancel button.
- Double-clicking folders toggles expand; double-clicking files opens Diff Studio.
"""

import os
import subprocess
from typing import Optional, List, Dict, Tuple
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLineEdit, QComboBox, QLabel, QFileDialog, QHeaderView,
    QSplitter, QFrame, QButtonGroup, QMessageBox, QSizePolicy, QMenu,
    QProgressBar, QApplication, QCheckBox, QStyledItemDelegate, QStyle
)
from PySide6.QtCore import Qt, Signal, QThread, QRect, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QAction, QBrush, QPainter, QKeySequence, QShortcut
from app.ui.styles.icons import get_line_icon
from app.core.folder_compare_engine import FolderCompareEngine, FolderCompareItem
from app.ui.dialogs.folder_sync_dialog import FolderSyncDialog


class FolderCompareWorker(QThread):
    """Background worker thread so comparing 10k+ files never freezes the UI."""
    progress = Signal(int, str)
    finished = Signal(list, str, str)  # items, left_dir, right_dir
    failed = Signal(str)

    def __init__(self, left_dir: str, right_dir: str, mode: str, filter_expr: str, respect_gitignore: bool = True):
        super().__init__()
        self.left_dir = left_dir
        self.right_dir = right_dir
        self.mode = mode
        self.filter_expr = filter_expr
        self.respect_gitignore = respect_gitignore
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            import time
            last_emit_time = 0.0
            last_emit_count = 0

            def cb(count, msg):
                nonlocal last_emit_time, last_emit_count
                if self._is_cancelled:
                    raise InterruptedError("Cancelled by user")

                now = time.monotonic()
                # Adaptive throttle: emit every 250 items or 50ms to prevent Qt event queue saturation
                if (count - last_emit_count >= 250) or (now - last_emit_time >= 0.05) or (count == 0):
                    self.progress.emit(count, msg)
                    last_emit_time = now
                    last_emit_count = count

            items = FolderCompareEngine.compare_directories(
                self.left_dir,
                self.right_dir,
                mode=self.mode,
                filter_expr=self.filter_expr,
                progress_callback=cb,
                respect_gitignore=self.respect_gitignore
            )
            if not self._is_cancelled:
                self.progress.emit(last_emit_count, "Comparison scan complete.")
                self.finished.emit(items, self.left_dir, self.right_dir)
        except InterruptedError:
            pass
        except Exception as e:
            self.failed.emit(str(e))


class GutterItemDelegate(QStyledItemDelegate):
    """
    Custom delegate for the center diff gutter tree in diff_and_compare_tool.
    Renders status symbols (≠, ←, →, =) perfectly centered in the gutter column,
    completely independent of tree nesting depth or item indentation.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter: QPainter, option, index):
        painter.save()

        # Compute full row width spanning the entire viewport
        viewport_width = option.widget.viewport().width() if option.widget else option.rect.width()
        row_rect = QRect(0, option.rect.y(), viewport_width, option.rect.height())

        # Render background (selection, hover, or clean alternating row colors)
        if option.state & QStyle.State_Selected:
            painter.fillRect(row_rect, QColor("#dbeafe"))
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(row_rect, QColor("#f1f5f9"))
        else:
            painter.fillRect(row_rect, QColor("#f8fafc"))

        # Subtle bottom row separator line matching the trees
        painter.setPen(QColor("#f1f5f9"))
        painter.drawLine(0, row_rect.bottom(), viewport_width, row_rect.bottom())

        # Render centered text
        text = index.data(Qt.DisplayRole) or ""
        if text:
            fg = index.data(Qt.ForegroundRole)
            if isinstance(fg, (QBrush, QColor)):
                color = fg.color() if isinstance(fg, QBrush) else fg
            else:
                color = QColor("#475569")

            font = painter.font()
            font.setFamily("Segoe UI")
            font.setBold(True)
            font.setPointSize(12)
            painter.setFont(font)
            painter.setPen(color)

            # Draw text perfectly centered horizontally and vertically
            painter.drawText(row_rect, Qt.AlignCenter, str(text))

        painter.restore()

    def sizeHint(self, option, index):
        sh = super().sizeHint(option, index)
        return QSize(sh.width(), max(24, sh.height()))


class DirCompareView(QWidget):
    """Signature diff_and_compare_tool Dual-Tree Folder Comparison Studio."""

    openInDiffRequested = Signal(str, str)          # (left_file_path, right_file_path)
    homeRequested = Signal()                        # Switch to Home screen

    def __init__(self, parent=None):
        super().__init__(parent)
        self.left_dir: str = ""
        self.right_dir: str = ""
        self.current_filter_mode = "all"            # "all", "diffs", "same"
        self._is_syncing_scroll = False
        self._is_syncing_expand = False
        self._is_syncing_current = False
        self._worker: Optional[FolderCompareWorker] = None
        self._cached_items: List[FolderCompareItem] = []

        self.setup_ui()
        # Load sample demo comparison
        self._load_initial_demo()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------------------------------------------------
        # 1. Top diff_and_compare_tool Ribbon
        # ---------------------------------------------------------
        ribbon = QWidget()
        ribbon.setObjectName("DirRibbon")
        ribbon.setFixedHeight(48)
        ribbon.setStyleSheet("""
            #DirRibbon {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f8fafc);
                border-bottom: 1.5px solid #cbd5e1;
            }
        """)
        r_layout = QHBoxLayout(ribbon)
        r_layout.setContentsMargins(10, 6, 10, 6)
        r_layout.setSpacing(6)

        # Home
        self.btn_home = QPushButton(" Home")
        self.btn_home.setIcon(get_line_icon("sparkles", "#0969da"))
        self.btn_home.setFixedHeight(30)
        self.btn_home.clicked.connect(self.homeRequested.emit)
        r_layout.addWidget(self.btn_home)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet("color: #cbd5e1;")
        r_layout.addWidget(sep1)

        # View Filter Buttons: * All, ≠ Diffs, = Same (Instant In-Memory Filtering)
        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)

        self.btn_filter_all = QPushButton(" * All")
        self.btn_filter_all.setCheckable(True)
        self.btn_filter_all.setChecked(True)
        self.btn_filter_all.setFixedHeight(30)
        self.btn_filter_all.clicked.connect(lambda: self._set_filter_mode("all"))
        self.filter_group.addButton(self.btn_filter_all)
        r_layout.addWidget(self.btn_filter_all)

        self.btn_filter_diffs = QPushButton(" ≠ Diffs")
        self.btn_filter_diffs.setCheckable(True)
        self.btn_filter_diffs.setFixedHeight(30)
        self.btn_filter_diffs.clicked.connect(lambda: self._set_filter_mode("diffs"))
        self.filter_group.addButton(self.btn_filter_diffs)
        r_layout.addWidget(self.btn_filter_diffs)

        self.btn_filter_same = QPushButton(" = Same")
        self.btn_filter_same.setCheckable(True)
        self.btn_filter_same.setFixedHeight(30)
        self.btn_filter_same.clicked.connect(lambda: self._set_filter_mode("same"))
        self.filter_group.addButton(self.btn_filter_same)
        r_layout.addWidget(self.btn_filter_same)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet("color: #cbd5e1;")
        r_layout.addWidget(sep2)

        # Rules button
        self.combo_rules = QComboBox()
        self.combo_rules.setFixedHeight(30)
        self.combo_rules.addItems([
            "Byte-by-Byte (SHA-256)",
            "Size & Timestamp Match",
            "Rules-Based (Ignore Whitespace)"
        ])
        self.combo_rules.currentIndexChanged.connect(self.run_comparison)
        r_layout.addWidget(self.combo_rules)

        # Expand / Collapse
        self.btn_expand = QPushButton()
        self.btn_expand.setIcon(get_line_icon("arrow-down", "#1e293b"))
        self.btn_expand.setToolTip("Expand All Folders")
        self.btn_expand.setFixedHeight(30)
        self.btn_expand.setFixedWidth(34)
        self.btn_expand.clicked.connect(self._expand_all)
        r_layout.addWidget(self.btn_expand)

        self.btn_collapse = QPushButton()
        self.btn_collapse.setIcon(get_line_icon("arrow-up", "#1e293b"))
        self.btn_collapse.setToolTip("Collapse All Folders")
        self.btn_collapse.setFixedHeight(30)
        self.btn_collapse.setFixedWidth(34)
        self.btn_collapse.clicked.connect(self._collapse_all)
        r_layout.addWidget(self.btn_collapse)

        # Swap
        self.btn_swap = QPushButton(" Swap")
        self.btn_swap.setIcon(get_line_icon("swap", "#1e293b"))
        self.btn_swap.setFixedHeight(30)
        self.btn_swap.clicked.connect(self._swap_folders)
        r_layout.addWidget(self.btn_swap)

        # Refresh
        self.btn_refresh = QPushButton(" Refresh")
        self.btn_refresh.setIcon(get_line_icon("refresh", "#1e293b"))
        self.btn_refresh.setFixedHeight(30)
        self.btn_refresh.clicked.connect(self.run_comparison)
        r_layout.addWidget(self.btn_refresh)

        # Sync Hub button (Interactive Synchronization)
        self.btn_sync = QPushButton(" 🔄 Sync Hub...")
        self.btn_sync.setIcon(get_line_icon("refresh", "#0969da"))
        self.btn_sync.setFixedHeight(30)
        self.btn_sync.setToolTip("Open interactive folder synchronization hub (Mirror, Bi-directional, Update)")
        self.btn_sync.clicked.connect(self._open_sync_dialog)
        r_layout.addWidget(self.btn_sync)

        r_layout.addSpacing(6)

        # Smart .gitignore & Exclusions toggle
        self.chk_gitignore = QCheckBox(".gitignore / Exclusions")
        self.chk_gitignore.setChecked(True)
        self.chk_gitignore.setToolTip("Respect root .gitignore, .hgignore, and common exclusions (node_modules, __pycache__, .venv, .git)")
        self.chk_gitignore.toggled.connect(self.run_comparison)
        r_layout.addWidget(self.chk_gitignore)

        # Filters entry e.g. -kb_*.*
        lbl_flt = QLabel("Filters:")
        lbl_flt.setStyleSheet("font-weight: 600; color: #475569;")
        r_layout.addWidget(lbl_flt)

        self.txt_filter_pattern = QLineEdit()
        self.txt_filter_pattern.setPlaceholderText("-*.tmp; *.py")
        self.txt_filter_pattern.setFixedHeight(30)
        self.txt_filter_pattern.setFixedWidth(140)
        self.txt_filter_pattern.returnPressed.connect(self.run_comparison)
        r_layout.addWidget(self.txt_filter_pattern)

        r_layout.addStretch()

        main_layout.addWidget(ribbon)

        # ---------------------------------------------------------
        # 2. Dual Path Selection Header Bar
        # ---------------------------------------------------------
        path_bar = QFrame()
        path_bar.setFixedHeight(46)
        path_bar.setStyleSheet("background-color: #f8fafc; border-bottom: 1px solid #cbd5e1;")
        pb_layout = QHBoxLayout(path_bar)
        pb_layout.setContentsMargins(10, 6, 10, 6)
        pb_layout.setSpacing(12)

        # Left folder path
        lbl_l = QLabel("Left:")
        lbl_l.setStyleSheet("font-weight: 700; color: #0969da;")
        pb_layout.addWidget(lbl_l)

        self.txt_left_path = QLineEdit()
        self.txt_left_path.setFixedHeight(30)
        self.txt_left_path.returnPressed.connect(self.run_comparison)
        pb_layout.addWidget(self.txt_left_path, 1)

        self.btn_browse_left = QPushButton(" Browse...")
        self.btn_browse_left.setIcon(get_line_icon("folder", "#0969da"))
        self.btn_browse_left.setFixedHeight(30)
        self.btn_browse_left.clicked.connect(self._browse_left)
        pb_layout.addWidget(self.btn_browse_left)

        self.btn_up_left = QPushButton("↑")
        self.btn_up_left.setToolTip("Go up one folder")
        self.btn_up_left.setFixedHeight(30)
        self.btn_up_left.setFixedWidth(30)
        self.btn_up_left.clicked.connect(lambda: self._go_up(self.txt_left_path))
        pb_layout.addWidget(self.btn_up_left)

        # Divider
        sep_path = QFrame()
        sep_path.setFrameShape(QFrame.VLine)
        sep_path.setStyleSheet("color: #cbd5e1;")
        pb_layout.addWidget(sep_path)

        # Right folder path
        lbl_r = QLabel("Right:")
        lbl_r.setStyleSheet("font-weight: 700; color: #16a34a;")
        pb_layout.addWidget(lbl_r)

        self.txt_right_path = QLineEdit()
        self.txt_right_path.setFixedHeight(30)
        self.txt_right_path.returnPressed.connect(self.run_comparison)
        pb_layout.addWidget(self.txt_right_path, 1)

        self.btn_browse_right = QPushButton(" Browse...")
        self.btn_browse_right.setIcon(get_line_icon("folder", "#16a34a"))
        self.btn_browse_right.setFixedHeight(30)
        self.btn_browse_right.clicked.connect(self._browse_right)
        pb_layout.addWidget(self.btn_browse_right)

        self.btn_up_right = QPushButton("↑")
        self.btn_up_right.setToolTip("Go up one folder")
        self.btn_up_right.setFixedHeight(30)
        self.btn_up_right.setFixedWidth(30)
        self.btn_up_right.clicked.connect(lambda: self._go_up(self.txt_right_path))
        pb_layout.addWidget(self.btn_up_right)

        # Explorer Search Divider
        sep_search = QFrame()
        sep_search.setFrameShape(QFrame.VLine)
        sep_search.setStyleSheet("color: #cbd5e1;")
        pb_layout.addWidget(sep_search)

        # Explorer Search Text Box (Matches Windows 11 Explorer path bar)
        self.txt_explorer_search = QLineEdit()
        self.txt_explorer_search.setPlaceholderText("🔍 Search files & folders... (Ctrl+F)")
        self.txt_explorer_search.setFixedHeight(30)
        self.txt_explorer_search.setFixedWidth(240)
        self.txt_explorer_search.setClearButtonEnabled(True)
        self.txt_explorer_search.setToolTip("Instant interactive filter for folder trees (Ctrl+F)")
        self.txt_explorer_search.setStyleSheet("""
            QLineEdit {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 0 8px;
                font-size: 12px;
                color: #0f172a;
            }
            QLineEdit:focus {
                border: 1.5px solid #0969da;
            }
        """)
        self.txt_explorer_search.textChanged.connect(self._on_search_text_changed)
        pb_layout.addWidget(self.txt_explorer_search)

        # Keyboard shortcuts for Explorer Search
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)
        QShortcut(QKeySequence("Escape"), self, self._clear_search)

        main_layout.addWidget(path_bar)

        # ---------------------------------------------------------
        # 3. Smart Subfolder Matcher Banner
        # ---------------------------------------------------------
        self.banner_suggestion = QFrame()
        self.banner_suggestion.setFixedHeight(40)
        self.banner_suggestion.setStyleSheet("""
            QFrame {
                background-color: #eff6ff;
                border-bottom: 1.5px solid #93c5fd;
                padding: 4px 12px;
            }
        """)
        bs_layout = QHBoxLayout(self.banner_suggestion)
        bs_layout.setContentsMargins(12, 0, 12, 0)
        bs_layout.setSpacing(10)

        self.lbl_suggestion = QLabel()
        self.lbl_suggestion.setStyleSheet("font-size: 12px; font-weight: 600; color: #1e40af;")
        bs_layout.addWidget(self.lbl_suggestion, 1)

        self.btn_apply_suggestion = QPushButton("Compare Directly ➜")
        self.btn_apply_suggestion.setFixedHeight(26)
        self.btn_apply_suggestion.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 600;
                font-size: 11px;
                border-radius: 4px;
                padding: 0 10px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.btn_apply_suggestion.clicked.connect(self._on_apply_suggestion)
        bs_layout.addWidget(self.btn_apply_suggestion)

        btn_dismiss = QPushButton("✕ Dismiss")
        btn_dismiss.setFixedHeight(26)
        btn_dismiss.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #64748b;
                font-size: 11px;
                border-radius: 4px;
                padding: 0 8px;
                border: 1px solid #cbd5e1;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                color: #0f172a;
            }
        """)
        btn_dismiss.clicked.connect(lambda: self.banner_suggestion.setVisible(False))
        bs_layout.addWidget(btn_dismiss)

        self.banner_suggestion.setVisible(False)
        main_layout.addWidget(self.banner_suggestion)

        # ---------------------------------------------------------
        # 4. Synchronized Dual Trees with Center Difference Column
        # ---------------------------------------------------------
        self.trees_splitter = QSplitter(Qt.Horizontal)
        self.trees_splitter.setStyleSheet("QSplitter::handle { background-color: #cbd5e1; width: 4px; }")

        # Left Tree
        self.tree_left = QTreeWidget()
        self.tree_left.setHeaderLabels(["Name", "Size", "Modified"])
        self.tree_left.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree_left.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree_left.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree_left.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_left.customContextMenuRequested.connect(lambda pos: self._show_tree_context_menu(self.tree_left, pos, "left"))
        self._style_tree(self.tree_left)

        # Center Status Gutter Tree (displays mismatch symbols: ≠, ←, →, =)
        self.tree_gutter = QTreeWidget()
        self.tree_gutter.setHeaderLabels(["Diff"])
        self.tree_gutter.setFixedWidth(64)
        self.tree_gutter.setIndentation(0)
        self.tree_gutter.setRootIsDecorated(False)
        self.tree_gutter.setItemsExpandable(False)
        self.tree_gutter.setMouseTracking(True)
        self.tree_gutter.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tree_gutter.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tree_gutter.header().setDefaultAlignment(Qt.AlignCenter)
        self.tree_gutter.header().setMinimumSectionSize(0)
        self.tree_gutter.header().setStretchLastSection(True)
        self.tree_gutter.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree_gutter.setItemDelegate(GutterItemDelegate(self.tree_gutter))
        self._style_gutter(self.tree_gutter)

        # Right Tree
        self.tree_right = QTreeWidget()
        self.tree_right.setHeaderLabels(["Name", "Size", "Modified"])
        self.tree_right.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree_right.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree_right.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree_right.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_right.customContextMenuRequested.connect(lambda pos: self._show_tree_context_menu(self.tree_right, pos, "right"))
        self._style_tree(self.tree_right)

        # Synchronize scrollbars
        self.tree_left.verticalScrollBar().valueChanged.connect(lambda: self._sync_scroll(self.tree_left.verticalScrollBar()))
        self.tree_right.verticalScrollBar().valueChanged.connect(lambda: self._sync_scroll(self.tree_right.verticalScrollBar()))
        self.tree_gutter.verticalScrollBar().valueChanged.connect(lambda: self._sync_scroll(self.tree_gutter.verticalScrollBar()))

        # Synchronize selection/current item across left, gutter, and right trees
        self.tree_left.currentItemChanged.connect(self._sync_current_item)
        self.tree_gutter.currentItemChanged.connect(self._sync_current_item)
        self.tree_right.currentItemChanged.connect(self._sync_current_item)

        # Synchronize expansion/collapse in O(1) time
        self.tree_left.itemExpanded.connect(self._sync_item_expanded)
        self.tree_left.itemCollapsed.connect(self._sync_item_collapsed)
        self.tree_right.itemExpanded.connect(self._sync_item_expanded)
        self.tree_right.itemCollapsed.connect(self._sync_item_collapsed)
        self.tree_gutter.itemExpanded.connect(self._sync_item_expanded)
        self.tree_gutter.itemCollapsed.connect(self._sync_item_collapsed)

        # Double click handler (toggle folder or open file in diff)
        self.tree_left.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree_gutter.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree_right.itemDoubleClicked.connect(self._on_item_double_clicked)

        self.trees_splitter.addWidget(self.tree_left)
        self.trees_splitter.addWidget(self.tree_gutter)
        self.trees_splitter.addWidget(self.tree_right)
        self.trees_splitter.setCollapsible(0, False)
        self.trees_splitter.setCollapsible(1, False)
        self.trees_splitter.setCollapsible(2, False)
        self.trees_splitter.setSizes([550, 64, 550])

        main_layout.addWidget(self.trees_splitter, 1)

        # ---------------------------------------------------------
        # 5. Bottom Status & Activity Log Bar
        # ---------------------------------------------------------
        self.status_bar = QFrame()
        self.status_bar.setFixedHeight(30)
        self.status_bar.setStyleSheet("""
            QFrame {
                background-color: #f1f5f9;
                border-top: 1px solid #cbd5e1;
                padding: 2px 8px;
            }
        """)
        sb_layout = QHBoxLayout(self.status_bar)
        sb_layout.setContentsMargins(8, 0, 8, 0)
        sb_layout.setSpacing(12)

        self.lbl_log = QLabel("● Ready")
        self.lbl_log.setStyleSheet("font-size: 11px; color: #475569; font-weight: 500;")
        sb_layout.addWidget(self.lbl_log, 1)

        # Live Progress Bar for large comparisons
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setFixedWidth(140)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #cbd5e1;
                border-radius: 3px;
                background-color: #e2e8f0;
            }
            QProgressBar::chunk {
                background-color: #0969da;
                border-radius: 2px;
            }
        """)
        self.progress_bar.setVisible(False)
        sb_layout.addWidget(self.progress_bar)

        self.btn_cancel_comparison = QPushButton("Cancel")
        self.btn_cancel_comparison.setFixedHeight(22)
        self.btn_cancel_comparison.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                color: #b91c1c;
                font-size: 11px;
                font-weight: 600;
                border: 1px solid #fca5a5;
                border-radius: 3px;
                padding: 0 6px;
            }
            QPushButton:hover {
                background-color: #fecaca;
            }
        """)
        self.btn_cancel_comparison.clicked.connect(self._cancel_worker)
        self.btn_cancel_comparison.setVisible(False)
        sb_layout.addWidget(self.btn_cancel_comparison)

        self.lbl_stats = QLabel("0 files | 0 differences")
        self.lbl_stats.setStyleSheet("font-size: 11px; font-weight: 700; color: #0969da;")
        sb_layout.addWidget(self.lbl_stats)

        main_layout.addWidget(self.status_bar)

    def _style_tree(self, tree: QTreeWidget):
        tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #cbd5e1;
                background-color: #ffffff;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 3px 2px;
                border-bottom: 1px solid #f8fafc;
            }
            QTreeWidget::item:hover {
                background-color: #f1f5f9;
            }
            QTreeWidget::item:selected {
                background-color: #dbeafe;
                color: #0f172a;
            }
            QHeaderView::section {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f8fafc);
                color: #334155;
                font-weight: 600;
                padding: 6px;
                border: none;
                border-right: 1px solid #cbd5e1;
                border-bottom: 1px solid #cbd5e1;
            }
        """)

    def _style_gutter(self, tree: QTreeWidget):
        tree.setStyleSheet("""
            QTreeWidget {
                border-top: 1px solid #cbd5e1;
                border-bottom: 1px solid #cbd5e1;
                border-left: 1px solid #e2e8f0;
                border-right: 1px solid #e2e8f0;
                background-color: #f8fafc;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                font-weight: 700;
            }
            QTreeWidget::item {
                padding: 3px 0px;
                border-bottom: 1px solid #f1f5f9;
            }
            QHeaderView::section {
                background: #f1f5f9;
                color: #475569;
                font-weight: 700;
                font-size: 11px;
                text-align: center;
                padding: 6px 2px;
                border: none;
                border-bottom: 1px solid #cbd5e1;
            }
        """)

    def set_directories(self, left_path: str, right_path: str):
        """Sets directories and triggers comparison."""
        self.txt_left_path.setText(left_path)
        self.txt_right_path.setText(right_path)
        self.run_comparison()

    def run_comparison(self):
        """Executes recursive directory comparison on a background worker thread."""
        left = self.txt_left_path.text().strip()
        right = self.txt_right_path.text().strip()
        self.left_dir = left
        self.right_dir = right

        filter_expr = self.txt_filter_pattern.text().strip()
        mode_idx = self.combo_rules.currentIndex()
        mode_map = {0: "hash", 1: "timestamp", 2: "rules"}
        mode = mode_map.get(mode_idx, "hash")

        # Cancel any active running worker cleanly
        self._cancel_worker()

        self.tree_left.clear()
        self.tree_gutter.clear()
        self.tree_right.clear()
        self.banner_suggestion.setVisible(False)

        if not left or not right:
            self.lbl_log.setText("● Please select both Left and Right folders to compare.")
            self.lbl_stats.setText("0 files | 0 differences")
            return

        if not os.path.exists(left):
            self.lbl_log.setText(f"❌ Left folder not found: {left}")
            return
        if not os.path.exists(right):
            self.lbl_log.setText(f"❌ Right folder not found: {right}")
            return

        self.lbl_log.setText(f"● Comparing: {os.path.basename(left)} vs {os.path.basename(right)} ({mode.upper()})...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # indeterminate animation
        self.btn_cancel_comparison.setVisible(True)

        respect_git = self.chk_gitignore.isChecked()
        self._worker = FolderCompareWorker(left, right, mode=mode, filter_expr=filter_expr, respect_gitignore=respect_git)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)
        self._worker.start()

    def _open_sync_dialog(self):
        if not self._cached_items:
            QMessageBox.information(self, "No Items", "Please run a folder comparison first before synchronizing.")
            return
        dlg = FolderSyncDialog(self, self._cached_items, self.left_dir, self.right_dir)
        if dlg.exec():
            self.run_comparison()

    def _cancel_worker(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(400)
            self._worker = None
        self.progress_bar.setVisible(False)
        self.btn_cancel_comparison.setVisible(False)

    def _on_worker_progress(self, count: int, message: str):
        self.lbl_log.setText(f"● {message}")

    def _on_worker_failed(self, error_msg: str):
        self.progress_bar.setVisible(False)
        self.btn_cancel_comparison.setVisible(False)
        self.lbl_log.setText(f"❌ Error during folder comparison: {error_msg}")

    def _on_worker_finished(self, items: List[FolderCompareItem], left: str, right: str):
        self.progress_bar.setVisible(False)
        self.btn_cancel_comparison.setVisible(False)
        self._cached_items = items
        self._populate_dual_trees(items)
        self._check_smart_suggestion(left, right)

    def _check_smart_suggestion(self, left: str, right: str):
        """Checks if a subfolder on one side matches the root of the other side."""
        match = FolderCompareEngine.find_subfolder_match(left, right)
        if match:
            side, sub_path, sub_name = match
            if side == "left":
                other_name = os.path.basename(os.path.abspath(right))
                self.lbl_suggestion.setText(
                    f"💡 Subfolder Match: Left folder contains '{sub_name}', which corresponds directly to Right folder '{other_name}'."
                )
                self.btn_apply_suggestion.setText(f"Compare '{sub_name}' Directly ➜")
                self.btn_apply_suggestion.setProperty("target_side", "left")
                self.btn_apply_suggestion.setProperty("target_path", sub_path)
                self.banner_suggestion.setVisible(True)
            elif side == "right":
                other_name = os.path.basename(os.path.abspath(left))
                self.lbl_suggestion.setText(
                    f"💡 Subfolder Match: Right folder contains '{sub_name}', which corresponds directly to Left folder '{other_name}'."
                )
                self.btn_apply_suggestion.setText(f"Compare '{sub_name}' Directly ➜")
                self.btn_apply_suggestion.setProperty("target_side", "right")
                self.btn_apply_suggestion.setProperty("target_path", sub_path)
                self.banner_suggestion.setVisible(True)
        else:
            self.banner_suggestion.setVisible(False)

    def _on_apply_suggestion(self):
        side = self.btn_apply_suggestion.property("target_side")
        target_path = self.btn_apply_suggestion.property("target_path")
        if side == "left":
            self.txt_left_path.setText(target_path)
        elif side == "right":
            self.txt_right_path.setText(target_path)
        self.banner_suggestion.setVisible(False)
        self.run_comparison()

    def _populate_dual_trees(self, items: List[FolderCompareItem]):
        """Populates left, center gutter, and right trees with high-performance batch updates."""
        self.tree_left.setUpdatesEnabled(False)
        self.tree_gutter.setUpdatesEnabled(False)
        self.tree_right.setUpdatesEnabled(False)

        self.tree_left.blockSignals(True)
        self.tree_gutter.blockSignals(True)
        self.tree_right.blockSignals(True)

        total_files = 0
        diff_count = 0
        same_count = 0

        def add_items(parent_l, parent_g, parent_r, child_items):
            nonlocal total_files, diff_count, same_count
            for it in child_items:
                if not it.is_dir:
                    total_files += 1
                    if it.status == "SAME":
                        same_count += 1
                    else:
                        diff_count += 1

                # Left Node
                node_l = QTreeWidgetItem(parent_l)
                # Right Node
                node_r = QTreeWidgetItem(parent_r)
                # Center Gutter Node
                node_g = QTreeWidgetItem(parent_g)
                node_g.setTextAlignment(0, Qt.AlignCenter)

                # Store metadata
                node_l.setData(0, Qt.UserRole, it.left_path)
                node_l.setData(1, Qt.UserRole, it.right_path)
                node_l.setData(0, Qt.UserRole + 2, it.is_dir)
                node_l.setData(0, Qt.UserRole + 3, it.status)

                node_r.setData(0, Qt.UserRole, it.left_path)
                node_r.setData(1, Qt.UserRole, it.right_path)
                node_r.setData(0, Qt.UserRole + 2, it.is_dir)
                node_r.setData(0, Qt.UserRole + 3, it.status)

                node_g.setData(0, Qt.UserRole, it.left_path)
                node_g.setData(1, Qt.UserRole, it.right_path)
                node_g.setData(0, Qt.UserRole + 2, it.is_dir)
                node_g.setData(0, Qt.UserRole + 3, it.status)

                # Cross-link partners for O(1) sync
                node_l.setData(0, Qt.UserRole + 1, (node_g, node_r))
                node_r.setData(0, Qt.UserRole + 1, (node_l, node_g))
                node_g.setData(0, Qt.UserRole + 1, (node_l, node_r))

                # Display Left Node
                if it.left_path:
                    icon_prefix = "📁 " if it.is_dir else "   "
                    node_l.setText(0, f"{icon_prefix}{it.name}")
                    node_l.setText(1, it.left_size_str)
                    node_l.setText(2, it.left_mtime_str)
                else:
                    node_l.setText(0, "")
                    # Spacer node: suppress expand carets
                    node_l.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)

                # Display Right Node
                if it.right_path:
                    icon_prefix = "📁 " if it.is_dir else "   "
                    node_r.setText(0, f"{icon_prefix}{it.name}")
                    node_r.setText(1, it.right_size_str)
                    node_r.setText(2, it.right_mtime_str)
                else:
                    node_r.setText(0, "")
                    # Spacer node: suppress expand carets
                    node_r.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)

                # Gutter node indicator
                node_g.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)

                # Styling based on comparison status
                if it.status == "DIFF":
                    node_g.setText(0, "≠")
                    node_g.setForeground(0, QColor("#cf222e"))
                    font = QFont()
                    font.setBold(True)
                    if it.left_path:
                        node_l.setForeground(0, QColor("#cf222e"))
                        node_l.setFont(0, font)
                    if it.right_path:
                        node_r.setForeground(0, QColor("#cf222e"))
                        node_r.setFont(0, font)
                elif it.status == "LEFT_ONLY":
                    node_g.setText(0, "←")
                    node_g.setForeground(0, QColor("#0969da"))
                    node_l.setForeground(0, QColor("#0969da"))
                elif it.status == "RIGHT_ONLY":
                    node_g.setText(0, "→")
                    node_g.setForeground(0, QColor("#8250df"))
                    node_r.setForeground(0, QColor("#8250df"))
                else:
                    # SAME
                    if not it.is_dir:
                        node_g.setText(0, "=")
                        node_g.setForeground(0, QColor("#94a3b8"))
                    node_l.setForeground(0, QColor("#475569"))
                    node_r.setForeground(0, QColor("#475569"))

                # Recurse children
                if it.children:
                    add_items(node_l, node_g, node_r, it.children)

        add_items(self.tree_left, self.tree_gutter, self.tree_right, items)

        # Re-enable updates
        self.tree_left.setUpdatesEnabled(True)
        self.tree_gutter.setUpdatesEnabled(True)
        self.tree_right.setUpdatesEnabled(True)

        self.tree_left.blockSignals(False)
        self.tree_gutter.blockSignals(False)
        self.tree_right.blockSignals(False)

        # Expand small comparisons automatically; keep large comparisons collapsed so UI is instant
        if len(items) <= 50:
            self._is_syncing_expand = True
            for i in range(self.tree_left.topLevelItemCount()):
                it_l = self.tree_left.topLevelItem(i)
                it_g = self.tree_gutter.topLevelItem(i)
                it_r = self.tree_right.topLevelItem(i)
                if it_l and it_l.childCount() <= 80:
                    it_l.setExpanded(True)
                    if it_g: it_g.setExpanded(True)
                    if it_r: it_r.setExpanded(True)
            self._is_syncing_expand = False

        self._cached_stats_text = f"{total_files:,} files | {diff_count:,} differences | {same_count:,} identical"
        self.lbl_stats.setText(self._cached_stats_text)
        self.lbl_log.setText(f"● Comparison complete: {total_files:,} items evaluated.")

        # Re-apply filter if not "all" or if search query is active
        if self.current_filter_mode != "all" or (hasattr(self, 'txt_explorer_search') and self.txt_explorer_search.text().strip()):
            self._apply_view_filter()

    def _focus_search(self):
        """Focuses the Explorer search box and selects all text (Ctrl+F)."""
        if hasattr(self, 'txt_explorer_search'):
            self.txt_explorer_search.setFocus()
            self.txt_explorer_search.selectAll()

    def _clear_search(self):
        """Clears the search box and returns focus to the left tree (Esc)."""
        if hasattr(self, 'txt_explorer_search') and self.txt_explorer_search.text():
            self.txt_explorer_search.clear()
        self.tree_left.setFocus()

    def _on_search_text_changed(self, text: str):
        """Real-time instant tree filter as the user types in the search box."""
        self._apply_view_filter()

    def _set_filter_mode(self, mode: str):
        """Instant in-memory filtering: hides or shows tree rows without re-scanning disk."""
        self.current_filter_mode = mode
        self._apply_view_filter()

    def _apply_view_filter(self):
        """Applies current filter mode (all, diffs, same) and explorer search query directly to tree items."""
        mode = self.current_filter_mode
        search_query = self.txt_explorer_search.text().strip().lower() if hasattr(self, 'txt_explorer_search') else ""
        match_count = 0

        def filter_node(node_l: QTreeWidgetItem, node_g: QTreeWidgetItem, node_r: QTreeWidgetItem) -> bool:
            nonlocal match_count
            is_dir = node_l.data(0, Qt.UserRole + 2)
            status = node_l.data(0, Qt.UserRole + 3)
            name_l = (node_l.text(0) or "").lower()
            name_r = (node_r.text(0) or "").lower()

            any_child_visible = False
            for i in range(node_l.childCount()):
                c_l = node_l.child(i)
                c_g = node_g.child(i)
                c_r = node_r.child(i)
                if filter_node(c_l, c_g, c_r):
                    any_child_visible = True

            if mode == "all":
                mode_ok = True
            elif mode == "diffs":
                mode_ok = (status != "SAME") or any_child_visible
            elif mode == "same":
                mode_ok = (status == "SAME") or any_child_visible
            else:
                mode_ok = True

            if search_query:
                text_ok = (search_query in name_l) or (search_query in name_r)
                if is_dir:
                    visible = (mode_ok and any_child_visible) or (text_ok and mode_ok)
                    if visible and any_child_visible:
                        node_l.setExpanded(True)
                        node_g.setExpanded(True)
                        node_r.setExpanded(True)
                else:
                    visible = mode_ok and text_ok
                    if visible:
                        match_count += 1
            else:
                visible = mode_ok

            node_l.setHidden(not visible)
            node_g.setHidden(not visible)
            node_r.setHidden(not visible)
            return visible

        self.tree_left.setUpdatesEnabled(False)
        self.tree_gutter.setUpdatesEnabled(False)
        self.tree_right.setUpdatesEnabled(False)

        for i in range(self.tree_left.topLevelItemCount()):
            filter_node(
                self.tree_left.topLevelItem(i),
                self.tree_gutter.topLevelItem(i),
                self.tree_right.topLevelItem(i)
            )

        self.tree_left.setUpdatesEnabled(True)
        self.tree_gutter.setUpdatesEnabled(True)
        self.tree_right.setUpdatesEnabled(True)

        if hasattr(self, 'lbl_stats'):
            if search_query:
                total_items = len(self._cached_items) if self._cached_items else self.tree_left.topLevelItemCount()
                self.lbl_stats.setText(f"🔍 {match_count} matched | {total_items:,} items")
            elif hasattr(self, '_cached_stats_text') and self._cached_stats_text:
                self.lbl_stats.setText(self._cached_stats_text)

    def _expand_all(self):
        self._is_syncing_expand = True
        self.tree_left.setUpdatesEnabled(False)
        self.tree_gutter.setUpdatesEnabled(False)
        self.tree_right.setUpdatesEnabled(False)

        self.tree_left.expandAll()
        self.tree_gutter.expandAll()
        self.tree_right.expandAll()

        self.tree_left.setUpdatesEnabled(True)
        self.tree_gutter.setUpdatesEnabled(True)
        self.tree_right.setUpdatesEnabled(True)
        self._is_syncing_expand = False

    def _collapse_all(self):
        self._is_syncing_expand = True
        self.tree_left.setUpdatesEnabled(False)
        self.tree_gutter.setUpdatesEnabled(False)
        self.tree_right.setUpdatesEnabled(False)

        self.tree_left.collapseAll()
        self.tree_gutter.collapseAll()
        self.tree_right.collapseAll()

        self.tree_left.setUpdatesEnabled(True)
        self.tree_gutter.setUpdatesEnabled(True)
        self.tree_right.setUpdatesEnabled(True)
        self._is_syncing_expand = False

    def _swap_folders(self):
        l = self.txt_left_path.text()
        r = self.txt_right_path.text()
        self.txt_left_path.setText(r)
        self.txt_right_path.setText(l)
        self.run_comparison()

    def _browse_left(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Left Folder")
        if folder:
            self.txt_left_path.setText(folder)
            self.run_comparison()

    def _browse_right(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Right Folder")
        if folder:
            self.txt_right_path.setText(folder)
            self.run_comparison()

    def _go_up(self, edit: QLineEdit):
        cur = edit.text().strip()
        if cur and os.path.exists(cur):
            parent = os.path.dirname(os.path.abspath(cur))
            if parent != cur:
                edit.setText(parent)
                self.run_comparison()

    # Synchronized Scrolling
    def _sync_scroll(self, source_scrollbar):
        if self._is_syncing_scroll:
            return
        self._is_syncing_scroll = True
        val = source_scrollbar.value()
        for tree in (self.tree_left, self.tree_gutter, self.tree_right):
            sb = tree.verticalScrollBar()
            if sb != source_scrollbar and sb.value() != val:
                sb.setValue(val)
        self._is_syncing_scroll = False

    # Synchronized Node Expansion in O(1) time
    def _sync_item_expanded(self, item: QTreeWidgetItem):
        if self._is_syncing_expand:
            return
        self._is_syncing_expand = True
        try:
            partners = item.data(0, Qt.UserRole + 1)
            if partners:
                for p in partners:
                    if p and not p.isExpanded():
                        p.setExpanded(True)
        finally:
            self._is_syncing_expand = False

    def _sync_item_collapsed(self, item: QTreeWidgetItem):
        if self._is_syncing_expand:
            return
        self._is_syncing_expand = True
        try:
            partners = item.data(0, Qt.UserRole + 1)
            if partners:
                for p in partners:
                    if p and p.isExpanded():
                        p.setExpanded(False)
        finally:
            self._is_syncing_expand = False

    def _sync_current_item(self, current: QTreeWidgetItem, previous: QTreeWidgetItem):
        if self._is_syncing_current:
            return
        self._is_syncing_current = True
        try:
            if current:
                partners = current.data(0, Qt.UserRole + 1)
                if partners:
                    for p in partners:
                        if p and p.treeWidget():
                            p.treeWidget().setCurrentItem(p)
        finally:
            self._is_syncing_current = False

    def _on_item_double_clicked(self, item: QTreeWidgetItem, col: int):
        is_dir = item.data(0, Qt.UserRole + 2)
        if is_dir:
            # Toggle expansion for folder
            item.setExpanded(not item.isExpanded())
            return

        l_path = item.data(0, Qt.UserRole)
        r_path = item.data(1, Qt.UserRole)
        if (l_path and os.path.isfile(l_path)) or (r_path and os.path.isfile(r_path)):
            self.openInDiffRequested.emit(l_path or "", r_path or "")

    def _show_tree_context_menu(self, tree: QTreeWidget, pos, side: str):
        item = tree.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        is_dir = item.data(0, Qt.UserRole + 2)
        l_path = item.data(0, Qt.UserRole)
        r_path = item.data(1, Qt.UserRole)
        target_path = l_path if side == "left" else r_path

        if is_dir and target_path and os.path.isdir(target_path):
            act_base = menu.addAction(f"📂 Set as {side.capitalize()} Base Folder")
            act_base.triggered.connect(lambda: self._set_as_base(side, target_path))

            act_exp = menu.addAction("📁 Open in File Explorer")
            act_exp.triggered.connect(lambda: self._open_in_explorer(target_path))

            act_copy = menu.addAction("📋 Copy Folder Path")
            act_copy.triggered.connect(lambda: self._copy_path(target_path))
        elif target_path and os.path.isfile(target_path):
            act_diff = menu.addAction("🔍 Open in Diff Studio")
            act_diff.triggered.connect(lambda: self.openInDiffRequested.emit(l_path or "", r_path or ""))

            act_exp = menu.addAction("📁 Show in File Explorer")
            act_exp.triggered.connect(lambda: self._open_in_explorer(os.path.dirname(target_path)))

            act_copy = menu.addAction("📋 Copy File Path")
            act_copy.triggered.connect(lambda: self._copy_path(target_path))

        menu.exec_(tree.viewport().mapToGlobal(pos))

    def _set_as_base(self, side: str, path: str):
        if side == "left":
            self.txt_left_path.setText(path)
        else:
            self.txt_right_path.setText(path)
        self.run_comparison()

    def _open_in_explorer(self, path: str):
        if path and os.path.exists(path):
            if os.path.isdir(path):
                os.startfile(path)
            else:
                subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')

    def _copy_path(self, path: str):
        QApplication.clipboard().setText(path)

    def _load_initial_demo(self):
        """Loads a realistic demo directory comparison matching initial studio."""
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        core_dir = os.path.join(app_dir, "core")
        ui_dir = os.path.join(app_dir, "ui")

        if os.path.exists(core_dir) and os.path.exists(ui_dir):
            self.txt_left_path.setText(core_dir)
            self.txt_right_path.setText(ui_dir)
            self.run_comparison()
