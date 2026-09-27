"""
Workspace Profile & Session Management Dialog
Allows users to save and load named comparison profiles.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QLineEdit, QMessageBox, QFrame
)
from app.core.session_manager import SessionManager
from app.ui.styles.icons import get_line_icon


class SessionProfileDialog(QDialog):
    """Dialog to manage named comparison workspace profiles."""

    def __init__(self, parent=None, current_session_data=None):
        super().__init__(parent)
        self.setWindowTitle("Workspace Profiles")
        self.resize(480, 360)
        self.current_data = current_session_data or []
        self.selected_profile_name = None

        self.setup_ui()
        self._refresh_list()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("📁 Comparison Profiles & Workspaces")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #1f2328;")
        layout.addWidget(title)

        # Profile List
        self.list_profiles = QListWidget()
        self.list_profiles.setStyleSheet("""
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: #ffffff;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.list_profiles, 1)

        # Save current session row
        save_frame = QFrame()
        s_layout = QHBoxLayout(save_frame)
        s_layout.setContentsMargins(0, 0, 0, 0)
        s_layout.setSpacing(8)

        self.txt_profile_name = QLineEdit()
        self.txt_profile_name.setPlaceholderText("New profile name...")
        self.txt_profile_name.setFixedHeight(30)
        s_layout.addWidget(self.txt_profile_name)

        self.btn_save = QPushButton(" Save Current Workspace")
        self.btn_save.setIcon(get_line_icon("save", "#0969da"))
        self.btn_save.setFixedHeight(30)
        self.btn_save.clicked.connect(self._save_profile)
        s_layout.addWidget(self.btn_save)

        layout.addWidget(save_frame)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_close = QPushButton("Cancel")
        self.btn_close.setFixedHeight(30)
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)

        self.btn_load = QPushButton("Load Profile")
        self.btn_load.setIcon(get_line_icon("check", "#ffffff"))
        self.btn_load.setObjectName("PrimaryButton")
        self.btn_load.setFixedHeight(30)
        self.btn_load.clicked.connect(self._load_selected)
        btn_layout.addWidget(self.btn_load)

        layout.addLayout(btn_layout)

    def _refresh_list(self):
        self.list_profiles.clear()
        profiles = SessionManager.load_all_profiles()
        for name in profiles.keys():
            self.list_profiles.addItem(name)

    def _save_profile(self):
        name = self.txt_profile_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a profile name.")
            return

        SessionManager.save_profile(name, self.current_data)
        self.txt_profile_name.clear()
        self._refresh_list()

    def _load_selected(self):
        item = self.list_profiles.currentItem()
        if not item:
            QMessageBox.warning(self, "Select Profile", "Please select a profile to load.")
            return
        self.selected_profile_name = item.text()
        self.accept()

    def get_loaded_profile_data(self):
        if not self.selected_profile_name:
            return None
        profiles = SessionManager.load_all_profiles()
        return profiles.get(self.selected_profile_name)
