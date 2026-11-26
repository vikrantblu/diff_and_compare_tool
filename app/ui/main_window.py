"""
Modern Desktop Main Window Shell (White / Light Theme Only)
Houses the Multi-Format Comparison Studios:
1. 2-Way Text & Code Diff (Myers + diff_match_patch + Moved Blocks + AST + AI Summary)
2. 3-Way Merge Studio (Ancestors, Conflicts, AI Resolve)
3. Directory & Virtual Archive Comparison (SHA-256 / BLAKE3 / VFS / Folder Sync)
4. Visual Media & PDF Diff (Swipe Curtain, Onion-Skin, Pixel Heatmap, Flicker, Zoom)
5. Tabular / Spreadsheet Diff (Keyed Row Alignment, CSV/TSV/Excel/Parquet/SQLite)
6. Structured Tree & API Contract Diff (JSON/YAML/XML + OpenAPI/GraphQL/Protobuf Audit)
7. Hex & Binary Diff (Virtualized Memory-Mapped Multi-GB Inspector)

With multi-session tabs, unsaved-changes guards, workspace profile persistence, and Git CLI integration.
"""

import os
import sys
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QTabBar, QVBoxLayout, QHBoxLayout, QWidget, QStatusBar,
    QLabel, QPushButton, QMenu, QMessageBox, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut

from app.ui.home_view import HomeView
from app.ui.diff_view import DiffView
from app.ui.merge_view import MergeView
from app.ui.dir_compare_view import DirCompareView
from app.ui.image_diff_view import ImageDiffView
from app.ui.tabular_diff_view import TabularDiffView
from app.ui.structured_diff_view import StructuredDiffView
from app.ui.hex_diff_view import HexDiffView
from app.ui.dialogs.session_dialog import SessionProfileDialog

from app.ui.styles.theme import MODERN_LIGHT_QSS
from app.ui.styles.icons import get_line_icon, get_app_icon
from app.ui.styles.windows_effects import apply_windows_material, BACKDROP_MICA_ALT
from app.core.session_manager import SessionManager
from app.core.archive_vfs import ArchiveVFS
from app.core.file_io import is_vfs_path
from app.core.shell_integration import install_context_menu, uninstall_context_menu


