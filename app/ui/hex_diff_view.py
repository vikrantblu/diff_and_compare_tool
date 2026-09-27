"""
Memory-Mapped Hex & Binary Inspection Studio
Features:
- Side-by-side memory-mapped binary inspection with zero UI freeze on multi-GB files.
- Aligned 16-byte rows with offset, hexadecimal representation, and printable ASCII.
- Byte-level mismatch highlighting with Next/Previous difference navigation.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTableWidget, QTableWidgetItem, QFrame, QSplitter,
    QHeaderView, QScrollBar
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QFont

from app.core.hex_diff import HexDiffEngine, HexDiffSummary, HexRowDiff
from app.ui.styles.icons import get_line_icon


class HexDiffView(QWidget):
    """Studio for side-by-side binary and hex comparison."""

    PAGE_SIZE = 100  # Number of rows loaded per page

    def __init__(self):
        super().__init__()
        self.left_path: Optional[str] = None
        self.right_path: Optional[str] = None
        self.summary: Optional[HexDiffSummary] = None
        self.cur_diff_index = -1
        self.current_start_row = 0
        self._is_syncing_scroll = False

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Top File Selection Bar
        file_bar = QFrame()
        file_bar.setFixedHeight(46)
        file_bar.setStyleSheet("background-color: #f8fafc; border-bottom: 1px solid #cbd5e1; padding: 2px 4px;")
        fb_layout = QHBoxLayout(file_bar)
        fb_layout.setContentsMargins(10, 0, 10, 0)
        fb_layout.setSpacing(10)

        self.btn_left = QPushButton(" Browse Left Binary...")
        self.btn_left.setIcon(get_line_icon("folder", "#0969da"))
        self.btn_left.setFixedHeight(30)
        self.btn_left.clicked.connect(self._browse_left)
        self.lbl_left = QLabel("Left: (None)")
        self.lbl_left.setStyleSheet("color: #475569; font-weight: 600; padding: 4px 8px; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px;")

        self.btn_right = QPushButton(" Browse Right Binary...")
        self.btn_right.setIcon(get_line_icon("folder", "#0969da"))
        self.btn_right.setFixedHeight(30)
        self.btn_right.clicked.connect(self._browse_right)
        self.lbl_right = QLabel("Right: (None)")
        self.lbl_right.setStyleSheet("color: #475569; font-weight: 600; padding: 4px 8px; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px;")

        fb_layout.addWidget(self.btn_left)
        fb_layout.addWidget(self.lbl_left, 1)
        fb_layout.addWidget(self.btn_right)
        fb_layout.addWidget(self.lbl_right, 1)

        layout.addWidget(file_bar)

        # 2. Command Bar (Navigation & Stats)
        cmd_bar = QFrame()
        cmd_bar.setFixedHeight(46)
        cmd_bar.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #cbd5e1; padding: 2px 4px;")
        cb_layout = QHBoxLayout(cmd_bar)
        cb_layout.setContentsMargins(10, 0, 10, 0)
        cb_layout.setSpacing(8)

        self.btn_prev = QPushButton(" Prev Diff")
        self.btn_prev.setIcon(get_line_icon("arrow-up", "#24292f"))
        self.btn_prev.setFixedHeight(30)
        self.btn_prev.clicked.connect(self._prev_diff)
        cb_layout.addWidget(self.btn_prev)

        self.btn_next = QPushButton(" Next Diff")
        self.btn_next.setIcon(get_line_icon("arrow-down", "#24292f"))
        self.btn_next.setFixedHeight(30)
        self.btn_next.clicked.connect(self._next_diff)
        cb_layout.addWidget(self.btn_next)

        self.lbl_stats = QLabel("  ● Ready")
        self.lbl_stats.setStyleSheet("color: #0969da; font-weight: 600; padding: 4px 10px; background: #e0f2fe; border: 1px solid #bae6fd; border-radius: 12px; font-size: 11px;")
        cb_layout.addWidget(self.lbl_stats)

        cb_layout.addStretch()

        self.btn_refresh = QPushButton(" Refresh")
        self.btn_refresh.setIcon(get_line_icon("refresh", "#24292f"))
        self.btn_refresh.setFixedHeight(30)
        self.btn_refresh.clicked.connect(self._recompute_diff)
        cb_layout.addWidget(self.btn_refresh)

        layout.addWidget(cmd_bar)

        # 3. Synchronized Split Hex Tables
        self.splitter = QSplitter(Qt.Horizontal)

        self.table_left = self._create_hex_table()
        self.table_right = self._create_hex_table()

        self.table_left.verticalScrollBar().valueChanged.connect(self._sync_scroll_left)
        self.table_right.verticalScrollBar().valueChanged.connect(self._sync_scroll_right)

        self.splitter.addWidget(self.table_left)
        self.splitter.addWidget(self.table_right)
        self.splitter.setSizes([600, 600])

        layout.addWidget(self.splitter, 1)

    def _create_hex_table(self) -> QTableWidget:
        tbl = QTableWidget()
        tbl.setColumnCount(3)
        tbl.setHorizontalHeaderLabels(["Offset", "Hex (16 Bytes)", "ASCII"])
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        tbl.setStyleSheet("""
            QTableWidget {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: #ffffff;
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 12px;
                gridline-color: #e2e8f0;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #334155;
                font-weight: 600;
                padding: 6px;
                border: 1px solid #cbd5e1;
            }
        """)
        return tbl

    def _browse_left(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open Left Binary File", "", "All Files (*.*)")
        if file:
            self.left_path = file
            self.lbl_left.setText(f"Left: {os.path.basename(file)} ({os.path.getsize(file):,} B)")
            self._recompute_diff()

    def _browse_right(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open Right Binary File", "", "All Files (*.*)")
        if file:
            self.right_path = file
            self.lbl_right.setText(f"Right: {os.path.basename(file)} ({os.path.getsize(file):,} B)")
            self._recompute_diff()

    def set_files(self, left_path: str, right_path: str):
        self.left_path = left_path
        self.right_path = right_path
        self.lbl_left.setText(f"Left: {os.path.basename(left_path)}")
        self.lbl_right.setText(f"Right: {os.path.basename(right_path)}")
        self._recompute_diff()

    def _recompute_diff(self):
        if not self.left_path or not self.right_path:
            return

        self.summary = HexDiffEngine.compare_files_summary(self.left_path, self.right_path)
        if not self.summary:
            self.lbl_stats.setText("⚠️ Failed to compare binary files")
            return

        s = self.summary
        self.lbl_stats.setText(
            f"Total: {s.total_rows:,} rows | Differing: {s.differing_bytes_count:,} B ({s.difference_percentage:.2f}%) | {len(s.mismatched_rows):,} mismatch rows"
        )
        self.cur_diff_index = -1
        self.current_start_row = 0
        self._load_current_page()

    def _load_current_page(self):
        if not self.left_path or not self.right_path or not self.summary:
            return

        rows = HexDiffEngine.read_row_range(
            self.left_path, self.right_path, self.current_start_row, self.PAGE_SIZE
        )

        for tbl in (self.table_left, self.table_right):
            tbl.clearContents()
            tbl.setRowCount(len(rows))

        c_diff = QBrush(QColor("#fff8c5"))
        c_diff_text = QBrush(QColor("#cf222e"))

        for idx, r in enumerate(rows):
            offset_str = f"{r.offset:08X}"

            # Left items
            item_off_l = QTableWidgetItem(offset_str)
            item_hex_l = QTableWidgetItem(r.left_hex)
            item_asc_l = QTableWidgetItem(r.left_ascii)

            # Right items
            item_off_r = QTableWidgetItem(offset_str)
            item_hex_r = QTableWidgetItem(r.right_hex)
            item_asc_r = QTableWidgetItem(r.right_ascii)

            if r.mismatched_byte_indices or r.is_left_only or r.is_right_only:
                for item in (item_off_l, item_hex_l, item_asc_l, item_off_r, item_hex_r, item_asc_r):
                    item.setBackground(c_diff)
                item_hex_l.setForeground(c_diff_text)
                item_hex_r.setForeground(c_diff_text)

            self.table_left.setItem(idx, 0, item_off_l)
            self.table_left.setItem(idx, 1, item_hex_l)
            self.table_left.setItem(idx, 2, item_asc_l)

            self.table_right.setItem(idx, 0, item_off_r)
            self.table_right.setItem(idx, 1, item_hex_r)
            self.table_right.setItem(idx, 2, item_asc_r)

    def _next_diff(self):
        if not self.summary or not self.summary.mismatched_rows:
            return
        self.cur_diff_index = (self.cur_diff_index + 1) % len(self.summary.mismatched_rows)
        target_row = self.summary.mismatched_rows[self.cur_diff_index]
        self.current_start_row = max(0, target_row - 10)
        self._load_current_page()
        # Highlight row in current view
        local_row = target_row - self.current_start_row
        if 0 <= local_row < self.table_left.rowCount():
            self.table_left.selectRow(local_row)
            self.table_right.selectRow(local_row)

    def _prev_diff(self):
        if not self.summary or not self.summary.mismatched_rows:
            return
        self.cur_diff_index = (self.cur_diff_index - 1) % len(self.summary.mismatched_rows)
        target_row = self.summary.mismatched_rows[self.cur_diff_index]
        self.current_start_row = max(0, target_row - 10)
        self._load_current_page()
        local_row = target_row - self.current_start_row
        if 0 <= local_row < self.table_left.rowCount():
            self.table_left.selectRow(local_row)
            self.table_right.selectRow(local_row)

    def _sync_scroll_left(self, val):
        if not self._is_syncing_scroll:
            self._is_syncing_scroll = True
            self.table_right.verticalScrollBar().setValue(val)
            self._is_syncing_scroll = False

    def _sync_scroll_right(self, val):
        if not self._is_syncing_scroll:
            self._is_syncing_scroll = True
            self.table_left.verticalScrollBar().setValue(val)
            self._is_syncing_scroll = False
