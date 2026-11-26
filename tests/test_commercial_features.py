"""
Comprehensive Test Suite for Commercial-Grade Diff & Compare Enhancements (White / Fluent Light Mode).
"""

import csv
import gc
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from PIL import Image
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.file_io import is_docx_path, extract_docx_text, read_text_file, write_text_file
from app.core.folder_compare_engine import FolderCompareEngine
from app.core.git_staging import GitStagingManager
from app.core.headless_reporter import HeadlessReporter
from app.core.session_manager import SessionManager
from app.ui.dialogs.command_palette import CommandPaletteDialog
from app.ui.dialogs.noise_filter_dialog import NoiseFilterDialog
from app.ui.diff_view import DiffView
from app.ui.dir_compare_view import DirCompareView
from app.ui.image_diff_view import ImageDiffView
from app.ui.main_window import MainWindow
from app.ui.widgets.line_details_panel import LineDetailsPanel


def _make_minimal_docx(path: str, paragraphs: list, table_rows: list = None):
    """Writes a minimal valid OOXML .docx archive containing paragraphs and optional table."""
    body_parts = []
    for p in paragraphs:
        body_parts.append(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>")
    if table_rows:
        trs = []
        for row in table_rows:
            tcs = "".join(f"<w:tc><w:p><w:r><w:t>{cell}</w:t></w:r></w:p></w:tc>" for cell in row)
            trs.append(f"<w:tr>{tcs}</w:tr>")
        body_parts.append(f"<w:tbl>{''.join(trs)}</w:tbl>")

    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(body_parts)}</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", doc_xml)


