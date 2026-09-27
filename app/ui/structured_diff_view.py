"""
Structured Data Comparison Studio (JSON, YAML, XML)
Hierarchical tree comparison that visualizes key mutations, node additions,
and deletions, regardless of formatting or indentation differences.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QCheckBox, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QFrame, QHeaderView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QFont

from app.core.structured_diff import StructuredDiffEngine, StructuredDiffResult, StructuredNode
from app.ui.styles.icons import get_line_icon


class StructuredDiffView(QWidget):
    """Studio for comparing structured formats (JSON, YAML, XML)."""

    def __init__(self):
        super().__init__()
        self.left_path: Optional[str] = None
        self.right_path: Optional[str] = None
        self.left_content: str = ""
        self.right_content: str = ""
        self.diff_result: Optional[StructuredDiffResult] = None

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

        self.btn_left = QPushButton(" Browse Left...")
        self.btn_left.setIcon(get_line_icon("folder", "#0969da"))
        self.btn_left.setFixedHeight(30)
        self.btn_left.clicked.connect(self._browse_left)
        self.lbl_left = QLabel("Left: (None)")
        self.lbl_left.setStyleSheet("color: #475569; font-weight: 600; padding: 4px 8px; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px;")

        self.btn_right = QPushButton(" Browse Right...")
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

        # 2. Command Bar (Format selection, sorting, filtering)
        cmd_bar = QFrame()
        cmd_bar.setFixedHeight(46)
        cmd_bar.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #cbd5e1; padding: 2px 4px;")
        cb_layout = QHBoxLayout(cmd_bar)
        cb_layout.setContentsMargins(10, 0, 10, 0)
        cb_layout.setSpacing(8)

        lbl_fmt = QLabel("Format:")
        lbl_fmt.setStyleSheet("font-weight: 600; color: #334155;")
        cb_layout.addWidget(lbl_fmt)
        self.combo_format = QComboBox()
        self.combo_format.addItems(["Auto Detect", "JSON", "YAML", "XML"])
        self.combo_format.setFixedHeight(30)
        self.combo_format.currentIndexChanged.connect(self._recompute_diff)
        cb_layout.addWidget(self.combo_format)

        self.chk_sort = QCheckBox("Sort Keys")
        self.chk_sort.setChecked(True)
        self.chk_sort.setFixedHeight(30)
        self.chk_sort.toggled.connect(self._recompute_diff)
        cb_layout.addWidget(self.chk_sort)

        self.chk_unordered = QCheckBox("Unordered Arrays")
        self.chk_unordered.setFixedHeight(30)
        self.chk_unordered.setToolTip("Semantically matches arrays as unordered collections (matches by value or object id rather than sequential index)")
        self.chk_unordered.toggled.connect(self._recompute_diff)
        cb_layout.addWidget(self.chk_unordered)

        self.chk_diffs_only = QCheckBox("Show Diffs Only")
        self.chk_diffs_only.setFixedHeight(30)
        self.chk_diffs_only.toggled.connect(self._populate_tree)
        cb_layout.addWidget(self.chk_diffs_only)

        self.txt_query = QLineEdit()
        self.txt_query.setPlaceholderText("JSONPath / XPath (e.g. $.items[*])...")
        self.txt_query.setFixedWidth(220)
        self.txt_query.setFixedHeight(30)
        self.txt_query.setToolTip("Filter trees using JSONPath ($.path) or XPath (//element). Press Enter to apply.")
        self.txt_query.returnPressed.connect(self._recompute_diff)
        cb_layout.addWidget(self.txt_query)

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filter visible text...")
        self.txt_filter.setFixedWidth(140)
        self.txt_filter.setFixedHeight(30)
        self.txt_filter.textChanged.connect(self._populate_tree)
        cb_layout.addWidget(self.txt_filter)

        self.btn_expand = QPushButton(" Expand All")
        self.btn_expand.setFixedHeight(30)
        self.btn_expand.clicked.connect(lambda: self.tree.expandAll())
        cb_layout.addWidget(self.btn_expand)

        self.btn_collapse = QPushButton(" Collapse All")
        self.btn_collapse.setFixedHeight(30)
        self.btn_collapse.clicked.connect(lambda: self.tree.collapseAll())
        cb_layout.addWidget(self.btn_collapse)

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

        # 3. Hierarchical Tree Widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Key / Node", "Left Value", "Right Value", "Status"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Interactive)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Interactive)
        self.tree.header().setSectionResizeMode(2, QHeaderView.Interactive)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tree.setColumnWidth(0, 280)
        self.tree.setColumnWidth(1, 350)
        self.tree.setColumnWidth(2, 350)
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: #ffffff;
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 5px;
                border-bottom: 1px solid #f1f5f9;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #334155;
                font-weight: 600;
                padding: 6px;
                border: 1px solid #cbd5e1;
            }
        """)

        layout.addWidget(self.tree, 1)

    def _browse_left(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open Left Structured File", "", "Data Files (*.json *.yaml *.yml *.xml *.txt);;All Files (*.*)")
        if file:
            self.left_path = file
            self.lbl_left.setText(f"Left: {os.path.basename(file)}")
            with open(file, "r", encoding="utf-8", errors="replace") as f:
                self.left_content = f.read()
            self._recompute_diff()

    def _browse_right(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open Right Structured File", "", "Data Files (*.json *.yaml *.yml *.xml *.txt);;All Files (*.*)")
        if file:
            self.right_path = file
            self.lbl_right.setText(f"Right: {os.path.basename(file)}")
            with open(file, "r", encoding="utf-8", errors="replace") as f:
                self.right_content = f.read()
            self._recompute_diff()

    def set_files(self, left_path: str, right_path: str):
        if left_path and os.path.exists(left_path):
            self.left_path = left_path
            self.lbl_left.setText(f"Left: {os.path.basename(left_path)}")
            with open(left_path, "r", encoding="utf-8", errors="replace") as f:
                self.left_content = f.read()
        if right_path and os.path.exists(right_path):
            self.right_path = right_path
            self.lbl_right.setText(f"Right: {os.path.basename(right_path)}")
            with open(right_path, "r", encoding="utf-8", errors="replace") as f:
                self.right_content = f.read()
        self._recompute_diff()

    def set_content(self, left_text: str, right_text: str, left_title: str = "Left", right_title: str = "Right"):
        self.left_content = left_text
        self.right_content = right_text
        self.lbl_left.setText(f"Left: {left_title}")
        self.lbl_right.setText(f"Right: {right_title}")
        self._recompute_diff()

    def _recompute_diff(self):
        if not self.left_content and not self.right_content:
            return

        fmt_map = {"Auto Detect": "auto", "JSON": "json", "YAML": "yaml", "XML": "xml"}
        fmt = fmt_map.get(self.combo_format.currentText(), "auto")
        sort_keys = self.chk_sort.isChecked()
        unordered = self.chk_unordered.isChecked()
        query = self.txt_query.text().strip() or None

        self.diff_result = StructuredDiffEngine.compare(
            self.left_content, self.right_content,
            format_type=fmt,
            ignore_key_order=sort_keys,
            unordered_arrays=unordered,
            query=query
        )

        res = self.diff_result
        self.lbl_stats.setText(
            f"Nodes: {res.total_nodes} | +{res.added_count} Added | -{res.deleted_count} Deleted | ~{res.modified_count} Modified | = {res.equal_count} Equal"
        )

        self._populate_tree()

    def _populate_tree(self):
        self.tree.clear()
        if not self.diff_result or not self.diff_result.root_node:
            return

        diffs_only = self.chk_diffs_only.isChecked()
        filter_text = self.txt_filter.text().lower()

        root_node = self.diff_result.root_node
        for child in root_node.children:
            self._build_tree_item(self.tree, child, diffs_only, filter_text)

        self.tree.expandAll()

    def _build_tree_item(self, parent_widget, node: StructuredNode, diffs_only: bool, filter_text: str):
        if diffs_only and node.status == "equal" and not any(c.status != "equal" for c in node.children):
            return

        # Check search filter
        match_filter = True
        if filter_text:
            text_str = f"{node.name} {node.left_val} {node.right_val}".lower()
            match_filter = filter_text in text_str

        l_val_str = str(node.left_val) if node.left_val is not None else ""
        r_val_str = str(node.right_val) if node.right_val is not None else ""

        status_labels = {
            "equal": "— Equal",
            "added": "+ Added",
            "deleted": "− Deleted",
            "modified": "≠ Modified"
        }

        item = QTreeWidgetItem(parent_widget)
        item.setText(0, node.name)
        item.setText(1, l_val_str)
        item.setText(2, r_val_str)
        item.setText(3, status_labels.get(node.status, node.status))

        # Color styling
        if node.status == "added":
            item.setBackground(0, QBrush(QColor("#dafbe1")))
            item.setBackground(1, QBrush(QColor("#dafbe1")))
            item.setBackground(2, QBrush(QColor("#dafbe1")))
            item.setBackground(3, QBrush(QColor("#dafbe1")))
            item.setForeground(3, QBrush(QColor("#1a7f37")))
        elif node.status == "deleted":
            item.setBackground(0, QBrush(QColor("#ffebe9")))
            item.setBackground(1, QBrush(QColor("#ffebe9")))
            item.setBackground(2, QBrush(QColor("#ffebe9")))
            item.setBackground(3, QBrush(QColor("#ffebe9")))
            item.setForeground(3, QBrush(QColor("#cf222e")))
        elif node.status == "modified":
            item.setBackground(0, QBrush(QColor("#fff8c5")))
            item.setBackground(1, QBrush(QColor("#fff8c5")))
            item.setBackground(2, QBrush(QColor("#fff8c5")))
            item.setBackground(3, QBrush(QColor("#fff8c5")))
            item.setForeground(3, QBrush(QColor("#9a6700")))

        for child in node.children:
            self._build_tree_item(item, child, diffs_only, filter_text)
