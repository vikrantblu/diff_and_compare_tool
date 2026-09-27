"""
AI Pull Request & Change Summarizer Dialog
Generates natural-language diff summaries, risk evaluations, and PR descriptions.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QComboBox, QLineEdit, QApplication, QFrame
)
from PySide6.QtCore import Qt
from typing import List
from app.core.diff_engine import DiffChunk
from app.core.ai_assistant import AIAssistant
from app.ui.styles.icons import get_line_icon


class AISummaryDialog(QDialog):
    """Modal dialog displaying AI-generated PR summary and change explanation."""

    def __init__(self, parent=None, chunks: List[DiffChunk] = None, left_raw: List[str] = None, right_raw: List[str] = None, left_name: str = "Left", right_name: str = "Right"):
        super().__init__(parent)
        self.setWindowTitle("AI Pull Request & Diff Summary")
        self.resize(720, 580)

        self.chunks = chunks or []
        self.left_raw = left_raw or []
        self.right_raw = right_raw or []
        self.left_name = left_name
        self.right_name = right_name

        self.setup_ui()
        self._generate_summary()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title
        title_lbl = QLabel("🤖 AI Change Summarizer & PR Assistant")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #1f2328;")
        layout.addWidget(title_lbl)

        # Settings row
        settings_frame = QFrame()
        settings_frame.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 6px;")
        s_layout = QHBoxLayout(settings_frame)
        s_layout.setContentsMargins(10, 6, 10, 6)
        s_layout.setSpacing(8)

        lbl_prov = QLabel("Provider:")
        lbl_prov.setStyleSheet("font-weight: 600; color: #334155;")
        s_layout.addWidget(lbl_prov)
        self.combo_provider = QComboBox()
        self.combo_provider.setFixedHeight(30)
        self.combo_provider.addItems([
            "Smart Offline Heuristic (Zero Outbound)",
            "Local Ollama (localhost:11434)",
            "OpenAI / Copilot Compatible"
        ])
        s_layout.addWidget(self.combo_provider)

        lbl_mod = QLabel("Model:")
        lbl_mod.setStyleSheet("font-weight: 600; color: #334155;")
        s_layout.addWidget(lbl_mod)
        self.combo_model = QComboBox()
        self.combo_model.setEditable(True)
        self.combo_model.addItems(AIAssistant.SUPPORTED_MODELS)
        self.combo_model.setFixedHeight(30)
        self.combo_model.setFixedWidth(130)
        s_layout.addWidget(self.combo_model)

        lbl_shield = QLabel("🛡️ Privacy Shield Active")
        lbl_shield.setStyleSheet("background: #dafbe1; color: #1a7f37; border: 1px solid #4ac26b; padding: 4px 8px; border-radius: 6px; font-weight: 600; font-size: 11px;")
        lbl_shield.setToolTip("Automated credential and PII scrubber redacts sensitive tokens before AI processing.")
        s_layout.addWidget(lbl_shield)

        self.btn_regen = QPushButton(" Re-generate")
        self.btn_regen.setIcon(get_line_icon("sparkles", "#0969da"))
        self.btn_regen.setFixedHeight(30)
        self.btn_regen.clicked.connect(self._generate_summary)
        s_layout.addWidget(self.btn_regen)

        layout.addWidget(settings_frame)

        # Content Text Area
        self.txt_output = QTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                line-height: 1.5;
                padding: 10px;
            }
        """)
        layout.addWidget(self.txt_output, 1)

        # Bottom buttons
        btn_layout = QHBoxLayout()

        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color: #475569; font-weight: 500;")
        btn_layout.addWidget(self.lbl_status, 1)

        self.btn_copy = QPushButton(" Copy Summary")
        self.btn_copy.setIcon(get_line_icon("check", "#1a7f37"))
        self.btn_copy.setFixedHeight(30)
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        btn_layout.addWidget(self.btn_copy)

        self.btn_close = QPushButton("Close")
        self.btn_close.setFixedHeight(30)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def _generate_summary(self):
        self.lbl_status.setText("Analyzing diff chunks...")
        QApplication.processEvents()

        provider = self.combo_provider.currentText()
        endpoint = None
        model = self.combo_model.currentText().strip()

        if "Ollama" in provider:
            endpoint = "http://localhost:11434/api/generate"
        elif "OpenAI" in provider:
            endpoint = "https://api.openai.com/v1/chat/completions"

        summary = AIAssistant.generate_diff_summary(
            chunks=self.chunks,
            left_raw=self.left_raw,
            right_raw=self.right_raw,
            left_name=self.left_name,
            right_name=self.right_name,
            endpoint=endpoint,
            model=model
        )

        self.txt_output.setMarkdown(summary)
        self.lbl_status.setText("Generated successfully")

    def _copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.txt_output.toPlainText())
        self.lbl_status.setText("Copied to clipboard!")
