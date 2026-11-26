"""
Remote Connection Profiles Dialog (SFTP / Amazon S3 / FTP / FTPS)
Manages named remote profiles cleanly without persisting plaintext passwords to disk.
Users can authenticate via SSH keys, environment variable names, AWS profiles, or
session-only secrets held strictly in RAM.
"""

from typing import Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QListWidget, QListWidgetItem, QFormLayout, QSpinBox,
    QFileDialog, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, Signal

from app.core.session_manager import SessionManager
from app.core.remote_vfs import RemoteVFS
from app.ui.styles.icons import get_line_icon


class RemoteProfileDialog(QDialog):
    """Fluent Light dialog to configure SFTP, S3, FTP, and FTPS profiles."""

    remoteSelected = Signal(str, str)  # (side: 'left'|'right', uri)

    DEFAULT_PORTS = {"sftp": 22, "s3": 443, "ftp": 21, "ftps": 990}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Remote Filesystem Profiles (SFTP / S3 / FTP)")
        self.resize(760, 520)
        self.selected_side = None
        self.selected_uri = None

        self.setup_ui()
        self._reload_profile_list()

    def setup_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(14, 14, 14, 14)
        main.setSpacing(10)

        head = QLabel("Configure SFTP, Amazon S3 / MinIO, FTP, or FTPS targets. Passwords are never saved to disk.")
        head.setStyleSheet("color: #475569; font-size: 12px;")
        main.addWidget(head)

        body = QHBoxLayout()
        body.setSpacing(12)

        # Left column: profile list
        left_col = QVBoxLayout()
        lbl_saved = QLabel("Saved Profiles")
        lbl_saved.setStyleSheet("font-weight: 700; color: #0f172a;")
        left_col.addWidget(lbl_saved)

        self.list_profiles = QListWidget()
        self.list_profiles.setFixedWidth(210)
        self.list_profiles.currentItemChanged.connect(self._on_profile_selected)
        left_col.addWidget(self.list_profiles, 1)

        list_btns = QHBoxLayout()
        self.btn_new = QPushButton(" New")
        self.btn_new.setIcon(get_line_icon("plus", "#1e293b"))
        self.btn_new.setFixedHeight(28)
        self.btn_new.clicked.connect(self._clear_form)
        list_btns.addWidget(self.btn_new)

        self.btn_delete = QPushButton(" Delete")
        self.btn_delete.setIcon(get_line_icon("trash", "#cf222e"))
        self.btn_delete.setFixedHeight(28)
        self.btn_delete.clicked.connect(self._delete_selected)
        list_btns.addWidget(self.btn_delete)
        left_col.addLayout(list_btns)
        body.addLayout(left_col)

        # Right column: form
        form_frame = QFrame()
        form_frame.setStyleSheet("QFrame { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; }")
        ff_layout = QVBoxLayout(form_frame)
        ff_layout.setContentsMargins(14, 14, 14, 14)
        ff_layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("e.g. prod-sftp or staging-s3")
        form.addRow("Profile Name:", self.txt_name)

        self.combo_proto = QComboBox()
        self.combo_proto.addItems(["sftp", "s3", "ftp", "ftps"])
        self.combo_proto.currentTextChanged.connect(self._on_proto_changed)
        form.addRow("Protocol:", self.combo_proto)

        host_row = QHBoxLayout()
        self.txt_host = QLineEdit()
        self.txt_host.setPlaceholderText("sftp.example.com (or custom S3 endpoint URL)")
        self.spin_port = QSpinBox()
        self.spin_port.setRange(1, 65535)
        self.spin_port.setValue(22)
        self.spin_port.setFixedWidth(80)
        host_row.addWidget(self.txt_host, 1)
        host_row.addWidget(QLabel("Port:"))
        host_row.addWidget(self.spin_port)
        form.addRow("Host / Endpoint:", host_row)

        self.txt_bucket = QLineEdit()
        self.txt_bucket.setPlaceholderText("S3 Bucket Name (required for s3://)")
        form.addRow("S3 Bucket:", self.txt_bucket)

        self.txt_region = QLineEdit()
        self.txt_region.setPlaceholderText("us-east-1 (optional for s3://)")
        form.addRow("S3 Region:", self.txt_region)

        self.txt_base_path = QLineEdit()
        self.txt_base_path.setPlaceholderText("/var/www/app or s3/prefix")
        form.addRow("Base Path / Prefix:", self.txt_base_path)

        self.txt_user = QLineEdit()
        self.txt_user.setPlaceholderText("SSH/FTP username or AWS Access Key ID")
        form.addRow("Username / Key ID:", self.txt_user)

        self.txt_aws_profile = QLineEdit()
        self.txt_aws_profile.setPlaceholderText("Optional AWS CLI profile name (from ~/.aws)")
        form.addRow("AWS Profile:", self.txt_aws_profile)

        key_row = QHBoxLayout()
        self.txt_key_path = QLineEdit()
        self.txt_key_path.setPlaceholderText("~/.ssh/id_ed25519 (optional for SFTP)")
        btn_key = QPushButton("Browse...")
        btn_key.setFixedHeight(26)
        btn_key.clicked.connect(self._browse_key)
        key_row.addWidget(self.txt_key_path, 1)
        key_row.addWidget(btn_key)
        form.addRow("SSH Private Key:", key_row)

        self.txt_pass_env = QLineEdit()
        self.txt_pass_env.setPlaceholderText("Env var holding password / secret key (e.g. MY_SFTP_PASS)")
        form.addRow("Secret Env Var:", self.txt_pass_env)

        self.txt_session_secret = QLineEdit()
        self.txt_session_secret.setEchoMode(QLineEdit.Password)
        self.txt_session_secret.setPlaceholderText("In-memory session password/secret (never saved to disk)")
        form.addRow("Session Secret:", self.txt_session_secret)

        ff_layout.addLayout(form)

        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color: #475569; font-size: 11.5px; font-weight: 600; border: none; background: transparent;")
        ff_layout.addWidget(self.lbl_status)

        body.addWidget(form_frame, 1)
        main.addLayout(body, 1)

        # Bottom action buttons
        foot = QHBoxLayout()
        self.btn_test = QPushButton(" Test Connection")
        self.btn_test.setIcon(get_line_icon("zap", "#0969da"))
        self.btn_test.setFixedHeight(30)
        self.btn_test.clicked.connect(self._test_connection)
        foot.addWidget(self.btn_test)

        self.btn_save = QPushButton(" Save Profile")
        self.btn_save.setIcon(get_line_icon("save", "#1e293b"))
        self.btn_save.setFixedHeight(30)
        self.btn_save.clicked.connect(self.save_current_profile)
        foot.addWidget(self.btn_save)

        foot.addStretch()

        self.btn_load_left = QPushButton(" Load Left")
        self.btn_load_left.setIcon(get_line_icon("arrow-left", "#ffffff"))
        self.btn_load_left.setObjectName("PrimaryButton")
        self.btn_load_left.setFixedHeight(30)
        self.btn_load_left.clicked.connect(lambda: self.load_into_side("left"))
        foot.addWidget(self.btn_load_left)

        self.btn_load_right = QPushButton(" Load Right")
        self.btn_load_right.setIcon(get_line_icon("arrow-right", "#ffffff"))
        self.btn_load_right.setObjectName("PrimaryButton")
        self.btn_load_right.setFixedHeight(30)
        self.btn_load_right.clicked.connect(lambda: self.load_into_side("right"))
        foot.addWidget(self.btn_load_right)

        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(30)
        btn_close.clicked.connect(self.reject)
        foot.addWidget(btn_close)
        main.addLayout(foot)

        self._on_proto_changed(self.combo_proto.currentText())

    def _on_proto_changed(self, proto: str):
        self.spin_port.setValue(self.DEFAULT_PORTS.get(proto, 22))
        is_s3 = (proto == "s3")
        is_sftp = (proto == "sftp")
        self.txt_bucket.setEnabled(is_s3)
        self.txt_region.setEnabled(is_s3)
        self.txt_aws_profile.setEnabled(is_s3)
        self.txt_key_path.setEnabled(is_sftp)

    def _browse_key(self):
        p, _ = QFileDialog.getOpenFileName(self, "Select SSH Private Key")
        if p:
            self.txt_key_path.setText(p)

    def _clear_form(self):
        self.txt_name.clear()
        self.combo_proto.setCurrentText("sftp")
        self.txt_host.clear()
        self.txt_bucket.clear()
        self.txt_region.clear()
        self.txt_base_path.clear()
        self.txt_user.clear()
        self.txt_aws_profile.clear()
        self.txt_key_path.clear()
        self.txt_pass_env.clear()
        self.txt_session_secret.clear()
        self.lbl_status.setText("New profile")

    def _reload_profile_list(self, select_name: str = ""):
        self.list_profiles.clear()
        profiles = SessionManager.get_remote_profiles()
        for name in sorted(profiles.keys()):
            proto = profiles[name].get("protocol", "sftp")
            item = QListWidgetItem(f"[{proto.upper()}] {name}")
            item.setData(Qt.UserRole, name)
            self.list_profiles.addItem(item)
            if select_name and name == select_name:
                self.list_profiles.setCurrentItem(item)

    def _on_profile_selected(self, current: QListWidgetItem, _prev):
        if not current:
            return
        name = current.data(Qt.UserRole)
        cfg = SessionManager.get_remote_profiles().get(name, {})
        if not cfg:
            return
        self.txt_name.setText(name)
        self.combo_proto.setCurrentText(cfg.get("protocol", "sftp"))
        self.txt_host.setText(cfg.get("endpoint_url") or cfg.get("host", ""))
        self.spin_port.setValue(int(cfg.get("port", self.DEFAULT_PORTS.get(cfg.get("protocol", "sftp"), 22))))
        self.txt_bucket.setText(cfg.get("bucket", ""))
        self.txt_region.setText(cfg.get("region", ""))
        self.txt_base_path.setText(cfg.get("base_path", ""))
        self.txt_user.setText(cfg.get("username", ""))
        self.txt_aws_profile.setText(cfg.get("aws_profile", ""))
        self.txt_key_path.setText(cfg.get("key_path", ""))
        self.txt_pass_env.setText(cfg.get("password_env", ""))
        self.txt_session_secret.setText(RemoteVFS.get_session_secret(name) or "")

    def _gather_config(self) -> Dict[str, Any]:
        proto = self.combo_proto.currentText()
        host_val = self.txt_host.text().strip()
        return {
            "name": self.txt_name.text().strip(),
            "protocol": proto,
            "host": "" if proto == "s3" else host_val,
            "endpoint_url": host_val if (proto == "s3" and host_val.startswith("http")) else "",
            "port": self.spin_port.value(),
            "bucket": self.txt_bucket.text().strip(),
            "region": self.txt_region.text().strip(),
            "base_path": self.txt_base_path.text().strip(),
            "username": self.txt_user.text().strip(),
            "aws_profile": self.txt_aws_profile.text().strip(),
            "key_path": self.txt_key_path.text().strip(),
            "password_env": self.txt_pass_env.text().strip(),
        }

    def save_current_profile(self) -> bool:
        cfg = self._gather_config()
        name = cfg["name"]
        if not name:
            self.lbl_status.setText("Profile Name is required.")
            return False
        SessionManager.save_remote_profile(name, cfg)
        RemoteVFS.set_session_secret(name, self.txt_session_secret.text())
        self._reload_profile_list(select_name=name)
        self.lbl_status.setText(f"Saved profile '{name}' -> {RemoteVFS.build_remote_uri(cfg['protocol'], name)}")
        return True

    def _delete_selected(self):
        item = self.list_profiles.currentItem()
        if not item:
            return
        name = item.data(Qt.UserRole)
        SessionManager.delete_remote_profile(name)
        RemoteVFS.set_session_secret(name, "")
        self._clear_form()
        self._reload_profile_list()

    def _test_connection(self):
        cfg = self._gather_config()
        secret = self.txt_session_secret.text() or RemoteVFS.get_session_secret(cfg["name"])
        ok, msg = RemoteVFS.test_connection(cfg, session_secret=secret)
        self.lbl_status.setStyleSheet(
            f"color: {'#1a7f37' if ok else '#cf222e'}; font-size: 11.5px; font-weight: 700; border: none; background: transparent;"
        )
        self.lbl_status.setText(msg)

    def load_into_side(self, side: str) -> str:
        if not self.save_current_profile():
            return ""
        cfg = self._gather_config()
        uri = RemoteVFS.build_remote_uri(cfg["protocol"], cfg["name"])
        self.selected_side = side
        self.selected_uri = uri
        self.remoteSelected.emit(side, uri)
        self.accept()
        return uri
