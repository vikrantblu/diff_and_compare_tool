"""
Folder Synchronization Preview & Execution Dialog (White / Light Theme)
Displays interactive action table with per-row checkboxes, Recycle Bin safety option,
and background QThread execution so the UI stays responsive.
"""

import sys
from typing import List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QHeaderView,
    QProgressBar, QMessageBox, QFrame, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor

from app.core.folder_sync_engine import FolderSyncEngine, SyncActionItem, SyncExecutionSummary
from app.core.folder_compare_engine import FolderCompareItem
from app.ui.styles.icons import get_line_icon


class FolderSyncWorker(QThread):
    """Executes folder sync actions on a background thread."""
    progress = Signal(int, int, str)
    finished = Signal(object)

    def __init__(self, plan: List[SyncActionItem], use_recycle_bin: bool):
        super().__init__()
        self.plan = plan
        self.use_recycle_bin = use_recycle_bin

    def run(self):
        summary = FolderSyncEngine.execute_sync(
            self.plan,
            progress_callback=lambda c, t, m: self.progress.emit(c, t, m),
            use_recycle_bin=self.use_recycle_bin
        )
        self.finished.emit(summary)


class FolderSyncDialog(QDialog):
    """Interactive Folder Sync confirmation and execution modal."""

    def __init__(self, parent, items: List[FolderCompareItem], left_dir: str, right_dir: str):
        super().__init__(parent)
        self.setWindowTitle("Folder Synchronization Hub — diff_and_compare")
        self.resize(900, 580)
        self.items = items
        self.left_dir = left_dir
        self.right_dir = right_dir
        self.current_plan: List[SyncActionItem] = []
        self._worker: FolderSyncWorker = None

        self.setup_ui()
        self.refresh_plan()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        lbl_title = QLabel("Folder Synchronization Hub")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #0f172a; border: none; background: transparent;")
        layout.addWidget(lbl_title)

        mode_bar = QFrame()
        mode_bar.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px;")
        mb_layout = QHBoxLayout(mode_bar)
        mb_layout.setContentsMargins(8, 6, 8, 6)
        mb_layout.setSpacing(10)

        lbl_m = QLabel("Sync Mode:")
        lbl_m.setStyleSheet("font-weight: 600; border: none; background: transparent;")
        mb_layout.addWidget(lbl_m)

        self.combo_mode = QComboBox()
        self.combo_mode.setFixedHeight(30)
        self.combo_mode.addItem("Mirror Left to Right (Overwrite & Prune Orphans)", FolderSyncEngine.MODE_MIRROR_L2R)
        self.combo_mode.addItem("Bi-directional Sync (Propagate Newest Timestamps)", FolderSyncEngine.MODE_BIDIRECTIONAL)
        self.combo_mode.addItem("Update Left (Copy Missing or Newer from Right)", FolderSyncEngine.MODE_UPDATE_LEFT)
        self.combo_mode.addItem("Update Right (Copy Missing or Newer from Left)", FolderSyncEngine.MODE_UPDATE_RIGHT)
        self.combo_mode.currentIndexChanged.connect(self.refresh_plan)
        mb_layout.addWidget(self.combo_mode, 1)

        self.lbl_stats = QLabel("Calculating plan...")
        self.lbl_stats.setStyleSheet("font-weight: 600; color: #0969da; border: none; background: transparent;")
        mb_layout.addWidget(self.lbl_stats)

        layout.addWidget(mode_bar)

        # Action Table with Include Checkboxes
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Include", "Action", "Relative Path", "Size", "Reason"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemChanged.connect(self._update_selected_stats)
        layout.addWidget(self.table, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(20)
        layout.addWidget(self.progress_bar)

        btn_bar = QHBoxLayout()
        self.chk_recycle_bin = QCheckBox("Move deleted files to Recycle Bin (Safe Delete)")
        self.chk_recycle_bin.setChecked(sys.platform == "win32")
        self.chk_recycle_bin.setVisible(sys.platform == "win32")
        btn_bar.addWidget(self.chk_recycle_bin)

        btn_bar.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedHeight(32)
        self.btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(self.btn_cancel)

        self.btn_execute = QPushButton(" Run Synchronization")
        self.btn_execute.setIcon(get_line_icon("refresh", "#ffffff"))
        self.btn_execute.setFixedHeight(32)
        self.btn_execute.setObjectName("PrimaryButton")
        self.btn_execute.clicked.connect(self.execute_sync)
        btn_bar.addWidget(self.btn_execute)

        layout.addLayout(btn_bar)

    def refresh_plan(self):
        mode = self.combo_mode.currentData()
        self.current_plan = FolderSyncEngine.plan_sync(self.items, self.left_dir, self.right_dir, mode=mode)

        self.table.blockSignals(True)
        self.table.setRowCount(len(self.current_plan))

        for r_idx, act in enumerate(self.current_plan):
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk_item.setCheckState(Qt.Checked)

            act_text = "Copy L ➜ R" if act.action == "copy_l2r" else (
                "Copy R ➜ L" if act.action == "copy_r2l" else (
                    "Delete on Right" if act.action == "delete_r" else "Delete on Left"
                )
            )
            item_act = QTableWidgetItem(act_text)
            item_act.setFlags(item_act.flags() & ~Qt.ItemIsEditable)
            if "delete" in act.action:
                item_act.setForeground(QColor("#cf222e"))
            elif act.action == "copy_l2r":
                item_act.setForeground(QColor("#1a7f37"))
            else:
                item_act.setForeground(QColor("#0969da"))

            item_path = QTableWidgetItem(act.rel_path)
            item_path.setFlags(item_path.flags() & ~Qt.ItemIsEditable)
            item_size = QTableWidgetItem(f"{act.size:,} B" if act.size > 0 else "")
            item_size.setFlags(item_size.flags() & ~Qt.ItemIsEditable)
            item_reason = QTableWidgetItem(act.reason)
            item_reason.setFlags(item_reason.flags() & ~Qt.ItemIsEditable)

            self.table.setItem(r_idx, 0, chk_item)
            self.table.setItem(r_idx, 1, item_act)
            self.table.setItem(r_idx, 2, item_path)
            self.table.setItem(r_idx, 3, item_size)
            self.table.setItem(r_idx, 4, item_reason)

        self.table.blockSignals(False)
        self._update_selected_stats()

    def _get_selected_plan(self) -> List[SyncActionItem]:
        selected: List[SyncActionItem] = []
        for r_idx, act in enumerate(self.current_plan):
            item = self.table.item(r_idx, 0)
            if item and item.checkState() == Qt.Checked:
                selected.append(act)
        return selected

    def _update_selected_stats(self):
        selected = self._get_selected_plan()
        copy_count = sum(1 for a in selected if a.action.startswith("copy"))
        del_count = sum(1 for a in selected if a.action.startswith("delete"))
        total_bytes = sum(a.size for a in selected if a.action.startswith("copy"))
        mb_str = f"{total_bytes / (1024 * 1024):.2f} MB"
        self.lbl_stats.setText(f"{copy_count} to copy ({mb_str}) | {del_count} to delete")
        self.btn_execute.setEnabled(len(selected) > 0)

    def execute_sync(self):
        selected_plan = self._get_selected_plan()
        if not selected_plan:
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Folder Synchronization",
            f"Are you sure you want to execute {len(selected_plan)} selected sync action(s)?\n\n"
            f"Target Left: {self.left_dir}\n"
            f"Target Right: {self.right_dir}",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(selected_plan))
        self.btn_execute.setEnabled(False)
        self.btn_cancel.setEnabled(False)

        use_recycle = self.chk_recycle_bin.isChecked() if sys.platform == "win32" else False
        self._worker = FolderSyncWorker(selected_plan, use_recycle)
        self._worker.progress.connect(self._on_sync_progress)
        self._worker.finished.connect(self._on_sync_finished)
        self._worker.start()

    def _on_sync_progress(self, cur: int, total: int, msg: str):
        self.progress_bar.setValue(cur)
        self.lbl_stats.setText(msg)

    def _on_sync_finished(self, summary: SyncExecutionSummary):
        if summary.success:
            QMessageBox.information(
                self,
                "Synchronization Succeeded",
                f"Successfully completed synchronization!\n\n"
                f"• Copied/Updated: {summary.copied_count} files\n"
                f"• Deleted/Moved to Bin: {summary.deleted_count} files"
            )
        else:
            QMessageBox.warning(
                self,
                "Synchronization Completed with Warnings",
                f"Completed with {len(summary.errors)} error(s):\n\n" + "\n".join(summary.errors[:5])
            )
        self.accept()
