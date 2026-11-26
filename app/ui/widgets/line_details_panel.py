"""
Synchronized Bottom "Line Details" Character-by-Character Inspector Panel (White / Light Theme)
Displays the focused Left vs Right line stacked vertically with intraline character-level diff highlights,
inspired by Beyond Compare's signature bottom Line Details pane.
"""

import html
from typing import Optional
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextOption

from app.core.diff_engine import DiffEngine, CharDiffSpan


def _render_char_html(text: str, spans: list, span_bg: str, span_fg: str) -> str:
    """Renders a single line as HTML with intraline character spans highlighted."""
    if not text:
        return "<span style='color:#94a3b8;'>&lt;empty line&gt;</span>"
    if not spans:
        return html.escape(text)
    parts = []
    cursor = 0
    n = len(text)
    for sp in sorted(spans, key=lambda s: s.start):
        st = max(cursor, min(sp.start, n))
        en = max(st, min(sp.end, n))
        if st > cursor:
            parts.append(html.escape(text[cursor:st]))
        if en > st:
            parts.append(
                f"<span style='background-color:{span_bg}; color:{span_fg}; "
                f"font-weight:700; border-radius:2px;'>{html.escape(text[st:en])}</span>"
            )
        cursor = en
    if cursor < n:
        parts.append(html.escape(text[cursor:]))
    return "".join(parts)


class _SingleLineBox(QTextEdit):
    """Compact single-line read-only HTML display box for Line Details."""

    def __init__(self, bg_hex: str, border_hex: str, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFixedHeight(25)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWordWrapMode(QTextOption.NoWrap)
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: {bg_hex};
                color: #0f172a;
                border: 1px solid {border_hex};
                border-radius: 4px;
                padding: 2px 6px;
                font-family: Consolas, "Cascadia Code", monospace;
                font-size: 10pt;
            }}
        """)


class LineDetailsPanel(QFrame):
    """Stacked character-level line comparator docked at the bottom of DiffView."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LineDetailsPanel")
        self.setFixedHeight(92)
        self.setStyleSheet("""
            #LineDetailsPanel {
                background-color: #f8fafc;
                border-top: 1.5px solid #cbd5e1;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 6)
        layout.setSpacing(4)

        # Header row
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)

        lbl_title = QLabel("LINE DETAILS")
        lbl_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #475569; letter-spacing: 0.5px; border: none; background: transparent;")
        head.addWidget(lbl_title)

        self.lbl_coords = QLabel("L:—  vs  R:—")
        self.lbl_coords.setStyleSheet("font-size: 11px; font-weight: 600; color: #0f172a; border: none; background: transparent;")
        head.addWidget(self.lbl_coords)

        self.lbl_delta = QLabel("Select any line to inspect character differences")
        self.lbl_delta.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #475569; "
            "background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 1px 8px;"
        )
        head.addWidget(self.lbl_delta)
        head.addStretch()
        layout.addLayout(head)

        # Left line row
        row_l = QHBoxLayout()
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(6)
        lbl_l = QLabel("LEFT")
        lbl_l.setFixedWidth(44)
        lbl_l.setAlignment(Qt.AlignCenter)
        lbl_l.setStyleSheet("font-size: 10px; font-weight: 700; color: #1d4ed8; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 4px; padding: 2px;")
        self.box_left = _SingleLineBox("#ffffff", "#cbd5e1")
        row_l.addWidget(lbl_l)
        row_l.addWidget(self.box_left, 1)
        layout.addLayout(row_l)

        # Right line row
        row_r = QHBoxLayout()
        row_r.setContentsMargins(0, 0, 0, 0)
        row_r.setSpacing(6)
        lbl_r = QLabel("RIGHT")
        lbl_r.setFixedWidth(44)
        lbl_r.setAlignment(Qt.AlignCenter)
        lbl_r.setStyleSheet("font-size: 10px; font-weight: 700; color: #15803d; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 4px; padding: 2px;")
        self.box_right = _SingleLineBox("#ffffff", "#cbd5e1")
        row_r.addWidget(lbl_r)
        row_r.addWidget(self.box_right, 1)
        layout.addLayout(row_r)

    def update_pair(
        self,
        left_line_no: Optional[int],
        left_text: str,
        right_line_no: Optional[int],
        right_text: str,
        is_left_spacer: bool = False,
        is_right_spacer: bool = False,
        tag: str = ""
    ):
        l_str = f"L:{left_line_no}" if (left_line_no and not is_left_spacer) else "L:· (spacer)"
        r_str = f"R:{right_line_no}" if (right_line_no and not is_right_spacer) else "R:· (spacer)"
        self.lbl_coords.setText(f"{l_str}  vs  {r_str}")

        l_disp = "" if is_left_spacer else (left_text or "")
        r_disp = "" if is_right_spacer else (right_text or "")

        if is_left_spacer and not is_right_spacer:
            self.box_left.setHtml("<span style='color:#94a3b8; font-style:italic;'>· alignment spacer ·</span>")
            self.box_right.setHtml(f"<span style='background:#dafbe1; color:#116329;'>{html.escape(r_disp) or '&nbsp;'}</span>")
            self._set_delta_badge("Inserted Line", "#116329", "#dafbe1", "#4ac26b")
            return

        if is_right_spacer and not is_left_spacer:
            self.box_left.setHtml(f"<span style='background:#ffebe9; color:#82071e;'>{html.escape(l_disp) or '&nbsp;'}</span>")
            self.box_right.setHtml("<span style='color:#94a3b8; font-style:italic;'>· alignment spacer ·</span>")
            self._set_delta_badge("Deleted Line", "#cf222e", "#ffebe9", "#ff8182")
            return

        if l_disp == r_disp:
            safe = html.escape(l_disp) if l_disp else "<span style='color:#94a3b8;'>&lt;empty line&gt;</span>"
            self.box_left.setHtml(safe)
            self.box_right.setHtml(safe)
            badge = "Moved (Identical)" if tag == "moved" else "Identical"
            self._set_delta_badge(badge, "#1a7f37", "#dafbe1", "#4ac26b")
            return

        sp_l, sp_r = DiffEngine._compute_line_intraline(l_disp, r_disp)
        self.box_left.setHtml(_render_char_html(l_disp, sp_l, "#ffcecb", "#82071e"))
        self.box_right.setHtml(_render_char_html(r_disp, sp_r, "#aceebb", "#0a3622"))
        changed_chars = sum(s.end - s.start for s in sp_l) + sum(s.end - s.start for s in sp_r)
        self._set_delta_badge(f"Modified ({changed_chars} char delta)", "#0969da", "#eff6ff", "#93c5fd")

    def _set_delta_badge(self, text: str, fg: str, bg: str, border: str):
        self.lbl_delta.setText(text)
        self.lbl_delta.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {fg}; "
            f"background: {bg}; border: 1px solid {border}; border-radius: 4px; padding: 1px 8px;"
        )
