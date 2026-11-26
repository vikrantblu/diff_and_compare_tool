"""
True 3-Way Folder Merge Studio (White / Fluent Light Theme)
Compares Mine (Left), Base (Ancestor), and Theirs (Right) directory/archive/remote trees,
detects conflicting vs non-conflicting changes, allows per-file resolution or 3-way text merge
drill-down, and writes merged outputs cleanly to an Output directory.
"""

import os
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLineEdit, QComboBox, QLabel, QFileDialog, QHeaderView,
    QFrame, QButtonGroup, QMessageBox, QMenu, QProgressBar, QApplication, QGridLayout
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QColor, QFont

from app.core.folder_merge_engine import FolderMergeEngine, FolderMergeItem
from app.core.remote_vfs import RemoteVFS
from app.ui.styles.icons import get_line_icon


class FolderMergeWorker(QThread):
    """Non-blocking background worker for 3-way folder/archive/remote comparisons."""
    progress = Signal(int, str)
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, left_dir: str, base_dir: str, right_dir: str, mode: str = "hash"):
        super().__init__()
        self.left_dir = left_dir
        self.base_dir = base_dir
        self.right_dir = right_dir
        self.mode = mode
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            def cb(count, msg):
                if self._is_cancelled:
                    raise InterruptedError("Cancelled by user")
                self.progress.emit(count, msg)

            items = FolderMergeEngine.compare_3way_folders(
                self.left_dir, self.base_dir, self.right_dir,
                mode=self.mode, progress_callback=cb
            )
            if not self._is_cancelled:
                self.finished.emit(items)
        except InterruptedError:
            pass
        except Exception as e:
            self.failed.emit(str(e))


