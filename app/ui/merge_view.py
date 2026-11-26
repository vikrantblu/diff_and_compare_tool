"""
Modern 3-Way Merge Studio (White / Light Theme)
Layout:
- Top 3 Viewports: Mine (Local), Base (Ancestor), Theirs (Remote) with modern headers.
- Interactive Conflict Resolution Command Bar:
  Accept Mine, Accept Theirs, Accept Base, Take Both, AI Resolve, Undo/Redo, Prev/Next Conflict.
- Bottom Viewport: Interactive Merged Output buffer with real-time recalculation, syntax highlighting, and conflict highlighting.
"""

import os
from typing import List, Dict, Tuple, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSplitter,
    QLabel, QMessageBox, QFileDialog, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut

from app.ui.widgets.modern_editor import ModernCodeEditor
from app.ui.widgets.editor_header import EditorHeader
from app.core.diff_engine import DiffEngine, MergeConflictChunk
from app.core.file_io import read_text_file, write_text_file
from app.ui.styles.icons import get_line_icon


class MergeView(QWidget):
    """Modern 3-Way Merge Studio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.merge_chunks: List[MergeConflictChunk] = []
        self.current_conflict_idx = -1
        self._is_sample_state = True
        self._conflict_output_lines: Dict[int, int] = {}
        self._undo_stack: List[List[Tuple[str, List[str]]]] = []
        self._redo_stack: List[List[Tuple[str, List[str]]]] = []

        self.setup_ui()
        self.setup_connections()
        self.setup_shortcuts()

        # Load realistic 3-way merge conflict scenario
        sample_base = (
            "def authenticate_client(api_key, secret):\n"
            "    if not api_key:\n"
            "        return False\n"
            "    # Legacy authorization check\n"
            "    return check_v1_credentials(api_key, secret)\n"
            "\n"
            "def query_database(query):\n"
            "    print('Executing:', query)\n"
            "    return []\n"
        )
        sample_mine = (
            "def authenticate_client(api_key, secret):\n"
            "    if not api_key:\n"
            "        return False\n"
            "    # Mine: Added rate limiting protection\n"
            "    enforce_rate_limit(api_key)\n"
            "    return check_v2_oauth(api_key, secret)\n"
            "\n"
            "def query_database(query):\n"
            "    print('Executing:', query)\n"
            "    return []\n"
        )
        sample_theirs = (
            "def authenticate_client(api_key, secret):\n"
            "    if not api_key:\n"
            "        return False\n"
            "    # Theirs: Added JWT token verification\n"
            "    verify_jwt_signature(secret)\n"
            "    return check_v1_credentials(api_key, secret)\n"
            "\n"
            "def query_database(query, timeout=30):\n"
            "    print(f'Executing with timeout {timeout}:', query)\n"
            "    return []\n"
        )

        self._set_editor_text_quiet(self.editor_mine, sample_mine)
        self._set_editor_text_quiet(self.editor_base, sample_base)
        self._set_editor_text_quiet(self.editor_theirs, sample_theirs)

        self.header_mine.set_file_info("local_branch.py")
        self.header_base.set_file_info("common_ancestor.py")
        self.header_theirs.set_file_info("remote_origin.py")
        for ed in (self.editor_mine, self.editor_base, self.editor_theirs, self.editor_output):
            ed.set_language_from_path("merge.py")

        self.recompute_merge()

    def closeEvent(self, event):
        """Ensure child editors stop timers and detach syntax highlighters on close."""
        try:
            for attr in ("editor_mine", "editor_base", "editor_theirs", "editor_output"):
                ed = getattr(self, attr, None)
                if ed is not None:
                    ed.close()
        except Exception:
            pass
        super().closeEvent(event)

    @staticmethod
    def _set_editor_text_quiet(editor: ModernCodeEditor, text: str):
        editor._programmatic_change = True
        editor.setPlainText(text)
        editor._programmatic_change = False

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Conflict Action Ribbon
        action_ribbon = QWidget()
        action_ribbon.setObjectName("MergeRibbon")
        action_ribbon.setFixedHeight(46)
        action_ribbon.setStyleSheet("""
            #MergeRibbon {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f8fafc);
                border-bottom: 1.5px solid #cbd5e1;
            }
        """)
        ribbon_layout = QHBoxLayout(action_ribbon)
        ribbon_layout.setContentsMargins(10, 6, 10, 6)
        ribbon_layout.setSpacing(6)

        self.btn_prev_conflict = QPushButton(" Prev (F7)")
        self.btn_prev_conflict.setIcon(get_line_icon("arrow-up", "#1e293b"))
        self.btn_prev_conflict.setFixedHeight(30)

        self.btn_next_conflict = QPushButton(" Next (F8)")
        self.btn_next_conflict.setIcon(get_line_icon("arrow-down", "#1e293b"))
        self.btn_next_conflict.setFixedHeight(30)
        ribbon_layout.addWidget(self.btn_prev_conflict)
        ribbon_layout.addWidget(self.btn_next_conflict)

        self.lbl_conflict_status = QLabel("Conflicts: 0 remaining")
        self.lbl_conflict_status.setFixedHeight(30)
        ribbon_layout.addWidget(self.lbl_conflict_status)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #cbd5e1;")
        ribbon_layout.addWidget(sep)

        self.btn_accept_mine = QPushButton(" Mine")
        self.btn_accept_mine.setIcon(get_line_icon("arrow-left", "#16a34a"))
        self.btn_accept_mine.setFixedHeight(30)
        self.btn_accept_mine.setToolTip("Accept Mine (Local) for current conflict")

        self.btn_accept_theirs = QPushButton(" Theirs")
        self.btn_accept_theirs.setIcon(get_line_icon("arrow-right", "#2563eb"))
        self.btn_accept_theirs.setFixedHeight(30)
        self.btn_accept_theirs.setToolTip("Accept Theirs (Remote) for current conflict")

        self.btn_accept_base = QPushButton(" Base")
        self.btn_accept_base.setIcon(get_line_icon("check", "#475569"))
        self.btn_accept_base.setFixedHeight(30)
        self.btn_accept_base.setToolTip("Accept Base (Ancestor) for current conflict")

        self.btn_merge_both = QPushButton(" Both")
        self.btn_merge_both.setIcon(get_line_icon("layers", "#475569"))
        self.btn_merge_both.setFixedHeight(30)
        self.btn_merge_both.setToolTip("Include Mine followed by Theirs")

        self.btn_ai_resolve = QPushButton(" AI Resolve")
        self.btn_ai_resolve.setIcon(get_line_icon("sparkles", "#8250df"))
        self.btn_ai_resolve.setFixedHeight(30)
        self.btn_ai_resolve.setToolTip("Smart conflict synthesis")
        self.btn_ai_resolve.clicked.connect(self._ai_resolve_current_conflict)

        self.btn_undo = QPushButton(" Undo")
        self.btn_undo.setIcon(get_line_icon("undo", "#1e293b"))
        self.btn_undo.setFixedHeight(30)
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self.undo)

        ribbon_layout.addWidget(self.btn_accept_mine)
        ribbon_layout.addWidget(self.btn_accept_theirs)
        ribbon_layout.addWidget(self.btn_accept_base)
        ribbon_layout.addWidget(self.btn_merge_both)
        ribbon_layout.addWidget(self.btn_ai_resolve)
        ribbon_layout.addWidget(self.btn_undo)

        ribbon_layout.addStretch()

        self.btn_toggle_output = QPushButton(" Output Preview")
        self.btn_toggle_output.setIcon(get_line_icon("eye", "#1e293b"))
        self.btn_toggle_output.setCheckable(True)
        self.btn_toggle_output.setChecked(True)
        self.btn_toggle_output.setFixedHeight(30)
        self.btn_toggle_output.setToolTip("Toggle collapsible 4th bottom viewport for real-time merged output preview")
        self.btn_toggle_output.toggled.connect(self._toggle_output_pane)
        ribbon_layout.addWidget(self.btn_toggle_output)

        self.btn_save_merge = QPushButton(" Save Output")
        self.btn_save_merge.setIcon(get_line_icon("save", "#ffffff"))
        self.btn_save_merge.setFixedHeight(30)
        self.btn_save_merge.setObjectName("PrimaryButton")
        ribbon_layout.addWidget(self.btn_save_merge)

        main_layout.addWidget(action_ribbon, 0)

        # 2. Main Vertical Splitter: Top (3 Panes) | Bottom (Output)
        self.v_splitter = QSplitter(Qt.Vertical)
        self.h_splitter = QSplitter(Qt.Horizontal)

        mine_box = QWidget()
        l_mine = QVBoxLayout(mine_box)
        l_mine.setContentsMargins(0, 0, 0, 0)
        l_mine.setSpacing(0)
        self.header_mine = EditorHeader(title="Mine (Local)")
        self.editor_mine = ModernCodeEditor()
        l_mine.addWidget(self.header_mine)
        l_mine.addWidget(self.editor_mine)

        base_box = QWidget()
        l_base = QVBoxLayout(base_box)
        l_base.setContentsMargins(0, 0, 0, 0)
        l_base.setSpacing(0)
        self.header_base = EditorHeader(title="Base (Ancestor)")
        self.editor_base = ModernCodeEditor()
        l_base.addWidget(self.header_base)
        l_base.addWidget(self.editor_base)

        theirs_box = QWidget()
        l_theirs = QVBoxLayout(theirs_box)
        l_theirs.setContentsMargins(0, 0, 0, 0)
        l_theirs.setSpacing(0)
        self.header_theirs = EditorHeader(title="Theirs (Remote)")
        self.editor_theirs = ModernCodeEditor()
        l_theirs.addWidget(self.header_theirs)
        l_theirs.addWidget(self.editor_theirs)

        self.h_splitter.addWidget(mine_box)
        self.h_splitter.addWidget(base_box)
        self.h_splitter.addWidget(theirs_box)
        self.h_splitter.setSizes([350, 350, 350])

        self.out_box = QWidget()
        l_out = QVBoxLayout(self.out_box)
        l_out.setContentsMargins(0, 0, 0, 0)
        l_out.setSpacing(0)
        self.header_output = EditorHeader(title="Interactive Merged Output (Real-Time Result)", default_path="merged_output.py")
        self.editor_output = ModernCodeEditor()
        l_out.addWidget(self.header_output)
        l_out.addWidget(self.editor_output)

        self.v_splitter.addWidget(self.h_splitter)
        self.v_splitter.addWidget(self.out_box)
        self.v_splitter.setSizes([450, 250])

        main_layout.addWidget(self.v_splitter, 1)

    def setup_connections(self):
        self.editor_mine.scrolled.connect(self._sync_scroll_from_mine)
        self.editor_base.scrolled.connect(self._sync_scroll_from_base)
        self.editor_theirs.scrolled.connect(self._sync_scroll_from_theirs)

        self.editor_mine.liveTextChanged.connect(self._on_source_edited)
        self.editor_base.liveTextChanged.connect(self._on_source_edited)
        self.editor_theirs.liveTextChanged.connect(self._on_source_edited)
        self.editor_output.liveTextChanged.connect(lambda: self.header_output.set_dirty(True))

        # Wire Browse & Drag-and-Drop on all 3 source headers & editors
        self.header_mine.fileOpened.connect(lambda p, c: self._on_pane_loaded(self.editor_mine, self.header_mine, p, c))
        self.header_base.fileOpened.connect(lambda p, c: self._on_pane_loaded(self.editor_base, self.header_base, p, c))
        self.header_theirs.fileOpened.connect(lambda p, c: self._on_pane_loaded(self.editor_theirs, self.header_theirs, p, c))
        self.editor_mine.fileDropped.connect(self.header_mine.load_local_file)
        self.editor_base.fileDropped.connect(self.header_base.load_local_file)
        self.editor_theirs.fileDropped.connect(self.header_theirs.load_local_file)

        self.header_mine.saveRequested.connect(lambda: self._save_source_pane(self.editor_mine, self.header_mine))
        self.header_base.saveRequested.connect(lambda: self._save_source_pane(self.editor_base, self.header_base))
        self.header_theirs.saveRequested.connect(lambda: self._save_source_pane(self.editor_theirs, self.header_theirs))

        self.btn_accept_mine.clicked.connect(lambda: self.resolve_current("mine"))
        self.btn_accept_theirs.clicked.connect(lambda: self.resolve_current("theirs"))
        self.btn_accept_base.clicked.connect(lambda: self.resolve_current("base"))
        self.btn_merge_both.clicked.connect(lambda: self.resolve_current("both"))

        self.btn_prev_conflict.clicked.connect(self.jump_prev_conflict)
        self.btn_next_conflict.clicked.connect(self.jump_next_conflict)

        self.btn_save_merge.clicked.connect(self.save_merged_output)
        self.header_output.saveRequested.connect(self.save_merged_output)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("F7"), self, self.jump_prev_conflict)
        QShortcut(QKeySequence("F8"), self, self.jump_next_conflict)
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_merged_output)
        QShortcut(QKeySequence.Undo, self, self.undo)

    def load_files(self, mine_path: str = "", base_path: str = "", theirs_path: str = "", output_path: Optional[str] = None):
        if mine_path and os.path.exists(mine_path):
            content, enc, eol = read_text_file(mine_path)
            self._set_editor_text_quiet(self.editor_mine, content)
            self.header_mine.set_file_info(mine_path, dirty=False)
            self.header_mine.set_encoding_info(enc, eol)
            self.editor_mine.set_language_from_path(mine_path)
            self.editor_output.set_language_from_path(mine_path)
            self._is_sample_state = False

        if base_path and os.path.exists(base_path):
            content, enc, eol = read_text_file(base_path)
            self._set_editor_text_quiet(self.editor_base, content)
            self.header_base.set_file_info(base_path, dirty=False)
            self.header_base.set_encoding_info(enc, eol)
            self.editor_base.set_language_from_path(base_path)
            self._is_sample_state = False

        if theirs_path and os.path.exists(theirs_path):
            content, enc, eol = read_text_file(theirs_path)
            self._set_editor_text_quiet(self.editor_theirs, content)
            self.header_theirs.set_file_info(theirs_path, dirty=False)
            self.header_theirs.set_encoding_info(enc, eol)
            self.editor_theirs.set_language_from_path(theirs_path)
            self._is_sample_state = False

        if output_path:
            self.header_output.set_file_info(output_path, dirty=False)
            self.editor_output.set_language_from_path(output_path)

        if mine_path or base_path or theirs_path:
            self._undo_stack.clear()
            self._redo_stack.clear()
            self.btn_undo.setEnabled(False)
            self.recompute_merge()

    def _on_pane_loaded(self, editor: ModernCodeEditor, header: EditorHeader, path: str, content: str):
        self._is_sample_state = False
        self._set_editor_text_quiet(editor, content)
        header.set_file_info(path, dirty=False)
        editor.set_language_from_path(path)
        self.editor_output.set_language_from_path(path)
        self.recompute_merge()

    def _on_source_edited(self):
        self._is_sample_state = False
        self.recompute_merge()

    def _save_source_pane(self, editor: ModernCodeEditor, header: EditorHeader):
        path = header.current_file_path
        if not path or path.startswith(("local_", "common_", "remote_")):
            path, _ = QFileDialog.getSaveFileName(self, "Save File", path or "", "All Files (*.*)")
            if not path:
                return
        try:
            write_text_file(path, editor.toPlainText(), encoding_label=header.encoding, eol_label=header.eol)
            header.set_file_info(path, dirty=False)
        except Exception as e:
            QMessageBox.critical(self, "Error Saving", f"Failed to write file:\n{e}")

    def has_unsaved_changes(self) -> bool:
        return bool(self.header_output.is_dirty)

    def _sync_scroll_from_mine(self, val):
        self.editor_base.set_sync_scroll_value(val)
        self.editor_theirs.set_sync_scroll_value(val)

    def _sync_scroll_from_base(self, val):
        self.editor_mine.set_sync_scroll_value(val)
        self.editor_theirs.set_sync_scroll_value(val)

    def _sync_scroll_from_theirs(self, val):
        self.editor_mine.set_sync_scroll_value(val)
        self.editor_base.set_sync_scroll_value(val)

    def _toggle_output_pane(self, checked: bool):
        self.out_box.setVisible(checked)
        self.btn_toggle_output.setText(" Output Preview" if checked else " Show Output")
        if checked:
            self.v_splitter.setSizes([450, 250])

    def _push_resolution_undo(self):
        snapshot = [
            (c.resolution_state, list(c.resolved_lines))
            for c in self.merge_chunks if c.is_conflict
        ]
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > 40:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self.btn_undo.setEnabled(len(self._undo_stack) > 0)

    def undo(self):
        if not self._undo_stack:
            return
        snapshot = self._undo_stack.pop()
        conflicts = [c for c in self.merge_chunks if c.is_conflict]
        if len(conflicts) == len(snapshot):
            for c, (st, lines) in zip(conflicts, snapshot):
                c.resolution_state = st
                c.resolved_lines = list(lines)
            self._update_output_and_decorations()
        self.btn_undo.setEnabled(len(self._undo_stack) > 0)

    def recompute_merge(self):
        """Run 3-way merge logic and update decorations & output buffer."""
        base_text = self.editor_base.toPlainText()
        mine_text = self.editor_mine.toPlainText()
        theirs_text = self.editor_theirs.toPlainText()

        old_resolutions = [
            (c.resolution_state, list(c.resolved_lines))
            for c in self.merge_chunks if c.is_conflict
        ]

        self.merge_chunks = DiffEngine.compute_3way_merge(base_text, mine_text, theirs_text)

        new_conflicts = [c for c in self.merge_chunks if c.is_conflict]
        if len(new_conflicts) == len(old_resolutions):
            for i, (st, lines) in enumerate(old_resolutions):
                if st != "unresolved":
                    new_conflicts[i].resolution_state = st
                    new_conflicts[i].resolved_lines = list(lines)

        if not new_conflicts:
            self.current_conflict_idx = -1
        elif self.current_conflict_idx < 0 or self.current_conflict_idx >= len(new_conflicts):
            self.current_conflict_idx = 0

        self._update_output_and_decorations()

    def _update_output_and_decorations(self):
        """Assembles real-time output buffer and updates conflict status & decorations across all 4 panes."""
        conflicts = [c for c in self.merge_chunks if c.is_conflict]
        unresolved = [c for c in conflicts if c.resolution_state == "unresolved"]

        if unresolved:
            pos_str = f" ({self.current_conflict_idx + 1}/{len(conflicts)})" if self.current_conflict_idx >= 0 else ""
            self.lbl_conflict_status.setText(f"⚠ {len(unresolved)} UNRESOLVED{pos_str}")
            self.lbl_conflict_status.setStyleSheet("background: #ffebe9; color: #cf222e; border: 1px solid #ff8182; padding: 3px 10px; border-radius: 5px; font-weight: bold;")
        else:
            self.lbl_conflict_status.setText("✓ ALL CONFLICTS RESOLVED")
            self.lbl_conflict_status.setStyleSheet("background: #dafbe1; color: #1a7f37; border: 1px solid #4ac26b; padding: 3px 10px; border-radius: 5px; font-weight: bold;")

        output_lines: List[str] = []
        out_decorations: Dict[int, str] = {}
        out_tick_info: Dict[int, Tuple[str, str]] = {}
        self._conflict_output_lines = {}
        cur_out_line = 0
        conflict_counter = 0

        for chunk in self.merge_chunks:
            if not chunk.is_conflict:
                output_lines.extend(chunk.resolved_lines)
                cur_out_line += len(chunk.resolved_lines)
            else:
                chunk_start = cur_out_line
                self._conflict_output_lines[conflict_counter] = chunk_start
                conflict_counter += 1

                if chunk.resolution_state == "mine":
                    lines_to_emit = chunk.left_lines
                    color, label = "#16a34a", "Resolved: Mine"
                elif chunk.resolution_state == "theirs":
                    lines_to_emit = chunk.right_lines
                    color, label = "#2563eb", "Resolved: Theirs"
                elif chunk.resolution_state == "base":
                    lines_to_emit = chunk.base_lines
                    color, label = "#475569", "Resolved: Base"
                elif chunk.resolution_state == "both":
                    lines_to_emit = chunk.left_lines + chunk.right_lines
                    color, label = "#8250df", "Resolved: Both"
                elif chunk.resolution_state == "custom":
                    lines_to_emit = chunk.resolved_lines
                    color, label = "#0f766e", "Resolved: AI / Custom"
                else:
                    lines_to_emit = None

                if lines_to_emit is not None:
                    output_lines.extend(lines_to_emit)
                    for k in range(chunk_start, chunk_start + len(lines_to_emit)):
                        out_decorations[k] = color
                        out_tick_info[k] = (color, label)
                    cur_out_line += len(lines_to_emit)
                else:
                    # Standard diff3 conflict marker ordering
                    output_lines.append("<<<<<<< MINE (LOCAL)")
                    output_lines.extend(chunk.left_lines)
                    output_lines.append("||||||| BASE (ANCESTOR)")
                    output_lines.extend(chunk.base_lines)
                    output_lines.append("=======")
                    output_lines.extend(chunk.right_lines)
                    output_lines.append(">>>>>>> THEIRS (REMOTE)")
                    added_len = 4 + len(chunk.left_lines) + len(chunk.base_lines) + len(chunk.right_lines)
                    for k in range(chunk_start, chunk_start + added_len):
                        out_decorations[k] = "#d97706"
                        out_tick_info[k] = ("#d97706", "Unresolved Conflict")
                    cur_out_line += added_len

        self._set_editor_text_quiet(self.editor_output, '\n'.join(output_lines))
        self.editor_output.apply_diff_decorations(out_decorations, tick_info=out_tick_info)

        # Highlight conflict & change lines in Mine, Base, Theirs source editors
        mine_decorations: Dict[int, str] = {}
        base_decorations: Dict[int, str] = {}
        theirs_decorations: Dict[int, str] = {}

        for chunk in self.merge_chunks:
            if chunk.is_conflict:
                c_color = "#d97706" if chunk.resolution_state == "unresolved" else "#1a7f37"
                for i in range(chunk.left_start, max(chunk.left_start + 1, chunk.left_end)):
                    mine_decorations[i] = c_color
                for i in range(chunk.base_start, max(chunk.base_start + 1, chunk.base_end)):
                    base_decorations[i] = c_color
                for i in range(chunk.right_start, max(chunk.right_start + 1, chunk.right_end)):
                    theirs_decorations[i] = c_color
            elif chunk.left_lines != chunk.base_lines or chunk.right_lines != chunk.base_lines:
                if chunk.left_lines != chunk.base_lines:
                    for i in range(chunk.left_start, chunk.left_end):
                        mine_decorations[i] = "#16a34a"
                if chunk.right_lines != chunk.base_lines:
                    for i in range(chunk.right_start, chunk.right_end):
                        theirs_decorations[i] = "#2563eb"

        self.editor_mine.apply_diff_decorations(mine_decorations)
        self.editor_base.apply_diff_decorations(base_decorations)
        self.editor_theirs.apply_diff_decorations(theirs_decorations)

    def resolve_current(self, choice: str):
        conflicts = [c for c in self.merge_chunks if c.is_conflict]
        if not conflicts:
            QMessageBox.information(self, "No Conflicts", "There are no active conflicts to resolve!")
            return

        self._push_resolution_undo()
        target_idx = max(0, self.current_conflict_idx) if self.current_conflict_idx >= 0 else 0
        if target_idx < len(conflicts):
            target_chunk = conflicts[target_idx]
            target_chunk.resolution_state = choice
            if choice == "mine":
                target_chunk.resolved_lines = list(target_chunk.left_lines)
            elif choice == "theirs":
                target_chunk.resolved_lines = list(target_chunk.right_lines)
            elif choice == "base":
                target_chunk.resolved_lines = list(target_chunk.base_lines)
            elif choice == "both":
                target_chunk.resolved_lines = list(target_chunk.left_lines) + list(target_chunk.right_lines)

            self.header_output.set_dirty(True)
            unresolved = [i for i, c in enumerate(conflicts) if c.resolution_state == "unresolved"]
            if unresolved:
                self.current_conflict_idx = unresolved[0]

            self._update_output_and_decorations()

    def _ai_resolve_current_conflict(self):
        conflicts = [c for c in self.merge_chunks if c.is_conflict]
        if not conflicts:
            self.lbl_conflict_status.setToolTip("No active conflicts to resolve.")
            return

        self._push_resolution_undo()
        target_idx = max(0, self.current_conflict_idx) if self.current_conflict_idx >= 0 else 0
        target_chunk = conflicts[target_idx]
        from app.core.ai_assistant import AIAssistant
        res = AIAssistant.suggest_conflict_resolution(
            target_chunk,
            context_file=self.header_mine.current_file_path or "Source"
        )
        target_chunk.resolved_lines = res["resolved_lines"]
        target_chunk.resolution_state = "custom"
        self.header_output.set_dirty(True)
        self._update_output_and_decorations()

        # Use non-blocking status feedback so conflict resolution never stalls headless/automated flows
        explanation = res.get("explanation", "Resolved successfully")
        source = res.get("source", "AI")
        self._last_ai_explanation = (source, explanation)
        self.lbl_conflict_status.setToolTip(f"AI Resolution ({source}): {explanation}")
        if not any(c.resolution_state == "unresolved" for c in conflicts):
            self.lbl_conflict_status.setText(f"✓ AI RESOLVED ({source})")

    def _scroll_to_active_conflict(self):
        conflicts = [c for c in self.merge_chunks if c.is_conflict]
        if not conflicts or not (0 <= self.current_conflict_idx < len(conflicts)):
            return
        c = conflicts[self.current_conflict_idx]
        self.editor_mine.jump_to_line(c.left_start)
        self.editor_base.jump_to_line(c.base_start)
        self.editor_theirs.jump_to_line(c.right_start)
        out_line = self._conflict_output_lines.get(self.current_conflict_idx, 0)
        self.editor_output.jump_to_line(out_line)
        self._update_output_and_decorations()

    def jump_next_conflict(self):
        conflicts = [i for i, c in enumerate(self.merge_chunks) if c.is_conflict]
        if not conflicts:
            return
        self.current_conflict_idx = (self.current_conflict_idx + 1) % len(conflicts)
        self._scroll_to_active_conflict()

    def jump_prev_conflict(self):
        conflicts = [i for i, c in enumerate(self.merge_chunks) if c.is_conflict]
        if not conflicts:
            return
        self.current_conflict_idx = (self.current_conflict_idx - 1 + len(conflicts)) % len(conflicts)
        self._scroll_to_active_conflict()

    def save_merged_output(self):
        unresolved = [c for c in self.merge_chunks if c.is_conflict and c.resolution_state == "unresolved"]
        if unresolved:
            reply = QMessageBox.question(
                self,
                "Unresolved Conflicts Remaining",
                f"There are still {len(unresolved)} unresolved conflict(s) with conflict markers in the output.\nSave anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        cur_out = self.header_output.current_file_path
        if cur_out and cur_out != "merged_output.py" and os.path.isabs(cur_out):
            path = cur_out
        else:
            path, _ = QFileDialog.getSaveFileName(self, "Save Merged Output", cur_out or "merged_result.py", "All Files (*.*)")
            if not path:
                return

        try:
            write_text_file(
                path,
                self.editor_output.toPlainText(),
                encoding_label=self.header_mine.encoding,
                eol_label=self.header_mine.eol
            )
            self.header_output.set_file_info(path, dirty=False)
            QMessageBox.information(self, "Merge Saved", f"Successfully saved merged file to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error Saving", f"Failed to write file:\n{e}")
