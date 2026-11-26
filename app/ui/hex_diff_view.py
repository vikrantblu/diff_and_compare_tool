"""
Memory-Mapped Hex & Binary Inspection Studio (White / Light Theme)
Features:
- Virtualized QTableView + HexTableModel with LRU page caching across multi-GB files.
- Per-byte mismatch highlighting via HexByteDelegate.
- Go to Offset (hex or decimal), Find Hex / ASCII pattern, Swap, Drag & Drop, and Live Data Inspector.
"""

import os
import struct
from collections import OrderedDict
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTableView, QFrame, QSplitter, QHeaderView,
    QLineEdit, QStyledItemDelegate, QStyle
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor, QBrush, QPainter, QFont, QDragEnterEvent, QDropEvent

from app.core.hex_diff import HexDiffEngine, HexDiffSummary, HexRowDiff
from app.ui.styles.icons import get_line_icon


class HexTableModel(QAbstractTableModel):
    """Virtual table model streaming 16-byte rows from HexDiffEngine with a bounded LRU cache."""

    PAGE_SIZE = 128
    MAX_CACHED_PAGES = 16

    def __init__(self, parent=None):
        super().__init__(parent)
        self.left_path: Optional[str] = None
        self.right_path: Optional[str] = None
        self.total_rows = 0
        self.side = "left"
        self._cache: OrderedDict[int, List[HexRowDiff]] = OrderedDict()

    def set_source(self, left_path: Optional[str], right_path: Optional[str], total_rows: int, side: str):
        self.beginResetModel()
        self.left_path = left_path
        self.right_path = right_path
        self.total_rows = total_rows
        self.side = side
        self._cache.clear()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else self.total_rows

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else 3

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return ["Offset", "Hex (16 Bytes)", "ASCII"][section]
        return None

    def get_row_diff(self, row: int) -> Optional[HexRowDiff]:
        if not self.left_path or not self.right_path or row < 0 or row >= self.total_rows:
            return None
        page_idx = row // self.PAGE_SIZE
        if page_idx not in self._cache:
            start_row = page_idx * self.PAGE_SIZE
            rows = HexDiffEngine.read_row_range(self.left_path, self.right_path, start_row, self.PAGE_SIZE)
            self._cache[page_idx] = rows
            while len(self._cache) > self.MAX_CACHED_PAGES:
                self._cache.popitem(last=False)
        else:
            self._cache.move_to_end(page_idx)
        page_rows = self._cache.get(page_idx, [])
        local_idx = row - (page_idx * self.PAGE_SIZE)
        if 0 <= local_idx < len(page_rows):
            return page_rows[local_idx]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        rd = self.get_row_diff(index.row())
        if not rd:
            return None
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0:
                return f"{rd.offset:08X}"
            elif col == 1:
                return rd.left_hex if self.side == "left" else rd.right_hex
            elif col == 2:
                return rd.left_ascii if self.side == "left" else rd.right_ascii
        elif role == Qt.UserRole:
            return rd
        elif role == Qt.BackgroundRole:
            if rd.mismatched_byte_indices or rd.is_left_only or rd.is_right_only:
                return QBrush(QColor("#fffbeb"))
        return None


