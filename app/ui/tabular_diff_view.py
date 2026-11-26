"""
Tabular and Spreadsheet Comparison Studio (CSV, TSV, Excel, Parquet, SQLite) — White / Light Theme
Features:
- Cached parsed tables (instant key/tolerance switching without re-reading disk).
- Sheet / SQLite Table selector dropdowns.
- Keyed row alignment + float tolerance + duplicate-key / truncation reporting.
- Read-only synchronized grids with Prev/Next Diff Row, Swap, Export Diff CSV, and Drag & Drop.
"""

import csv
import os
from typing import Optional, List, Tuple
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QLineEdit, QFrame, QHeaderView, QSplitter, QDoubleSpinBox, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QDragEnterEvent, QDropEvent

from app.core.tabular_diff import TabularDiffEngine, TabularDiffResult, RowDiff
from app.ui.styles.icons import get_line_icon


class TabularDiffView(QWidget):
    """Studio for comparing tabular data (CSV, TSV, Excel, Parquet, SQLite)."""

    def __init__(self):
        super().__init__()
        self.left_path: Optional[str] = None
        self.right_path: Optional[str] = None
        self._left_cache: Optional[Tuple[List[str], List[List[str]]]] = None
        self._right_cache: Optional[Tuple[List[str], List[List[str]]]] = None
        self.diff_result: Optional[TabularDiffResult] = None
        self._is_syncing_scroll = False
        self._cur_diff_row_pos = -1
        self.setAcceptDrops(True)

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
        fb_layout.setSpacing(8)

        self.btn_left = QPushButton(" Browse Left Table...")
        self.btn_left.setIcon(get_line_icon("folder", "#0969da"))
        self.btn_left.setFixedHeight(30)
        self.btn_left.clicked.connect(self._browse_left)
        self.lbl_left = QLabel("Left: (None)")
        self.lbl_left.setStyleSheet("color: #475569; font-weight: 600; padding: 4px 8px; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px;")

        self.btn_swap = QPushButton(" Swap")
        self.btn_swap.setIcon(get_line_icon("swap", "#1e293b"))
        self.btn_swap.setFixedHeight(30)
        self.btn_swap.clicked.connect(self._swap_tables)

        self.btn_right = QPushButton(" Browse Right Table...")
        self.btn_right.setIcon(get_line_icon("folder", "#16a34a"))
        self.btn_right.setFixedHeight(30)
        self.btn_right.clicked.connect(self._browse_right)
        self.lbl_right = QLabel("Right: (None)")
        self.lbl_right.setStyleSheet("color: #475569; font-weight: 600; padding: 4px 8px; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px;")

        fb_layout.addWidget(self.btn_left)
        fb_layout.addWidget(self.lbl_left, 1)
        fb_layout.addWidget(self.btn_swap)
        fb_layout.addWidget(self.btn_right)
        fb_layout.addWidget(self.lbl_right, 1)

        layout.addWidget(file_bar)

        # 2. Command Bar
        cmd_bar = QFrame()
        cmd_bar.setFixedHeight(46)
        cmd_bar.setStyleSheet("background-color: #ffffff; border-bottom: 1.5px solid #cbd5e1; padding: 2px 4px;")
        cb_layout = QHBoxLayout(cmd_bar)
        cb_layout.setContentsMargins(10, 0, 10, 0)
        cb_layout.setSpacing(6)

        self.lbl_sheet = QLabel("Sheet/Table:")
        self.lbl_sheet.setStyleSheet("font-weight: 600; color: #334155; border: none; background: transparent;")
        self.lbl_sheet.setVisible(False)
        cb_layout.addWidget(self.lbl_sheet)

        self.combo_sheet = QComboBox()
        self.combo_sheet.setFixedHeight(30)
        self.combo_sheet.setVisible(False)
        self.combo_sheet.currentIndexChanged.connect(self._reload_and_diff)
        cb_layout.addWidget(self.combo_sheet)

        lbl_pk = QLabel("Primary Key:")
        lbl_pk.setStyleSheet("font-weight: 600; color: #334155; border: none; background: transparent;")
        cb_layout.addWidget(lbl_pk)
        self.combo_key = QComboBox()
        self.combo_key.addItem("(Sequential Row Index)")
        self.combo_key.setFixedHeight(30)
        self.combo_key.currentIndexChanged.connect(self._on_key_changed)
        cb_layout.addWidget(self.combo_key)

        lbl_tol = QLabel("Float Tol:")
        lbl_tol.setStyleSheet("font-weight: 600; color: #334155; margin-left: 2px; border: none; background: transparent;")
        cb_layout.addWidget(lbl_tol)
        self.spin_tol = QDoubleSpinBox()
        self.spin_tol.setRange(0.0, 1000000.0)
        self.spin_tol.setDecimals(4)
        self.spin_tol.setSingleStep(0.001)
        self.spin_tol.setValue(0.0)
        self.spin_tol.setFixedHeight(30)
        self.spin_tol.setFixedWidth(80)
        self.spin_tol.setToolTip("Numerical comparison tolerance")
        self.spin_tol.valueChanged.connect(self._recompute_diff_from_cache)
        cb_layout.addWidget(self.spin_tol)

        self.btn_prev_diff = QPushButton()
        self.btn_prev_diff.setIcon(get_line_icon("arrow-up", "#1e293b"))
        self.btn_prev_diff.setFixedSize(28, 28)
        self.btn_prev_diff.setToolTip("Previous Different Row")
        self.btn_prev_diff.clicked.connect(self._prev_diff_row)
        cb_layout.addWidget(self.btn_prev_diff)

        self.btn_next_diff = QPushButton()
        self.btn_next_diff.setIcon(get_line_icon("arrow-down", "#1e293b"))
        self.btn_next_diff.setFixedSize(28, 28)
        self.btn_next_diff.setToolTip("Next Different Row")
        self.btn_next_diff.clicked.connect(self._next_diff_row)
        cb_layout.addWidget(self.btn_next_diff)

        self.chk_diffs_only = QCheckBox("Diffs Only")
        self.chk_diffs_only.setFixedHeight(30)
        self.chk_diffs_only.toggled.connect(self._populate_tables)
        cb_layout.addWidget(self.chk_diffs_only)

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filter cells...")
        self.txt_filter.setFixedWidth(140)
        self.txt_filter.setFixedHeight(30)
        self.txt_filter.setClearButtonEnabled(True)
        self.txt_filter.textChanged.connect(self._populate_tables)
        cb_layout.addWidget(self.txt_filter)

        self.lbl_stats = QLabel("● Ready")
        self.lbl_stats.setStyleSheet("color: #0969da; font-weight: 600; padding: 4px 10px; background: #e0f2fe; border: 1px solid #bae6fd; border-radius: 12px; font-size: 11px;")
        cb_layout.addWidget(self.lbl_stats)

        cb_layout.addStretch()

        self.btn_export = QPushButton(" Export Diff CSV")
        self.btn_export.setIcon(get_line_icon("download", "#1e293b"))
        self.btn_export.setFixedHeight(30)
        self.btn_export.clicked.connect(self._export_diff_csv)
        cb_layout.addWidget(self.btn_export)

        self.btn_refresh = QPushButton(" Refresh")
        self.btn_refresh.setIcon(get_line_icon("refresh", "#24292f"))
        self.btn_refresh.setFixedHeight(30)
        self.btn_refresh.clicked.connect(self._reload_and_diff)
        cb_layout.addWidget(self.btn_refresh)

        layout.addWidget(cmd_bar)

        # 3. Synchronized Dual Tables
        self.splitter = QSplitter(Qt.Horizontal)

        self.table_left = QTableWidget()
        self.table_right = QTableWidget()

        self._style_table(self.table_left)
        self._style_table(self.table_right)

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
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
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

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile() and os.path.isfile(u.toLocalFile())]
        if len(paths) >= 2:
            self.set_files(paths[0], paths[1])
        elif len(paths) == 1:
            if not self.left_path:
                self.left_path = paths[0]
                self.lbl_left.setText(f"Left: {os.path.basename(paths[0])}")
                self._refresh_sheet_selector(paths[0])
                self._update_key_columns(paths[0])
            else:
                self.right_path = paths[0]
                self.lbl_right.setText(f"Right: {os.path.basename(paths[0])}")
            self._reload_and_diff()

    def _browse_left(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Open Left Table", "",
            "Table Files (*.csv *.tsv *.xlsx *.parquet *.db *.sqlite *.sqlite3);;All Files (*.*)"
        )
        if file:
            self.left_path = file
            self.lbl_left.setText(f"Left: {os.path.basename(file)}")
            self._refresh_sheet_selector(file)
            self._update_key_columns(file)
            self._reload_and_diff()

    def _browse_right(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Open Right Table", "",
            "Table Files (*.csv *.tsv *.xlsx *.parquet *.db *.sqlite *.sqlite3);;All Files (*.*)"
        )
        if file:
            self.right_path = file
            self.lbl_right.setText(f"Right: {os.path.basename(file)}")
            if not self.combo_sheet.isVisible():
                self._refresh_sheet_selector(file)
            self._reload_and_diff()

    def set_files(self, left_path: str, right_path: str):
        self.left_path = left_path
        self.right_path = right_path
        self.lbl_left.setText(f"Left: {os.path.basename(left_path)}")
        self.lbl_right.setText(f"Right: {os.path.basename(right_path)}")
        self._refresh_sheet_selector(left_path)
        self._update_key_columns(left_path)
        self._reload_and_diff()

    def _swap_tables(self):
        if not self.left_path and not self.right_path:
            return
        self.left_path, self.right_path = self.right_path, self.left_path
        self._left_cache, self._right_cache = self._right_cache, self._left_cache
        self.lbl_left.setText(f"Left: {os.path.basename(self.left_path)}" if self.left_path else "Left: (None)")
        self.lbl_right.setText(f"Right: {os.path.basename(self.right_path)}" if self.right_path else "Right: (None)")
        self._recompute_diff_from_cache()

    def _refresh_sheet_selector(self, path: str):
        ext = os.path.splitext(path or "")[1].lower()
        names: List[str] = []
        if ext in (".xlsx", ".xlsm", ".xltx"):
            names = TabularDiffEngine.list_excel_sheets(path)
        elif ext in (".db", ".sqlite", ".sqlite3"):
            names = TabularDiffEngine.list_sqlite_tables(path)

        self.combo_sheet.blockSignals(True)
        self.combo_sheet.clear()
        if names:
            for n in names:
                self.combo_sheet.addItem(n)
            self.lbl_sheet.setVisible(True)
            self.combo_sheet.setVisible(True)
        else:
            self.lbl_sheet.setVisible(False)
            self.combo_sheet.setVisible(False)
        self.combo_sheet.blockSignals(False)

    def _selected_sheet_or_table(self) -> Optional[str]:
        if self.combo_sheet.isVisible() and self.combo_sheet.count() > 0:
            return self.combo_sheet.currentText()
        return None

    def _update_key_columns(self, path: str):
        headers, _ = TabularDiffEngine.load_table(path, table_name=self._selected_sheet_or_table())
        cur = self.combo_key.currentText()
        self.combo_key.blockSignals(True)
        self.combo_key.clear()
        self.combo_key.addItem("(Sequential Row Index)")
        for h in headers:
            self.combo_key.addItem(h)
        idx = self.combo_key.findText(cur)
        if idx != -1:
            self.combo_key.setCurrentIndex(idx)
        self.combo_key.blockSignals(False)

    def _on_key_changed(self, idx: int):
        self._recompute_diff_from_cache()

    def _recompute_diff(self):
        self._reload_and_diff()

    def _reload_and_diff(self):
        if not self.left_path or not self.right_path:
            return
        sheet = self._selected_sheet_or_table()
        self._left_cache = TabularDiffEngine.load_table(self.left_path, table_name=sheet)
        self._right_cache = TabularDiffEngine.load_table(self.right_path, table_name=sheet)
        self._recompute_diff_from_cache()

    def _recompute_diff_from_cache(self):
        if not self._left_cache or not self._right_cache:
            if self.left_path and self.right_path:
                self._reload_and_diff()
            return

        key_col = self.combo_key.currentText()
        if key_col == "(Sequential Row Index)":
            key_col = None

        l_headers, l_rows = self._left_cache
        r_headers, r_rows = self._right_cache

        self.diff_result = TabularDiffEngine.compare_parsed_tables(
            l_headers, l_rows, r_headers, r_rows,
            key_column=key_col,
            float_tolerance=self.spin_tol.value()
        )

        res = self.diff_result
        extras = []
        if res.duplicate_keys_left or res.duplicate_keys_right:
            extras.append(f"Dup keys L:{res.duplicate_keys_left}/R:{res.duplicate_keys_right}")
        if res.truncated:
            extras.append("Capped at 50k rows")
        extra_str = f" | {' · '.join(extras)}" if extras else ""

        self.lbl_stats.setText(
            f"Rows: {res.total_rows:,} | +{res.added_count} Added | -{res.deleted_count} Deleted | ~{res.modified_count} Modified | = {res.equal_count} Equal{extra_str}"
        )
        self._cur_diff_row_pos = -1
        self._populate_tables()

    def _populate_tables(self):
        if not self.diff_result:
            return

        res = self.diff_result
        headers = res.headers
        diffs_only = self.chk_diffs_only.isChecked()
        filter_text = self.txt_filter.text().lower()

        visible_rows: List[RowDiff] = []
        for r in res.rows:
            if diffs_only and r.status == "equal":
                continue
            if filter_text:
                row_str = " ".join(r.left_cells + r.right_cells).lower()
                if filter_text not in row_str:
                    continue
            visible_rows.append(r)

        num_rows = len(visible_rows)
        num_cols = len(headers)

        self._visible_rows = visible_rows
        for tbl in (self.table_left, self.table_right):
            tbl.setUpdatesEnabled(False)
            tbl.clear()
            tbl.setRowCount(num_rows)
            tbl.setColumnCount(num_cols)
            tbl.setHorizontalHeaderLabels(headers)

        c_added = QBrush(QColor("#dafbe1"))
        c_deleted = QBrush(QColor("#ffebe9"))
        c_modified = QBrush(QColor("#fff8c5"))

        for r_idx, r in enumerate(visible_rows):
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
                    item_l.setText("")

                self.table_left.setItem(r_idx, c_idx, item_l)

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
                    item_r.setText("")

                self.table_right.setItem(r_idx, c_idx, item_r)

        for tbl in (self.table_left, self.table_right):
            tbl.setUpdatesEnabled(True)

    def _next_diff_row(self):
        rows = getattr(self, "_visible_rows", [])
        diff_indices = [i for i, r in enumerate(rows) if r.status != "equal"]
        if not diff_indices:
            return
        self._cur_diff_row_pos = (self._cur_diff_row_pos + 1) % len(diff_indices)
        target = diff_indices[self._cur_diff_row_pos]
        self.table_left.selectRow(target)
        self.table_right.selectRow(target)
        self.table_left.scrollToItem(self.table_left.item(target, 0))

    def _prev_diff_row(self):
        rows = getattr(self, "_visible_rows", [])
        diff_indices = [i for i, r in enumerate(rows) if r.status != "equal"]
        if not diff_indices:
            return
        self._cur_diff_row_pos = (self._cur_diff_row_pos - 1 + len(diff_indices)) % len(diff_indices)
        target = diff_indices[self._cur_diff_row_pos]
        self.table_left.selectRow(target)
        self.table_right.selectRow(target)
        self.table_left.scrollToItem(self.table_left.item(target, 0))

    def _export_diff_csv(self):
        if not self.diff_result:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Table Diff Summary", "table_diff.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Status", "Key"] + [f"{h} (Left)" for h in self.diff_result.headers] + [f"{h} (Right)" for h in self.diff_result.headers])
                for r in self.diff_result.rows:
                    if r.status != "equal":
                        writer.writerow([r.status.upper(), r.row_key] + r.left_cells + r.right_cells)
            QMessageBox.information(self, "Exported", f"Table diff exported to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

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
