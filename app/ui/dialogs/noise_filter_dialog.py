"""
Noise & Pattern Filtering Configuration Dialog
Configure dynamic regex rules, line ending tolerance, and comment filtering.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView, QFrame
)
from typing import List, Tuple
from app.core.diff_engine import NOISE_REGEX_PRESETS
from app.ui.styles.icons import get_line_icon


class NoiseFilterDialog(QDialog):
    """Dialog to configure noise filters and regex substitution rules."""

    def __init__(self, parent=None, active_rules: List[Tuple[str, str]] = None):
        super().__init__(parent)
        self.setWindowTitle("Noise & Regular Expression Filters")
        self.resize(560, 480)

        self.selected_rules: List[Tuple[str, str]] = active_rules or []
        self.preset_checkboxes = {}

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_lbl = QLabel("🛡️ Comparison Noise & Regex Filtering")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #1f2328;")
        layout.addWidget(title_lbl)

        desc_lbl = QLabel("Filter out non-semantic variations like timestamps, GUIDs, and comments before comparison.")
        desc_lbl.setStyleSheet("color: #57606a;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # Preset checkboxes group
        preset_frame = QFrame()
        preset_frame.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px;")
        p_layout = QVBoxLayout(preset_frame)
        p_layout.setSpacing(10)

        for name, (pat, repl) in NOISE_REGEX_PRESETS.items():
            chk = QCheckBox(name)
            # Check if active
            is_active = any(r[0] == pat for r in self.selected_rules)
            chk.setChecked(is_active)
            self.preset_checkboxes[name] = (chk, pat, repl)
            p_layout.addWidget(chk)

        layout.addWidget(preset_frame)

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

    def _apply(self):
        rules: List[Tuple[str, str]] = []
        for name, (chk, pat, repl) in self.preset_checkboxes.items():
            if chk.isChecked():
                rules.append((pat, repl))
        self.selected_rules = rules
        self.accept()

    def get_rules(self) -> List[Tuple[str, str]]:
        return self.selected_rules
