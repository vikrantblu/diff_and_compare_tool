"""
Modern High-Performance Code Editor Widget (Light / White Theme Optimized)
Features:
- Crisp white canvas with high-contrast typography.
- Horizontal Alignment with clean spacer rows.
- Non-destructive full-width line tinting + intraline character-level highlighting via ExtraSelections.
- True source line numbers in gutter.
- Overview diff minimap / ruler along the outer scrollbar border with colored tick marks:
  * Additions (green #1a7f37)
  * Deletions (red #cf222e)
  * Modifications (blue #0969da)
  * Conflicts (orange #d97706)
  * Moved blocks (purple #8250df)
- Tooltip inspection and instant click-to-jump navigation.
- Windowed View Virtualization for files exceeding 3,000+ or 100,000+ lines.
"""

from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget, QToolTip, QMenu
from PySide6.QtCore import Qt, QRect, QSize, Signal, QTimer, QPoint
from PySide6.QtGui import (
    QColor, QPainter, QTextFormat, QFont, QPen, QTextCursor,
    QPainterPath, QKeySequence, QAction
)
from typing import Dict, List, Tuple, Set, Optional


class LineNumberGutter(QWidget):
    """Modern line number and change marker gutter."""
    def __init__(self, editor: 'ModernCodeEditor'):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)


class OverviewRuler(QWidget):
    """
    Overview strip along the outer scrollbar border with colored tick marks representing
    additions (green), deletions (red), modifications (blue), conflicts (orange), and moved blocks.
    Clicking any tick jumps instantly to that delta.
    """
    def __init__(self, editor: 'ModernCodeEditor'):
        super().__init__(editor)
        self.editor = editor
        self.setFixedWidth(16)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.diff_lines: Dict[int, str] = {}
        self.tick_info: Dict[int, Tuple[str, str]] = {}  # line_idx -> (color_hex, label)
        self.total_lines_count = 1

    def set_diff_lines(self, diff_lines: Dict[int, str], tick_info: Optional[Dict[int, Tuple[str, str]]] = None, total_lines: Optional[int] = None):
        self.diff_lines = diff_lines
        if tick_info:
            self.tick_info = tick_info
        else:
            self.tick_info = {}
            for line, color in diff_lines.items():
                label = "Modification"
                if color == "#1a7f37": label = "Addition"
                elif color == "#cf222e": label = "Deletion"
                elif color == "#d97706" or color == "#f85149": label = "Conflict"
                elif color == "#8250df": label = "Moved"
                self.tick_info[line] = (color, label)
        if total_lines:
            self.total_lines_count = max(1, total_lines)
        else:
            self.total_lines_count = max(1, self.editor.get_total_line_count())
        self.update()

    def _get_target_line(self, y: int) -> int:
        h = max(1, self.height())
        ratio = max(0.0, min(1.0, y / h))
        return int(ratio * self.total_lines_count)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            target_line = self._get_target_line(int(event.position().y()))
            # Look for nearest diff tick within a small neighborhood
            best_line = target_line
            min_dist = float("inf")
            neighborhood = max(5, int(self.total_lines_count * 0.03))
            for tick_line in self.tick_info.keys():
                dist = abs(tick_line - target_line)
                if dist < min_dist and dist <= neighborhood:
                    min_dist = dist
                    best_line = tick_line
            self.editor.jump_to_line(best_line)

    def mouseMoveEvent(self, event):
        target_line = self._get_target_line(int(event.position().y()))
        # Check if mouse is hovering near a tick
        neighborhood = max(3, int(self.total_lines_count * 0.02))
        closest = None
        min_dist = float("inf")
        for tick_line, (color, label) in self.tick_info.items():
            dist = abs(tick_line - target_line)
            if dist < min_dist and dist <= neighborhood:
                min_dist = dist
                closest = (tick_line, label)

        if closest:
            tick_line, label = closest
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"Line {tick_line + 1}: {label}\nClick to jump",
                self
            )
        else:
            QToolTip.hideText()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#f8fafc"))
        painter.setPen(QColor("#cbd5e1"))
        painter.drawLine(0, 0, 0, self.height())
        painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

        total = max(1, self.total_lines_count)
        h = max(1, self.height())

        # Render ticks
        for line_idx, (color_hex, label) in self.tick_info.items():
            y = int((line_idx / total) * h)
            painter.fillRect(2, max(0, y - 1), self.width() - 4, 3, QColor(color_hex))


