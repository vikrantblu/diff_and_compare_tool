"""
Headless Automated Comparison & CI/CD HTML Reporting Engine
Enables automated non-GUI pipeline comparisons:
diff_and_compare --folder-diff dir_a/ dir_b/ --report-html report.html --exit-code
Exit codes:
0 = Identical
1 = Content / binary mismatch
2 = Error (missing path, permission, etc.)
"""

import os
import sys
import time
import html
from typing import Optional, List, Tuple
from app.core.folder_compare_engine import FolderCompareEngine, FolderCompareItem
from app.core.diff_engine import DiffEngine, DiffChunk


class HeadlessReporter:
    """Executes headless comparisons and generates standalone HTML reports."""

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

        # Flatten items
        flat_items = []
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

        patch_escaped = html.escape(patch)
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>File Diff Report — diff_and_compare</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 24px; }}
    .container {{ max-width: 1000px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #cbd5e1; overflow: hidden; }}
    .header {{ padding: 20px; border-bottom: 1px solid #e2e8f0; }}
    .banner {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; color: #ffffff; font-weight: 700; font-size: 12px; background-color: {status_banner_color}; }}
    pre {{ background: #0f172a; color: #f8fafc; padding: 16px; margin: 0; font-family: Consolas, monospace; font-size: 13px; overflow-x: auto; line-height: 1.5; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h2>File Diff Report</h2>
        <p><strong>A:</strong> {html.escape(file_a)}<br><strong>B:</strong> {html.escape(file_b)}</p>
        <span class="banner">{status_text}</span>
    </div>
    <pre>{patch_escaped}</pre>
</div>
</body>
</html>"""
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)
