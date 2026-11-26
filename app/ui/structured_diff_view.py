"""
Structured Data & API Contract Comparison Studio (White / Light Theme)
Features:
- Hierarchical tree diffing for JSON, YAML, and XML with working recursive text & diffs-only filters.
- Prev/Next Diff Node navigation, Swap, Context Menu (Copy Path / Left Value / Right Value), and Drag & Drop.
- Built-in API Contract Audit view (OpenAPI, GraphQL, Protobuf) powered by ContractDiffEngine
  highlighting BREAKING, WARNING, and ADDITIVE schema changes.
"""

import os
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QCheckBox, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QFrame, QHeaderView, QStackedWidget, QTableWidget,
    QTableWidgetItem, QMenu, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QDragEnterEvent, QDropEvent

from app.core.structured_diff import StructuredDiffEngine, StructuredDiffResult, StructuredNode
from app.core.contract_diff import ContractDiffEngine, ContractDiffReport
from app.ui.styles.icons import get_line_icon


class StructuredDiffView(QWidget):
    """Studio for comparing structured formats (JSON, YAML, XML) and API Contracts (OpenAPI/GraphQL/Protobuf)."""

    def __init__(self, initial_mode: str = "tree"):
        super().__init__()
        self.left_path: Optional[str] = None
        self.right_path: Optional[str] = None
        self.left_content: str = ""
        self.right_content: str = ""
        self.diff_result: Optional[StructuredDiffResult] = None
        self.contract_report: Optional[ContractDiffReport] = None
        self._diff_tree_items: List[QTreeWidgetItem] = []
        self._cur_diff_idx = -1
        self._prefer_contract = (initial_mode == "contract")
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

        self.btn_left = QPushButton(" Browse Left...")
        self.btn_left.setIcon(get_line_icon("folder", "#0969da"))
        self.btn_left.setFixedHeight(30)
        self.btn_left.clicked.connect(self._browse_left)
        self.lbl_left = QLabel("Left: (None)")
        self.lbl_left.setStyleSheet("color: #475569; font-weight: 600; padding: 4px 8px; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px;")

        self.btn_swap = QPushButton(" Swap")
        self.btn_swap.setIcon(get_line_icon("swap", "#1e293b"))
        self.btn_swap.setFixedHeight(30)
        self.btn_swap.clicked.connect(self._swap_sides)

        self.btn_right = QPushButton(" Browse Right...")
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

        lbl_fmt = QLabel("Format:")
        lbl_fmt.setStyleSheet("font-weight: 600; color: #334155; border: none; background: transparent;")
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
        self.chk_unordered.setToolTip("Semantically matches arrays by value or object id")
        self.chk_unordered.toggled.connect(self._recompute_diff)
        cb_layout.addWidget(self.chk_unordered)

        self.chk_diffs_only = QCheckBox("Diffs Only")
        self.chk_diffs_only.setFixedHeight(30)
        self.chk_diffs_only.toggled.connect(self._populate_tree)
        cb_layout.addWidget(self.chk_diffs_only)

        self.txt_query = QLineEdit()
        self.txt_query.setPlaceholderText("JSONPath / XPath ($.items[*])")
        self.txt_query.setFixedWidth(180)
        self.txt_query.setFixedHeight(30)
        self.txt_query.returnPressed.connect(self._recompute_diff)
        cb_layout.addWidget(self.txt_query)

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filter nodes...")
        self.txt_filter.setFixedWidth(130)
        self.txt_filter.setFixedHeight(30)
        self.txt_filter.setClearButtonEnabled(True)
        self.txt_filter.textChanged.connect(self._populate_tree)
        cb_layout.addWidget(self.txt_filter)

        self.btn_prev_diff = QPushButton()
        self.btn_prev_diff.setIcon(get_line_icon("arrow-up", "#1e293b"))
        self.btn_prev_diff.setFixedSize(28, 28)
        self.btn_prev_diff.setToolTip("Previous Different Node")
        self.btn_prev_diff.clicked.connect(self._prev_diff_node)
        cb_layout.addWidget(self.btn_prev_diff)

        self.btn_next_diff = QPushButton()
        self.btn_next_diff.setIcon(get_line_icon("arrow-down", "#1e293b"))
        self.btn_next_diff.setFixedSize(28, 28)
        self.btn_next_diff.setToolTip("Next Different Node")
        self.btn_next_diff.clicked.connect(self._next_diff_node)
        cb_layout.addWidget(self.btn_next_diff)

        self.btn_expand = QPushButton(" Expand")
        self.btn_expand.setFixedHeight(30)
        self.btn_expand.clicked.connect(lambda: self.tree.expandAll())
        cb_layout.addWidget(self.btn_expand)

        self.btn_collapse = QPushButton(" Collapse")
        self.btn_collapse.setFixedHeight(30)
        self.btn_collapse.clicked.connect(lambda: self.tree.collapseAll())
        cb_layout.addWidget(self.btn_collapse)

        self.btn_contract_view = QPushButton(" Contract Audit")
        self.btn_contract_view.setIcon(get_line_icon("shield", "#0969da"))
        self.btn_contract_view.setCheckable(True)
        self.btn_contract_view.setChecked(self._prefer_contract)
        self.btn_contract_view.setFixedHeight(30)
        self.btn_contract_view.setToolTip("Switch between Hierarchical Tree Diff and API Contract Breaking-Change Audit")
        self.btn_contract_view.toggled.connect(self._toggle_contract_view)
        cb_layout.addWidget(self.btn_contract_view)

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

        # 3. View Stack: Index 0 = Tree Diff, Index 1 = API Contract Audit
        self.view_stack = QStackedWidget()

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Key / Node", "Left Value", "Right Value", "Status"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Interactive)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Interactive)
        self.tree.header().setSectionResizeMode(2, QHeaderView.Interactive)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tree.setColumnWidth(0, 280)
        self.tree.setColumnWidth(1, 350)
        self.tree.setColumnWidth(2, 350)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: #ffffff;
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 12px;
            }
            QTreeWidget::item { padding: 5px; border-bottom: 1px solid #f1f5f9; }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #334155;
                font-weight: 600;
                padding: 6px;
                border: 1px solid #cbd5e1;
            }
        """)
        self.view_stack.addWidget(self.tree)

        # Contract Audit View
        contract_panel = QWidget()
        cp_layout = QVBoxLayout(contract_panel)
        cp_layout.setContentsMargins(10, 10, 10, 10)
        cp_layout.setSpacing(8)

        self.lbl_contract_banner = QLabel("Load OpenAPI (JSON/YAML), GraphQL (.graphql/.gql), or Protobuf (.proto) contracts to audit breaking changes.")
        self.lbl_contract_banner.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 12px; font-weight: 600; color: #334155;")
        cp_layout.addWidget(self.lbl_contract_banner)

        self.table_contract = QTableWidget(0, 6)
        self.table_contract.setHorizontalHeaderLabels(["Severity", "Contract", "Entity Path", "Change Type", "Old -> New", "Impact Description"])
        self.table_contract.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_contract.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_contract.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.table_contract.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_contract.horizontalHeader().setSectionResizeMode(4, QHeaderView.Interactive)
        self.table_contract.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table_contract.setColumnWidth(2, 220)
        self.table_contract.setColumnWidth(4, 150)
        self.table_contract.setAlternatingRowColors(True)
        self.table_contract.setEditTriggers(QTableWidget.NoEditTriggers)
        cp_layout.addWidget(self.table_contract, 1)

        self.view_stack.addWidget(contract_panel)
        self.view_stack.setCurrentIndex(1 if self._prefer_contract else 0)

        layout.addWidget(self.view_stack, 1)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile() and os.path.isfile(u.toLocalFile())]
        if len(paths) >= 2:
            self.set_files(paths[0], paths[1])
        elif len(paths) == 1:
            if not self.left_path:
                self.set_files(paths[0], self.right_path or "")
            else:
                self.set_files(self.left_path, paths[0])

    def _toggle_contract_view(self, checked: bool):
        self.view_stack.setCurrentIndex(1 if checked else 0)
        if checked:
            self._populate_contract_table()

    def _browse_left(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Open Left Structured / Contract File", "",
            "Structured & Contracts (*.json *.yaml *.yml *.xml *.graphql *.gql *.proto *.txt);;All Files (*.*)"
        )
        if file:
            self.left_path = file
            self.lbl_left.setText(f"Left: {os.path.basename(file)}")
            with open(file, "r", encoding="utf-8", errors="replace") as f:
                self.left_content = f.read()
            self._recompute_diff()

    def _browse_right(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Open Right Structured / Contract File", "",
            "Structured & Contracts (*.json *.yaml *.yml *.xml *.graphql *.gql *.proto *.txt);;All Files (*.*)"
        )
        if file:
            self.right_path = file
            self.lbl_right.setText(f"Right: {os.path.basename(file)}")
            with open(file, "r", encoding="utf-8", errors="replace") as f:
                self.right_content = f.read()
            self._recompute_diff()

    def _swap_sides(self):
        self.left_path, self.right_path = self.right_path, self.left_path
        self.left_content, self.right_content = self.right_content, self.left_content
        self.lbl_left.setText(f"Left: {os.path.basename(self.left_path)}" if self.left_path else "Left: (None)")
        self.lbl_right.setText(f"Right: {os.path.basename(self.right_path)}" if self.right_path else "Right: (None)")
        self._recompute_diff()

    def set_files(self, left_path: str, right_path: str, contract_mode: bool = False):
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

        if contract_mode or ContractDiffEngine.detect_format(self.right_content or self.left_content, self.right_path or self.left_path or ""):
            self._prefer_contract = True
            self.btn_contract_view.setChecked(True)
            self.view_stack.setCurrentIndex(1)

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

        # Compute API Contract report whenever possible
        self.contract_report = ContractDiffEngine.diff_contracts(
            self.left_content, self.right_content,
            self.left_path or "", self.right_path or ""
        )
        if self.contract_report.contract_type != "Unknown":
            self.btn_contract_view.setText(
                f" Contract ({self.contract_report.breaking_count} Breaking)"
                if self.contract_report.breaking_count else f" Contract ({self.contract_report.contract_type})"
            )
        else:
            self.btn_contract_view.setText(" Contract Audit")

        # If Protobuf/GraphQL, skip JSON/YAML structured parse error noise if user is viewing contract tab
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

        if self.btn_contract_view.isChecked() and self.contract_report.contract_type != "Unknown":
            r = self.contract_report
            self.lbl_stats.setText(
                f"{r.contract_type} | Breaking: {r.breaking_count} | Warnings: {r.warning_count} | Additive: {r.additive_count}"
            )
        else:
            res = self.diff_result
            self.lbl_stats.setText(
                f"Nodes: {res.total_nodes} | +{res.added_count} Added | -{res.deleted_count} Deleted | ~{res.modified_count} Modified | = {res.equal_count} Equal"
            )

        self._populate_tree()
        self._populate_contract_table()

    def _populate_contract_table(self):
        if not self.contract_report or self.contract_report.contract_type == "Unknown":
            self.lbl_contract_banner.setText("No OpenAPI, GraphQL, or Protobuf contract detected in current buffers.")
            self.lbl_contract_banner.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 12px; font-weight: 600; color: #475569;")
            self.table_contract.setRowCount(0)
            return

        r = self.contract_report
        if r.has_breaking_changes:
            self.lbl_contract_banner.setText(
                f"API Contract Audit ({r.contract_type}): {r.breaking_count} BREAKING, {r.warning_count} Warning(s), {r.additive_count} Additive"
            )
            self.lbl_contract_banner.setStyleSheet("background: #ffebe9; border: 1px solid #ff8182; border-radius: 6px; padding: 8px 12px; font-weight: 700; color: #cf222e;")
        else:
            self.lbl_contract_banner.setText(
                f"API Contract Audit ({r.contract_type}): Backward Compatible — {r.warning_count} Warning(s), {r.additive_count} Additive"
            )
            self.lbl_contract_banner.setStyleSheet("background: #dafbe1; border: 1px solid #4ac26b; border-radius: 6px; padding: 8px 12px; font-weight: 700; color: #1a7f37;")

        self.table_contract.setRowCount(len(r.changes))
        for idx, ch in enumerate(r.changes):
            bg = QColor("#ffebe9") if ch.category == "BREAKING" else (QColor("#fff8c5") if ch.category == "WARNING" else QColor("#dafbe1"))
            fg = QColor("#cf222e") if ch.category == "BREAKING" else (QColor("#9a6700") if ch.category == "WARNING" else QColor("#1a7f37"))
            delta = f"{ch.old_value or '—'} → {ch.new_value or '—'}"

            vals = [ch.category, ch.contract_type, ch.entity_path, ch.change_type, delta, ch.description]
            for c_i, val in enumerate(vals):
                it = QTableWidgetItem(val)
                it.setBackground(QBrush(bg))
                if c_i == 0:
                    it.setForeground(QBrush(fg))
                self.table_contract.setItem(idx, c_i, it)

    @staticmethod
    def _node_has_diff(node: StructuredNode) -> bool:
        if node.status != "equal":
            return True
        return any(StructuredDiffView._node_has_diff(c) for c in node.children)

    @staticmethod
    def _node_matches_filter(node: StructuredNode, filter_text: str) -> bool:
        if not filter_text:
            return True
        text_str = f"{node.name} {node.path} {node.left_val} {node.right_val}".lower()
        if filter_text in text_str:
            return True
        return any(StructuredDiffView._node_matches_filter(c, filter_text) for c in node.children)

    def _populate_tree(self):
        self.tree.clear()
        self._diff_tree_items = []
        self._cur_diff_idx = -1
        if not self.diff_result or not self.diff_result.root_node:
            return

        diffs_only = self.chk_diffs_only.isChecked()
        filter_text = self.txt_filter.text().strip().lower()

        root_node = self.diff_result.root_node
        if root_node.node_type == "error":
            self._build_tree_item(self.tree, root_node, False, "")
        else:
            for child in root_node.children:
                self._build_tree_item(self.tree, child, diffs_only, filter_text)

        self.tree.expandAll()

    def _build_tree_item(self, parent_widget, node: StructuredNode, diffs_only: bool, filter_text: str):
        if diffs_only and not self._node_has_diff(node):
            return
        if filter_text and not self._node_matches_filter(node, filter_text):
            return

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
        item.setData(0, Qt.UserRole, node.path)

        if node.status == "added":
            for col in range(4):
                item.setBackground(col, QBrush(QColor("#dafbe1")))
            item.setForeground(3, QBrush(QColor("#1a7f37")))
            self._diff_tree_items.append(item)
        elif node.status == "deleted":
            for col in range(4):
                item.setBackground(col, QBrush(QColor("#ffebe9")))
            item.setForeground(3, QBrush(QColor("#cf222e")))
            self._diff_tree_items.append(item)
        elif node.status == "modified":
            for col in range(4):
                item.setBackground(col, QBrush(QColor("#fff8c5")))
            item.setForeground(3, QBrush(QColor("#9a6700")))
            if not node.children:
                self._diff_tree_items.append(item)

        for child in node.children:
            self._build_tree_item(item, child, diffs_only, filter_text)

    def _next_diff_node(self):
        if not self._diff_tree_items:
            return
        self._cur_diff_idx = (self._cur_diff_idx + 1) % len(self._diff_tree_items)
        it = self._diff_tree_items[self._cur_diff_idx]
        self.tree.setCurrentItem(it)
        self.tree.scrollToItem(it)

    def _prev_diff_node(self):
        if not self._diff_tree_items:
            return
        self._cur_diff_idx = (self._cur_diff_idx - 1 + len(self._diff_tree_items)) % len(self._diff_tree_items)
        it = self._diff_tree_items[self._cur_diff_idx]
        self.tree.setCurrentItem(it)
        self.tree.scrollToItem(it)

    def _show_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        path_val = item.data(0, Qt.UserRole) or item.text(0)
        menu.addAction("Copy Node Path", lambda: QApplication.clipboard().setText(str(path_val)))
        menu.addAction("Copy Left Value", lambda: QApplication.clipboard().setText(item.text(1)))
        menu.addAction("Copy Right Value", lambda: QApplication.clipboard().setText(item.text(2)))
        menu.exec_(self.tree.viewport().mapToGlobal(pos))
