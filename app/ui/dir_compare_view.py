"""
diff_and_compare_tool Dual-Tree Folder & Virtual Archive Comparison Studio (White / Light Theme)
Features:
- Top Ribbon: Home, View Filters (* All, ≠ Diffs, = Same, Orphans), Rules (SHA-256, BLAKE3, Timestamp, Rules-Based),
  Prev/Next Diff navigation, Expand/Collapse, Swap, Refresh, Sync Hub, .gitignore toggle, Wildcard Filters.
- Smart Subfolder Matcher Banner.
- Side-by-Side Synchronized Dual Folder Trees with Drag & Drop and inline Copy/Delete context actions.
- Virtual Archive (.zip/.jar/.tar) transparent comparison & file opening.
"""

import os
import shutil
import subprocess
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLineEdit, QComboBox, QLabel, QFileDialog, QHeaderView,
    QSplitter, QFrame, QButtonGroup, QMessageBox, QMenu,
    QProgressBar, QApplication, QCheckBox, QStyledItemDelegate, QStyle
)
from PySide6.QtCore import Qt, Signal, QThread, QRect, QSize
from PySide6.QtGui import QColor, QFont, QBrush, QPainter, QKeySequence, QShortcut, QDragEnterEvent, QDropEvent

from app.ui.styles.icons import get_line_icon
from app.core.folder_compare_engine import FolderCompareEngine, FolderCompareItem
from app.core.archive_vfs import ArchiveVFS
from app.core.file_io import is_vfs_path, read_vfs_or_file_bytes
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


class DropTreeWidget(QTreeWidget):
    """QTreeWidget accepting folder or archive drops to load directly into Left or Right side."""
    pathDropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
            if urls and (os.path.isdir(urls[0]) or ArchiveVFS.is_archive(urls[0])):
                event.acceptProposedAction()
                return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            urls = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
            if urls and (os.path.isdir(urls[0]) or ArchiveVFS.is_archive(urls[0])):
                self.pathDropped.emit(urls[0])
                event.acceptProposedAction()
                return
        super().dropEvent(event)


class GutterItemDelegate(QStyledItemDelegate):
    """Renders status symbols (≠, ←, →, =) perfectly centered in the gutter column."""

    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter: QPainter, option, index):
        painter.save()
        viewport_width = option.widget.viewport().width() if option.widget else option.rect.width()
        row_rect = QRect(0, option.rect.y(), viewport_width, option.rect.height())

        if option.state & QStyle.State_Selected:
            painter.fillRect(row_rect, QColor("#dbeafe"))
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(row_rect, QColor("#f1f5f9"))
        else:
            painter.fillRect(row_rect, QColor("#f8fafc"))

        painter.setPen(QColor("#f1f5f9"))
        painter.drawLine(0, row_rect.bottom(), viewport_width, row_rect.bottom())

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
            painter.drawText(row_rect, Qt.AlignCenter, str(text))

        painter.restore()

    def sizeHint(self, option, index):
        sh = super().sizeHint(option, index)
        return QSize(sh.width(), max(24, sh.height()))


