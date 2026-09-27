"""
Tabular and Spreadsheet Comparison Studio (CSV, TSV, Excel)
Features:
- Keyed row alignment (designate a Primary Key column to preserve row identity across sorts).
- Dual synchronized grid view with locked scrolling.
- Cell-level mutation highlighting and old-vs-new tooltips.
"""

import os
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QLineEdit, QFrame, QHeaderView, QSplitter, QDoubleSpinBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QFont

from app.core.tabular_diff import TabularDiffEngine, TabularDiffResult, RowDiff
from app.ui.styles.icons import get_line_icon


class TabularDiffView(QWidget):
    """Studio for comparing tabular data (CSV, TSV, Excel)."""

    def __init__(self):
        super().__init__()
        self.left_path: Optional[str] = None
        self.right_path: Optional[str] = None
        self.diff_result: Optional[TabularDiffResult] = None
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

        self.btn_left = QPushButton(" Browse Left Table...")
        self.btn_left.setIcon(get_line_icon("folder", "#0969da"))
        self.btn_left.setFixedHeight(30)
        self.btn_left.clicked.connect(self._browse_left)
        self.lbl_left = QLabel("Left: (None)")
        self.lbl_left.setStyleSheet("color: #475569; font-weight: 600; padding: 4px 8px; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px;")

        self.btn_right = QPushButton(" Browse Right Table...")
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

        # 2. Command Bar (Key column selector, diffs only, filter)
        cmd_bar = QFrame()
        cmd_bar.setFixedHeight(46)
        cmd_bar.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #cbd5e1; padding: 2px 4px;")
        cb_layout = QHBoxLayout(cmd_bar)
        cb_layout.setContentsMargins(10, 0, 10, 0)
        cb_layout.setSpacing(8)

        lbl_pk = QLabel("Primary Key:")
        lbl_pk.setStyleSheet("font-weight: 600; color: #334155;")
        cb_layout.addWidget(lbl_pk)
        self.combo_key = QComboBox()
        self.combo_key.addItem("(Sequential Row Index)")
        self.combo_key.setFixedHeight(30)
        self.combo_key.currentIndexChanged.connect(self._on_key_changed)
        cb_layout.addWidget(self.combo_key)

        lbl_tol = QLabel("Float Tol:")
        lbl_tol.setStyleSheet("font-weight: 600; color: #334155; margin-left: 4px;")
        cb_layout.addWidget(lbl_tol)
        self.spin_tol = QDoubleSpinBox()
        self.spin_tol.setRange(0.0, 1000000.0)
        self.spin_tol.setDecimals(4)
        self.spin_tol.setSingleStep(0.001)
        self.spin_tol.setValue(0.0)
        self.spin_tol.setFixedHeight(30)
        self.spin_tol.setFixedWidth(80)
        self.spin_tol.setToolTip("Numerical comparison tolerance (cells with numerical diff <= tolerance are treated as equal)")
        self.spin_tol.valueChanged.connect(self._recompute_diff)
        cb_layout.addWidget(self.spin_tol)

        self.chk_diffs_only = QCheckBox("Show Diffs Only")
        self.chk_diffs_only.setFixedHeight(30)
        self.chk_diffs_only.toggled.connect(self._populate_tables)
        cb_layout.addWidget(self.chk_diffs_only)

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filter table cells...")
        self.txt_filter.setFixedWidth(160)
        self.txt_filter.setFixedHeight(30)
        self.txt_filter.textChanged.connect(self._populate_tables)
        cb_layout.addWidget(self.txt_filter)

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

        # 3. Synchronized Dual Tables
        self.splitter = QSplitter(Qt.Horizontal)

        self.table_left = QTableWidget()
        self.table_right = QTableWidget()

        self._style_table(self.table_left)
        self._style_table(self.table_right)

        # Synchronize scrolling
        self.table_left.verticalScrollBar().valueChanged.connect(self._sync_vscroll_left)
        self.table_right.verticalScrollBar().valueChanged.connect(self._sync_vscroll_right)
        self.table_left.horizontalScrollBar().valueChanged.connect(self._sync_hscroll_left)
        self.table_right.horizontalScrollBar().valueChanged.connect(self._sync_hscroll_right)

        self.splitter.addWidget(self.table_left)
        self.splitter.addWidget(self.table_right)
        self.splitter.setSizes([600, 600])

        layout.addWidget(self.splitter, 1)

    def _style_table(self, table: QTableWidget):
        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: #ffffff;
                gridline-color: #e2e8f0;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #334155;
                font-weight: 600;
                padding: 6px;
                border: 1px solid #cbd5e1;
            }
        """)

    def _browse_left(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Open Left Table", "",
            "Table Files (*.csv *.tsv *.xlsx *.parquet *.db *.sqlite *.sqlite3);;CSV/TSV (*.csv *.tsv);;Excel Files (*.xlsx);;Parquet Files (*.parquet);;SQLite Databases (*.db *.sqlite *.sqlite3);;All Files (*.*)"
        )
        if file:
            self.left_path = file
            self.lbl_left.setText(f"Left: {os.path.basename(file)}")
            self._update_key_columns(file)
            self._recompute_diff()

    def _browse_right(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Open Right Table", "",
            "Table Files (*.csv *.tsv *.xlsx *.parquet *.db *.sqlite *.sqlite3);;CSV/TSV (*.csv *.tsv);;Excel Files (*.xlsx);;Parquet Files (*.parquet);;SQLite Databases (*.db *.sqlite *.sqlite3);;All Files (*.*)"
        )
        if file:
            self.right_path = file
            self.lbl_right.setText(f"Right: {os.path.basename(file)}")
            self._recompute_diff()

    def set_files(self, left_path: str, right_path: str):
        self.left_path = left_path
        self.right_path = right_path
        self.lbl_left.setText(f"Left: {os.path.basename(left_path)}")
        self.lbl_right.setText(f"Right: {os.path.basename(right_path)}")
        self._update_key_columns(left_path)
        self._recompute_diff()

    def _update_key_columns(self, path: str):
        headers, _ = TabularDiffEngine.load_table(path)
        cur = self.combo_key.currentText()
        self.combo_key.blockSignals(True)
        self.combo_key.clear()
        self.combo_key.addItem("(Sequential Row Index)")
        for h in headers:
            self.combo_key.addItem(h)
        # Restore if matches
        idx = self.combo_key.findText(cur)
        if idx != -1:
            self.combo_key.setCurrentIndex(idx)
        self.combo_key.blockSignals(False)

    def _on_key_changed(self, idx: int):
        self._recompute_diff()

    def _recompute_diff(self):
        if not self.left_path or not self.right_path:
            return

        key_col = self.combo_key.currentText()
        if key_col == "(Sequential Row Index)":
            key_col = None

        float_tol = self.spin_tol.value()

        self.diff_result = TabularDiffEngine.compare_tables(
            self.left_path, self.right_path, key_column=key_col, float_tolerance=float_tol
        )

        res = self.diff_result
        self.lbl_stats.setText(
            f"Rows: {res.total_rows} | +{res.added_count} Added | -{res.deleted_count} Deleted | ~{res.modified_count} Modified | = {res.equal_count} Equal"
        )

        self._populate_tables()

    def _populate_tables(self):
        if not self.diff_result:
            return

        res = self.diff_result
        headers = res.headers
        diffs_only = self.chk_diffs_only.isChecked()
        filter_text = self.txt_filter.text().lower()

        # Filter rows
        visible_rows: List[RowDiff] = []
        for r in res.rows:
            if diffs_only and r.status == "equal":
                continue
            if filter_text:
                row_str = " ".join(r.left_cells + r.right_cells).lower()
                if filter_text not in row_str:
                    continue
            visible_rows.append(r)

        # Set up table dimensions
        num_rows = len(visible_rows)
        num_cols = len(headers)

        for tbl in (self.table_left, self.table_right):
            tbl.clear()
            tbl.setRowCount(num_rows)
            tbl.setColumnCount(num_cols)
            tbl.setHorizontalHeaderLabels(headers)

        c_added = QBrush(QColor("#dafbe1"))
        c_deleted = QBrush(QColor("#ffebe9"))
        c_modified = QBrush(QColor("#fff8c5"))

        for r_idx, r in enumerate(visible_rows):
            # Left table row
            for c_idx in range(num_cols):
                val_l = r.left_cells[c_idx] if c_idx < len(r.left_cells) else ""
                item_l = QTableWidgetItem(val_l)

                if r.status == "deleted":
                    item_l.setBackground(c_deleted)
                elif r.status == "modified" and c_idx in r.modified_cols:
                    item_l.setBackground(c_modified)
                    val_r = r.right_cells[c_idx] if c_idx < len(r.right_cells) else ""
                    item_l.setToolTip(f"Modified:\nOriginal: {val_l}\nModified: {val_r}")
                elif r.status == "added":
                    item_l.setText("")  # Empty on left

                self.table_left.setItem(r_idx, c_idx, item_l)

            # Right table row
            for c_idx in range(num_cols):
                val_r = r.right_cells[c_idx] if c_idx < len(r.right_cells) else ""
                item_r = QTableWidgetItem(val_r)

                if r.status == "added":
                    item_r.setBackground(c_added)
                elif r.status == "modified" and c_idx in r.modified_cols:
                    item_r.setBackground(c_modified)
                    val_l = r.left_cells[c_idx] if c_idx < len(r.left_cells) else ""
                    item_r.setToolTip(f"Modified:\nOriginal: {val_l}\nModified: {val_r}")
                elif r.status == "deleted":
                    item_r.setText("")  # Empty on right

                self.table_right.setItem(r_idx, c_idx, item_r)

    def _sync_vscroll_left(self, val):
        if not self._is_syncing_scroll:
            self._is_syncing_scroll = True
            self.table_right.verticalScrollBar().setValue(val)
            self._is_syncing_scroll = False

    def _sync_vscroll_right(self, val):
        if not self._is_syncing_scroll:
            self._is_syncing_scroll = True
            self.table_left.verticalScrollBar().setValue(val)
            self._is_syncing_scroll = False

    def _sync_hscroll_left(self, val):
        if not self._is_syncing_scroll:
            self._is_syncing_scroll = True
            self.table_right.horizontalScrollBar().setValue(val)
            self._is_syncing_scroll = False

    def _sync_hscroll_right(self, val):
        if not self._is_syncing_scroll:
            self._is_syncing_scroll = True
            self.table_left.horizontalScrollBar().setValue(val)
            self._is_syncing_scroll = False
