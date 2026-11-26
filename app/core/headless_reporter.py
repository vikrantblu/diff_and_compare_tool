"""
Headless Automated Comparison & CI/CD HTML/JSON Reporting Engine
Enables automated non-GUI pipeline comparisons:
diff_and_compare --folder-diff dir_a/ dir_b/ --report-html report.html --exit-code
diff_and_compare --contract-diff old.yaml new.yaml --report-json report.json --exit-code
Exit codes:
0 = Identical / Non-breaking
1 = Content / binary mismatch or breaking contract change
2 = Error (missing path, permission, etc.)
"""

import csv
import os
import sys
import time
import html
import json
from dataclasses import asdict
from typing import Optional, List, Tuple
from app.core.folder_compare_engine import FolderCompareEngine, FolderCompareItem
from app.core.diff_engine import DiffEngine, AlignedDiffResult
from app.core.contract_diff import ContractDiffEngine


class HeadlessReporter:
    """Executes headless comparisons and generates standalone HTML/JSON reports."""

    @classmethod
    def run_folder_comparison(
        cls,
        dir_a: str,
        dir_b: str,
        report_html_path: Optional[str] = None,
        mode: str = "hash",
        respect_gitignore: bool = True
    ) -> Tuple[int, str]:
        """
        Runs headless folder comparison.
        Returns (exit_code, summary_message).
        Exit code: 0 = match, 1 = mismatch, 2 = error.
        """
        if not dir_a or not dir_b:
            return 2, "Error: Both dir_a and dir_b must be specified."
        if not os.path.exists(dir_a):
            return 2, f"Error: Folder '{dir_a}' does not exist."
        if not os.path.exists(dir_b):
            return 2, f"Error: Folder '{dir_b}' does not exist."

        try:
            items = FolderCompareEngine.compare_directories(
                dir_a, dir_b, mode=mode, respect_gitignore=respect_gitignore
            )
        except Exception as e:
            return 2, f"Error during folder comparison: {e}"

        flat_items: List[FolderCompareItem] = []

        def flatten(lst):
            for it in lst:
                flat_items.append(it)
                if it.children:
                    flatten(it.children)

        flatten(items)

        total_files = 0
        diff_count = 0
        left_only = 0
        right_only = 0
        same_count = 0

        for it in flat_items:
            if not it.is_dir:
                total_files += 1
                if it.status == "DIFF":
                    diff_count += 1
                elif it.status == "LEFT_ONLY":
                    left_only += 1
                elif it.status == "RIGHT_ONLY":
                    right_only += 1
                elif it.status == "SAME":
                    same_count += 1

        has_mismatch = (diff_count > 0 or left_only > 0 or right_only > 0)
        exit_code = 1 if has_mismatch else 0

        summary_msg = (
            f"Comparison Complete: {total_files} files evaluated. "
            f"Diffs: {diff_count}, Left Only: {left_only}, Right Only: {right_only}, Identical: {same_count}. "
            f"Status: {'MISMATCH' if has_mismatch else 'IDENTICAL'}"
        )

        if report_html_path:
            cls._generate_folder_html_report(
                dir_a, dir_b, flat_items, report_html_path,
                total_files, diff_count, left_only, right_only, same_count, exit_code
            )

        return exit_code, summary_msg

    @classmethod
    def _generate_folder_html_report(
        cls,
        dir_a: str,
        dir_b: str,
        flat_items: List[FolderCompareItem],
        output_file: str,
        total: int,
        diffs: int,
        left_only: int,
        right_only: int,
        same: int,
        exit_code: int
    ):
        status_banner_color = "#10b981" if exit_code == 0 else "#ef4444"
        status_text = "MATCH — IDENTICAL" if exit_code == 0 else "MISMATCH — DIFFERENCES DETECTED"

        rows_html = []
        for it in flat_items:
            badge_class = "badge-same"
            badge_text = "= MATCH"
            if it.status == "DIFF":
                badge_class = "badge-diff"
                badge_text = "≠ DIFF"
            elif it.status == "LEFT_ONLY":
                badge_class = "badge-left"
                badge_text = "← LEFT ONLY"
            elif it.status == "RIGHT_ONLY":
                badge_class = "badge-right"
                badge_text = "→ RIGHT ONLY"

            type_icon = "📁 " if it.is_dir else "📄 "
            l_sz = it.left_size_str or "-"
            r_sz = it.right_size_str or "-"

            rows_html.append(f"""
            <tr>
                <td><span class="badge {badge_class}">{badge_text}</span></td>
                <td>{type_icon}{html.escape(it.rel_path)}</td>
                <td>{l_sz}</td>
                <td>{r_sz}</td>
                <td>{html.escape(it.diff_reason or 'Match')}</td>
            </tr>
            """)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Folder Comparison Report — diff_and_compare</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 24px; }}
    .container {{ max-width: 1200px; margin: 0 auto; background: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; overflow: hidden; }}
    .header {{ padding: 24px; border-bottom: 1px solid #e2e8f0; }}
    .title {{ font-size: 20px; font-weight: 700; margin: 0 0 8px 0; color: #0f172a; }}
    .paths {{ font-size: 13px; color: #64748b; margin-bottom: 16px; font-family: monospace; }}
    .banner {{ display: inline-block; padding: 6px 14px; border-radius: 9999px; color: #ffffff; font-weight: 700; font-size: 12px; background-color: {status_banner_color}; }}
    .stats-grid {{ display: flex; gap: 16px; padding: 16px 24px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }}
    .stat-card {{ background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px 16px; flex: 1; }}
    .stat-val {{ font-size: 18px; font-weight: 700; }}
    .stat-lbl {{ font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }}
    th {{ background: #f1f5f9; padding: 12px 16px; border-bottom: 1.5px solid #cbd5e1; font-weight: 600; color: #475569; }}
    td {{ padding: 10px 16px; border-bottom: 1px solid #f1f5f9; font-family: Consolas, monospace; }}
    tr:hover {{ background-color: #f8fafc; }}
    .badge {{ display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; text-align: center; }}
    .badge-same {{ background: #f1f5f9; color: #64748b; }}
    .badge-diff {{ background: #ffe4e6; color: #e11d48; }}
    .badge-left {{ background: #eff6ff; color: #2563eb; }}
    .badge-right {{ background: #f5f3ff; color: #7c3aed; }}
    .footer {{ padding: 16px 24px; font-size: 12px; color: #94a3b8; text-align: right; border-top: 1px solid #e2e8f0; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1 class="title">Folder Comparison CI/CD Report</h1>
        <div class="paths">
            <strong>Left:</strong> {html.escape(os.path.abspath(dir_a))}<br>
            <strong>Right:</strong> {html.escape(os.path.abspath(dir_b))}
        </div>
        <span class="banner">{status_text}</span>
    </div>
    <div class="stats-grid">
        <div class="stat-card"><div class="stat-val">{total:,}</div><div class="stat-lbl">Total Files</div></div>
        <div class="stat-card"><div class="stat-val" style="color: #e11d48;">{diffs:,}</div><div class="stat-lbl">Differences</div></div>
        <div class="stat-card"><div class="stat-val" style="color: #2563eb;">{left_only:,}</div><div class="stat-lbl">Left Only</div></div>
        <div class="stat-card"><div class="stat-val" style="color: #7c3aed;">{right_only:,}</div><div class="stat-lbl">Right Only</div></div>
        <div class="stat-card"><div class="stat-val" style="color: #10b981;">{same:,}</div><div class="stat-lbl">Identical</div></div>
    </div>
    <table>
        <thead>
            <tr>
                <th style="width: 120px;">Status</th>
                <th>Item Path</th>
                <th style="width: 110px;">Left Size</th>
                <th style="width: 110px;">Right Size</th>
                <th style="width: 200px;">Reason</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows_html)}
        </tbody>
    </table>
    <div class="footer">
        Generated by diff_and_compare Automated Engine at {time.strftime('%Y-%m-%d %H:%M:%S')} (Exit Code: {exit_code})
    </div>
</div>
</body>
</html>
"""
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

    @classmethod
    def run_file_comparison(
        cls,
        file_a: str,
        file_b: str,
        report_html_path: Optional[str] = None
    ) -> Tuple[int, str]:
        """Runs headless 2-way file comparison."""
        if not os.path.exists(file_a) or not os.path.exists(file_b):
            return 2, "Error: One or both files do not exist."

        try:
            with open(file_a, "r", encoding="utf-8", errors="replace") as f:
                t_a = f.read()
            with open(file_b, "r", encoding="utf-8", errors="replace") as f:
                t_b = f.read()

            chunks, _, _ = DiffEngine.compute_2way_diff(t_a, t_b)
            diffs = [c for c in chunks if c.tag != "equal"]
            exit_code = 1 if len(diffs) > 0 else 0

            patch = DiffEngine.generate_unified_patch(t_a, t_b, file_a, file_b)
            if report_html_path:
                cls._generate_file_html_report(file_a, file_b, patch, len(diffs), report_html_path, exit_code)

            return exit_code, f"File Comparison: {len(diffs)} difference chunk(s). Status: {'MISMATCH' if exit_code == 1 else 'IDENTICAL'}"
        except Exception as e:
            return 2, f"Error during file comparison: {e}"

    @classmethod
    def _generate_file_html_report(cls, file_a: str, file_b: str, patch: str, diff_count: int, output_file: str, exit_code: int):
        status_banner_color = "#10b981" if exit_code == 0 else "#ef4444"
        status_text = "MATCH — IDENTICAL" if exit_code == 0 else f"MISMATCH — {diff_count} DIFF CHUNKS"

        diff_lines_html = []
        for line in patch.splitlines():
            esc = html.escape(line)
            if line.startswith("+++") or line.startswith("---"):
                diff_lines_html.append(f'<div class="diff-meta">{esc}</div>')
            elif line.startswith("@@"):
                diff_lines_html.append(f'<div class="diff-hunk">{esc}</div>')
            elif line.startswith("+"):
                diff_lines_html.append(f'<div class="diff-add">{esc}</div>')
            elif line.startswith("-"):
                diff_lines_html.append(f'<div class="diff-del">{esc}</div>')
            else:
                diff_lines_html.append(f'<div class="diff-ctx">{esc}</div>')

        body_html = "\n".join(diff_lines_html) if diff_lines_html else '<div class="diff-ctx">(Files are identical)</div>'
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>File Diff Report — diff_and_compare</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #f8fafc; color: #0f172a; margin: 0; padding: 24px; }}
    .container {{ max-width: 1100px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #cbd5e1; overflow: hidden; }}
    .header {{ padding: 20px; border-bottom: 1px solid #e2e8f0; }}
    .banner {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; color: #ffffff; font-weight: 700; font-size: 12px; background-color: {status_banner_color}; }}
    .diff-box {{ background: #ffffff; font-family: Consolas, monospace; font-size: 13px; overflow-x: auto; line-height: 1.5; padding: 8px 0; }}
    .diff-box div {{ padding: 1px 16px; white-space: pre; }}
    .diff-meta {{ background: #f1f5f9; color: #334155; font-weight: 700; }}
    .diff-hunk {{ background: #eff6ff; color: #0969da; font-weight: 600; }}
    .diff-add {{ background: #dafbe1; color: #116329; }}
    .diff-del {{ background: #ffebe9; color: #a40e26; }}
    .diff-ctx {{ color: #334155; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h2>File Diff Report</h2>
        <p><strong>A:</strong> {html.escape(file_a)}<br><strong>B:</strong> {html.escape(file_b)}</p>
        <span class="banner">{status_text}</span>
    </div>
    <div class="diff-box">{body_html}</div>
</div>
</body>
</html>"""
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

    @classmethod
    def run_contract_comparison(
        cls,
        file_a: str,
        file_b: str,
        report_html_path: Optional[str] = None,
        report_json_path: Optional[str] = None
    ) -> Tuple[int, str]:
        """Runs headless API contract comparison (OpenAPI, GraphQL, Protobuf). Returns exit_code 1 if breaking changes detected."""
        if not os.path.exists(file_a) or not os.path.exists(file_b):
            return 2, "Error: One or both contract files do not exist."

        try:
            with open(file_a, "r", encoding="utf-8", errors="replace") as f:
                t_a = f.read()
            with open(file_b, "r", encoding="utf-8", errors="replace") as f:
                t_b = f.read()

            report = ContractDiffEngine.diff_contracts(t_a, t_b, file_a, file_b)
            exit_code = 1 if report.has_breaking_changes else 0

            if report_json_path:
                payload = {
                    "contract_type": report.contract_type,
                    "has_breaking_changes": report.has_breaking_changes,
                    "breaking_count": report.breaking_count,
                    "warning_count": report.warning_count,
                    "additive_count": report.additive_count,
                    "changes": [asdict(c) for c in report.changes],
                }
                with open(report_json_path, "w", encoding="utf-8") as jf:
                    json.dump(payload, jf, indent=2)

            if report_html_path:
                cls._generate_contract_html_report(file_a, file_b, report, report_html_path, exit_code)

            return exit_code, (
                f"Contract Audit ({report.contract_type}): "
                f"Breaking={report.breaking_count}, Warnings={report.warning_count}, Additive={report.additive_count}. "
                f"Status: {'BREAKING' if report.has_breaking_changes else 'COMPATIBLE'}"
            )
        except Exception as e:
            return 2, f"Error during contract comparison: {e}"

    @classmethod
    def _generate_contract_html_report(cls, file_a: str, file_b: str, report, output_file: str, exit_code: int):
        banner_color = "#ef4444" if report.has_breaking_changes else "#10b981"
        banner_text = f"BREAKING CHANGES ({report.breaking_count})" if report.has_breaking_changes else "BACKWARD COMPATIBLE"
        rows = []
        for c in report.changes:
            cls_name = "badge-diff" if c.category == "BREAKING" else ("badge-warn" if c.category == "WARNING" else "badge-add")
            rows.append(
                f"<tr><td><span class='badge {cls_name}'>{html.escape(c.category)}</span></td>"
                f"<td>{html.escape(c.entity_path)}</td>"
                f"<td>{html.escape(c.change_type)}</td>"
                f"<td>{html.escape(c.description)}</td></tr>"
            )
        html_content = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>API Contract Audit — diff_and_compare</title>
<style>
    body {{ font-family: "Segoe UI", sans-serif; background: #f8fafc; color: #0f172a; margin: 0; padding: 24px; }}
    .container {{ max-width: 1100px; margin: 0 auto; background: #fff; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; }}
    .header {{ padding: 20px; border-bottom: 1px solid #e2e8f0; }}
    .banner {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; color: #fff; font-weight: 700; font-size: 12px; background: {banner_color}; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ padding: 10px 14px; border-bottom: 1px solid #f1f5f9; text-align: left; }}
    th {{ background: #f1f5f9; color: #334155; }}
    .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; }}
    .badge-diff {{ background: #ffe4e6; color: #cf222e; }}
    .badge-warn {{ background: #fff8c5; color: #9a6700; }}
    .badge-add {{ background: #dafbe1; color: #1a7f37; }}
</style></head>
<body><div class="container"><div class="header">
<h2>API Contract Audit ({html.escape(report.contract_type)})</h2>
<p><strong>Old:</strong> {html.escape(file_a)}<br><strong>New:</strong> {html.escape(file_b)}</p>
<span class="banner">{banner_text}</span>
</div><table><thead><tr><th>Severity</th><th>Entity</th><th>Change Type</th><th>Description</th></tr></thead>
<tbody>{"".join(rows) if rows else "<tr><td colspan='4'>No contract changes detected.</td></tr>"}</tbody></table>
</div></body></html>"""
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

    @staticmethod
    def _render_highlighted_html(text: str, spans, mark_cls: str) -> str:
        """Escapes line text cleanly while wrapping intraline diff spans in <mark>."""
        if not text:
            return "&nbsp;"
        if not spans:
            return html.escape(text)
        parts = []
        cursor = 0
        n = len(text)
        for s in sorted(spans, key=lambda sp: sp.start):
            st = max(cursor, min(s.start, n))
            en = max(st, min(s.end, n))
            if st > cursor:
                parts.append(html.escape(text[cursor:st]))
            if en > st:
                parts.append(f'<mark class="{mark_cls}">{html.escape(text[st:en])}</mark>')
            cursor = en
        if cursor < n:
            parts.append(html.escape(text[cursor:]))
        return "".join(parts)

    @classmethod
    def generate_side_by_side_html_report(
        cls,
        left_text: str,
        right_text: str,
        left_label: str = "Left",
        right_label: str = "Right",
        output_file: Optional[str] = None,
        ignore_whitespace: str = "none",
        ignore_case: bool = False,
        regex_rules=None
    ) -> str:
        """Generates a self-contained Fluent Light side-by-side HTML diff report with intraline marks."""
        res: AlignedDiffResult = DiffEngine.build_aligned_diff(
            left_text, right_text,
            ignore_whitespace=ignore_whitespace,
            ignore_case=ignore_case,
            regex_rules=regex_rules or [],
            ast_semantic=False,
        )

        n_rows = len(res.left_display_lines)
        row_tags = ["equal"] * n_rows
        l_spans_by_row = {}
        r_spans_by_row = {}
        added = deleted = modified = moved = 0

        for ch in res.chunks:
            if ch.tag == "equal":
                continue
            if ch.tag == "insert":
                added += 1
            elif ch.tag == "delete":
                deleted += 1
            elif ch.tag == "replace":
                modified += 1
            elif ch.tag == "moved":
                moved += 1
            for r in range(ch.left_start, min(ch.left_end, n_rows)):
                row_tags[r] = ch.tag
            for k, sp in ch.left_char_spans.items():
                l_spans_by_row[ch.left_start + k] = sp
            for k, sp in ch.right_char_spans.items():
                r_spans_by_row[ch.right_start + k] = sp

        rows_html = []
        for idx in range(n_rows):
            tag = row_tags[idx]
            is_diff = "1" if tag != "equal" else "0"
            l_spacer = idx in res.left_spacers
            r_spacer = idx in res.right_spacers

            l_num = "" if l_spacer else str(res.left_line_numbers.get(idx, idx + 1))
            r_num = "" if r_spacer else str(res.right_line_numbers.get(idx, idx + 1))

            l_cls = "cell-spacer" if l_spacer else f"cell-{tag}-l"
            r_cls = "cell-spacer" if r_spacer else f"cell-{tag}-r"
            if tag == "replace" and not l_spacer and r_spacer:
                l_cls = "cell-delete-l"
            elif tag == "replace" and l_spacer and not r_spacer:
                r_cls = "cell-insert-r"

            l_html = "&nbsp;" if l_spacer else cls._render_highlighted_html(
                res.left_display_lines[idx], l_spans_by_row.get(idx), "mark-del"
            )
            r_html = "&nbsp;" if r_spacer else cls._render_highlighted_html(
                res.right_display_lines[idx], r_spans_by_row.get(idx), "mark-add"
            )
            rows_html.append(
                f'<tr class="diff-row" data-diff="{is_diff}">'
                f'<td class="ln">{l_num}</td><td class="code {l_cls}">{l_html}</td>'
                f'<td class="ln">{r_num}</td><td class="code {r_cls}">{r_html}</td></tr>'
            )

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Side-by-Side Diff Report — diff_and_compare_tool</title>
<style>
    body {{ font-family: "Segoe UI", -apple-system, sans-serif; background: #f8fafc; color: #0f172a; margin: 0; padding: 20px; }}
    .wrap {{ max-width: 1440px; margin: 0 auto; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 12px rgba(15,23,42,0.06); }}
    .head {{ padding: 18px 22px; background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%); border-bottom: 1px solid #cbd5e1; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; }}
    .head h1 {{ margin: 0 0 6px 0; font-size: 18px; color: #0f172a; }}
    .meta {{ font-size: 12px; color: #475569; font-family: Consolas, monospace; }}
    .badges {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
    .pill {{ padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; border: 1px solid #cbd5e1; background: #fff; }}
    .p-add {{ color: #1a7f37; background: #dafbe1; border-color: #4ac26b; }}
    .p-del {{ color: #cf222e; background: #ffebe9; border-color: #ff8182; }}
    .p-mod {{ color: #0969da; background: #eff6ff; border-color: #93c5fd; }}
    .p-mov {{ color: #8250df; background: #f5f3ff; border-color: #c4b5fd; }}
    .btn {{ padding: 5px 12px; border-radius: 6px; border: 1px solid #cbd5e1; background: #ffffff; color: #0f172a; font-weight: 600; cursor: pointer; font-size: 12px; }}
    .btn.active {{ background: #0969da; color: #ffffff; border-color: #0969da; }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; font-family: Consolas, "Cascadia Code", monospace; font-size: 12.5px; line-height: 1.45; }}
    th {{ background: #f1f5f9; color: #334155; font-family: "Segoe UI", sans-serif; font-size: 12px; text-align: left; padding: 8px 10px; border-bottom: 1.5px solid #cbd5e1; }}
    td.ln {{ width: 46px; text-align: right; padding: 1px 8px; color: #64748b; background: #f8fafc; border-right: 1px solid #e2e8f0; user-select: none; }}
    td.code {{ padding: 1px 10px; white-space: pre-wrap; word-break: break-word; border-right: 1px solid #e2e8f0; vertical-align: top; }}
    .cell-spacer {{ background: repeating-linear-gradient(45deg, #f8fafc, #f8fafc 4px, #f1f5f9 4px, #f1f5f9 8px); }}
    .cell-insert-r, .cell-insert-l {{ background: #e6ffec; }}
    .cell-delete-l, .cell-delete-r {{ background: #ffebe9; }}
    .cell-replace-l, .cell-replace-r {{ background: #eff6ff; }}
    .cell-moved-l, .cell-moved-r {{ background: #f5f3ff; }}
    mark.mark-del {{ background: #ffcecb; color: #82071e; border-radius: 2px; padding: 0 1px; }}
    mark.mark-add {{ background: #aceebb; color: #0a3622; border-radius: 2px; padding: 0 1px; }}
</style>
</head>
<body>
<div class="wrap">
    <div class="head">
        <div>
            <h1>Side-by-Side Comparison Report</h1>
            <div class="meta"><strong>Left:</strong> {html.escape(left_label)} &nbsp;|&nbsp; <strong>Right:</strong> {html.escape(right_label)}</div>
        </div>
        <div class="badges">
            <span class="pill p-add">+{added} added</span>
            <span class="pill p-del">-{deleted} deleted</span>
            <span class="pill p-mod">~{modified} modified</span>
            <span class="pill p-mov">{moved} moved</span>
            <button class="btn active" onclick="filterRows(false, this)">All Lines</button>
            <button class="btn" onclick="filterRows(true, this)">Diffs Only</button>
        </div>
    </div>
    <table>
        <thead><tr><th style="width:46px">#</th><th>{html.escape(left_label)}</th><th style="width:46px">#</th><th>{html.escape(right_label)}</th></tr></thead>
        <tbody>{"".join(rows_html)}</tbody>
    </table>
</div>
<script>
function filterRows(diffsOnly, btn) {{
    document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('tr.diff-row').forEach(tr => {{
        tr.style.display = (diffsOnly && tr.dataset.diff !== '1') ? 'none' : '';
    }});
}}
</script>
</body>
</html>"""
        if output_file:
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(html_content)
        return html_content

    @classmethod
    def generate_folder_csv_report(cls, flat_items: List[FolderCompareItem], output_file: str) -> None:
        """Exports folder comparison items as a UTF-8 CSV report."""
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Status", "Type", "RelativePath", "LeftSizeBytes", "RightSizeBytes", "Reason"])
            for it in flat_items:
                writer.writerow([
                    it.status,
                    "Folder" if it.is_dir else "File",
                    it.rel_path,
                    "" if it.left_size is None else it.left_size,
                    "" if it.right_size is None else it.right_size,
                    it.diff_reason or ("Match" if it.status == "SAME" else ""),
                ])
