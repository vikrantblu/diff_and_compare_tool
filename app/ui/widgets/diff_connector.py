"""
Interactive Diff Connector Widget (Light Theme)
Renders clean horizontal alignment bridges for aligned diff blocks
with interactive chunk-transfer action buttons (> and <).
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath
from typing import List
from app.core.diff_engine import DiffChunk


class DiffConnectorWidget(QWidget):
    """Visual bridge connecting Left and Right editors with interactive transfer buttons."""

    transferLeftToRight = Signal(int)
    transferRightToLeft = Signal(int)
    stageHunkRequested = Signal(int)
    discardHunkRequested = Signal(int)
    unstageHunkRequested = Signal(int)

    def __init__(self, left_editor, right_editor, parent=None):
        super().__init__(parent)
        self.left_editor = left_editor
        self.right_editor = right_editor
        self.setFixedWidth(38)
        self.setMouseTracking(True)

        self.chunks: List[DiffChunk] = []
        self.hovered_chunk_idx = -1
        self.hovered_button = None

        # Crisp Light Mode Colors
        self.COLOR_REPLACE = QColor(9, 105, 218, 38)   # Modern Blue
        self.COLOR_DELETE = QColor(209, 36, 47, 38)    # Soft Red
        self.COLOR_INSERT = QColor(46, 160, 67, 38)    # Soft Green

    def set_chunks(self, chunks: List[DiffChunk]):
        self.chunks = chunks
        self.update()

    def _get_line_y(self, editor, line_number: int) -> float:
        doc = editor.document()
        block = doc.findBlockByNumber(line_number)
        if block.isValid():
            return editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top()
        fm = editor.fontMetrics()
        return (line_number * fm.height()) + editor.contentOffset().y()

    def _get_line_height(self, editor) -> float:
        return float(editor.fontMetrics().height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Crisp light background & border
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.setPen(QColor("#d0d7de"))
        painter.drawLine(0, 0, 0, self.height())
        painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

        if not self.chunks:
            return

        w = float(self.width())
        lh = self._get_line_height(self.left_editor)

        for idx, chunk in enumerate(self.chunks):
            if chunk.tag == 'equal':
                continue

            if chunk.tag == 'replace':
                fill_color = self.COLOR_REPLACE
                border_color = QColor("#0969da")
            elif chunk.tag == 'delete':
                fill_color = self.COLOR_DELETE
                border_color = QColor("#cf222e")
            elif chunk.tag == 'insert':
                fill_color = self.COLOR_INSERT
                border_color = QColor("#2da44e")
            else:
                continue

            y_l1 = self._get_line_y(self.left_editor, chunk.left_start)
            y_l2 = self._get_line_y(self.left_editor, chunk.left_end - 1) + lh
            y_r1 = self._get_line_y(self.right_editor, chunk.right_start)
            y_r2 = self._get_line_y(self.right_editor, chunk.right_end - 1) + lh

            if max(y_l2, y_r2) < 0 or min(y_l1, y_r1) > self.height():
                continue

            path = QPainterPath()
            path.moveTo(0, y_l1)
            path.cubicTo(w * 0.5, y_l1, w * 0.5, y_r1, w, y_r1)
            path.lineTo(w, y_r2)
            path.cubicTo(w * 0.5, y_r2, w * 0.5, y_l2, 0, y_l2)
            path.closeSubpath()

            painter.setBrush(fill_color)
            painter.setPen(Qt.NoPen)
            painter.drawPath(path)

            pen = QPen(border_color, 1.0)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)

            top_edge = QPainterPath()
            top_edge.moveTo(0, y_l1)
            top_edge.cubicTo(w * 0.5, y_l1, w * 0.5, y_r1, w, y_r1)
            painter.drawPath(top_edge)

            bot_edge = QPainterPath()
            bot_edge.moveTo(0, y_l2)
            bot_edge.cubicTo(w * 0.5, y_l2, w * 0.5, y_r2, w, y_r2)
            painter.drawPath(bot_edge)

            mid_y = (y_l1 + y_r1) / 2.0
            if 8 < mid_y < self.height() - 8:
                self._draw_action_buttons(painter, idx, mid_y, chunk.tag)

    def _draw_action_buttons(self, painter: QPainter, idx: int, y: float, tag: str):
        cx = self.width() / 2.0
        btn_w, btn_h = 14, 14

        r_ltr = QRectF(cx - btn_w - 1, y - btn_h / 2, btn_w, btn_h)
        r_rtl = QRectF(cx + 1, y - btn_h / 2, btn_w, btn_h)

        is_hover_ltr = (self.hovered_chunk_idx == idx and self.hovered_button == 'ltr')
        is_hover_rtl = (self.hovered_chunk_idx == idx and self.hovered_button == 'rtl')

        if tag in ('replace', 'delete'):
            painter.fillRect(r_ltr, QColor("#0969da") if is_hover_ltr else QColor("#ffffff"))
            painter.setPen(QColor("#0969da") if is_hover_ltr else QColor("#d0d7de"))
            painter.drawRect(r_ltr)
            painter.setPen(QColor("#ffffff") if is_hover_ltr else QColor("#57606a"))
            painter.drawText(r_ltr, Qt.AlignCenter, ">")

        if tag in ('replace', 'insert'):
            painter.fillRect(r_rtl, QColor("#0969da") if is_hover_rtl else QColor("#ffffff"))
            painter.setPen(QColor("#0969da") if is_hover_rtl else QColor("#d0d7de"))
            painter.drawRect(r_rtl)
            painter.setPen(QColor("#ffffff") if is_hover_rtl else QColor("#57606a"))
            painter.drawText(r_rtl, Qt.AlignCenter, "<")

    def mouseMoveEvent(self, event):
        pos = event.position()
        old_hover = (self.hovered_chunk_idx, self.hovered_button)

        self.hovered_chunk_idx = -1
        self.hovered_button = None

        cx = self.width() / 2.0
        btn_w, btn_h = 14, 14

        for idx, chunk in enumerate(self.chunks):
            if chunk.tag == 'equal':
                continue

            y_l1 = self._get_line_y(self.left_editor, chunk.left_start)
            y_r1 = self._get_line_y(self.right_editor, chunk.right_start)
            mid_y = (y_l1 + y_r1) / 2.0

            r_ltr = QRectF(cx - btn_w - 1, mid_y - btn_h / 2, btn_w, btn_h)
            r_rtl = QRectF(cx + 1, mid_y - btn_h / 2, btn_w, btn_h)

            if r_ltr.contains(pos) and chunk.tag in ('replace', 'delete'):
                self.hovered_chunk_idx = idx
                self.hovered_button = 'ltr'
                break
            elif r_rtl.contains(pos) and chunk.tag in ('replace', 'insert'):
                self.hovered_chunk_idx = idx
                self.hovered_button = 'rtl'
                break

        if old_hover != (self.hovered_chunk_idx, self.hovered_button):
            self.setCursor(Qt.PointingHandCursor if self.hovered_button else Qt.ArrowCursor)
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.hovered_chunk_idx != -1:
            if self.hovered_button == 'ltr':
                self.transferLeftToRight.emit(self.hovered_chunk_idx)
            elif self.hovered_button == 'rtl':
                self.transferRightToLeft.emit(self.hovered_chunk_idx)

    def contextMenuEvent(self, event):
        pos = event.position()
        target_idx = -1
        lh = self._get_line_height(self.left_editor)

        for idx, chunk in enumerate(self.chunks):
            if chunk.tag == 'equal':
                continue
            y_l1 = self._get_line_y(self.left_editor, chunk.left_start)
            y_l2 = self._get_line_y(self.left_editor, chunk.left_end - 1) + lh
            y_r1 = self._get_line_y(self.right_editor, chunk.right_start)
            y_r2 = self._get_line_y(self.right_editor, chunk.right_end - 1) + lh
            top_y = min(y_l1, y_r1)
            bot_y = max(y_l2, y_r2)

            if top_y - 4 <= pos.y() <= bot_y + 4:
                target_idx = idx
                break

        if target_idx == -1:
            return

        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 0px;
                font-size: 12px;
            }
            QMenu::item {
                padding: 6px 20px 6px 12px;
            }
            QMenu::item:selected {
                background: #f1f5f9;
                color: #0969da;
            }
        """)

        act_stage = menu.addAction("➕  Stage Hunk to Git Index")
        act_unstage = menu.addAction("↺  Unstage Hunk from Index")
        act_discard = menu.addAction("🗑  Discard Hunk (Revert Working Changes)")
        menu.addSeparator()
        act_ltr = menu.addAction("▶  Copy Left to Right (>)")
        act_rtl = menu.addAction("◀  Copy Right to Left (<)")

        chosen = menu.exec(event.globalPos().toPoint())
        if chosen == act_stage:
            self.stageHunkRequested.emit(target_idx)
        elif chosen == act_unstage:
            self.unstageHunkRequested.emit(target_idx)
        elif chosen == act_discard:
            self.discardHunkRequested.emit(target_idx)
        elif chosen == act_ltr:
            self.transferLeftToRight.emit(target_idx)
        elif chosen == act_rtl:
            self.transferRightToLeft.emit(target_idx)
