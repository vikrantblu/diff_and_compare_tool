"""
Universal Keyboard-First Command Palette (Ctrl+K / Ctrl+Shift+P)
Provides instant fuzzy search across all 10 studios, active-tab actions, Git tools, and recent comparisons.
"""

from typing import Callable, List, Tuple, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QPushButton
)
from PySide6.QtCore import Qt, QEvent
from app.ui.styles.icons import get_line_icon


CommandEntry = Tuple[str, str, str, Callable]  # (title, category, shortcut_hint, callback)


class CommandPaletteDialog(QDialog):
    """Fluent Light Command Palette launcher for studios, tools, and recent comparisons."""

    def __init__(self, commands: List[CommandEntry], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Command Palette (Ctrl+K)")
        self.resize(580, 420)
        self._commands: List[CommandEntry] = list(commands)
        self._filtered_indices: List[int] = []
        self._selected_callback: Optional[Callable] = None

        self.setup_ui()
        self.filter_commands("")

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        head = QHBoxLayout()
        lbl_icon = QLabel()
        lbl_icon.setPixmap(get_line_icon("command", "#0969da", 18).pixmap(18, 18))
        lbl_icon.setStyleSheet("border: none; background: transparent;")
        head.addWidget(lbl_icon)

        self.txt_query = QLineEdit()
        self.txt_query.setPlaceholderText("Type a command, studio, or recent comparison... (Up/Down, Enter)")
        self.txt_query.setFixedHeight(34)
        self.txt_query.setClearButtonEnabled(True)
        self.txt_query.textChanged.connect(self.filter_commands)
        self.txt_query.installEventFilter(self)
        head.addWidget(self.txt_query, 1)
        layout.addLayout(head)

        self.list_commands = QListWidget()
        self.list_commands.setStyleSheet("""
            QListWidget {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 4px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 5px;
                color: #0f172a;
            }
            QListWidget::item:selected {
                background: #eff6ff;
                color: #0969da;
                font-weight: 600;
            }
            QListWidget::item:hover {
                background: #f8fafc;
            }
        """)
        self.list_commands.itemDoubleClicked.connect(lambda _it: self.execute_selected())
        layout.addWidget(self.list_commands, 1)

        foot = QHBoxLayout()
        self.lbl_count = QLabel("0 commands")
        self.lbl_count.setStyleSheet("color: #64748b; font-size: 11px; border: none; background: transparent;")
        foot.addWidget(self.lbl_count)
        foot.addStretch()

        btn_cancel = QPushButton("Close (Esc)")
        btn_cancel.setFixedHeight(28)
        btn_cancel.clicked.connect(self.reject)
        foot.addWidget(btn_cancel)

        self.btn_run = QPushButton("Run Command")
        self.btn_run.setObjectName("PrimaryButton")
        self.btn_run.setFixedHeight(28)
        self.btn_run.clicked.connect(self.execute_selected)
        foot.addWidget(self.btn_run)
        layout.addLayout(foot)

    def eventFilter(self, obj, event):
        if obj is self.txt_query and event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Down:
                row = self.list_commands.currentRow()
                if row + 1 < self.list_commands.count():
                    self.list_commands.setCurrentRow(row + 1)
                return True
            if key == Qt.Key_Up:
                row = self.list_commands.currentRow()
                if row - 1 >= 0:
                    self.list_commands.setCurrentRow(row - 1)
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self.execute_selected()
                return True
        return super().eventFilter(obj, event)

    def filter_commands(self, query: str):
        tokens = [t for t in (query or "").lower().split() if t]
        self.list_commands.clear()
        self._filtered_indices = []

        for idx, (title, category, shortcut, _cb) in enumerate(self._commands):
            haystack = f"{category} {title} {shortcut}".lower()
            if all(tok in haystack for tok in tokens):
                self._filtered_indices.append(idx)
                sc_str = f"    [{shortcut}]" if shortcut else ""
                item = QListWidgetItem(f"{category}:  {title}{sc_str}")
                item.setData(Qt.UserRole, idx)
                self.list_commands.addItem(item)

        if self.list_commands.count() > 0:
            self.list_commands.setCurrentRow(0)
        self.lbl_count.setText(f"{self.list_commands.count()} matching command(s)")

    def execute_selected(self) -> bool:
        item = self.list_commands.currentItem()
        if not item:
            return False
        cmd_idx = item.data(Qt.UserRole)
        if cmd_idx is None or not (0 <= cmd_idx < len(self._commands)):
            return False
        self._selected_callback = self._commands[cmd_idx][3]
        self.accept()
        if self._selected_callback:
            self._selected_callback()
        return True