class ModernCodeEditor(QPlainTextEdit):
    """
    Production-grade Code Editor with crisp light / white theme styling,
    Overview Minimap Ruler, and Windowed Virtual Scrolling for ultra-large files (100k+ lines).
    """

    liveTextChanged = Signal()
    scrolled = Signal(int)
    alignWithRequested = Signal(int)       # 1-indexed real file line
    alignmentTargetClicked = Signal(int)   # 1-indexed line clicked in alignment mode
    clearAlignmentRequested = Signal()

    VIRTUALIZATION_THRESHOLD = 3000
    WINDOW_SIZE = 300

    def __init__(self, parent=None):
        super().__init__(parent)

        # Virtualization data & state initialized before any signal or subwidget
        self._is_virtualized = False
        self._virtual_lines: List[str] = []
        self._virtual_spacers: Set[int] = set()
        self._virtual_line_numbers: Dict[int, int] = {}
        self._window_start = 0
        self._cached_line_decorations: Dict[int, str] = {}
        self._cached_char_decorations: Dict[int, List[Tuple[int, int, str]]] = {}

        # Alignment metadata
        self.spacer_lines: Set[int] = set()
        self.real_line_numbers: Dict[int, int] = {}
        self.line_markers: Dict[int, Tuple[str, str]] = {}
        self._is_syncing_scroll = False
        self._programmatic_change = False
        self._diff_extra_selections: List[QTextEdit.ExtraSelection] = []
        self._search_extra_selections: List[QTextEdit.ExtraSelection] = []

        self.gutter = LineNumberGutter(self)
        self.overview_ruler = OverviewRuler(self)

        # Reactive debounce timer for live editing
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(200)
        self.debounce_timer.timeout.connect(self.liveTextChanged.emit)

        self.textChanged.connect(self._on_text_changed)
        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

        # Styling & Font
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        
        # Clean white canvas
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #ffffff;
                color: #1f2328;
                border: none;
                padding-left: 2px;
                selection-background-color: #b6e3ff;
                selection-color: #0969da;
            }
        """)

        self._update_gutter_width(0)

    def get_total_line_count(self) -> int:
        if self._is_virtualized:
            return len(self._virtual_lines)
        return self.blockCount()

    def _on_text_changed(self):
        if not self._programmatic_change:
            self.debounce_timer.start()

    def _on_scroll(self, val):
        if not self._is_syncing_scroll:
            if self._is_virtualized:
                # Sliding window reload
                self._update_virtual_window(val)
            self.scrolled.emit(val)

    def set_sync_scroll_value(self, val):
        self._is_syncing_scroll = True
        self.verticalScrollBar().setValue(val)
        if self._is_virtualized:
            self._update_virtual_window(val)
        self._is_syncing_scroll = False

    def gutter_width(self) -> int:
        total = self.get_total_line_count()
        digits = max(1, len(str(total)))
        char_width = self.fontMetrics().horizontalAdvance('9')
        return 18 + digits * char_width + 12

    def _update_gutter_width(self, _):
        self.setViewportMargins(self.gutter_width(), 0, self.overview_ruler.width(), 0)

    def _update_gutter(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))
        self.overview_ruler.setGeometry(
            QRect(cr.right() - self.overview_ruler.width(), cr.top(), self.overview_ruler.width(), cr.height())
        )

    def set_aligned_lines(self, lines: List[str], spacers: Set[int], line_numbers: Dict[int, int]):
        total_lines = len(lines)
        if total_lines > self.VIRTUALIZATION_THRESHOLD:
            # Enable View Virtualization
            self._is_virtualized = True
            self._virtual_lines = lines
            self._virtual_spacers = set(spacers)
            self._virtual_line_numbers = dict(line_numbers)
            self._window_start = 0

            # Set virtual scrollbar range to cover all lines
            sb = self.verticalScrollBar()
            sb.setRange(0, max(0, total_lines - 30))
            self._load_virtual_slice(0)
            self.overview_ruler.total_lines_count = total_lines
            self.overview_ruler.update()
            return

        # Standard in-memory mode for normal files
        self._is_virtualized = False
        self._virtual_lines = []
        new_text = '\n'.join(lines)
        if self.toPlainText() == new_text:
            self.spacer_lines = set(spacers)
            self.real_line_numbers = dict(line_numbers)
            self.gutter.update()
            self.overview_ruler.total_lines_count = len(lines)
            self.overview_ruler.update()
            return

        cursor = self.textCursor()
        block_num = cursor.blockNumber()
        col = cursor.positionInBlock()
        sb = self.verticalScrollBar().value()

        self._programmatic_change = True
        self.spacer_lines = set(spacers)
        self.real_line_numbers = dict(line_numbers)
        self.setPlainText(new_text)

        new_block = self.document().findBlockByNumber(min(block_num, max(0, self.blockCount() - 1)))
        if new_block.isValid():
            new_cursor = QTextCursor(new_block)
            new_cursor.setPosition(min(new_block.position() + col, new_block.position() + max(0, new_block.length() - 1)))
            self.setTextCursor(new_cursor)

        self.verticalScrollBar().setValue(sb)
        self._programmatic_change = False
        self._update_gutter_width(0)
        self.overview_ruler.total_lines_count = len(lines)
        self.overview_ruler.update()

    def _update_virtual_window(self, center_line: int):
        new_start = max(0, center_line - 20)
        if abs(new_start - self._window_start) > 40:
            self._load_virtual_slice(new_start)

    def _load_virtual_slice(self, start_idx: int):
        self._window_start = start_idx
        end_idx = min(len(self._virtual_lines), start_idx + self.WINDOW_SIZE)
        slice_lines = self._virtual_lines[start_idx:end_idx]

        self._programmatic_change = True
        self.spacer_lines = {idx - start_idx for idx in self._virtual_spacers if start_idx <= idx < end_idx}
        self.real_line_numbers = {
            idx - start_idx: self._virtual_line_numbers.get(idx, idx + 1)
            for idx in range(start_idx, end_idx)
        }
        self.setPlainText('\n'.join(slice_lines))
        self._programmatic_change = False

        self._reapply_virtual_decorations()
        self.gutter.update()
        self._update_gutter_width(0)

    def jump_to_line(self, line_idx: int):
        """Jumps directly to the specified line number, whether virtualized or normal."""
        if self._is_virtualized:
            target_start = max(0, line_idx - 10)
            self._load_virtual_slice(target_start)
            local_line = max(0, line_idx - target_start)
            block = self.document().findBlockByNumber(min(local_line, self.blockCount() - 1))
            if block.isValid():
                self.setTextCursor(QTextCursor(block))
                self.centerCursor()
            self.verticalScrollBar().setValue(line_idx)
        else:
            block = self.document().findBlockByNumber(min(line_idx, max(0, self.blockCount() - 1)))
            if block.isValid():
                cursor = QTextCursor(block)
                self.setTextCursor(cursor)
                self.centerCursor()

    def get_clean_text(self) -> str:
        if self._is_virtualized:
            if not self._virtual_spacers:
                return '\n'.join(self._virtual_lines)
            clean = [line for idx, line in enumerate(self._virtual_lines) if idx not in self._virtual_spacers]
            return '\n'.join(clean)

        lines = self.toPlainText().split('\n')
        if not self.spacer_lines:
            return self.toPlainText()
        clean = [line for idx, line in enumerate(lines) if idx not in self.spacer_lines]
        return '\n'.join(clean)

    def paint_gutter(self, event):
        painter = QPainter(self.gutter)
        painter.fillRect(event.rect(), QColor("#f6f8fa"))

        # Right border
        painter.setPen(QColor("#d0d7de"))
        painter.drawLine(self.gutter.width() - 1, event.rect().top(), self.gutter.width() - 1, event.rect().bottom())

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        active_block_number = self.textCursor().blockNumber()
        line_height = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                abs_line = self._window_start + block_number if self._is_virtualized else block_number
                is_spacer = (abs_line in self._virtual_spacers) if self._is_virtualized else (block_number in self.spacer_lines)

                if is_spacer:
                    painter.setPen(QColor("#afb8c1"))
                    painter.drawText(
                        0, top, self.gutter.width() - 10, line_height,
                        Qt.AlignRight | Qt.AlignVCenter, "·"
                    )
                else:
                    if self._is_virtualized:
                        real_num = self._virtual_line_numbers.get(abs_line, abs_line + 1)
                    else:
                        real_num = self.real_line_numbers.get(block_number, block_number + 1)
                    num_str = str(real_num)
                    
                    if block_number == active_block_number:
                        painter.setPen(QColor("#0969da"))
                        font = painter.font()
                        font.setBold(True)
                        painter.setFont(font)
                    else:
                        painter.setPen(QColor("#656d76"))
                        font = painter.font()
                        font.setBold(False)
                        painter.setFont(font)

                    painter.drawText(
                        0, top, self.gutter.width() - 10, line_height,
                        Qt.AlignRight | Qt.AlignVCenter, num_str
                    )

                # Draw change stripe on right edge of gutter
                marker_check = abs_line if self._is_virtualized else block_number
                if marker_check in self.line_markers:
                    color_hex, symbol = self.line_markers[marker_check]
                    stripe_color = QColor(color_hex)
                    painter.fillRect(self.gutter.width() - 3, top, 3, line_height, stripe_color)

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def apply_diff_decorations(
        self,
        line_decorations: Dict[int, str],
        char_decorations: Optional[Dict[int, List[Tuple[int, int, str]]]] = None,
        tick_info: Optional[Dict[int, Tuple[str, str]]] = None
    ):
        """
        Apply non-destructive line-level, intraline character-level, and spacer highlights
        using QTextEdit.ExtraSelection, and configure overview minimap ruler.
        """
        self._cached_line_decorations = line_decorations
        self._cached_char_decorations = char_decorations or {}

        total = self.get_total_line_count()
        self.line_markers = {line: (color, "~") for line, color in line_decorations.items()}
        self.gutter.update()
        self.overview_ruler.set_diff_lines(line_decorations, tick_info, total_lines=total)

        if self._is_virtualized:
            self._reapply_virtual_decorations()
            return

        doc = self.document()
        extra_selections: List[QTextEdit.ExtraSelection] = []

        # 1. Spacer Line Fill
        for spacer_idx in self.spacer_lines:
            block = doc.findBlockByNumber(spacer_idx)
            if not block.isValid():
                continue
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor(240, 242, 245))
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = QTextCursor(block)
            extra_selections.append(selection)

        # 2. Full-width Line Highlights
        for line_idx, color_hex in line_decorations.items():
            if line_idx in self.spacer_lines:
                continue
            block = doc.findBlockByNumber(line_idx)
            if not block.isValid():
                continue

            selection = QTextEdit.ExtraSelection()
            bg_color = QColor(color_hex)
            bg_color.setAlpha(32)

            selection.format.setBackground(bg_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = QTextCursor(block)
            extra_selections.append(selection)

        # 3. Intraline Character Highlights
        if char_decorations:
            for line_idx, spans in char_decorations.items():
                if line_idx in self.spacer_lines:
                    continue
                block = doc.findBlockByNumber(line_idx)
                if not block.isValid():
                    continue

                block_start = block.position()
                for start_char, end_char, char_color_hex in spans:
                    if start_char >= end_char:
                        continue
                    selection = QTextEdit.ExtraSelection()
                    c_color = QColor(char_color_hex)
                    c_color.setAlpha(85)
                    selection.format.setBackground(c_color)

                    cursor = QTextCursor(doc)
                    cursor.setPosition(block_start + start_char)
                    cursor.setPosition(block_start + end_char, QTextCursor.KeepAnchor)
                    selection.cursor = cursor
                    extra_selections.append(selection)

        self._diff_extra_selections = extra_selections
        self._update_all_extra_selections()

    def set_search_selections(self, selections: List[QTextEdit.ExtraSelection]):
        """Sets active search highlights without interfering with line diff highlights."""
        self._search_extra_selections = selections
        self._update_all_extra_selections()

    def clear_search_selections(self):
        """Clears active search highlights."""
        self._search_extra_selections = []
        self._update_all_extra_selections()

    def _update_all_extra_selections(self):
        """Composes diff decorations and search selections together."""
        self.setExtraSelections(self._diff_extra_selections + self._search_extra_selections)

    def _reapply_virtual_decorations(self):
        """Applies decorations for the currently active virtual window slice."""
        doc = self.document()
        extra_selections: List[QTextEdit.ExtraSelection] = []
        start = self._window_start
        end = start + self.WINDOW_SIZE

        for spacer_idx in self.spacer_lines:
            block = doc.findBlockByNumber(spacer_idx)
            if not block.isValid():
                continue
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor(240, 242, 245))
            sel.format.setProperty(QTextFormat.FullWidthSelection, True)
            sel.cursor = QTextCursor(block)
            extra_selections.append(sel)

        for abs_line, color_hex in self._cached_line_decorations.items():
            if start <= abs_line < end:
                local_line = abs_line - start
                if local_line in self.spacer_lines:
                    continue
                block = doc.findBlockByNumber(local_line)
                if not block.isValid():
                    continue
                sel = QTextEdit.ExtraSelection()
                c = QColor(color_hex)
                c.setAlpha(32)
                sel.format.setBackground(c)
                sel.format.setProperty(QTextFormat.FullWidthSelection, True)
                sel.cursor = QTextCursor(block)
                extra_selections.append(sel)

        for abs_line, spans in self._cached_char_decorations.items():
            if start <= abs_line < end:
                local_line = abs_line - start
                if local_line in self.spacer_lines:
                    continue
                block = doc.findBlockByNumber(local_line)
                if not block.isValid():
                    continue
                block_start = block.position()
                for start_char, end_char, char_color_hex in spans:
                    if start_char >= end_char:
                        continue
                    sel = QTextEdit.ExtraSelection()
                    c = QColor(char_color_hex)
                    c.setAlpha(85)
                    sel.format.setBackground(c)
                    cursor = QTextCursor(doc)
                    cursor.setPosition(block_start + start_char)
                    cursor.setPosition(block_start + end_char, QTextCursor.KeepAnchor)
                    sel.cursor = cursor
                    extra_selections.append(sel)

        self._diff_extra_selections = extra_selections
        self._update_all_extra_selections()

    def get_real_line_for_cursor_or_point(self, pos: Optional[QPoint] = None) -> int:
        """Returns 1-indexed real file line number for a viewport point or active text cursor."""
        if pos is not None:
            cursor = self.cursorForPosition(pos)
        else:
            cursor = self.textCursor()
        block_num = cursor.blockNumber()
        if self._is_virtualized:
            abs_row = self._window_start + block_num
            return self._virtual_line_numbers.get(abs_row, abs_row + 1)
        return self.real_line_numbers.get(block_num, block_num + 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            line_num = self.get_real_line_for_cursor_or_point(event.pos())
            self.alignmentTargetClicked.emit(line_num)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        pos = event.pos()
        line_num = self.get_real_line_for_cursor_or_point(pos)
        menu = self.createStandardContextMenu()
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
        menu.addSeparator()

        act_align = menu.addAction(f"📌 Align With... (Line {line_num})")
        act_align.setShortcut(QKeySequence("F7"))
        act_align.triggered.connect(lambda: self.alignWithRequested.emit(line_num))

        act_clear = menu.addAction("❌ Clear Manual Alignments")
        act_clear.setShortcut(QKeySequence("Ctrl+F7"))
        act_clear.triggered.connect(self.clearAlignmentRequested.emit)

        menu.exec_(event.globalPos())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F7 and not (event.modifiers() & Qt.ControlModifier):
            line_num = self.get_real_line_for_cursor_or_point()
            self.alignWithRequested.emit(line_num)
            event.accept()
            return
        elif event.key() == Qt.Key_F7 and (event.modifiers() & Qt.ControlModifier):
            self.clearAlignmentRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

