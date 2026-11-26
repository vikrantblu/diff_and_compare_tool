"""
Regression & Integration Test Suite for Audit Fixes and Enhancements (White Mode Only).
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = QApplication.instance() or QApplication(sys.argv)

from app.core.diff_engine import DiffEngine, NOISE_REGEX_PRESETS
from app.core.folder_compare_engine import FolderCompareEngine
from app.core.structured_diff import StructuredDiffEngine
from app.core.tabular_diff import TabularDiffEngine
from app.core.hex_diff import HexDiffEngine
from app.core.image_diff import ImageDiffEngine
from app.core.ai_assistant import AIAssistant
from app.core.headless_reporter import HeadlessReporter
from app.core.wal_journal import WALJournal
from app.core.shell_integration import generate_reg_content
from app.core.session_manager import SessionManager
from app.core.file_io import read_text_file, write_text_file
from app.ui.main_window import MainWindow
from app.ui.merge_view import MergeView
from app.ui.diff_view import DiffView
from app.ui.structured_diff_view import StructuredDiffView
from app.ui.hex_diff_view import HexDiffView
from app.ui.image_diff_view import ImageDiffView


class TestAuditFixes(unittest.TestCase):

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

    def test_aligned_diff_preserves_moved_blocks_and_raw_coords(self):
        t_left = "blockA\nblockB\nblockC\ncommon\n"
        t_right = "common\nblockA\nblockB\nblockC\n"
        res = DiffEngine.build_aligned_diff(t_left, t_right, detect_moved=True)
        # Moved block lines must actually appear in the aligned display lines
        self.assertTrue(any("blockA" in l for l in res.left_display_lines))
        self.assertTrue(any("blockA" in l for l in res.right_display_lines))
        moved = [c for c in res.chunks if c.tag == "moved"]
        self.assertGreater(len(moved), 0)
        for c in moved:
            self.assertIsNotNone(c.raw_left_start)
            self.assertIsNotNone(c.raw_right_start)

    def test_manual_alignment_monotonic_and_line1(self):
        left = "L1\nL2\nL3"
        right = "R1\nR2\nR3"
        # Crossing anchors (3,1) then (1,3) — second crossing anchor must be filtered out safely
        res = DiffEngine.build_aligned_diff(left, right, manual_alignments=[(1, 1), (3, 2), (2, 3)])
        self.assertEqual(res.left_line_numbers[0], 1)
        self.assertEqual(res.right_line_numbers[0], 1)
        self.assertEqual(res.left_display_lines[0], "L1")
        self.assertEqual(res.right_display_lines[0], "R1")

    def test_normalize_text_multiline_comments_preserve_line_count(self):
        code_a = "x = 1\n/* multi\nline\ncomment */\ny = 2\n"
        code_b = "x = 1\n/* other\nchanged\ncomment */\ny = 2\n"
        rules = [NOISE_REGEX_PRESETS["C/C++/Java/JS Comments"]]
        norm_a = DiffEngine.normalize_text(code_a, regex_rules=rules)
        norm_b = DiffEngine.normalize_text(code_b, regex_rules=rules)
        self.assertEqual(len(norm_a), len(code_a.split("\n")))
        self.assertEqual(norm_a, norm_b)

    def test_3way_merge_mid_file_insertion_and_conflicts(self):
        base = "line1\nline2\nline3\n"
        mine = "line1\nmine_inserted\nline2\nline3\n"
        theirs = "line1\nline2\ntheirs_inserted\nline3\n"
        chunks = DiffEngine.compute_3way_merge(base, mine, theirs)
        resolved = []
        for c in chunks:
            self.assertFalse(c.is_conflict)
            resolved.extend(c.resolved_lines)
        self.assertIn("mine_inserted", resolved)
        self.assertIn("theirs_inserted", resolved)
        self.assertIn("line1", resolved)
        self.assertIn("line3", resolved)

        # Conflicting insertion at the exact same spot
        mine2 = "line1\nmine_opt\nline2\nline3\n"
        theirs2 = "line1\ntheirs_opt\nline2\nline3\n"
        chunks2 = DiffEngine.compute_3way_merge(base, mine2, theirs2)
        self.assertTrue(any(c.is_conflict for c in chunks2))

    def test_merge_view_ai_resolve_markers_and_jump(self):
        mv = MergeView()
        mv._ai_resolve_current_conflict()
        out_text = mv.editor_output.toPlainText()
        self.assertNotIn("<<<<<<< MINE (LOCAL)", out_text)
        mv.jump_next_conflict()
        mv.jump_prev_conflict()

        # Verify unresolved marker ordering follows standard diff3
        mv2 = MergeView()
        out2 = mv2.editor_output.toPlainText()
        self.assertIn("<<<<<<< MINE (LOCAL)", out2)
        self.assertIn("||||||| BASE (ANCESTOR)", out2)
        self.assertIn("=======", out2)
        self.assertIn(">>>>>>> THEIRS (REMOTE)", out2)
        self.assertLess(out2.index("======="), out2.index(">>>>>>> THEIRS (REMOTE)"))
        mv.close()
        mv2.close()

    def test_white_mode_only_and_session_persistence(self):
        win = MainWindow()
        self.assertFalse(hasattr(win, "toggle_theme"))
        self.assertFalse(hasattr(win, "btn_theme_toggle"))

        with tempfile.TemporaryDirectory() as td:
            f1 = os.path.join(td, "a.py")
            f2 = os.path.join(td, "b.py")
            with open(f1, "w", encoding="utf-8") as f:
                f.write("print(1)\n")
            with open(f2, "w", encoding="utf-8") as f:
                f.write("print(2)\n")

            win.open_file_diff(f1, f2)
            sess = win._get_current_session_data()
            diff_entries = [s for s in sess if s.get("type") == "DiffView"]
            self.assertEqual(len(diff_entries), 1)
            self.assertEqual(diff_entries[0]["left_path"], f1)
            self.assertEqual(diff_entries[0]["right_path"], f2)
        win.close()

    def test_pdf_and_contract_routing(self):
        win = MainWindow()
        win.smart_open_comparison("doc1.pdf", "doc2.pdf")
        self.assertIsInstance(win.tabs.currentWidget(), ImageDiffView)

        win.smart_open_comparison("svc1.proto", "svc2.proto")
        cur = win.tabs.currentWidget()
        self.assertIsInstance(cur, StructuredDiffView)
        self.assertTrue(cur.btn_contract_view.isChecked())
        win.close()

    def test_diff_view_transfer_with_whitespace_options(self):
        dv = DiffView()
        dv.combo_whitespace.setCurrentIndex(2)  # Ignore All Whitespace
        dv._raw_left = "a = 1\nb = 2\nc = 3"
        dv._raw_right = "  a = 1\nb = 99\nc = 3"
        dv.run_diff()
        diff_idx = next(i for i, c in enumerate(dv.chunks) if c.tag != "equal")
        dv.transfer_left_to_right(diff_idx)
        self.assertIn("b = 2", dv._raw_right)
        dv.close()

    def test_folder_compare_zip_vfs_and_deep_propagation_and_filters(self):
        with tempfile.TemporaryDirectory() as td:
            z1 = os.path.join(td, "v1.zip")
            z2 = os.path.join(td, "v2.zip")
            with zipfile.ZipFile(z1, "w") as zf:
                zf.writestr("pkg/same.txt", "identical")
                zf.writestr("pkg/sub/mod.py", "x = 1")
            with zipfile.ZipFile(z2, "w") as zf:
                zf.writestr("pkg/same.txt", "identical")
                zf.writestr("pkg/sub/mod.py", "x = 2")

            items = FolderCompareEngine.compare_directories(z1, z2, mode="hash")
            pkg = items[0]
            self.assertEqual(pkg.status, "DIFF")
            sub = [c for c in pkg.children if c.name == "sub"][0]
            self.assertEqual(sub.status, "DIFF")
            same = [c for c in pkg.children if c.name == "same.txt"][0]
            self.assertEqual(same.status, "SAME")

            # Multi-include OR filter on disk folders
            d1 = os.path.join(td, "d1")
            d2 = os.path.join(td, "d2")
            os.makedirs(os.path.join(d1, "nested"), exist_ok=True)
            os.makedirs(os.path.join(d2, "nested"), exist_ok=True)
            with open(os.path.join(d1, "nested", "a.py"), "w") as f: f.write("1")
            with open(os.path.join(d1, "nested", "b.md"), "w") as f: f.write("2")
            with open(os.path.join(d1, "nested", "c.tmp"), "w") as f: f.write("3")
            with open(os.path.join(d2, "nested", "a.py"), "w") as f: f.write("1")
            with open(os.path.join(d2, "nested", "b.md"), "w") as f: f.write("2")

            filtered = FolderCompareEngine.compare_directories(d1, d2, filter_expr="*.py; *.md")
            nested_names = {c.name for c in filtered[0].children}
            self.assertEqual(nested_names, {"a.py", "b.md"})

    def test_structured_view_filter_and_xml_tag_rename(self):
        sv = StructuredDiffView()
        sv.set_content('{"alpha": 1, "beta": 2}', '{"alpha": 1, "beta": 3}')
        sv.txt_filter.setText("beta")
        top_names = [sv.tree.topLevelItem(i).text(0) for i in range(sv.tree.topLevelItemCount())]
        self.assertIn("beta", top_names)
        self.assertNotIn("alpha", top_names)
        sv.close()

        xml_res = StructuredDiffEngine.compare("<oldTag>hi</oldTag>", "<newTag>hi</newTag>", format_type="xml")
        self.assertEqual(xml_res.root_node.status, "modified")
        self.assertIn("oldTag", xml_res.root_node.name)
        self.assertIn("newTag", xml_res.root_node.name)

    def test_hex_view_virtual_rows_and_find_pattern(self):
        with tempfile.TemporaryDirectory() as td:
            p1 = os.path.join(td, "b1.bin")
            p2 = os.path.join(td, "b2.bin")
            data1 = bytes(range(256)) * 20  # 5120 bytes -> 320 rows (>100)
            data2 = bytearray(data1)
            data2[4000] ^= 0xFF
            with open(p1, "wb") as f: f.write(data1)
            with open(p2, "wb") as f: f.write(bytes(data2))

            pos = HexDiffEngine.find_pattern(p2, bytes([data2[4000], data2[4001]]))
            self.assertIsNotNone(pos)

            hv = HexDiffView()
            hv.set_files(p1, p2)
            self.assertEqual(hv.model_left.rowCount(), 320)
            hv.txt_offset.setText("0xFA0")
            hv._jump_to_offset()
            hv.close()

    def test_tabular_duplicate_key_reporting_and_encoding_roundtrip(self):
        csv1 = "id,val\n1,A\n1,B\n"
        csv2 = "id,val\n1,B\n2,C\n"
        res = TabularDiffEngine.compare_tables(csv1, csv2, key_column="id")
        self.assertEqual(res.duplicate_keys_left, 1)
        self.assertEqual(res.duplicate_keys_right, 0)

        with tempfile.TemporaryDirectory() as td:
            fp = os.path.join(td, "bom_crlf.txt")
            write_text_file(fp, "line1\nline2\n", encoding_label="UTF-8 BOM", eol_label="CRLF")
            txt, enc, eol = read_text_file(fp)
            self.assertEqual(enc, "UTF-8 BOM")
            self.assertEqual(eol, "CRLF")
            self.assertIn("line1", txt)

    def test_ai_offline_zero_outbound_and_openai_payload(self):
        payload = AIAssistant.build_llm_payload("hello", "https://api.openai.com/v1/chat/completions", "gpt-4o")
        self.assertIn("messages", payload)
        self.assertNotIn("prompt", payload)

        # Zero outbound: returns offline heuristic directly when endpoint=None
        out = AIAssistant.generate_diff_summary([], ["a"], ["b"], endpoint=None)
        self.assertIn("AI Change Analysis", out)

    def test_headless_contract_reporter_and_reg_export(self):
        with tempfile.TemporaryDirectory() as td:
            p1 = os.path.join(td, "v1.proto")
            p2 = os.path.join(td, "v2.proto")
            jp = os.path.join(td, "report.json")
            hp = os.path.join(td, "report.html")
            with open(p1, "w") as f:
                f.write('syntax = "proto3";\nmessage User { string id = 1; }\n')
            with open(p2, "w") as f:
                f.write('syntax = "proto3";\nmessage User { int32 id = 1; }\n')

            code, summary = HeadlessReporter.run_contract_comparison(p1, p2, report_html_path=hp, report_json_path=jp)
            self.assertEqual(code, 1)
            self.assertIn("BREAKING", summary)
            with open(jp, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertTrue(data["has_breaking_changes"])

        reg = generate_reg_content(target_exe=r"C:\app\diff.exe")
        self.assertNotIn('\\"\\"', reg)
        self.assertIn('diff.exe\\" --compare \\"%1\\""', reg)
        self.assertNotIn(r"CurrentVersion\\Uninstall", reg)
        self.assertIn(r"CurrentVersion\Uninstall\diff_and_compare_tool]", reg)

    def test_wal_unique_session_ids(self):
        tmp_dir = tempfile.mkdtemp()
        orig = WALJournal.get_wal_dir
        WALJournal.get_wal_dir = classmethod(lambda cls: tmp_dir)
        try:
            w1 = WALJournal()
            w2 = WALJournal()
            self.assertNotEqual(w1.wal_path, w2.wal_path)
            w1.clean_exit()
            w2.clean_exit()
        finally:
            WALJournal.get_wal_dir = orig
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
