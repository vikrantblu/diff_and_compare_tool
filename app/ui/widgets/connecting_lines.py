from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath
from PySide6.QtCore import Qt

class ConnectingLinesWidget(QWidget):
    def __init__(self, left_editor, right_editor, parent=None):
        super().__init__(parent)
        self.left_editor = left_editor
        self.right_editor = right_editor
        self.setFixedWidth(50)
        self.connections = [] # List of tuples: (left_line_start, left_line_end, right_line_start, right_line_end, color)

    def set_connections(self, connections):
        self.connections = connections
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Fill background
        painter.fillRect(self.rect(), QColor("#1e1e1e"))
        
        if not self.connections:
            return

        left_offset = self.left_editor.contentOffset().y()
        right_offset = self.right_editor.contentOffset().y()
        
        fm = self.left_editor.fontMetrics()
        line_height = fm.height()

        for (l_start, l_end, r_start, r_end, color_hex) in self.connections:
            # Calculate Y positions based on line numbers and current scroll offsets
            
            # Simple approximation assuming fixed line height (works well for code editors)
            l_y_start = l_start * line_height + left_offset
            l_y_end = l_end * line_height + left_offset
            
            r_y_start = r_start * line_height + right_offset
            r_y_end = r_end * line_height + right_offset
            
            color = QColor(color_hex)
            color.setAlpha(150)
            
            path = QPainterPath()
            path.moveTo(0, l_y_start)
            path.cubicTo(self.width() / 2, l_y_start, self.width() / 2, r_y_start, self.width(), r_y_start)
            path.lineTo(self.width(), r_y_end)
            path.cubicTo(self.width() / 2, r_y_end, self.width() / 2, l_y_end, 0, l_y_end)
            path.closeSubpath()

            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawPath(path)
            
            # Draw outline
            pen = QPen(QColor(color_hex).darker(120), 1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            
            path_top = QPainterPath()
            path_top.moveTo(0, l_y_start)
            path_top.cubicTo(self.width() / 2, l_y_start, self.width() / 2, r_y_start, self.width(), r_y_start)
            painter.drawPath(path_top)
            
            path_bottom = QPainterPath()
            path_bottom.moveTo(0, l_y_end)
            path_bottom.cubicTo(self.width() / 2, l_y_end, self.width() / 2, r_y_end, self.width(), r_y_end)
            painter.drawPath(path_bottom)
