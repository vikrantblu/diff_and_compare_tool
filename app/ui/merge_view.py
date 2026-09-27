"""
Modern 3-Way Merge Studio
Layout:
- Top 3 Viewports: Mine (Local), Base (Ancestor), Theirs (Remote) with modern headers.
- Interactive Conflict Resolution Command Bar:
  Accept Mine, Accept Theirs, Accept Base, Merge Both, Prev/Next Conflict.
- Bottom Viewport: Interactive Merged Output buffer with real-time recalculation and manual edit freedom.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSplitter,
    QLabel, QMessageBox, QFileDialog, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor

from app.ui.widgets.modern_editor import ModernCodeEditor
from app.ui.widgets.editor_header import EditorHeader
from app.core.diff_engine import DiffEngine, MergeConflictChunk
from app.ui.styles.icons import get_line_icon
from typing import List, Dict


class MergeView(QWidget):
    """Modern 3-Way Merge Studio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.merge_chunks: List[MergeConflictChunk] = []
        self.current_conflict_idx = -1

        self.setup_ui()
        self.setup_connections()

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

        self.editor_mine.setPlainText(sample_mine)
        self.editor_base.setPlainText(sample_base)
        self.editor_theirs.setPlainText(sample_theirs)

        self.header_mine.set_file_info("local_branch.py")
        self.header_base.set_file_info("common_ancestor.py")
        self.header_theirs.set_file_info("remote_origin.py")

        self.recompute_merge()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Conflict Action Ribbon with Elevated Styling & Proper Borders
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
        ribbon_layout.setSpacing(8)

        # Conflict navigation with line icons
        self.btn_prev_conflict = QPushButton(" Prev Conflict")
        self.btn_prev_conflict.setIcon(get_line_icon("arrow-up", "#1e293b"))
        self.btn_prev_conflict.setFixedHeight(30)

        self.btn_next_conflict = QPushButton(" Next Conflict")
        self.btn_next_conflict.setIcon(get_line_icon("arrow-down", "#1e293b"))
        self.btn_next_conflict.setFixedHeight(30)
        ribbon_layout.addWidget(self.btn_prev_conflict)
        ribbon_layout.addWidget(self.btn_next_conflict)

        # Conflict state label with pill border
        self.lbl_conflict_status = QLabel("Conflicts: 0 remaining")
        self.lbl_conflict_status.setFixedHeight(30)
        self.lbl_conflict_status.setStyleSheet("""
            background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #fff1f2, stop:1 #ffe4e6);
            color: #e11d48;
            padding: 4px 12px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 11px;
            border: 1px solid #fecdd3;
        """)
        ribbon_layout.addWidget(self.lbl_conflict_status)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #cbd5e1;")
        ribbon_layout.addWidget(sep)

        # Resolution Actions with line icons
        self.btn_accept_mine = QPushButton(" Accept Mine (Left)")
        self.btn_accept_mine.setIcon(get_line_icon("arrow-left", "#16a34a"))
        self.btn_accept_mine.setFixedHeight(30)

        self.btn_accept_theirs = QPushButton(" Accept Theirs (Right)")
        self.btn_accept_theirs.setIcon(get_line_icon("arrow-right", "#2563eb"))
        self.btn_accept_theirs.setFixedHeight(30)

        self.btn_accept_base = QPushButton(" Accept Base (Center)")
        self.btn_accept_base.setIcon(get_line_icon("check", "#475569"))
        self.btn_accept_base.setFixedHeight(30)

        self.btn_merge_both = QPushButton(" Take Both")
        self.btn_merge_both.setIcon(get_line_icon("layers", "#475569"))
        self.btn_merge_both.setFixedHeight(30)

        # AI Resolve Button
        self.btn_ai_resolve = QPushButton(" AI Resolve")
        self.btn_ai_resolve.setIcon(get_line_icon("sparkles", "#8250df"))
        self.btn_ai_resolve.setFixedHeight(30)
        self.btn_ai_resolve.setToolTip("Smart AI conflict synthesis using intent recognition")
        self.btn_ai_resolve.clicked.connect(self._ai_resolve_current_conflict)

        ribbon_layout.addWidget(self.btn_accept_mine)
        ribbon_layout.addWidget(self.btn_accept_theirs)
        ribbon_layout.addWidget(self.btn_accept_base)
        ribbon_layout.addWidget(self.btn_merge_both)
        ribbon_layout.addWidget(self.btn_ai_resolve)

        ribbon_layout.addStretch()

        # Collapsible 4th Output Preview toggle
        self.btn_toggle_output = QPushButton(" 👁 Output Preview")
        self.btn_toggle_output.setCheckable(True)
        self.btn_toggle_output.setChecked(True)
        self.btn_toggle_output.setFixedHeight(30)
        self.btn_toggle_output.setToolTip("Toggle collapsible 4th bottom viewport for real-time merged output preview")
        self.btn_toggle_output.toggled.connect(self._toggle_output_pane)
        ribbon_layout.addWidget(self.btn_toggle_output)

        # Save Merged Output Action with line icon
        self.btn_save_merge = QPushButton(" Save Merged Output...")
        self.btn_save_merge.setIcon(get_line_icon("save", "#ffffff"))
        self.btn_save_merge.setFixedHeight(30)
        self.btn_save_merge.setObjectName("PrimaryButton")
        ribbon_layout.addWidget(self.btn_save_merge)

        main_layout.addWidget(action_ribbon, 0)

        # 2. Main Vertical Splitter: Top (3 Panes) | Bottom (Output)
        self.v_splitter = QSplitter(Qt.Vertical)

        # Top Horizontal Splitter: Mine | Base | Theirs
        self.h_splitter = QSplitter(Qt.Horizontal)

        # Mine container
        mine_box = QWidget()
        l_mine = QVBoxLayout(mine_box)
        l_mine.setContentsMargins(0, 0, 0, 0)
        l_mine.setSpacing(0)
        self.header_mine = EditorHeader(title="Mine (Local)")
        self.editor_mine = ModernCodeEditor()
        l_mine.addWidget(self.header_mine)
        l_mine.addWidget(self.editor_mine)

        # Base container
        base_box = QWidget()
        l_base = QVBoxLayout(base_box)
        l_base.setContentsMargins(0, 0, 0, 0)
        l_base.setSpacing(0)
        self.header_base = EditorHeader(title="Base (Ancestor)")
        self.editor_base = ModernCodeEditor()
        l_base.addWidget(self.header_base)
        l_base.addWidget(self.editor_base)

        # Theirs container
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

        # Bottom Output container (Collapsible 4th Viewport)
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
        # Synchronized scrolling across the 3 top editors
        self.editor_mine.scrolled.connect(self._sync_scroll_from_mine)
        self.editor_base.scrolled.connect(self._sync_scroll_from_base)
        self.editor_theirs.scrolled.connect(self._sync_scroll_from_theirs)

        # Live re-diff when user edits any of the buffers
        self.editor_mine.liveTextChanged.connect(self.recompute_merge)
        self.editor_base.liveTextChanged.connect(self.recompute_merge)
        self.editor_theirs.liveTextChanged.connect(self.recompute_merge)

        # Resolution button actions
        self.btn_accept_mine.clicked.connect(lambda: self.resolve_current("mine"))
        self.btn_accept_theirs.clicked.connect(lambda: self.resolve_current("theirs"))
        self.btn_accept_base.clicked.connect(lambda: self.resolve_current("base"))
        self.btn_merge_both.clicked.connect(lambda: self.resolve_current("both"))

        # Navigation
        self.btn_prev_conflict.clicked.connect(self.jump_prev_conflict)
        self.btn_next_conflict.clicked.connect(self.jump_next_conflict)

        # Save actions
        self.btn_save_merge.clicked.connect(self.save_merged_output)
        self.header_output.saveRequested.connect(self.save_merged_output)

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
        self.btn_toggle_output.setText(" 👁 Output Preview" if checked else " 👁 Show Output")
        if checked:
            self.v_splitter.setSizes([450, 250])

    def recompute_merge(self):
        """Run 3-way merge logic and update decorations & output buffer."""
        base_text = self.editor_base.toPlainText()
        mine_text = self.editor_mine.toPlainText()
        theirs_text = self.editor_theirs.toPlainText()

        # Preserve any manual resolutions if chunk count matches
        old_resolutions = [c.resolution_state for c in self.merge_chunks if c.is_conflict]

        self.merge_chunks = DiffEngine.compute_3way_merge(base_text, mine_text, theirs_text)

        new_conflicts = [c for c in self.merge_chunks if c.is_conflict]
        if len(new_conflicts) == len(old_resolutions):
            for i, st in enumerate(old_resolutions):
                if st != "unresolved":
                    new_conflicts[i].resolution_state = st

        self._update_output_and_decorations()

    def _update_output_and_decorations(self):
        """Assembles real-time output buffer and updates conflict status & decorations."""
        conflicts = [c for c in self.merge_chunks if c.is_conflict]
        unresolved = [c for c in conflicts if c.resolution_state == "unresolved"]

        if unresolved:
            self.lbl_conflict_status.setText(f"⚠ {len(unresolved)} CONFLICTS UNRESOLVED")
            self.lbl_conflict_status.setStyleSheet("background: #ffebe9; color: #cf222e; border: 1px solid #ff8182; padding: 3px 8px; border-radius: 4px; font-weight: bold;")
        else:
            self.lbl_conflict_status.setText("✓ ALL CONFLICTS RESOLVED")
            self.lbl_conflict_status.setStyleSheet("background: #dafbe1; color: #1a7f37; border: 1px solid #4ac26b; padding: 3px 8px; border-radius: 4px; font-weight: bold;")

        # Assemble Output Buffer in Real-Time
        output_lines = []
        out_decorations: Dict[int, str] = {}
        out_tick_info: Dict[int, Tuple[str, str]] = {}
        cur_out_line = 0

        for chunk in self.merge_chunks:
            if not chunk.is_conflict:
                output_lines.extend(chunk.resolved_lines)
                cur_out_line += len(chunk.resolved_lines)
            else:
                chunk_start = cur_out_line
                if chunk.resolution_state == "mine":
                    output_lines.extend(chunk.left_lines)
                    lines_count = len(chunk.left_lines)
                    for k in range(chunk_start, chunk_start + lines_count):
                        out_decorations[k] = "#16a34a"
                        out_tick_info[k] = ("#16a34a", "Resolved: Mine")
                    cur_out_line += lines_count
                elif chunk.resolution_state == "theirs":
                    output_lines.extend(chunk.right_lines)
                    lines_count = len(chunk.right_lines)
                    for k in range(chunk_start, chunk_start + lines_count):
                        out_decorations[k] = "#2563eb"
                        out_tick_info[k] = ("#2563eb", "Resolved: Theirs")
                    cur_out_line += lines_count
                elif chunk.resolution_state == "base":
                    output_lines.extend(chunk.base_lines)
                    lines_count = len(chunk.base_lines)
                    for k in range(chunk_start, chunk_start + lines_count):
                        out_decorations[k] = "#475569"
                        out_tick_info[k] = ("#475569", "Resolved: Base")
                    cur_out_line += lines_count
                elif chunk.resolution_state == "both":
                    both = chunk.left_lines + chunk.right_lines
                    output_lines.extend(both)
                    lines_count = len(both)
                    for k in range(chunk_start, chunk_start + lines_count):
                        out_decorations[k] = "#8250df"
                        out_tick_info[k] = ("#8250df", "Resolved: Both")
                    cur_out_line += lines_count
                else:
                    # Unresolved conflict markers
                    output_lines.append("<<<<<<< MINE (LOCAL)")
                    cur_out_line += 1
                    output_lines.extend(chunk.left_lines)
                    cur_out_line += len(chunk.left_lines)
                    output_lines.append("======= BASE")
                    cur_out_line += 1
                    output_lines.extend(chunk.base_lines)
                    cur_out_line += len(chunk.base_lines)
                    output_lines.append(">>>>>>> THEIRS (REMOTE)")
                    cur_out_line += 1
                    output_lines.extend(chunk.right_lines)
                    cur_out_line += len(chunk.right_lines)

                    for k in range(chunk_start, cur_out_line):
                        out_decorations[k] = "#d97706"
                        out_tick_info[k] = ("#d97706", "Unresolved Conflict")

        self.editor_output.setPlainText('\n'.join(output_lines))
        self.editor_output.apply_diff_decorations(out_decorations, tick_info=out_tick_info)

        # Highlight conflicts in source editors
        mine_decorations: Dict[int, str] = {}
        theirs_decorations: Dict[int, str] = {}
        base_decorations: Dict[int, str] = {}

        for chunk in self.merge_chunks:
            if chunk.is_conflict:
                color = "#d97706" if chunk.resolution_state == "unresolved" else "#1a7f37"
                # mark in editors
                # (highlight conflict lines in mine, base, theirs)

    def resolve_current(self, choice: str):
        conflicts = [c for c in self.merge_chunks if c.is_conflict]
        if not conflicts:
            QMessageBox.information(self, "No Conflicts", "There are no active conflicts to resolve!")
            return

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

            # Advance to next unresolved conflict if available
            unresolved = [i for i, c in enumerate(conflicts) if c.resolution_state == "unresolved"]
            if unresolved:
                self.current_conflict_idx = unresolved[0]

            self._update_output_and_decorations()

    def _ai_resolve_current_conflict(self):
        conflicts = [c for c in self.merge_chunks if c.is_conflict]
        if not conflicts:
            QMessageBox.information(self, "No Conflicts", "There are no active conflicts to resolve!")
            return

        target_idx = max(0, self.current_conflict_idx) if self.current_conflict_idx >= 0 else 0
        target_chunk = conflicts[target_idx]
        from app.core.ai_assistant import AIAssistant
        res = AIAssistant.suggest_conflict_resolution(
            target_chunk,
            context_file=self.header_mine.current_file_path or "Source"
        )
        target_chunk.resolved_lines = res["resolved_lines"]
        target_chunk.resolution_state = "custom"
        self._update_output_and_decorations()

        QMessageBox.information(
            self,
            "AI Resolution Applied",
            f"Provider: {res.get('source', 'AI')}\n\nSynthesis Explanation:\n{res.get('explanation', 'Resolved successfully')}"
        )

    def jump_next_conflict(self):
        conflicts = [i for i, c in enumerate(self.merge_chunks) if c.is_conflict]
        if not conflicts:
            return
        self.current_conflict_idx = (self.current_conflict_idx + 1) % len(conflicts)

    def jump_prev_conflict(self):
        conflicts = [i for i, c in enumerate(self.merge_chunks) if c.is_conflict]
        if not conflicts:
            return
        self.current_conflict_idx = (self.current_conflict_idx - 1 + len(conflicts)) % len(conflicts)

    def save_merged_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Merged Output", "merged_result.py", "All Files (*.*)")
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.editor_output.toPlainText())
            self.header_output.set_file_info(path, dirty=False)
            QMessageBox.information(self, "Merge Saved", f"Successfully saved merged file to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error Saving", f"Failed to write file:\n{e}")
