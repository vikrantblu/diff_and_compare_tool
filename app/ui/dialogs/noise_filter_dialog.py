"""
Noise & Pattern Filtering Configuration Dialog
Configure dynamic regex rules, line ending tolerance, and comment filtering.
"""

import re
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox
)
from typing import List, Tuple
from app.core.diff_engine import NOISE_REGEX_PRESETS
from app.core.session_manager import SessionManager
from app.ui.styles.icons import get_line_icon


class NoiseFilterDialog(QDialog):
    """Dialog to configure preset & custom regex unimportant-difference rules."""

    def __init__(self, parent=None, active_rules: List[Tuple[str, str]] = None):
        super().__init__(parent)
        self.setWindowTitle("Noise & Unimportant Difference Filters")
        self.resize(620, 560)

        self.selected_rules: List[Tuple[str, str]] = list(active_rules or [])
        self.preset_checkboxes = {}

        self.setup_ui()
        self._load_custom_rules()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_lbl = QLabel("Unimportant Differences & Regex Rules")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #1f2328;")
        layout.addWidget(title_lbl)

        desc_lbl = QLabel("Ignore non-semantic variations like timestamps, GUIDs, comments, or custom regex substitutions during comparison.")
        desc_lbl.setStyleSheet("color: #57606a;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # Preset checkboxes group
        preset_frame = QFrame()
        preset_frame.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px;")
        p_layout = QVBoxLayout(preset_frame)
        p_layout.setSpacing(8)

        for name, (pat, repl) in NOISE_REGEX_PRESETS.items():
            chk = QCheckBox(name)
            is_active = any(r[0] == pat for r in self.selected_rules)
            chk.setChecked(is_active)
            self.preset_checkboxes[name] = (chk, pat, repl)
            p_layout.addWidget(chk)

        layout.addWidget(preset_frame)

        # Custom Regex Rules Table
        lbl_custom = QLabel("Custom Regex Replacements (Saved Automatically):")
        lbl_custom.setStyleSheet("font-size: 12px; font-weight: 700; color: #1f2328;")
        layout.addWidget(lbl_custom)

        self.table_custom = QTableWidget(0, 2)
        self.table_custom.setHorizontalHeaderLabels(["Pattern (Regex)", "Replace With"])
        self.table_custom.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_custom.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table_custom.setColumnWidth(1, 180)
        self.table_custom.setMinimumHeight(130)
        layout.addWidget(self.table_custom)

        c_btn_row = QHBoxLayout()
        btn_add = QPushButton(" + Add Custom Rule")
        btn_add.setFixedHeight(28)
        btn_add.clicked.connect(lambda: self.add_custom_rule("", ""))
        c_btn_row.addWidget(btn_add)

        btn_del = QPushButton(" Remove Selected")
        btn_del.setFixedHeight(28)
        btn_del.clicked.connect(self._remove_selected_rule)
        c_btn_row.addWidget(btn_del)
        c_btn_row.addStretch()
        layout.addLayout(c_btn_row)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedHeight(30)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_apply = QPushButton("Apply Filters")
        self.btn_apply.setIcon(get_line_icon("check", "#ffffff"))
        self.btn_apply.setObjectName("PrimaryButton")
        self.btn_apply.setFixedHeight(30)
        self.btn_apply.clicked.connect(self._apply)
        btn_layout.addWidget(self.btn_apply)

        layout.addLayout(btn_layout)

    def _load_custom_rules(self):
        saved = SessionManager.get_custom_noise_rules()
        preset_pats = {pat for _, pat, _ in self.preset_checkboxes.values()}
        merged = list(saved)
        for pat, repl in self.selected_rules:
            if pat not in preset_pats and (pat, repl) not in merged:
                merged.append((pat, repl))
        for pat, repl in merged:
            self.add_custom_rule(pat, repl)

    def add_custom_rule(self, pattern: str = "", replacement: str = ""):
        row = self.table_custom.rowCount()
        self.table_custom.insertRow(row)
        self.table_custom.setItem(row, 0, QTableWidgetItem(pattern))
        self.table_custom.setItem(row, 1, QTableWidgetItem(replacement))

    def _remove_selected_rule(self):
        row = self.table_custom.currentRow()
        if row >= 0:
            self.table_custom.removeRow(row)

    def _apply(self):
        rules: List[Tuple[str, str]] = []
        for _name, (chk, pat, repl) in self.preset_checkboxes.items():
            if chk.isChecked():
                rules.append((pat, repl))

        custom_rules: List[Tuple[str, str]] = []
        for row in range(self.table_custom.rowCount()):
            pat_item = self.table_custom.item(row, 0)
            repl_item = self.table_custom.item(row, 1)
            pat = pat_item.text().strip() if pat_item else ""
            repl = repl_item.text() if repl_item else ""
            if not pat:
                continue
            try:
                re.compile(pat)
            except re.error as e:
                QMessageBox.warning(self, "Invalid Regex", f"Row {row + 1} contains an invalid regular expression:\n{pat}\n\n{e}")
                return
            custom_rules.append((pat, repl))
            rules.append((pat, repl))

        SessionManager.save_custom_noise_rules(custom_rules)
        self.selected_rules = rules
        self.accept()

    def get_rules(self) -> List[Tuple[str, str]]:
        return self.selected_rules
