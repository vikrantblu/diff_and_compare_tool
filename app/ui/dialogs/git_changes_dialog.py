"""
Git Working-Tree Changeset Browser Dialog (Ctrl+G)
Lists modified, staged, untracked, and conflicted files in the current Git repository
and opens any selected file directly in DiffView comparing Git HEAD vs Working Copy.
"""

import os
from typing import List, Dict
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush

from app.core.git_staging import GitStagingManager
from app.ui.styles.icons import get_line_icon


class GitChangesDialog(QDialog):
    """Fluent Light dialog browsing Git working-tree changes for instant HEAD vs Working diff."""

    openGitFileDiff = Signal(str)  # abs_path

    def __init__(self, initial_path: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Git Working-Tree Changes (Ctrl+G)")
        self.resize(740, 490)
        self._all_changes: List[Dict[str, str]] = []

        root = GitStagingManager.find_git_root(initial_path or os.getcwd())
        self.repo_path = root or (initial_path if os.path.isdir(initial_path) else os.getcwd())

        self.setup_ui()
        self.refresh_changes()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Repository picker row
        repo_row = QHBoxLayout()
        lbl_repo = QLabel("Repository:")
        lbl_repo.setStyleSheet("font-weight: 700; color: #334155;")
        repo_row.addWidget(lbl_repo)

        self.txt_repo = QLineEdit(self.repo_path)
        self.txt_repo.setFixedHeight(30)
        self.txt_repo.returnPressed.connect(self.refresh_changes)
        repo_row.addWidget(self.txt_repo, 1)

        btn_browse = QPushButton(" Browse...")
        btn_browse.setIcon(get_line_icon("folder", "#1e293b"))
        btn_browse.setFixedHeight(30)
        btn_browse.clicked.connect(self._browse_repo)
        repo_row.addWidget(btn_browse)

        btn_refresh = QPushButton(" Refresh")
        btn_refresh.setIcon(get_line_icon("refresh", "#1e293b"))
        btn_refresh.setFixedHeight(30)
        btn_refresh.clicked.connect(self.refresh_changes)
        repo_row.addWidget(btn_refresh)
        layout.addLayout(repo_row)

        # Filter box
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filter changed files by path or status...")
        self.txt_filter.setFixedHeight(30)
        self.txt_filter.setClearButtonEnabled(True)
        self.txt_filter.textChanged.connect(self._populate_table)
        layout.addWidget(self.txt_filter)

        # Changes table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Status", "Changed File (Relative Path)", "Full Path"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.setColumnWidth(2, 220)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.itemDoubleClicked.connect(lambda _it: self._open_selected())
        layout.addWidget(self.table, 1)

        # Bottom row
        foot = QHBoxLayout()
        self.lbl_summary = QLabel("0 changed file(s)")
        self.lbl_summary.setStyleSheet("color: #475569; font-weight: 600; font-size: 12px;")
        foot.addWidget(self.lbl_summary)
        foot.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(30)
        btn_close.clicked.connect(self.reject)
        foot.addWidget(btn_close)

        self.btn_open = QPushButton(" Open Diff (HEAD vs Working)")
        self.btn_open.setIcon(get_line_icon("diff", "#ffffff"))
        self.btn_open.setObjectName("PrimaryButton")
        self.btn_open.setFixedHeight(30)
        self.btn_open.clicked.connect(self._open_selected)
        foot.addWidget(self.btn_open)
        layout.addLayout(foot)

    def _browse_repo(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Git Repository Folder", self.txt_repo.text())
        if folder:
            root = GitStagingManager.find_git_root(folder)
            self.txt_repo.setText(root or folder)
            self.refresh_changes()

    def refresh_changes(self):
        repo_dir = self.txt_repo.text().strip()
        self._all_changes = GitStagingManager.get_working_tree_changes(repo_dir)
        self._populate_table()

    def _populate_table(self):
        q = (self.txt_filter.text() or "").strip().lower()
        filtered = [
            ch for ch in self._all_changes
            if not q or q in ch["rel_path"].lower() or q in ch["label"].lower()
        ]
        self.table.setRowCount(len(filtered))

        color_map = {
            "Modified": QColor("#0969da"),
            "Staged": QColor("#1a7f37"),
            "Staged (Added)": QColor("#1a7f37"),
            "Staged + Modified": QColor("#8250df"),
            "Untracked": QColor("#0891b2"),
            "Deleted": QColor("#cf222e"),
            "Conflict": QColor("#d97706"),
        }

        for r, ch in enumerate(filtered):
            st_item = QTableWidgetItem(ch["label"])
            st_item.setFlags(st_item.flags() & ~Qt.ItemIsEditable)
            st_item.setForeground(QBrush(color_map.get(ch["label"], QColor("#334155"))))
            st_item.setData(Qt.UserRole, ch["abs_path"])

            rel_item = QTableWidgetItem(ch["rel_path"])
            rel_item.setFlags(rel_item.flags() & ~Qt.ItemIsEditable)

            abs_item = QTableWidgetItem(ch["abs_path"])
            abs_item.setFlags(abs_item.flags() & ~Qt.ItemIsEditable)

            self.table.setItem(r, 0, st_item)
            self.table.setItem(r, 1, rel_item)
            self.table.setItem(r, 2, abs_item)

        if filtered:
            self.table.selectRow(0)
        root = GitStagingManager.find_git_root(self.txt_repo.text().strip())
        if not root:
            self.lbl_summary.setText("Not a Git repository — select a Git folder above")
        else:
            self.lbl_summary.setText(f"{len(filtered)} changed file(s) in {os.path.basename(root)}")

    def _open_selected(self) -> bool:
        row = self.table.currentRow()
        if row < 0:
            return False
        item = self.table.item(row, 0)
        if not item:
            return False
        abs_path = item.data(Qt.UserRole)
        if abs_path:
            self.openGitFileDiff.emit(abs_path)
            self.accept()
            return True
        return False