class FolderMergeView(QWidget):
    """True Ancestor-Aware 3-Way Folder Merge Studio."""

    open3WayFileMergeRequested = Signal(str, str, str, str)  # (mine, base, theirs, output_file)
    homeRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.left_dir: str = ""
        self.base_dir: str = ""
        self.right_dir: str = ""
        self.output_dir: str = ""
        self.current_filter_mode: str = "all"
        self._cached_items: List[FolderMergeItem] = []
        self._worker: Optional[FolderMergeWorker] = None

        self.setup_ui()
        if QApplication.instance() is not None:
            QApplication.instance().aboutToQuit.connect(self._cancel_worker)

    def closeEvent(self, event):
        self._cancel_worker()
        super().closeEvent(event)

    def _cancel_worker(self):
        worker = self._worker
        self._worker = None
        if worker is not None:
            for sig in (worker.progress, worker.finished, worker.failed):
                try:
                    sig.disconnect()
                except Exception:
                    pass
            if worker.isRunning():
                worker.cancel()
                worker.quit()
                worker.wait(3000)
        if hasattr(self, "progress_bar"):
            self.progress_bar.setVisible(False)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Ribbon
        ribbon = QWidget()
        ribbon.setObjectName("FolderMergeRibbon")
        ribbon.setFixedHeight(46)
        ribbon.setStyleSheet("""
            #FolderMergeRibbon {
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

        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)
        for mode_id, label in [
            ("all", "* All"),
            ("conflicts", "⚠ Conflicts"),
            ("automerge", "⇄ Auto-Merge"),
            ("identical", "= Identical"),
        ]:
            btn = QPushButton(f" {label}")
            btn.setCheckable(True)
            btn.setChecked(mode_id == "all")
            btn.setFixedHeight(30)
            btn.clicked.connect(lambda _=False, m=mode_id: self._set_filter_mode(m))
            self.filter_group.addButton(btn)
            r_layout.addWidget(btn)
            setattr(self, f"btn_filter_{mode_id}", btn)

        self.combo_rules = QComboBox()
        self.combo_rules.setFixedHeight(30)
        self.combo_rules.addItems([
            "Byte-by-Byte (SHA-256)",
            "BLAKE3 (Ultra-Fast Hash)",
            "Size & Timestamp (±2s)",
        ])
        r_layout.addWidget(self.combo_rules)

        self.btn_compare = QPushButton(" Compare 3-Way")
        self.btn_compare.setIcon(get_line_icon("refresh", "#1e293b"))
        self.btn_compare.setFixedHeight(30)
        self.btn_compare.clicked.connect(self.run_comparison)
        r_layout.addWidget(self.btn_compare)

        self.btn_auto_mine = QPushButton(" Conflicts -> Mine")
        self.btn_auto_mine.setFixedHeight(30)
        self.btn_auto_mine.clicked.connect(lambda: self._resolve_all_conflicts("take_left"))
        r_layout.addWidget(self.btn_auto_mine)

        self.btn_auto_theirs = QPushButton(" Conflicts -> Theirs")
        self.btn_auto_theirs.setFixedHeight(30)
        self.btn_auto_theirs.clicked.connect(lambda: self._resolve_all_conflicts("take_right"))
        r_layout.addWidget(self.btn_auto_theirs)

        self.btn_execute = QPushButton(" Execute Merge...")
        self.btn_execute.setIcon(get_line_icon("folder-merge", "#ffffff"))
        self.btn_execute.setObjectName("PrimaryButton")
        self.btn_execute.setFixedHeight(30)
        self.btn_execute.clicked.connect(self._execute_merge_ui)
        r_layout.addWidget(self.btn_execute)

        self.btn_export_csv = QPushButton(" CSV")
        self.btn_export_csv.setIcon(get_line_icon("download", "#1e293b"))
        self.btn_export_csv.setFixedHeight(30)
        self.btn_export_csv.clicked.connect(self._export_csv)
        r_layout.addWidget(self.btn_export_csv)

        r_layout.addStretch()
        main_layout.addWidget(ribbon)

        # 2. 4-Path Header Grid (Mine, Base, Theirs, Output)
        paths_frame = QFrame()
        paths_frame.setStyleSheet("QFrame { background: #f8fafc; border-bottom: 1.5px solid #cbd5e1; }")
        pg = QGridLayout(paths_frame)
        pg.setContentsMargins(10, 6, 10, 6)
        pg.setSpacing(6)

        self.txt_left = QLineEdit()
        self.txt_base = QLineEdit()
        self.txt_right = QLineEdit()
        self.txt_output = QLineEdit()

        specs = [
            (0, 0, "MINE (LEFT)", "#1d4ed8", "#eff6ff", self.txt_left),
            (0, 3, "BASE (ANCESTOR)", "#475569", "#f1f5f9", self.txt_base),
            (1, 0, "THEIRS (RIGHT)", "#15803d", "#f0fdf4", self.txt_right),
            (1, 3, "OUTPUT FOLDER", "#8250df", "#f5f3ff", self.txt_output),
        ]
        for row, col, title, fg, bg, edit in specs:
            lbl = QLabel(title)
            lbl.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {fg}; background: {bg}; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px;")
            edit.setFixedHeight(26)
            edit.setPlaceholderText(f"Select or paste {title.lower()} directory path...")
            btn = QPushButton("Browse...")
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda _=False, ed=edit, t=title: self._browse_dir(ed, t))
            pg.addWidget(lbl, row, col)
            pg.addWidget(edit, row, col + 1)
            pg.addWidget(btn, row, col + 2)

        main_layout.addWidget(paths_frame)

        # 3. 3-Way Merge Tree
        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["Item Path", "3-Way Status", "Resolution Action", "Mine / Base / Theirs Sizes", "Details"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(4, QHeaderView.Interactive)
        self.tree.setColumnWidth(4, 240)
        self.tree.setAlternatingRowColors(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        main_layout.addWidget(self.tree, 1)

        # 4. Status Bar
        status_bar = QFrame()
        status_bar.setFixedHeight(28)
        status_bar.setStyleSheet("QFrame { background: #f1f5f9; border-top: 1px solid #cbd5e1; padding: 0 8px; }")
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(8, 0, 8, 0)
        sb_layout.setSpacing(10)

        self.lbl_log = QLabel("● Select Mine, Base, Theirs, and Output folders to run a 3-way folder merge.")
        self.lbl_log.setStyleSheet("font-size: 11px; color: #475569; border: none; background: transparent;")
        sb_layout.addWidget(self.lbl_log, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedSize(130, 14)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        sb_layout.addWidget(self.progress_bar)

        self.lbl_stats = QLabel("0 Conflicts | 0 Auto-Merge | 0 Identical")
        self.lbl_stats.setStyleSheet("font-size: 11px; font-weight: 700; color: #0f172a; border: none; background: transparent;")
        sb_layout.addWidget(self.lbl_stats)
        main_layout.addWidget(status_bar)

    def _browse_dir(self, target_edit: QLineEdit, title: str):
        folder = QFileDialog.getExistingDirectory(self, f"Select {title}")
        if folder:
            target_edit.setText(folder)

    def set_directories(self, left_dir: str, base_dir: str, right_dir: str, output_dir: str = ""):
        self.txt_left.setText(left_dir)
        self.txt_base.setText(base_dir)
        self.txt_right.setText(right_dir)
        if output_dir:
            self.txt_output.setText(output_dir)
        self.run_comparison()

    def run_comparison(self):
        self.left_dir = self.txt_left.text().strip()
        self.base_dir = self.txt_base.text().strip()
        self.right_dir = self.txt_right.text().strip()
        self.output_dir = self.txt_output.text().strip()

        if not (self.left_dir and self.base_dir and self.right_dir):
            self.lbl_log.setText("● Please provide Mine, Base, and Theirs directories.")
            return

        for label, d in (("Mine", self.left_dir), ("Base", self.base_dir), ("Theirs", self.right_dir)):
            if not RemoteVFS.is_remote_path(d) and not os.path.exists(d):
                self.lbl_log.setText(f"{label} directory not found: {d}")
                return

        self._cancel_worker()
        self.tree.clear()
        mode_map = {0: "hash", 1: "blake3", 2: "timestamp"}
        mode = mode_map.get(self.combo_rules.currentIndex(), "hash")
        self.progress_bar.setVisible(True)
        self.lbl_log.setText("● Comparing 3 directory trees...")

        self._worker = FolderMergeWorker(self.left_dir, self.base_dir, self.right_dir, mode=mode)
        self._worker.progress.connect(lambda _c, msg: self.lbl_log.setText(f"● {msg}"))
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_failed(self, err: str):
        self.progress_bar.setVisible(False)
        self.lbl_log.setText(f"3-way folder comparison error: {err}")

    def _on_finished(self, items: List[FolderMergeItem]):
        self.progress_bar.setVisible(False)
        self.set_merge_items(items)

    def set_merge_items(self, items: List[FolderMergeItem]):
        """Populates the tree directly (used both by worker completion and tests)."""
        self._cached_items = items
        self._rebuild_tree()

    def _set_filter_mode(self, mode: str):
        self.current_filter_mode = mode
        self._rebuild_tree()

    def _rebuild_tree(self):
        self.tree.clear()
        conflicts = 0
        automerge = 0
        identical = 0

        def count_files(nodes: List[FolderMergeItem]):
            nonlocal conflicts, automerge, identical
            for it in nodes:
                if not it.is_dir:
                    if it.status == "CONFLICT" or it.resolution == "unresolved":
                        conflicts += 1
                    elif it.status == "IDENTICAL":
                        identical += 1
                    else:
                        automerge += 1
                if it.children:
                    count_files(it.children)

        count_files(self._cached_items)
        self.lbl_stats.setText(f"{conflicts} Conflicts | {automerge} Auto-Merge | {identical} Identical")
        self.lbl_log.setText("● 3-way folder evaluation ready.")

        mode = self.current_filter_mode
        status_colors = {
            "CONFLICT": QColor("#cf222e"),
            "LEFT_MODIFIED": QColor("#0969da"),
            "LEFT_ADDED": QColor("#0969da"),
            "RIGHT_MODIFIED": QColor("#1a7f37"),
            "RIGHT_ADDED": QColor("#1a7f37"),
            "LEFT_DELETED": QColor("#b45309"),
            "RIGHT_DELETED": QColor("#b45309"),
            "CONVERGED": QColor("#8250df"),
            "IDENTICAL": QColor("#64748b"),
            "AUTO_MERGE": QColor("#0969da"),
        }

        def add_nodes(parent, nodes: List[FolderMergeItem]) -> bool:
            any_added = False
            for it in nodes:
                node = QTreeWidgetItem(parent)
                node.setData(0, Qt.UserRole, it)
                prefix = "📁 " if it.is_dir else "📄 "
                node.setText(0, f"{prefix}{it.name}")
                node.setText(1, it.status)
                node.setText(2, "" if it.is_dir else FolderMergeEngine.RESOLUTION_LABELS.get(it.resolution, it.resolution))
                sz_str = "" if it.is_dir else (
                    f"M:{it.left_size if it.left_size is not None else '-'} | "
                    f"B:{it.base_size if it.base_size is not None else '-'} | "
                    f"T:{it.right_size if it.right_size is not None else '-'}"
                )
                node.setText(3, sz_str)
                node.setText(4, it.reason)

                col = status_colors.get(it.status, QColor("#334155"))
                node.setForeground(1, col)
                if it.status == "CONFLICT" or it.resolution == "unresolved":
                    f = QFont()
                    f.setBold(True)
                    node.setFont(1, f)
                    node.setForeground(2, QColor("#cf222e"))

                child_visible = add_nodes(node, it.children) if it.children else False

                if mode == "all":
                    vis = True
                elif mode == "conflicts":
                    vis = (it.status == "CONFLICT" or it.resolution == "unresolved") or child_visible
                elif mode == "automerge":
                    vis = (not it.is_dir and it.status not in ("IDENTICAL", "CONFLICT") and it.resolution != "unresolved") or child_visible
                elif mode == "identical":
                    vis = (it.status == "IDENTICAL") or child_visible
                else:
                    vis = True

                node.setHidden(not vis)
                if vis:
                    any_added = True
                    if it.is_dir and mode != "all" and child_visible:
                        node.setExpanded(True)
            return any_added

        add_nodes(self.tree, self._cached_items)
        self.tree.expandToDepth(1)

    def set_item_resolution(self, item: FolderMergeItem, resolution: str):
        item.resolution = resolution
        self._rebuild_tree()

    def _resolve_all_conflicts(self, choice: str):
        for f in FolderMergeEngine.flatten_files(self._cached_items):
            if f.status == "CONFLICT" or f.resolution == "unresolved":
                f.resolution = choice
        self._rebuild_tree()

    def _show_context_menu(self, pos):
        qitem = self.tree.itemAt(pos)
        if not qitem:
            return
        m_item: FolderMergeItem = qitem.data(0, Qt.UserRole)
        if not m_item or m_item.is_dir:
            return

        menu = QMenu(self)
        if m_item.left_path:
            menu.addAction("← Take Mine (Left)", lambda: self.set_item_resolution(m_item, "take_left"))
        if m_item.right_path:
            menu.addAction("→ Take Theirs (Right)", lambda: self.set_item_resolution(m_item, "take_right"))
        if m_item.base_path:
            menu.addAction("○ Revert to Base", lambda: self.set_item_resolution(m_item, "take_base"))
        menu.addAction("✕ Delete in Output", lambda: self.set_item_resolution(m_item, "delete"))
        menu.addAction("— Skip File", lambda: self.set_item_resolution(m_item, "skip"))
        menu.addSeparator()
        menu.addAction("Open in 3-Way Text Merge Studio", lambda: self._open_file_in_3way(m_item))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _open_file_in_3way(self, m_item: FolderMergeItem):
        out_root = self.txt_output.text().strip()
        out_file = os.path.join(out_root, m_item.rel_path.replace("/", os.sep)) if out_root else ""
        self.open3WayFileMergeRequested.emit(
            m_item.left_path or "",
            m_item.base_path or "",
            m_item.right_path or "",
            out_file,
        )

    def _on_item_double_clicked(self, qitem: QTreeWidgetItem, _col: int):
        m_item: FolderMergeItem = qitem.data(0, Qt.UserRole)
        if not m_item or m_item.is_dir:
            return
        self._open_file_in_3way(m_item)

    def _execute_merge_ui(self):
        if not self._cached_items:
            QMessageBox.information(self, "Nothing to Merge", "Run a 3-way folder comparison first.")
            return
        out_dir = self.txt_output.text().strip()
        if not out_dir:
            out_dir = QFileDialog.getExistingDirectory(self, "Select Output Folder for Merged Files")
            if not out_dir:
                return
            self.txt_output.setText(out_dir)

        summary = FolderMergeEngine.execute_merge(self._cached_items, out_dir, skip_conflicts=True)
        msg = (
            f"Written/Copied: {summary.written_count}\n"
            f"Deleted in Output: {summary.deleted_count}\n"
            f"Skipped Conflicts: {summary.skipped_conflicts}"
        )
        if summary.errors:
            msg += "\n\nErrors:\n" + "\n".join(summary.errors[:5])
        QMessageBox.information(self, "3-Way Folder Merge Complete", msg)
        self.lbl_log.setText(f"● Merged {summary.written_count} file(s) into {out_dir}")

    def _export_csv(self):
        if not self._cached_items:
            return
        file, _ = QFileDialog.getSaveFileName(self, "Export 3-Way Folder Merge CSV", "folder_merge.csv", "CSV Files (*.csv)")
        if file:
            FolderMergeEngine.export_csv_report(self._cached_items, file)
            self.lbl_log.setText(f"● Exported CSV: {os.path.basename(file)}")
