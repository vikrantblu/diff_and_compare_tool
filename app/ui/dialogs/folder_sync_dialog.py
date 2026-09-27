"""
Folder Synchronization Preview & Execution Dialog
Displays interactive action table before performing sync:
- Mirror Left-to-Right
- Bi-directional Sync
- Update Left / Update Right
"""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QHeaderView,
    QProgressBar, QMessageBox, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from app.core.folder_sync_engine import FolderSyncEngine, SyncActionItem
from app.core.folder_compare_engine import FolderCompareItem
from app.ui.styles.icons import get_line_icon
from typing import List


class FolderSyncDialog(QDialog):
    """Interactive Folder Sync confirmation and execution modal."""

    def __init__(self, parent, items: List[FolderCompareItem], left_dir: str, right_dir: str):
        super().__init__(parent)
        self.setWindowTitle("Folder Synchronization Hub — diff_and_compare")
        self.resize(880, 560)
        self.items = items
        self.left_dir = left_dir
        self.right_dir = right_dir
        self.current_plan: List[SyncActionItem] = []

        self.setup_ui()
        self.refresh_plan()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Title
        lbl_title = QLabel("Folder Synchronization Hub")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #0f172a;")
        layout.addWidget(lbl_title)

        # Mode Selection Bar
        mode_bar = QFrame()
        mode_bar.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px;")
        mb_layout = QHBoxLayout(mode_bar)
        mb_layout.setContentsMargins(8, 6, 8, 6)
        mb_layout.setSpacing(10)

        mb_layout.addWidget(QLabel("Sync Mode:"))
        self.combo_mode = QComboBox()
        self.combo_mode.setFixedHeight(30)
        self.combo_mode.addItem("Mirror Left to Right (Overwrite & Prune Orphans)", FolderSyncEngine.MODE_MIRROR_L2R)
        self.combo_mode.addItem("Bi-directional Sync (Propagate Newest Timestamps)", FolderSyncEngine.MODE_BIDIRECTIONAL)
        self.combo_mode.addItem("Update Left (Copy Missing or Newer from Right)", FolderSyncEngine.MODE_UPDATE_LEFT)
        self.combo_mode.addItem("Update Right (Copy Missing or Newer from Left)", FolderSyncEngine.MODE_UPDATE_RIGHT)
        self.combo_mode.currentIndexChanged.connect(self.refresh_plan)
        mb_layout.addWidget(self.combo_mode, 1)

        self.lbl_stats = QLabel("Calculating plan...")
        self.lbl_stats.setStyleSheet("font-weight: 600; color: #0969da;")
        mb_layout.addWidget(self.lbl_stats)

        layout.addWidget(mode_bar)

        # Action Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Action", "Relative Path", "Size", "Reason"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table, 1)

        # Progress bar (hidden until execution)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(20)
        layout.addWidget(self.progress_bar)

        # Bottom Button Bar
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedHeight(32)
        self.btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(self.btn_cancel)

        self.btn_execute = QPushButton(" Run Synchronization")
        self.btn_execute.setIcon(get_line_icon("refresh", "#ffffff"))
        self.btn_execute.setFixedHeight(32)
        self.btn_execute.setObjectName("PrimaryButton")
        self.btn_execute.setStyleSheet("""
            QPushButton#PrimaryButton {
                background-color: #0969da;
                color: #ffffff;
                font-weight: 600;
                padding: 4px 16px;
                border-radius: 6px;
            }
            QPushButton#PrimaryButton:hover {
                background-color: #0854ad;
            }
        """)
        self.btn_execute.clicked.connect(self.execute_sync)
        btn_bar.addWidget(self.btn_execute)

        layout.addLayout(btn_bar)

    def refresh_plan(self):
        mode = self.combo_mode.currentData()
        self.current_plan = FolderSyncEngine.plan_sync(self.items, self.left_dir, self.right_dir, mode=mode)

        self.table.setRowCount(len(self.current_plan))
        copy_count = 0
        del_count = 0
        total_bytes = 0

        for r_idx, act in enumerate(self.current_plan):
            if act.action.startswith("copy"):
                copy_count += 1
                total_bytes += act.size
            elif act.action.startswith("delete"):
                del_count += 1

            # Action Item with Icon/Badge
            act_text = "Copy L ➜ R" if act.action == "copy_l2r" else (
                "Copy R ➜ L" if act.action == "copy_r2l" else (
                    "Delete on Right" if act.action == "delete_r" else "Delete on Left"
                )
            )
            item_act = QTableWidgetItem(act_text)
            if "delete" in act.action:
                item_act.setForeground(QColor("#cf222e"))
            elif act.action == "copy_l2r":
                item_act.setForeground(QColor("#1a7f37"))
            else:
                item_act.setForeground(QColor("#0969da"))

            item_path = QTableWidgetItem(act.rel_path)
            item_size = QTableWidgetItem(f"{act.size:,} B" if act.size > 0 else "")
            item_reason = QTableWidgetItem(act.reason)

            self.table.setItem(r_idx, 0, item_act)
            self.table.setItem(r_idx, 1, item_path)
            self.table.setItem(r_idx, 2, item_size)
            self.table.setItem(r_idx, 3, item_reason)

        mb_str = f"{total_bytes / (1024*1024):.2f} MB"
        self.lbl_stats.setText(f"{copy_count} to copy ({mb_str}) | {del_count} to delete")
        self.btn_execute.setEnabled(len(self.current_plan) > 0)

    def execute_sync(self):
        if not self.current_plan:
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Folder Synchronization",
            f"Are you sure you want to execute {len(self.current_plan)} sync actions?\n\n"
            f"Target Left: {self.left_dir}\n"
            f"Target Right: {self.right_dir}\n\n"
            f"This will copy/overwrite files and delete pruned orphans.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(self.current_plan))
        self.btn_execute.setEnabled(False)
        self.btn_cancel.setEnabled(False)

        def cb(cur, total, msg):
            self.progress_bar.setValue(cur)
            self.lbl_stats.setText(msg)

        summary = FolderSyncEngine.execute_sync(self.current_plan, progress_callback=cb)

        if summary.success:
            QMessageBox.information(
                self,
                "Synchronization Succeeded",
                f"Successfully completed synchronization!\n\n"
                f"• Copied/Updated: {summary.copied_count} files\n"
                f"• Deleted Orphans: {summary.deleted_count} files"
            )
            self.accept()
        else:
            QMessageBox.warning(
                self,
                "Synchronization Completed with Warnings",
                f"Completed with {len(summary.errors)} error(s):\n\n" + "\n".join(summary.errors[:5])
            )
            self.accept()