class TestCommercialFeatures(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self._tmp_session_dir = tempfile.mkdtemp()
        self._orig_storage_dir = SessionManager.get_storage_dir
        SessionManager.get_storage_dir = classmethod(lambda cls, d=self._tmp_session_dir: d)
        self._orig_recovery = MainWindow._check_crash_recovery
        MainWindow._check_crash_recovery = lambda self: None

    def tearDown(self):
        MainWindow._check_crash_recovery = self._orig_recovery
        SessionManager.get_storage_dir = self._orig_storage_dir
        shutil.rmtree(self._tmp_session_dir, ignore_errors=True)
        QApplication.sendPostedEvents()
        QApplication.processEvents()

    @classmethod
    def tearDownClass(cls):
        gc.collect()
        QApplication.sendPostedEvents()
        QApplication.processEvents()

    def test_docx_extraction_and_routing(self):
        with tempfile.TemporaryDirectory() as td:
            d1 = os.path.join(td, "contract_v1.docx")
            d2 = os.path.join(td, "contract_v2.docx")
            _make_minimal_docx(d1, ["Clause 1: Payment Net 30"], [["Tier", "Price"], ["Basic", "100"]])
            _make_minimal_docx(d2, ["Clause 1: Payment Net 15"], [["Tier", "Price"], ["Basic", "120"]])

            self.assertTrue(is_docx_path(d1))
            txt1, enc1, eol1 = read_text_file(d1)
            self.assertEqual(enc1, "DOCX (Extracted)")
            self.assertEqual(eol1, "LF")
            self.assertIn("Clause 1: Payment Net 30", txt1)
            self.assertIn("Basic\t100", txt1)

            win = MainWindow()
            win.smart_open_comparison(d1, d2)
            cur = win.tabs.currentWidget()
            self.assertIsInstance(cur, DiffView)
            self.assertTrue(cur.left_header.is_read_only())
            self.assertTrue(cur.right_header.is_read_only())
            self.assertIn("Net 15", cur._raw_right)
            win.close()

    def test_line_details_panel_and_display_scope_filter(self):
        panel = LineDetailsPanel()
        panel.update_pair(12, "rate = 0.20", 12, "rate = 0.25", tag="replace")
        self.assertIn("L:12", panel.lbl_coords.text())
        self.assertIn("Modified", panel.lbl_delta.text())
        panel.close()

        dv = DiffView()
        dv._raw_left = "\n".join(f"line_{i}" for i in range(1, 20))
        dv._raw_right = "\n".join(("line_10_MOD" if i == 10 else f"line_{i}") for i in range(1, 20))
        dv.combo_view_scope.setCurrentText("Diffs Only")
        # Diffs Only keeps only changed rows cleanly and sets filtered editors read-only
        self.assertTrue(dv.left_editor.isReadOnly())
        self.assertIn("line_10", dv.left_editor.toPlainText())
        self.assertNotIn("line_1\n", dv.left_editor.toPlainText())

        dv.combo_view_scope.setCurrentText("Context ±3")
        self.assertIn("line_7", dv.left_editor.toPlainText())
        self.assertIn("line_13", dv.left_editor.toPlainText())

        dv.combo_view_scope.setCurrentText("All Lines")
        self.assertFalse(dv.left_editor.isReadOnly())
        dv.close()

    def test_editor_header_lock_and_encoding_converter(self):
        dv = DiffView()
        dv._raw_left = "alpha\nbeta\ngamma"
        dv._raw_right = "alpha\nBETA\ngamma"
        dv.run_diff()

        dv.right_header.set_read_only(True)
        diff_idx = next(i for i, c in enumerate(dv.chunks) if c.tag != "equal")
        dv.transfer_left_to_right(diff_idx)
        # Transfer must be blocked when Right pane is Read-Only locked
        self.assertIn("BETA", dv._raw_right)

        dv.right_header.set_read_only(False)
        dv.right_header._change_encoding("UTF-8 BOM")
        dv.right_header._change_eol("CRLF")
        self.assertTrue(dv.right_header.is_dirty)
        self.assertEqual(dv.right_header.btn_meta.text(), "UTF-8 BOM | CRLF")

        with tempfile.TemporaryDirectory() as td:
            out_p = os.path.join(td, "encoded.txt")
            write_text_file(out_p, dv._raw_right, encoding_label=dv.right_header.encoding, eol_label=dv.right_header.eol)
            with open(out_p, "rb") as f:
                raw = f.read()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            self.assertIn(b"\r\n", raw)
        dv.close()

    def test_custom_noise_rules_persistence_and_ignore_unimportant_toggle(self):
        SessionManager.save_custom_noise_rules([(r"BUILD_\d+", "BUILD_X")])
        loaded = SessionManager.get_custom_noise_rules()
        self.assertEqual(loaded, [(r"BUILD_\d+", "BUILD_X")])

        dlg = NoiseFilterDialog()
        dlg.add_custom_rule(r"v\d+\.\d+", "vX")
        dlg._apply()
        self.assertIn((r"v\d+\.\d+", "vX"), dlg.get_rules())
        dlg.close()

        dv = DiffView()
        dv.active_noise_rules = [(r"BUILD_\d+", "BUILD_X")]
        dv._raw_left = "tag = BUILD_101"
        dv._raw_right = "tag = BUILD_202"
        dv.chk_ignore_unimportant.setChecked(True)
        dv.run_diff()
        self.assertEqual(sum(1 for c in dv.chunks if c.tag != "equal"), 0)

        dv.chk_ignore_unimportant.setChecked(False)
        self.assertEqual(sum(1 for c in dv.chunks if c.tag != "equal"), 1)
        dv.close()

    def test_side_by_side_html_and_folder_csv_reports(self):
        with tempfile.TemporaryDirectory() as td:
            hp = os.path.join(td, "sbs.html")
            html_out = HeadlessReporter.generate_side_by_side_html_report(
                "x = 1\ny = 2", "x = 1\ny = 99", "a.py", "b.py", output_file=hp
            )
            self.assertTrue(os.path.exists(hp))
            self.assertIn("mark-del", html_out)
            self.assertIn("mark-add", html_out)
            self.assertNotIn("toggleTheme", html_out)

            d1 = os.path.join(td, "d1")
            d2 = os.path.join(td, "d2")
            os.makedirs(d1)
            os.makedirs(d2)
            with open(os.path.join(d1, "same.txt"), "w") as f:
                f.write("ok")
            with open(os.path.join(d2, "same.txt"), "w") as f:
                f.write("ok")
            items = FolderCompareEngine.compare_directories(d1, d2)
            cp = os.path.join(td, "folder.csv")
            HeadlessReporter.generate_folder_csv_report(FolderCompareEngine.flatten_tree(items), cp)
            with open(cp, "r", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0][0], "Status")
            self.assertEqual(rows[1][2], "same.txt")

    def test_folder_flatten_and_timestamp_tolerance(self):
        with tempfile.TemporaryDirectory() as td:
            d1 = os.path.join(td, "left")
            d2 = os.path.join(td, "right")
            os.makedirs(os.path.join(d1, "nested"))
            os.makedirs(os.path.join(d2, "nested"))

            p1 = os.path.join(d1, "nested", "within_tol.txt")
            p2 = os.path.join(d2, "nested", "within_tol.txt")
            with open(p1, "w") as f: f.write("hello")
            with open(p2, "w") as f: f.write("hello")
            os.utime(p1, (1000000.0, 1000000.0))
            os.utime(p2, (1000001.2, 1000001.2))  # 1.2s skew <= 2.0s tolerance -> SAME

            q1 = os.path.join(d1, "nested", "outside_tol.txt")
            q2 = os.path.join(d2, "nested", "outside_tol.txt")
            with open(q1, "w") as f: f.write("hello")
            with open(q2, "w") as f: f.write("hello")
            os.utime(q1, (1000000.0, 1000000.0))
            os.utime(q2, (1000010.0, 1000010.0))  # 10s skew > 2.0s tolerance -> DIFF

            tree = FolderCompareEngine.compare_directories(d1, d2, mode="timestamp", timestamp_tolerance_sec=2.0)
            flat = FolderCompareEngine.flatten_tree(tree)
            by_rel = {it.rel_path: it.status for it in flat}
            self.assertEqual(by_rel["nested/within_tol.txt"], "SAME")
            self.assertEqual(by_rel["nested/outside_tol.txt"], "DIFF")

            dv = DirCompareView()
            dv._cancel_worker()
            dv._cached_items = tree
            dv.btn_flatten.setChecked(True)
            top_texts = [dv.tree_left.topLevelItem(i).text(0) for i in range(dv.tree_left.topLevelItemCount())]
            self.assertIn("nested/within_tol.txt", top_texts)
            self.assertIn("nested/outside_tol.txt", top_texts)
            dv.close()

    def test_git_working_tree_changes_and_local_config(self):
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["git", "init"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=td, check=True, capture_output=True)

            tracked = os.path.join(td, "app.py")
            with open(tracked, "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            subprocess.run(["git", "add", "app.py"], cwd=td, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=td, check=True, capture_output=True)

            with open(tracked, "w", encoding="utf-8") as f:
                f.write("x = 2\n")
            untracked = os.path.join(td, "new_notes.txt")
            with open(untracked, "w", encoding="utf-8") as f:
                f.write("hello\n")

            changes = GitStagingManager.get_working_tree_changes(td)
            rels = {c["rel_path"]: c["label"] for c in changes}
            self.assertEqual(rels.get("app.py"), "Modified")
            self.assertEqual(rels.get("new_notes.txt"), "Untracked")

            ok, _msg = GitStagingManager.configure_git_difftool_mergetool(
                exe_command='"diff_and_compare.exe"', scope="local", cwd=td
            )
            self.assertTrue(ok)
            status = GitStagingManager.get_git_tool_config_status(scope="local", cwd=td)
            self.assertEqual(status["diff.tool"], "diff_and_compare")
            self.assertEqual(status["merge.tool"], "diff_and_compare")
            self.assertIn("--diff", status["difftool.diff_and_compare.cmd"])

    def test_command_palette_filter_and_image_pixel_inspector(self):
        called = []
        cmds = [
            ("Open Text Studio", "Studio", "", lambda: called.append("text")),
            ("Browse Git Changes", "Git", "Ctrl+G", lambda: called.append("git")),
        ]
        pal = CommandPaletteDialog(cmds)
        pal.filter_commands("git")
        self.assertEqual(pal.list_commands.count(), 1)
        self.assertTrue(pal.execute_selected())
        self.assertEqual(called, ["git"])
        pal.close()

        with tempfile.TemporaryDirectory() as td:
            p1 = os.path.join(td, "img1.png")
            p2 = os.path.join(td, "img2.png")
            Image.new("RGBA", (8, 8), (10, 20, 30, 255)).save(p1)
            Image.new("RGBA", (8, 8), (15, 20, 40, 255)).save(p2)

            iv = ImageDiffView()
            iv.set_images(p1, p2)
            iv._on_pixel_hovered(2, 3)
            txt = iv.lbl_pixel_info.text()
            self.assertIn("(2, 3)", txt)
            self.assertIn("ΔRGBA: (5, 0, 10, 0)", txt)
            iv.close()

    def test_docs_website_exists_and_light_mode_only(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        site = os.path.join(root, "docs", "index.html")
        self.assertTrue(os.path.isfile(site))
        with open(site, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("diff_and_compare_tool", content)
        self.assertIn("Beyond Compare 5", content)
        self.assertNotIn("toggleTheme", content)
        self.assertNotIn("dark-mode", content.lower())


if __name__ == "__main__":
    unittest.main()