class HexByteDelegate(QStyledItemDelegate):
    """Paints individual differing bytes inside the Hex & ASCII columns with crisp red highlights."""

    def paint(self, painter: QPainter, option, index):
        rd: Optional[HexRowDiff] = index.data(Qt.UserRole)
        col = index.column()
        if not rd or col not in (1, 2) or not rd.mismatched_byte_indices:
            super().paint(painter, option, index)
            return

        painter.save()
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#dbeafe"))
        else:
            painter.fillRect(option.rect, QColor("#fffbeb"))

        font = QFont("Cascadia Code", 10)
        font.setStyleHint(QFont.Monospace)
        painter.setFont(font)
        fm = painter.fontMetrics()
        char_w = fm.horizontalAdvance("0")
        x = option.rect.x() + 6
        y = option.rect.y() + (option.rect.height() + fm.ascent() - fm.descent()) // 2

        if col == 1:
            side_bytes = rd.left_bytes if index.model().side == "left" else rd.right_bytes
            for idx, b in enumerate(side_bytes):
                if idx == 8:
                    x += char_w  # mid-row spacer after 8 bytes
                token = f"{b:02X}"
                token_w = char_w * 2
                if idx in rd.mismatched_byte_indices:
                    painter.fillRect(x - 1, option.rect.y() + 2, token_w + 2, option.rect.height() - 4, QColor("#fecaca"))
                    painter.setPen(QColor("#b91c1c"))
                else:
                    painter.setPen(QColor("#0f172a"))
                painter.drawText(x, y, token)
                x += token_w + char_w
        else:
            ascii_str = rd.left_ascii if index.model().side == "left" else rd.right_ascii
            for idx, ch in enumerate(ascii_str):
                if idx in rd.mismatched_byte_indices:
                    painter.fillRect(x, option.rect.y() + 2, char_w, option.rect.height() - 4, QColor("#fecaca"))
                    painter.setPen(QColor("#b91c1c"))
                else:
                    painter.setPen(QColor("#334155"))
                painter.drawText(x, y, ch)
                x += char_w

        painter.restore()