class MainWindow(QMainWindow):
    """Modern Desktop-Grade Diff & Merge Application Shell (White / Light Mode)."""

    @property
    def diff_tab(self) -> DiffView:
        return self._get_or_create_tab(DiffView, "text")

    @property
    def merge_tab(self) -> MergeView:
        return self._get_or_create_tab(MergeView, "merge")

    @property
    def dir_compare_tab(self) -> DirCompareView:
        return self._get_or_create_tab(DirCompareView, "folder")

    @property
    def image_tab(self) -> ImageDiffView:
        return self._get_or_create_tab(ImageDiffView, "image")

    @property
    def table_tab(self) -> TabularDiffView:
        return self._get_or_create_tab(TabularDiffView, "table")

    @property
    def structured_tab(self) -> StructuredDiffView:
        return self._get_or_create_tab(StructuredDiffView, "structured")

    @property
    def hex_tab(self) -> HexDiffView:
        return self._get_or_create_tab(HexDiffView, "hex")

    def __init__(self):
        super().__init__()
        self.setWindowTitle("diff_and_compare_tool — Next-Gen Diff & Merge Studio")
        self.setWindowIcon(get_app_icon())
        self.resize(1380, 880)

        self.setStyleSheet(MODERN_LIGHT_QSS)

        # Apply Windows 11 DWM Mica Alt Light Backdrop
        apply_windows_material(int(self.winId()), backdrop_type=BACKDROP_MICA_ALT, dark_mode=False)

        self.setup_ui()
        self.setup_menu()
        self.setup_status_bar()
        QShortcut(QKeySequence("Ctrl+W"), self, self._close_current_tab)

        self._restore_session_if_available()
        self._check_crash_recovery()

    def setup_ui(self):
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabCloseRequested.connect(self._on_tab_close)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.home_tab = HomeView()
        self.tabs.addTab(self.home_tab, get_line_icon("sparkles", "#0969da"), " Home")
        self.tabs.setTabToolTip(0, "diff_and_compare Home / Welcome Screen & Session Launcher")
        self.home_tab.sessionSelected.connect(self._on_home_session_selected)
        self.home_tab.compareFilesRequested.connect(self.smart_open_comparison)
        self.home_tab.clipboardCompareRequested.connect(self._compare_clipboard)
        self._update_tab_close_buttons()

        c_row = QWidget()
        r_layout = QHBoxLayout(c_row)
        r_layout.setContentsMargins(0, 4, 8, 4)
        r_layout.setSpacing(6)

        self.btn_home_corner = QPushButton(" Home")
        self.btn_home_corner.setIcon(get_line_icon("sparkles", "#0969da"))
        self.btn_home_corner.setFixedHeight(28)
        self.btn_home_corner.clicked.connect(self.show_home_tab)
        r_layout.addWidget(self.btn_home_corner)

        self.btn_new_tab = QPushButton(" New Tab")
        self.btn_new_tab.setIcon(get_line_icon("plus", "#0969da"))
        self.btn_new_tab.setFixedHeight(28)

        new_menu = QMenu(self)
        new_menu.addAction(get_line_icon("diff", "#0969da"), "Text & Code Comparison").triggered.connect(lambda: self.add_new_tab("text"))
        new_menu.addAction(get_line_icon("git-merge", "#1a7f37"), "3-Way Merge Studio").triggered.connect(lambda: self.add_new_tab("merge"))
        new_menu.addAction(get_line_icon("folder", "#0969da"), "Folder / Archive Comparison").triggered.connect(lambda: self.add_new_tab("folder"))
        new_menu.addAction(get_line_icon("image", "#8250df"), "Image & PDF Diff").triggered.connect(lambda: self.add_new_tab("image"))
        new_menu.addAction(get_line_icon("table", "#1a7f37"), "Tabular / CSV Spreadsheet Diff").triggered.connect(lambda: self.add_new_tab("table"))
        new_menu.addAction(get_line_icon("code", "#cf222e"), "Structured Data (JSON/YAML/XML)").triggered.connect(lambda: self.add_new_tab("structured"))
        new_menu.addAction(get_line_icon("shield", "#0969da"), "API Contract Audit (OpenAPI/GraphQL/Proto)").triggered.connect(lambda: self.add_new_tab("contract"))
        new_menu.addAction(get_line_icon("cpu", "#57606a"), "Hex & Binary Inspector").triggered.connect(lambda: self.add_new_tab("hex"))

        self.btn_new_tab.setMenu(new_menu)
        r_layout.addWidget(self.btn_new_tab)

        self.btn_profiles = QPushButton(" Workspaces")
        self.btn_profiles.setIcon(get_line_icon("folder", "#475569"))
        self.btn_profiles.setFixedHeight(28)
        self.btn_profiles.clicked.connect(self._open_profiles_dialog)
        r_layout.addWidget(self.btn_profiles)

        self.tabs.setCornerWidget(c_row, Qt.TopRightCorner)

        layout.addWidget(self.tabs)
        self.setCentralWidget(central_widget)

    def setup_status_bar(self):
        status = QStatusBar()
        self.setStatusBar(status)

        self.lbl_status = QLabel("  ● Ready")
        self.lbl_status.setStyleSheet("color: #0969da; font-weight: 600; padding: 2px 8px; background: #e0f2fe; border: 1px solid #bae6fd; border-radius: 10px; font-size: 11px;")

        self.lbl_engine = QLabel("Engine: Myers + Intraline DMP + AST + Diff3")
        self.lbl_engine.setStyleSheet("color: #64748b; font-size: 11px; padding: 0 8px; border-left: 1px solid #cbd5e1;")

        self.lbl_env = QLabel("White Fluent Mode | MMF Streaming | UTF-8")
        self.lbl_env.setStyleSheet("color: #64748b; font-size: 11px; padding: 0 8px; border-left: 1px solid #cbd5e1;")

        status.addWidget(self.lbl_status)
        status.addPermanentWidget(self.lbl_engine)
        status.addPermanentWidget(self.lbl_env)

    def _count_tabs(self, view_class) -> int:
        return sum(1 for i in range(self.tabs.count()) if isinstance(self.tabs.widget(i), view_class))

    def _update_tab_close_buttons(self):
        home_idx = self.tabs.indexOf(self.home_tab)
        if home_idx != -1:
            bar = self.tabs.tabBar()
            bar.setTabButton(home_idx, QTabBar.ButtonPosition.RightSide, None)
            bar.setTabButton(home_idx, QTabBar.ButtonPosition.LeftSide, None)

    def show_home_tab(self):
        idx = self.tabs.indexOf(self.home_tab)
        if idx == -1:
            self.tabs.insertTab(0, self.home_tab, get_line_icon("sparkles", "#0969da"), " Home")
            self.tabs.setTabToolTip(0, "diff_and_compare Home / Welcome Screen & Session Launcher")
            self._update_tab_close_buttons()
            self.tabs.setCurrentIndex(0)
        else:
            self.tabs.setCurrentIndex(idx)
        self.home_tab.refresh_state()

    def _is_tab_empty(self, w) -> bool:
        if isinstance(w, DiffView):
            if not getattr(w, "_is_sample_state", False):
                return (
                    not getattr(w.left_header, "current_file_path", "")
                    and not getattr(w.right_header, "current_file_path", "")
                    and not getattr(w, "_raw_left", "")
                    and not getattr(w, "_raw_right", "")
                )
            return not w.has_unsaved_changes()
        elif isinstance(w, MergeView):
            if not getattr(w, "_is_sample_state", False):
                return (
                    not getattr(w.header_mine, "current_file_path", "")
                    and not getattr(w.header_theirs, "current_file_path", "")
                    and not getattr(w.header_base, "current_file_path", "")
                )
            return not w.has_unsaved_changes()
        elif isinstance(w, DirCompareView):
            return (
                not getattr(w, "left_dir", "")
                and not getattr(w, "right_dir", "")
                and not w.txt_left_path.text().strip()
                and not w.txt_right_path.text().strip()
            )
        elif isinstance(w, ImageDiffView):
            return not getattr(w, "left_path", None) and not getattr(w, "right_path", None)
        elif isinstance(w, TabularDiffView):
            return not getattr(w, "left_path", None) and not getattr(w, "right_path", None)
        elif isinstance(w, StructuredDiffView):
            return not getattr(w, "left_path", None) and not getattr(w, "right_path", None)
        elif isinstance(w, HexDiffView):
            return not getattr(w, "left_path", None) and not getattr(w, "right_path", None)
        return False

    def _get_or_create_tab(self, view_class, mode: str, allow_reuse_empty: bool = True):
        """Finds an existing empty tab or creates a new one, adds it to tabs, and activates it."""
        if allow_reuse_empty:
            for i in range(self.tabs.count()):
                w = self.tabs.widget(i)
                if isinstance(w, view_class) and self._is_tab_empty(w):
                    self.tabs.setCurrentIndex(i)
                    return w
        return self.add_new_tab(mode)

    def _update_widget_tab_title(self, widget: QWidget, left_path: str, right_path: str, fallback: str):
        idx = self.tabs.indexOf(widget)
        if idx == -1:
            return
        l_name = os.path.basename(left_path) if left_path else ""
        r_name = os.path.basename(right_path) if right_path else ""
        if l_name and r_name:
            self.tabs.setTabText(idx, f" {l_name} ↔ {r_name}")
            self.tabs.setTabToolTip(idx, f"{left_path}\nvs\n{right_path}")
        elif l_name or r_name:
            self.tabs.setTabText(idx, f" {l_name or r_name}")
        else:
            self.tabs.setTabText(idx, fallback)

    def add_new_tab(self, mode: str):
        if mode == "text":
            w = DiffView()
            w.statusMessage.connect(lambda msg: self.lbl_status.setText(f"  ● {msg}"))
            w.filesChanged.connect(lambda lp, rp, widget=w: self._update_widget_tab_title(widget, lp, rp, " 2-Way Text"))
            count = self._count_tabs(DiffView)
            title = " 2-Way Text" if count == 0 else f" Text Diff ({count + 1})"
            idx = self.tabs.addTab(w, get_line_icon("diff", "#0969da"), title)
            self.tabs.setTabToolTip(idx, "2-Way Side-by-Side Text & Code Difference Studio")
        elif mode == "merge":
            w = MergeView()
            count = self._count_tabs(MergeView)
            title = " 3-Way Merge" if count == 0 else f" Merge ({count + 1})"
            idx = self.tabs.addTab(w, get_line_icon("git-merge", "#1a7f37"), title)
            self.tabs.setTabToolTip(idx, "3-Way Ancestor Conflict Resolution Merge Studio")
        elif mode in ("folder", "folder_merge", "folder_sync"):
            w = DirCompareView(initial_mode=mode)
            w.openInDiffRequested.connect(self.smart_open_comparison)
            w.homeRequested.connect(self.show_home_tab)
            count = self._count_tabs(DirCompareView)
            base_title = " Folders & VFS" if mode == "folder" else (" Folder Merge" if mode == "folder_merge" else " Folder Sync")
            icon_name = "folder" if mode == "folder" else ("folder-merge" if mode == "folder_merge" else "folder-sync")
            icon_color = "#0969da" if mode == "folder" else ("#b45309" if mode == "folder_merge" else "#059669")
            title = base_title if count == 0 else f"{base_title} ({count + 1})"
            idx = self.tabs.addTab(w, get_line_icon(icon_name, icon_color), title)
            self.tabs.setTabToolTip(idx, "Dual-Tree Directory & Virtual Archive Comparison")
        elif mode == "image":
            w = ImageDiffView()
            count = self._count_tabs(ImageDiffView)
            title = " Image Diff" if count == 0 else f" Image Diff ({count + 1})"
            idx = self.tabs.addTab(w, get_line_icon("image", "#8250df"), title)
            self.tabs.setTabToolTip(idx, "Visual Media & PDF Difference Studio (Curtain/Heatmap)")
        elif mode == "table":
            w = TabularDiffView()
            count = self._count_tabs(TabularDiffView)
            title = " Table & CSV" if count == 0 else f" Table Diff ({count + 1})"
            idx = self.tabs.addTab(w, get_line_icon("table", "#1a7f37"), title)
            self.tabs.setTabToolTip(idx, "Tabular & Spreadsheet Keyed Grid Diff (CSV/TSV/Excel)")
        elif mode in ("structured", "contract"):
            w = StructuredDiffView(initial_mode=("contract" if mode == "contract" else "tree"))
            count = self._count_tabs(StructuredDiffView)
            if mode == "contract":
                title = " API Contract" if count == 0 else f" API Contract ({count + 1})"
                icon = get_line_icon("shield", "#0969da")
                tip = "API Contract Breaking-Change Audit (OpenAPI / GraphQL / Protobuf)"
            else:
                title = " Tree (JSON/XML)" if count == 0 else f" JSON/XML ({count + 1})"
                icon = get_line_icon("code", "#cf222e")
                tip = "Structured Data Hierarchical Tree Diff (JSON/YAML/XML)"
            idx = self.tabs.addTab(w, icon, title)
            self.tabs.setTabToolTip(idx, tip)
        elif mode == "hex":
            w = HexDiffView()
            count = self._count_tabs(HexDiffView)
            title = " Hex & Binary" if count == 0 else f" Hex Diff ({count + 1})"
            idx = self.tabs.addTab(w, get_line_icon("cpu", "#57606a"), title)
            self.tabs.setTabToolTip(idx, "Memory-Mapped Hexadecimal & Binary Inspector")
        else:
            return None

        self._update_tab_close_buttons()
        self.tabs.setCurrentIndex(self.tabs.count() - 1)
        return w

    def _close_current_tab(self):
        idx = self.tabs.currentIndex()
        if idx > 0:
            self._on_tab_close(idx)

    def _on_tab_close(self, index: int):
        w = self.tabs.widget(index)
        if w == self.home_tab:
            return

        if hasattr(w, "has_unsaved_changes") and w.has_unsaved_changes():
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"Tab '{self.tabs.tabText(index).strip()}' has unsaved changes.\nClose without saving?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        if isinstance(w, DirCompareView):
            w._cancel_worker()

        if hasattr(w, "wal") and w.wal:
            try:
                w.wal.clean_exit()
            except Exception:
                pass

        self.tabs.removeTab(index)
        self._update_tab_close_buttons()

    def _open_profiles_dialog(self):
        tabs_info = self._get_current_session_data()
        dialog = SessionProfileDialog(self, current_session_data=tabs_info)
        if dialog.exec():
            loaded_data = dialog.get_loaded_profile_data()
            if loaded_data:
                self._restore_tabs_from_data(loaded_data)
                self.lbl_status.setText(f"  ● Loaded Profile: {dialog.selected_profile_name}")

    def _get_current_session_data(self):
        data = []
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            t_name = type(w).__name__
            tab_info = {"index": i, "type": t_name, "title": self.tabs.tabText(i)}

            if isinstance(w, DiffView):
                if getattr(w, "_is_sample_state", False):
                    continue
                tab_info["left_path"] = getattr(w.left_header, "current_file_path", "") or ""
                tab_info["right_path"] = getattr(w.right_header, "current_file_path", "") or ""
            elif isinstance(w, DirCompareView):
                tab_info["left_path"] = w.txt_left_path.text().strip()
                tab_info["right_path"] = w.txt_right_path.text().strip()
            elif isinstance(w, ImageDiffView):
                tab_info["left_path"] = getattr(w, "left_path", "") or ""
                tab_info["right_path"] = getattr(w, "right_path", "") or ""
            elif isinstance(w, TabularDiffView):
                tab_info["left_path"] = getattr(w, "left_path", "") or ""
                tab_info["right_path"] = getattr(w, "right_path", "") or ""
            elif isinstance(w, StructuredDiffView):
                tab_info["left_path"] = getattr(w, "left_path", "") or ""
                tab_info["right_path"] = getattr(w, "right_path", "") or ""
                tab_info["contract_mode"] = bool(w.btn_contract_view.isChecked())
            elif isinstance(w, HexDiffView):
                tab_info["left_path"] = getattr(w, "left_path", "") or ""
                tab_info["right_path"] = getattr(w, "right_path", "") or ""
            elif isinstance(w, MergeView):
                if getattr(w, "_is_sample_state", False):
                    continue
                tab_info["mine_path"] = getattr(w.header_mine, "current_file_path", "") or ""
                tab_info["base_path"] = getattr(w.header_base, "current_file_path", "") or ""
                tab_info["theirs_path"] = getattr(w.header_theirs, "current_file_path", "") or ""
                tab_info["output_path"] = getattr(w.header_output, "current_file_path", "") or ""
            else:
                continue

            data.append(tab_info)
        return data

    def _restore_tabs_from_data(self, tabs: list):
        for tab_info in tabs:
            t_name = tab_info.get("type")
            l_path = tab_info.get("left_path")
            r_path = tab_info.get("right_path")

            if t_name == "DiffView" and (l_path or r_path):
                self.open_file_diff(l_path or "", r_path or "")
            elif t_name == "DirCompareView" and (l_path or r_path):
                self.open_folder_diff(l_path or "", r_path or "")
            elif t_name == "ImageDiffView" and (l_path or r_path):
                self.open_image_diff(l_path or "", r_path or "")
            elif t_name == "TabularDiffView" and (l_path or r_path):
                self.open_table_diff(l_path or "", r_path or "")
            elif t_name == "StructuredDiffView" and (l_path or r_path):
                if tab_info.get("contract_mode"):
                    self.open_contract_diff(l_path or "", r_path or "")
                else:
                    self.open_structured_diff(l_path or "", r_path or "")
            elif t_name == "HexDiffView" and (l_path or r_path):
                self.open_hex_diff(l_path or "", r_path or "")
            elif t_name == "MergeView" and (tab_info.get("mine_path") or tab_info.get("theirs_path")):
                self.open_3way_merge(
                    tab_info.get("mine_path", ""),
                    tab_info.get("base_path", ""),
                    tab_info.get("theirs_path", ""),
                    tab_info.get("output_path", "")
                )

    def _restore_session_if_available(self):
        session = SessionManager.load_session()
        if not session:
            return
        tabs = session.get("tabs", [])
        self._restore_tabs_from_data(tabs)
        if "active_index" in session:
            idx = session["active_index"]
            if 0 <= idx < self.tabs.count():
                self.tabs.setCurrentIndex(idx)
            else:
                self.tabs.setCurrentIndex(0)

    def _check_crash_recovery(self):
        """Checks for unrecovered WAL journals from previous abnormal shutdowns."""
        from app.core.wal_journal import WALJournal
        unrecovered = WALJournal.get_unrecovered_sessions()
        if not unrecovered:
            return

        count = len(unrecovered)
        files_str = "\n".join(f"• {u['file_path']} ({u['pane']} pane)" for u in unrecovered[:5])
        if count > 5:
            files_str += f"\n... and {count - 5} more"

        reply = QMessageBox.question(
            self,
            "Crash Recovery — Unsaved Work Detected",
            f"diff_and_compare_tool detected {count} unsaved buffer modification(s) from an unexpected termination:\n\n{files_str}\n\nWould you like to recover this work?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply == QMessageBox.Yes:
            tab = self.open_file_diff()
            tab._is_sample_state = False
            recovered_wals = set()
            for u in unrecovered:
                if u["pane"] == "left":
                    tab._raw_left = u["content"]
                    tab.left_header.set_file_info(u["file_path"], dirty=True, display_title=f"{os.path.basename(u['file_path'])} (Recovered)")
                elif u["pane"] == "right":
                    tab._raw_right = u["content"]
                    tab.right_header.set_file_info(u["file_path"], dirty=True, display_title=f"{os.path.basename(u['file_path'])} (Recovered)")
                if u.get("wal_file"):
                    recovered_wals.add(u["wal_file"])
            tab.run_diff()
            for wf in recovered_wals:
                WALJournal.discard_wal(wf)
            self.lbl_status.setText(f"  ● Recovered {count} buffer(s) from WAL crash journal")
        else:
            WALJournal.discard_all_unrecovered()

    def closeEvent(self, event):
        dirty_tabs = [
            self.tabs.tabText(i).strip()
            for i in range(1, self.tabs.count())
            if hasattr(self.tabs.widget(i), "has_unsaved_changes") and self.tabs.widget(i).has_unsaved_changes()
        ]
        if dirty_tabs:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"The following tab(s) have unsaved changes:\n• " + "\n• ".join(dirty_tabs[:5]) + "\n\nExit without saving?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                event.ignore()
                return

        tabs_data = self._get_current_session_data()
        SessionManager.save_session(tabs_data, self.tabs.currentIndex())

        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, DirCompareView):
                w._cancel_worker()
            if hasattr(w, "wal") and w.wal:
                try:
                    w.wal.clean_exit()
                except Exception:
                    pass

        super().closeEvent(event)

    def setup_menu(self):
        menubar = self.menuBar()

        menu_session = menubar.addMenu("&Session")
        menu_session.addAction(get_line_icon("sparkles", "#0969da"), "Home Screen").triggered.connect(self.show_home_tab)
        menu_session.addSeparator()
        menu_session.addAction(get_line_icon("diff", "#0969da"), "New 2-Way Text Diff").triggered.connect(lambda: self.add_new_tab("text"))
        menu_session.addAction(get_line_icon("git-merge", "#1a7f37"), "New 3-Way Merge").triggered.connect(lambda: self.add_new_tab("merge"))
        menu_session.addAction(get_line_icon("folder", "#0969da"), "New Folder Compare").triggered.connect(lambda: self.add_new_tab("folder"))
        menu_session.addAction(get_line_icon("image", "#8250df"), "New Image & PDF Diff").triggered.connect(lambda: self.add_new_tab("image"))
        menu_session.addAction(get_line_icon("table", "#1a7f37"), "New Table & CSV Diff").triggered.connect(lambda: self.add_new_tab("table"))
        menu_session.addAction(get_line_icon("code", "#cf222e"), "New Structured Tree Diff").triggered.connect(lambda: self.add_new_tab("structured"))
        menu_session.addAction(get_line_icon("shield", "#0969da"), "New API Contract Audit").triggered.connect(lambda: self.add_new_tab("contract"))
        menu_session.addAction(get_line_icon("cpu", "#57606a"), "New Hex & Binary Diff").triggered.connect(lambda: self.add_new_tab("hex"))
        menu_session.addSeparator()
        menu_session.addAction(get_line_icon("folder", "#0969da"), "Workspace Profiles...").triggered.connect(self._open_profiles_dialog)
        menu_session.addAction("Exit").triggered.connect(self.close)

        menu_tools = menubar.addMenu("&Tools")
        menu_tools.addAction(get_line_icon("clipboard", "#0969da"), "Compare Clipboard in Text Studio").triggered.connect(self._compare_clipboard)
        if sys.platform == "win32":
            menu_tools.addSeparator()
            menu_tools.addAction(get_line_icon("check", "#16a34a"), "Install Windows Explorer Menu ('Select Left', 'Select Right')").triggered.connect(self._install_shell_menu)
            menu_tools.addAction(get_line_icon("x", "#cf222e"), "Uninstall Windows Explorer Menu").triggered.connect(self._uninstall_shell_menu)

    def _compare_clipboard(self):
        clip = QApplication.clipboard().text()
        tab = self.open_file_diff()
        tab._is_sample_state = False
        tab._raw_left = clip or ""
        tab.left_header.set_file_info("Clipboard (Left)", dirty=False)
        tab.run_diff()
        self.lbl_status.setText("  ● Loaded clipboard contents into Left pane")

    def _install_shell_menu(self):
        ok, msg = install_context_menu()
        QMessageBox.information(self, "Windows Explorer Menu", msg)
        self.home_tab.refresh_state()

    def _uninstall_shell_menu(self):
        ok, msg = uninstall_context_menu()
        QMessageBox.information(self, "Windows Explorer Menu", msg)
        self.home_tab.refresh_state()

    def _on_tab_changed(self, index: int):
        self._update_tab_close_buttons()
        if 0 <= index < self.tabs.count():
            widget = self.tabs.widget(index)
            if widget == self.home_tab:
                self.home_tab.refresh_state()

    def _on_home_session_selected(self, mode_id: str):
        if mode_id == "folder":
            self.open_folder_diff(mode="folder")
        elif mode_id == "folder_merge":
            self.open_folder_diff(mode="folder_merge")
        elif mode_id == "folder_sync":
            self.open_folder_diff(mode="folder_sync")
        elif mode_id == "text":
            self.open_file_diff()
        elif mode_id == "merge":
            self.open_3way_merge()
        elif mode_id == "image":
            self.open_image_diff()
        elif mode_id == "table":
            self.open_table_diff()
        elif mode_id == "structured":
            self.open_structured_diff()
        elif mode_id == "contract":
            self.open_contract_diff()
        elif mode_id == "hex":
            self.open_hex_diff()

    def smart_open_comparison(self, left_path: str, right_path: str, left_title: str = None, right_title: str = None):
        """Intelligently detects file types and opens the corresponding comparison studio."""
        if not left_path and not right_path:
            return

        if not is_vfs_path(left_path or "") and not is_vfs_path(right_path or ""):
            if (left_path and (os.path.isdir(left_path) or ArchiveVFS.is_archive(left_path))) or \
               (right_path and (os.path.isdir(right_path) or ArchiveVFS.is_archive(right_path))):
                self.open_folder_diff(left_path, right_path)
                return

        ext = os.path.splitext(left_path or right_path)[1].lower()
        if ext in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".svg", ".tiff", ".ico", ".pdf"}:
            self.open_image_diff(left_path, right_path)
        elif ext in {".csv", ".tsv", ".xlsx", ".xls", ".parquet", ".sqlite", ".db"}:
            self.open_table_diff(left_path, right_path)
        elif ext in {".proto", ".graphql", ".gql"}:
            self.open_contract_diff(left_path, right_path)
        elif ext in {".json", ".yaml", ".yml", ".xml"}:
            self.open_structured_diff(left_path, right_path)
        elif ext in {".exe", ".dll", ".bin", ".dat", ".so", ".o", ".class", ".pyc"}:
            self.open_hex_diff(left_path, right_path)
        else:
            self.open_file_diff(left_path, right_path, left_title=left_title, right_title=right_title)

    def _record_recent(self, left_path: str, right_path: str, mode: str):
        if left_path and right_path and os.path.exists(left_path) and os.path.exists(right_path):
            SessionManager.add_recent_comparison(left_path, right_path, mode)

    def open_folder_diff(self, left_path: str = "", right_path: str = "", mode: str = "folder") -> DirCompareView:
        tab = self._get_or_create_tab(DirCompareView, mode)
        self.tabs.setCurrentWidget(tab)
        if left_path or right_path:
            tab.set_directories(left_path, right_path)
            self._update_widget_tab_title(tab, left_path, right_path, " Folders & VFS")
            self._record_recent(left_path, right_path, mode)
        return tab

    def open_structured_diff(self, left_path: str = "", right_path: str = "") -> StructuredDiffView:
        tab = self._get_or_create_tab(StructuredDiffView, "structured")
        self.tabs.setCurrentWidget(tab)
        if left_path or right_path:
            tab.set_files(left_path, right_path, contract_mode=False)
            self._update_widget_tab_title(tab, left_path, right_path, " Tree (JSON/XML)")
            self._record_recent(left_path, right_path, "structured")
        return tab

    def open_contract_diff(self, left_path: str = "", right_path: str = "") -> StructuredDiffView:
        tab = self._get_or_create_tab(StructuredDiffView, "contract")
        tab.btn_contract_view.setChecked(True)
        tab.view_stack.setCurrentIndex(1)
        self.tabs.setCurrentWidget(tab)
        if left_path or right_path:
            tab.set_files(left_path, right_path, contract_mode=True)
            self._update_widget_tab_title(tab, left_path, right_path, " API Contract")
            self._record_recent(left_path, right_path, "contract")
        return tab

    def open_file_diff(self, left_path: str = "", right_path: str = "", left_title: str = None, right_title: str = None) -> DiffView:
        tab = self._get_or_create_tab(DiffView, "text")
        self.tabs.setCurrentWidget(tab)
        if left_path or right_path:
            tab._is_sample_state = False
            tab.load_files(left_path, right_path, left_title=left_title, right_title=right_title)
            self._update_widget_tab_title(tab, left_path, right_path, " 2-Way Text")
            self._record_recent(left_path, right_path, "text")
        return tab

    def open_3way_merge(self, mine_path: str = "", base_path: str = "", theirs_path: str = "", output_path: str = None) -> MergeView:
        tab = self._get_or_create_tab(MergeView, "merge")
        self.tabs.setCurrentWidget(tab)
        if mine_path or base_path or theirs_path or output_path:
            tab._is_sample_state = False
            tab.load_files(mine_path, base_path, theirs_path, output_path)
            self._update_widget_tab_title(tab, mine_path, theirs_path, " 3-Way Merge")
        return tab

    def open_image_diff(self, img1: str = "", img2: str = "") -> ImageDiffView:
        tab = self._get_or_create_tab(ImageDiffView, "image")
        self.tabs.setCurrentWidget(tab)
        if img1 or img2:
            tab.set_images(img1, img2)
            self._update_widget_tab_title(tab, img1, img2, " Image Diff")
            self._record_recent(img1, img2, "image")
        return tab

    def open_table_diff(self, tbl1: str = "", tbl2: str = "") -> TabularDiffView:
        tab = self._get_or_create_tab(TabularDiffView, "table")
        self.tabs.setCurrentWidget(tab)
        if tbl1 or tbl2:
            tab.set_files(tbl1, tbl2)
            self._update_widget_tab_title(tab, tbl1, tbl2, " Table & CSV")
            self._record_recent(tbl1, tbl2, "table")
        return tab

    def open_hex_diff(self, bin1: str = "", bin2: str = "") -> HexDiffView:
        tab = self._get_or_create_tab(HexDiffView, "hex")
        self.tabs.setCurrentWidget(tab)
        if bin1 or bin2:
            tab.set_files(bin1, bin2)
            self._update_widget_tab_title(tab, bin1, bin2, " Hex & Binary")
            self._record_recent(bin1, bin2, "hex")
        return tab

    def handle_remote_args(self, remote_args: list, remote_cwd: str = ""):
        """Handles incoming command-line arguments dispatched from secondary process instances."""
        from app.main import parse_arguments
        args, _ = parse_arguments(remote_args)

        def fix_path(p: str) -> str:
            if not p or p == "-":
                return p
            if os.path.isabs(p):
                return p
            return os.path.normpath(os.path.join(remote_cwd, p)) if remote_cwd else os.path.abspath(p)

        if args.select_left:
            from app.core.shell_integration import set_left_path, show_native_notification
            target = fix_path(args.select_left)
            set_left_path(target)
            show_native_notification(
                "diff_and_compare_tool",
                f"✓ Selected as Left:\n{target}\n\nNow right-click on the second file/folder and choose 'Select Right'."
            )
            return

        if args.select_right:
            from app.core.shell_integration import get_left_path
            right_target = fix_path(args.select_right)
            left_target = get_left_path()
            if left_target and os.path.exists(left_target):
                self.smart_open_comparison(left_target, right_target)
            return

        if args.compare:
            if len(args.compare) >= 2:
                self.smart_open_comparison(fix_path(args.compare[0]), fix_path(args.compare[1]))
            elif len(args.compare) == 1:
                from app.core.shell_integration import get_left_path
                left_target = get_left_path()
                item = fix_path(args.compare[0])
                if left_target and os.path.exists(left_target) and os.path.abspath(left_target) != item:
                    self.smart_open_comparison(left_target, item)
            return

        if args.diff:
            from app.core.stream_diff import resolve_stream_input
            p1, t1 = resolve_stream_input(fix_path(args.diff[0]), fix_path(args.diff[1]))
            p2, t2 = resolve_stream_input(fix_path(args.diff[1]), fix_path(args.diff[0]))
            self.open_file_diff(p1, p2, left_title=t1, right_title=t2)
        elif args.folder_diff:
            self.open_folder_diff(fix_path(args.folder_diff[0]), fix_path(args.folder_diff[1]))
        elif args.contract_diff:
            self.open_contract_diff(fix_path(args.contract_diff[0]), fix_path(args.contract_diff[1]))
        elif args.image_diff:
            self.open_image_diff(fix_path(args.image_diff[0]), fix_path(args.image_diff[1]))
        elif args.table_diff:
            self.open_table_diff(fix_path(args.table_diff[0]), fix_path(args.table_diff[1]))
        elif args.hex_diff:
            self.open_hex_diff(fix_path(args.hex_diff[0]), fix_path(args.hex_diff[1]))
        elif len(args.files) == 2:
            from app.core.stream_diff import resolve_stream_input
            p1, t1 = resolve_stream_input(fix_path(args.files[0]), fix_path(args.files[1]))
            p2, t2 = resolve_stream_input(fix_path(args.files[1]), fix_path(args.files[0]))
            self.smart_open_comparison(p1, p2, left_title=t1, right_title=t2)
        elif len(args.files) == 3:
            self.open_3way_merge(fix_path(args.files[0]), fix_path(args.files[1]), fix_path(args.files[2]))

        self.showNormal()
        self.activateWindow()
        self.raise_()