class DirCompareView(QWidget):
    """Signature diff_and_compare_tool Dual-Tree Folder Comparison Studio."""

    openInDiffRequested = Signal(str, str)          # (left_file_path, right_file_path)
    homeRequested = Signal()                        # Switch to Home screen

    def __init__(self, parent=None, initial_mode: str = "folder"):
        super().__init__(parent)
        self.left_dir: str = ""
        self.right_dir: str = ""
        self.initial_mode = initial_mode
        self.current_filter_mode = "diffs" if initial_mode in ("folder_sync", "folder_merge") else "all"
        self._is_syncing_scroll = False
        self._is_syncing_expand = False
        self._is_syncing_current = False
        self._worker: Optional[FolderCompareWorker] = None
        self._cached_items: List[FolderCompareItem] = []
        self._diff_nav_index = -1

        self.setup_ui()
        if self.current_filter_mode == "diffs":
            self.btn_filter_diffs.setChecked(True)
        self._load_initial_demo()

    def closeEvent(self, event):
        self._cancel_worker()
        super().closeEvent(event)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Ribbon
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

        self.btn_home = QPushButton(" Home")
        self.btn_home.setIcon(get_line_icon("sparkles", "#0969da"))
        self.btn_home.setFixedHeight(30)
        self.btn_home.clicked.connect(self.homeRequested.emit)
        r_layout.addWidget(self.btn_home)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet("color: #cbd5e1;")
        r_layout.addWidget(sep1)

        # View Filter Buttons: * All, ≠ Diffs, = Same, Orphans
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

        self.btn_filter_orphans = QPushButton(" Orphans")
        self.btn_filter_orphans.setCheckable(True)
        self.btn_filter_orphans.setFixedHeight(30)
        self.btn_filter_orphans.setToolTip("Show only files present on one side (Left Only / Right Only)")
        self.btn_filter_orphans.clicked.connect(lambda: self._set_filter_mode("orphans"))
        self.filter_group.addButton(self.btn_filter_orphans)
        r_layout.addWidget(self.btn_filter_orphans)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet("color: #cbd5e1;")
        r_layout.addWidget(sep2)

        # Comparison Rules including BLAKE3
        self.combo_rules = QComboBox()
        self.combo_rules.setFixedHeight(30)
        self.combo_rules.addItems([
            "Byte-by-Byte (SHA-256)",
            "BLAKE3 (Ultra-Fast Hash)",
            "Size & Timestamp Match",
            "Rules-Based (Ignore Whitespace)"
        ])
        self.combo_rules.currentIndexChanged.connect(self.run_comparison)
        r_layout.addWidget(self.combo_rules)

        # Prev / Next Diff File Navigation
        self.btn_prev_diff = QPushButton()
        self.btn_prev_diff.setIcon(get_line_icon("chevron-left", "#1e293b"))
        self.btn_prev_diff.setToolTip("Previous Different File")
        self.btn_prev_diff.setFixedSize(30, 30)
        self.btn_prev_diff.clicked.connect(self._jump_prev_diff)
        r_layout.addWidget(self.btn_prev_diff)

        self.btn_next_diff = QPushButton()
        self.btn_next_diff.setIcon(get_line_icon("chevron-right", "#1e293b"))
        self.btn_next_diff.setToolTip("Next Different File")
        self.btn_next_diff.setFixedSize(30, 30)
        self.btn_next_diff.clicked.connect(self._jump_next_diff)
        r_layout.addWidget(self.btn_next_diff)

        # Expand / Collapse
        self.btn_expand = QPushButton()
        self.btn_expand.setIcon(get_line_icon("arrow-down", "#1e293b"))
        self.btn_expand.setToolTip("Expand All Folders")
        self.btn_expand.setFixedSize(30, 30)
        self.btn_expand.clicked.connect(self._expand_all)
        r_layout.addWidget(self.btn_expand)

        self.btn_collapse = QPushButton()
        self.btn_collapse.setIcon(get_line_icon("arrow-up", "#1e293b"))
        self.btn_collapse.setToolTip("Collapse All Folders")
        self.btn_collapse.setFixedSize(30, 30)
        self.btn_collapse.clicked.connect(self._collapse_all)
        r_layout.addWidget(self.btn_collapse)

        self.btn_swap = QPushButton(" Swap")
        self.btn_swap.setIcon(get_line_icon("swap", "#1e293b"))
        self.btn_swap.setFixedHeight(30)
        self.btn_swap.clicked.connect(self._swap_folders)
        r_layout.addWidget(self.btn_swap)

        self.btn_refresh = QPushButton(" Refresh")
        self.btn_refresh.setIcon(get_line_icon("refresh", "#1e293b"))
        self.btn_refresh.setFixedHeight(30)
        self.btn_refresh.clicked.connect(self.run_comparison)
        r_layout.addWidget(self.btn_refresh)

        self.btn_sync = QPushButton(" Sync Hub...")
        self.btn_sync.setIcon(get_line_icon("folder-sync", "#0969da"))
        self.btn_sync.setFixedHeight(30)
        self.btn_sync.setToolTip("Open interactive folder synchronization hub (Mirror, Bi-directional, Update)")
        self.btn_sync.clicked.connect(self._open_sync_dialog)
        r_layout.addWidget(self.btn_sync)

        r_layout.addSpacing(4)

        self.chk_gitignore = QCheckBox(".gitignore")
        self.chk_gitignore.setChecked(True)
        self.chk_gitignore.setToolTip("Respect root .gitignore, .hgignore, and common exclusions (node_modules, __pycache__, .venv, .git)")
        self.chk_gitignore.toggled.connect(self.run_comparison)
        r_layout.addWidget(self.chk_gitignore)

        lbl_flt = QLabel("Filter:")
        lbl_flt.setStyleSheet("font-weight: 600; color: #475569; background: transparent; border: none;")
        r_layout.addWidget(lbl_flt)

        self.txt_filter_pattern = QLineEdit()
        self.txt_filter_pattern.setPlaceholderText("*.py; -*.tmp")
        self.txt_filter_pattern.setFixedHeight(30)
        self.txt_filter_pattern.setFixedWidth(120)
        self.txt_filter_pattern.returnPressed.connect(self.run_comparison)
        r_layout.addWidget(self.txt_filter_pattern)

        r_layout.addStretch()
        main_layout.addWidget(ribbon)

        # 2. Dual Path Selection Header Bar
        path_bar = QFrame()
        path_bar.setFixedHeight(46)
        path_bar.setStyleSheet("background-color: #f8fafc; border-bottom: 1px solid #cbd5e1;")
        pb_layout = QHBoxLayout(path_bar)
        pb_layout.setContentsMargins(10, 6, 10, 6)
        pb_layout.setSpacing(10)

        lbl_l = QLabel("Left:")
        lbl_l.setStyleSheet("font-weight: 700; color: #0969da; background: transparent; border: none;")
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
        self.btn_up_left.setFixedSize(30, 30)
        self.btn_up_left.clicked.connect(lambda: self._go_up(self.txt_left_path))
        pb_layout.addWidget(self.btn_up_left)

        sep_path = QFrame()
        sep_path.setFrameShape(QFrame.VLine)
        sep_path.setStyleSheet("color: #cbd5e1;")
        pb_layout.addWidget(sep_path)

        lbl_r = QLabel("Right:")
        lbl_r.setStyleSheet("font-weight: 700; color: #16a34a; background: transparent; border: none;")
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
        self.btn_up_right.setFixedSize(30, 30)
        self.btn_up_right.clicked.connect(lambda: self._go_up(self.txt_right_path))
        pb_layout.addWidget(self.btn_up_right)

        sep_search = QFrame()
        sep_search.setFrameShape(QFrame.VLine)
        sep_search.setStyleSheet("color: #cbd5e1;")
        pb_layout.addWidget(sep_search)

        self.txt_explorer_search = QLineEdit()
        self.txt_explorer_search.setPlaceholderText("🔍 Search files & folders... (Ctrl+F)")
        self.txt_explorer_search.setFixedHeight(30)
        self.txt_explorer_search.setFixedWidth(230)
        self.txt_explorer_search.setClearButtonEnabled(True)
        self.txt_explorer_search.setToolTip("Instant interactive filter for folder trees (Ctrl+F)")
        self.txt_explorer_search.textChanged.connect(self._on_search_text_changed)
        pb_layout.addWidget(self.txt_explorer_search)

        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)
        QShortcut(QKeySequence("Escape"), self, self._clear_search)

        main_layout.addWidget(path_bar)

        # 3. Smart Subfolder Matcher Banner
        self.banner_suggestion = QFrame()
        self.banner_suggestion.setFixedHeight(40)
        self.banner_suggestion.setStyleSheet("QFrame { background-color: #eff6ff; border-bottom: 1.5px solid #93c5fd; padding: 4px 12px; }")
        bs_layout = QHBoxLayout(self.banner_suggestion)
        bs_layout.setContentsMargins(12, 0, 12, 0)
        bs_layout.setSpacing(10)

        self.lbl_suggestion = QLabel()
        self.lbl_suggestion.setStyleSheet("font-size: 12px; font-weight: 600; color: #1e40af; border: none; background: transparent;")
        bs_layout.addWidget(self.lbl_suggestion, 1)

        self.btn_apply_suggestion = QPushButton("Compare Directly ➜")
        self.btn_apply_suggestion.setFixedHeight(26)
        self.btn_apply_suggestion.setObjectName("PrimaryButton")
        self.btn_apply_suggestion.clicked.connect(self._on_apply_suggestion)
        bs_layout.addWidget(self.btn_apply_suggestion)

        btn_dismiss = QPushButton("✕ Dismiss")
        btn_dismiss.setFixedHeight(26)
        btn_dismiss.clicked.connect(lambda: self.banner_suggestion.setVisible(False))
        bs_layout.addWidget(btn_dismiss)

        self.banner_suggestion.setVisible(False)
        main_layout.addWidget(self.banner_suggestion)

        # 4. Synchronized Dual Trees with Center Difference Column
        self.trees_splitter = QSplitter(Qt.Horizontal)
        self.trees_splitter.setStyleSheet("QSplitter::handle { background-color: #cbd5e1; width: 4px; }")

        self.tree_left = DropTreeWidget()
        self.tree_left.setHeaderLabels(["Name", "Size", "Modified"])
        self.tree_left.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree_left.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree_left.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree_left.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_left.customContextMenuRequested.connect(lambda pos: self._show_tree_context_menu(self.tree_left, pos, "left"))
        self.tree_left.pathDropped.connect(lambda p: self._set_as_base("left", p))
        self._style_tree(self.tree_left)

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

        self.tree_right = DropTreeWidget()
        self.tree_right.setHeaderLabels(["Name", "Size", "Modified"])
        self.tree_right.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree_right.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree_right.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree_right.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_right.customContextMenuRequested.connect(lambda pos: self._show_tree_context_menu(self.tree_right, pos, "right"))
        self.tree_right.pathDropped.connect(lambda p: self._set_as_base("right", p))
        self._style_tree(self.tree_right)

        self.tree_left.verticalScrollBar().valueChanged.connect(lambda: self._sync_scroll(self.tree_left.verticalScrollBar()))
        self.tree_right.verticalScrollBar().valueChanged.connect(lambda: self._sync_scroll(self.tree_right.verticalScrollBar()))
        self.tree_gutter.verticalScrollBar().valueChanged.connect(lambda: self._sync_scroll(self.tree_gutter.verticalScrollBar()))

        self.tree_left.currentItemChanged.connect(self._sync_current_item)
        self.tree_gutter.currentItemChanged.connect(self._sync_current_item)
        self.tree_right.currentItemChanged.connect(self._sync_current_item)

        self.tree_left.itemExpanded.connect(self._sync_item_expanded)
        self.tree_left.itemCollapsed.connect(self._sync_item_collapsed)
        self.tree_right.itemExpanded.connect(self._sync_item_expanded)
        self.tree_right.itemCollapsed.connect(self._sync_item_collapsed)
        self.tree_gutter.itemExpanded.connect(self._sync_item_expanded)
        self.tree_gutter.itemCollapsed.connect(self._sync_item_collapsed)

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

        # 5. Bottom Status & Activity Log Bar
        self.status_bar = QFrame()
        self.status_bar.setFixedHeight(30)
        self.status_bar.setStyleSheet("QFrame { background-color: #f1f5f9; border-top: 1px solid #cbd5e1; padding: 2px 8px; }")
        sb_layout = QHBoxLayout(self.status_bar)
        sb_layout.setContentsMargins(8, 0, 8, 0)
        sb_layout.setSpacing(12)

        self.lbl_log = QLabel("● Ready")
        self.lbl_log.setStyleSheet("font-size: 11px; color: #475569; font-weight: 500; border: none; background: transparent;")
        sb_layout.addWidget(self.lbl_log, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setFixedWidth(140)
        self.progress_bar.setTextVisible(False)
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
            QPushButton:hover { background-color: #fecaca; }
        """)
        self.btn_cancel_comparison.clicked.connect(self._cancel_worker)
        self.btn_cancel_comparison.setVisible(False)
        sb_layout.addWidget(self.btn_cancel_comparison)

        self.lbl_stats = QLabel("0 files | 0 differences")
        self.lbl_stats.setStyleSheet("font-size: 11px; font-weight: 700; color: #0969da; border: none; background: transparent;")
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
            QTreeWidget::item { padding: 3px 2px; border-bottom: 1px solid #f8fafc; }
            QTreeWidget::item:hover { background-color: #f1f5f9; }
            QTreeWidget::item:selected { background-color: #dbeafe; color: #0f172a; }
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
            QTreeWidget::item { padding: 3px 0px; border-bottom: 1px solid #f1f5f9; }
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
        self.txt_left_path.setText(left_path)
        self.txt_right_path.setText(right_path)
        self.run_comparison()

    def run_comparison(self):
        left = self.txt_left_path.text().strip()
        right = self.txt_right_path.text().strip()
        self.left_dir = left
        self.right_dir = right

        filter_expr = self.txt_filter_pattern.text().strip()
        mode_idx = self.combo_rules.currentIndex()
        mode_map = {0: "hash", 1: "blake3", 2: "timestamp", 3: "rules"}
        mode = mode_map.get(mode_idx, "hash")

        self._cancel_worker()

        self.tree_left.clear()
        self.tree_gutter.clear()
        self.tree_right.clear()
        self.banner_suggestion.setVisible(False)
        self._diff_nav_index = -1

        if not left or not right:
            self.lbl_log.setText("● Please select both Left and Right folders or archives to compare.")
            self.lbl_stats.setText("0 files | 0 differences")
            return

        if not os.path.exists(left):
            self.lbl_log.setText(f"Left folder not found: {left}")
            return
        if not os.path.exists(right):
            self.lbl_log.setText(f"Right folder not found: {right}")
            return

        self.lbl_log.setText(f"● Comparing: {os.path.basename(left)} vs {os.path.basename(right)} ({mode.upper()})...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
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
            self._worker.wait(800)
        self._worker = None
        self.progress_bar.setVisible(False)
        self.btn_cancel_comparison.setVisible(False)

    def _on_worker_progress(self, count: int, message: str):
        self.lbl_log.setText(f"● {message}")

    def _on_worker_failed(self, error_msg: str):
        self.progress_bar.setVisible(False)
        self.btn_cancel_comparison.setVisible(False)
        self.lbl_log.setText(f"Error during folder comparison: {error_msg}")

    def _on_worker_finished(self, items: List[FolderCompareItem], left: str, right: str):
        self.progress_bar.setVisible(False)
        self.btn_cancel_comparison.setVisible(False)
        self._cached_items = items
        self._populate_dual_trees(items)
        self._check_smart_suggestion(left, right)

    def _check_smart_suggestion(self, left: str, right: str):
        match = FolderCompareEngine.find_subfolder_match(left, right)
        if match:
            side, sub_path, sub_name = match
            if side == "left":
                other_name = os.path.basename(os.path.abspath(right))
                self.lbl_suggestion.setText(
                    f"Subfolder Match: Left folder contains '{sub_name}', matching Right folder '{other_name}'."
                )
                self.btn_apply_suggestion.setText(f"Compare '{sub_name}' Directly ➜")
                self.btn_apply_suggestion.setProperty("target_side", "left")
                self.btn_apply_suggestion.setProperty("target_path", sub_path)
                self.banner_suggestion.setVisible(True)
            elif side == "right":
                other_name = os.path.basename(os.path.abspath(left))
                self.lbl_suggestion.setText(
                    f"Subfolder Match: Right folder contains '{sub_name}', matching Left folder '{other_name}'."
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

                node_l = QTreeWidgetItem(parent_l)
                node_r = QTreeWidgetItem(parent_r)
                node_g = QTreeWidgetItem(parent_g)
                node_g.setTextAlignment(0, Qt.AlignCenter)

                for nd in (node_l, node_r, node_g):
                    nd.setData(0, Qt.UserRole, it.left_path)
                    nd.setData(1, Qt.UserRole, it.right_path)
                    nd.setData(0, Qt.UserRole + 2, it.is_dir)
                    nd.setData(0, Qt.UserRole + 3, it.status)
                    nd.setData(0, Qt.UserRole + 4, it.rel_path)

                node_l.setData(0, Qt.UserRole + 1, (node_g, node_r))
                node_r.setData(0, Qt.UserRole + 1, (node_l, node_g))
                node_g.setData(0, Qt.UserRole + 1, (node_l, node_r))

                if it.left_path:
                    icon_prefix = "📁 " if it.is_dir else "   "
                    node_l.setText(0, f"{icon_prefix}{it.name}")
                    node_l.setText(1, it.left_size_str)
                    node_l.setText(2, it.left_mtime_str)
                else:
                    node_l.setText(0, "")
                    node_l.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)

                if it.right_path:
                    icon_prefix = "📁 " if it.is_dir else "   "
                    node_r.setText(0, f"{icon_prefix}{it.name}")
                    node_r.setText(1, it.right_size_str)
                    node_r.setText(2, it.right_mtime_str)
                else:
                    node_r.setText(0, "")
                    node_r.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)

                node_g.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)

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
                    if not it.is_dir:
                        node_g.setText(0, "=")
                        node_g.setForeground(0, QColor("#94a3b8"))
                    node_l.setForeground(0, QColor("#475569"))
                    node_r.setForeground(0, QColor("#475569"))

                if it.children:
                    add_items(node_l, node_g, node_r, it.children)

        add_items(self.tree_left, self.tree_gutter, self.tree_right, items)

        self.tree_left.setUpdatesEnabled(True)
        self.tree_gutter.setUpdatesEnabled(True)
        self.tree_right.setUpdatesEnabled(True)

        self.tree_left.blockSignals(False)
        self.tree_gutter.blockSignals(False)
        self.tree_right.blockSignals(False)

        if len(items) <= 50:
            self._is_syncing_expand = True
            for i in range(self.tree_left.topLevelItemCount()):
                it_l = self.tree_left.topLevelItem(i)
                it_g = self.tree_gutter.topLevelItem(i)
                it_r = self.tree_right.topLevelItem(i)
                if it_l and it_l.childCount() <= 80:
                    it_l.setExpanded(True)
                    if it_g:
                        it_g.setExpanded(True)
                    if it_r:
                        it_r.setExpanded(True)
            self._is_syncing_expand = False

        self._cached_stats_text = f"{total_files:,} files | {diff_count:,} differences | {same_count:,} identical"
        self.lbl_stats.setText(self._cached_stats_text)
        self.lbl_log.setText(f"● Comparison complete: {total_files:,} items evaluated.")

        if self.current_filter_mode != "all" or (hasattr(self, 'txt_explorer_search') and self.txt_explorer_search.text().strip()):
            self._apply_view_filter()

    def _collect_diff_file_items(self) -> List[QTreeWidgetItem]:
        results: List[QTreeWidgetItem] = []

        def walk(node: QTreeWidgetItem):
            if node.isHidden():
                return
            is_dir = node.data(0, Qt.UserRole + 2)
            status = node.data(0, Qt.UserRole + 3)
            if not is_dir and status != "SAME":
                results.append(node)
            for i in range(node.childCount()):
                walk(node.child(i))

        for i in range(self.tree_left.topLevelItemCount()):
            walk(self.tree_left.topLevelItem(i))
        return results

    def _jump_next_diff(self):
        items = self._collect_diff_file_items()
        if not items:
            return
        self._diff_nav_index = (self._diff_nav_index + 1) % len(items)
        self._select_and_reveal(items[self._diff_nav_index])

    def _jump_prev_diff(self):
        items = self._collect_diff_file_items()
        if not items:
            return
        self._diff_nav_index = (self._diff_nav_index - 1 + len(items)) % len(items)
        self._select_and_reveal(items[self._diff_nav_index])

    def _select_and_reveal(self, item: QTreeWidgetItem):
        parent = item.parent()
        while parent:
            parent.setExpanded(True)
            parent = parent.parent()
        self.tree_left.setCurrentItem(item)
        self.tree_left.scrollToItem(item)

    def _focus_search(self):
        if hasattr(self, 'txt_explorer_search'):
            self.txt_explorer_search.setFocus()
            self.txt_explorer_search.selectAll()

    def _clear_search(self):
        if hasattr(self, 'txt_explorer_search') and self.txt_explorer_search.text():
            self.txt_explorer_search.clear()
        self.tree_left.setFocus()

    def _on_search_text_changed(self, text: str):
        self._apply_view_filter()

    def _set_filter_mode(self, mode: str):
        self.current_filter_mode = mode
        self._apply_view_filter()

    def _apply_view_filter(self):
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
                if filter_node(node_l.child(i), node_g.child(i), node_r.child(i)):
                    any_child_visible = True

            if mode == "all":
                mode_ok = True
            elif mode == "diffs":
                mode_ok = (status != "SAME") or any_child_visible
            elif mode == "same":
                mode_ok = (status == "SAME") or any_child_visible
            elif mode == "orphans":
                mode_ok = (status in ("LEFT_ONLY", "RIGHT_ONLY")) or any_child_visible
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
                self.lbl_stats.setText(f"{match_count} matched | {total_items:,} items")
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
            item.setExpanded(not item.isExpanded())
            return

        l_path = item.data(0, Qt.UserRole)
        r_path = item.data(1, Qt.UserRole)
        l_ok = bool(l_path and (is_vfs_path(l_path) or os.path.isfile(l_path)))
        r_ok = bool(r_path and (is_vfs_path(r_path) or os.path.isfile(r_path)))
        if l_ok or r_ok:
            self.openInDiffRequested.emit(l_path or "", r_path or "")

    def _copy_single_file(self, src_path: str, rel_path: str, to_side: str):
        dest_root = self.right_dir if to_side == "right" else self.left_dir
        if not dest_root or not os.path.isdir(dest_root):
            QMessageBox.warning(self, "Copy Blocked", f"Destination '{dest_root}' is not a writable directory.")
            return
        dest_path = os.path.join(dest_root, rel_path.replace("/", os.sep))
        try:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            if is_vfs_path(src_path):
                data = read_vfs_or_file_bytes(src_path)
                with open(dest_path, "wb") as f:
                    f.write(data)
            else:
                shutil.copy2(src_path, dest_path)
            self.run_comparison()
        except Exception as e:
            QMessageBox.critical(self, "Copy Failed", str(e))

    def _delete_single_item(self, target_path: str, is_dir: bool):
        if is_vfs_path(target_path):
            QMessageBox.warning(self, "Read-Only Archive", "Cannot delete entries inside a compressed archive.")
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete '{os.path.basename(target_path)}' from disk?\n\n{target_path}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        try:
            if is_dir:
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)
            self.run_comparison()
        except Exception as e:
            QMessageBox.critical(self, "Delete Failed", str(e))

    def _show_tree_context_menu(self, tree: QTreeWidget, pos, side: str):
        item = tree.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        is_dir = item.data(0, Qt.UserRole + 2)
        l_path = item.data(0, Qt.UserRole)
        r_path = item.data(1, Qt.UserRole)
        rel_path = item.data(0, Qt.UserRole + 4) or ""
        target_path = l_path if side == "left" else r_path

        if is_dir and target_path and os.path.isdir(target_path):
            act_base = menu.addAction(f"Set as {side.capitalize()} Base Folder")
            act_base.triggered.connect(lambda: self._set_as_base(side, target_path))

            act_exp = menu.addAction("Open in File Explorer")
            act_exp.triggered.connect(lambda: self._open_in_explorer(target_path))

            act_copy = menu.addAction("Copy Folder Path")
            act_copy.triggered.connect(lambda: self._copy_path(target_path))
        elif target_path and (is_vfs_path(target_path) or os.path.isfile(target_path)):
            act_diff = menu.addAction("Open in Diff Studio")
            act_diff.triggered.connect(lambda: self.openInDiffRequested.emit(l_path or "", r_path or ""))

            if side == "left" and l_path and os.path.isdir(self.right_dir or ""):
                act_c2r = menu.addAction("Copy Left ➜ Right")
                act_c2r.triggered.connect(lambda: self._copy_single_file(l_path, rel_path, "right"))
            elif side == "right" and r_path and os.path.isdir(self.left_dir or ""):
                act_c2l = menu.addAction("Copy Right ➜ Left")
                act_c2l.triggered.connect(lambda: self._copy_single_file(r_path, rel_path, "left"))

            if not is_vfs_path(target_path):
                menu.addSeparator()
                act_exp = menu.addAction("Show in File Explorer")
                act_exp.triggered.connect(lambda: self._open_in_explorer(os.path.dirname(target_path)))

                act_del = menu.addAction(f"Delete from {side.capitalize()}...")
                act_del.triggered.connect(lambda: self._delete_single_item(target_path, False))

            act_copy = menu.addAction("Copy File Path")
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
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        core_dir = os.path.join(app_dir, "core")
        ui_dir = os.path.join(app_dir, "ui")

        if os.path.exists(core_dir) and os.path.exists(ui_dir):
            self.txt_left_path.setText(core_dir)
            self.txt_right_path.setText(ui_dir)
            self.run_comparison()