class HexDiffView(QWidget):
    """Studio for virtualized side-by-side binary and hex comparison."""

    def __init__(self):
        super().__init__()
        self.left_path: Optional[str] = None
        self.right_path: Optional[str] = None
        self.summary: Optional[HexDiffSummary] = None
        self.cur_diff_index = -1
        self._is_syncing_scroll = False
        self._last_find_offset = -1
        self.setAcceptDrops(True)

        self.model_left = HexTableModel(self)
        self.model_right = HexTableModel(self)

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

        self.btn_left = QPushButton(" Browse Left Binary...")
        self.btn_left.setIcon(get_line_icon("folder", "#0969da"))
        self.btn_left.setFixedHeight(30)
        self.btn_left.clicked.connect(self._browse_left)
        self.lbl_left = QLabel("Left: (None)")
        self.lbl_left.setStyleSheet("color: #475569; font-weight: 600; padding: 4px 8px; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px;")

        self.btn_swap = QPushButton(" Swap")
        self.btn_swap.setIcon(get_line_icon("swap", "#1e293b"))
        self.btn_swap.setFixedHeight(30)
        self.btn_swap.clicked.connect(self._swap_files)

        self.btn_right = QPushButton(" Browse Right Binary...")
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

        self.txt_offset = QLineEdit()
        self.txt_offset.setPlaceholderText("Go to Offset (0x1A0)")
        self.txt_offset.setFixedWidth(145)
        self.txt_offset.setFixedHeight(30)
        self.txt_offset.returnPressed.connect(self._jump_to_offset)
        cb_layout.addWidget(self.txt_offset)

        self.btn_goto = QPushButton("Go")
        self.btn_goto.setFixedHeight(30)
        self.btn_goto.clicked.connect(self._jump_to_offset)
        cb_layout.addWidget(self.btn_goto)

        self.txt_find_hex = QLineEdit()
        self.txt_find_hex.setPlaceholderText("Find ASCII or hex:FF D8")
        self.txt_find_hex.setFixedWidth(175)
        self.txt_find_hex.setFixedHeight(30)
        self.txt_find_hex.returnPressed.connect(self._find_next_pattern)
        cb_layout.addWidget(self.txt_find_hex)

        self.btn_find_hex = QPushButton("Find")
        self.btn_find_hex.setIcon(get_line_icon("search", "#1e293b"))
        self.btn_find_hex.setFixedHeight(30)
        self.btn_find_hex.clicked.connect(self._find_next_pattern)
        cb_layout.addWidget(self.btn_find_hex)

        self.lbl_stats = QLabel("● Ready")
        self.lbl_stats.setStyleSheet("color: #0969da; font-weight: 600; padding: 4px 10px; background: #e0f2fe; border: 1px solid #bae6fd; border-radius: 12px; font-size: 11px;")
        cb_layout.addWidget(self.lbl_stats)

        cb_layout.addStretch()

        self.btn_refresh = QPushButton(" Refresh")
        self.btn_refresh.setIcon(get_line_icon("refresh", "#24292f"))
        self.btn_refresh.setFixedHeight(30)
        self.btn_refresh.clicked.connect(self._recompute_diff)
        cb_layout.addWidget(self.btn_refresh)

        layout.addWidget(cmd_bar)

        # 3. Synchronized Split Virtualized Hex Tables
        self.splitter = QSplitter(Qt.Horizontal)

        self.table_left = self._create_hex_table(self.model_left)
        self.table_right = self._create_hex_table(self.model_right)

        self.table_left.verticalScrollBar().valueChanged.connect(self._sync_scroll_left)
        self.table_right.verticalScrollBar().valueChanged.connect(self._sync_scroll_right)
        self.table_left.selectionModel().currentRowChanged.connect(self._on_row_selected)
        self.table_right.selectionModel().currentRowChanged.connect(self._on_row_selected)

        self.splitter.addWidget(self.table_left)
        self.splitter.addWidget(self.table_right)
        self.splitter.setSizes([600, 600])

        layout.addWidget(self.splitter, 1)

        # 4. Bottom Live Data Inspector Bar
        inspector = QFrame()
        inspector.setFixedHeight(32)
        inspector.setStyleSheet("background-color: #f8fafc; border-top: 1px solid #cbd5e1;")
        ins_layout = QHBoxLayout(inspector)
        ins_layout.setContentsMargins(10, 0, 10, 0)
        self.lbl_inspector = QLabel("Data Inspector: Select any row to decode uint8 / int16 / uint32 / float32 (LE & BE)")
        self.lbl_inspector.setStyleSheet("font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 11px; color: #334155; border: none; background: transparent;")
        ins_layout.addWidget(self.lbl_inspector)
        layout.addWidget(inspector)

    def _create_hex_table(self, model: HexTableModel) -> QTableView:
        tbl = QTableView()
        tbl.setModel(model)
        tbl.setItemDelegate(HexByteDelegate(tbl))
        tbl.setSelectionBehavior(QTableView.SelectRows)
        tbl.setSelectionMode(QTableView.SingleSelection)
        tbl.verticalHeader().setVisible(False)
        tbl.verticalHeader().setDefaultSectionSize(22)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        tbl.setStyleSheet("""
            QTableView {
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
                self.lbl_left.setText(f"Left: {os.path.basename(paths[0])} ({os.path.getsize(paths[0]):,} B)")
            else:
                self.right_path = paths[0]
                self.lbl_right.setText(f"Right: {os.path.basename(paths[0])} ({os.path.getsize(paths[0]):,} B)")
            self._recompute_diff()

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

    def _swap_files(self):
        self.left_path, self.right_path = self.right_path, self.left_path
        self.lbl_left.setText(f"Left: {os.path.basename(self.left_path)}" if self.left_path else "Left: (None)")
        self.lbl_right.setText(f"Right: {os.path.basename(self.right_path)}" if self.right_path else "Right: (None)")
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
            self.lbl_stats.setText("Failed to compare binary files")
            return

        s = self.summary
        trunc_note = "+" if s.mismatched_rows_truncated else ""
        self.lbl_stats.setText(
            f"Total: {s.total_rows:,} rows | Differing: {s.differing_bytes_count:,} B ({s.difference_percentage:.2f}%) | {len(s.mismatched_rows):,}{trunc_note} mismatch rows"
        )
        self.cur_diff_index = -1
        self._last_find_offset = -1
        self.model_left.set_source(self.left_path, self.right_path, s.total_rows, "left")
        self.model_right.set_source(self.left_path, self.right_path, s.total_rows, "right")
        self.table_left.setColumnWidth(2, 145)
        self.table_right.setColumnWidth(2, 145)

    def _jump_to_row(self, row: int):
        if not self.summary or self.summary.total_rows == 0:
            return
        clamped = max(0, min(self.summary.total_rows - 1, row))
        idx_l = self.model_left.index(clamped, 0)
        idx_r = self.model_right.index(clamped, 0)
        self.table_left.selectRow(clamped)
        self.table_right.selectRow(clamped)
        self.table_left.scrollTo(idx_l, QTableView.PositionAtCenter)
        self.table_right.scrollTo(idx_r, QTableView.PositionAtCenter)

    def _jump_to_offset(self):
        txt = self.txt_offset.text().strip()
        if not txt or not self.summary:
            return
        try:
            offset = int(txt, 16) if txt.lower().startswith("0x") else int(txt, 16 if any(c in "abcdefABCDEF" for c in txt) else 10)
            row = offset // HexDiffEngine.BYTES_PER_ROW
            self._jump_to_row(row)
        except ValueError:
            self.lbl_inspector.setText(f"Invalid offset: '{txt}' (use e.g. 0x1A0 or 416)")

    def _find_next_pattern(self):
        raw_q = self.txt_find_hex.text().strip()
        if not raw_q or not self.left_path:
            return
        if raw_q.lower().startswith("hex:"):
            try:
                needle = bytes.fromhex(raw_q[4:].strip())
            except ValueError:
                self.lbl_inspector.setText("Invalid hex pattern (use e.g. hex:FF D8)")
                return
        else:
            needle = raw_q.encode("utf-8", errors="replace")

        pos = HexDiffEngine.find_pattern(self.left_path, needle, start_offset=self._last_find_offset + 1)
        if pos is None and self._last_find_offset >= 0:
            pos = HexDiffEngine.find_pattern(self.left_path, needle, start_offset=0)
        if pos is not None:
            self._last_find_offset = pos
            row = pos // HexDiffEngine.BYTES_PER_ROW
            self._jump_to_row(row)
            self.lbl_inspector.setText(f"Pattern found in Left at offset 0x{pos:08X} (row {row})")
        else:
            self.lbl_inspector.setText("Pattern not found in Left binary.")

    def _on_row_selected(self, current: QModelIndex, _prev: QModelIndex):
        if not current.isValid():
            return
        rd = self.model_left.get_row_diff(current.row())
        if not rd:
            return
        b = rd.left_bytes or rd.right_bytes
        if not b:
            return
        u8 = b[0]
        i16 = struct.unpack("<h", b[:2])[0] if len(b) >= 2 else None
        u32 = struct.unpack("<I", b[:4])[0] if len(b) >= 4 else None
        f32 = struct.unpack("<f", b[:4])[0] if len(b) >= 4 else None
        parts = [f"Offset 0x{rd.offset:08X}", f"uint8={u8}"]
        if i16 is not None:
            parts.append(f"int16(LE)={i16}")
        if u32 is not None:
            parts.append(f"uint32(LE)={u32}")
        if f32 is not None:
            parts.append(f"float32(LE)={f32:.4g}")
        self.lbl_inspector.setText("Data Inspector:  " + "  |  ".join(parts))

    def _next_diff(self):
        if not self.summary or not self.summary.mismatched_rows:
            return
        self.cur_diff_index = (self.cur_diff_index + 1) % len(self.summary.mismatched_rows)
        self._jump_to_row(self.summary.mismatched_rows[self.cur_diff_index])

    def _prev_diff(self):
        if not self.summary or not self.summary.mismatched_rows:
            return
        self.cur_diff_index = (self.cur_diff_index - 1 + len(self.summary.mismatched_rows)) % len(self.summary.mismatched_rows)
        self._jump_to_row(self.summary.mismatched_rows[self.cur_diff_index])

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
