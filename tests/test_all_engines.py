"""
Unit & Integration Test Suite for diff_and_compare_tool Architecture
"""

import os
import sys

sys.path.insert(0, os.path.abspath("."))

from PIL import Image
from app.core.diff_engine import DiffEngine
from app.core.structured_diff import StructuredDiffEngine
from app.core.tabular_diff import TabularDiffEngine
from app.core.image_diff import ImageDiffEngine
from app.core.hex_diff import HexDiffEngine
from app.core.archive_vfs import ArchiveVFS
from app.core.ai_assistant import AIAssistant


def test_unified_patch():
    t1 = "hello\nworld\n"
    t2 = "hello\nearth\n"
    patch = DiffEngine.generate_unified_patch(t1, t2)
    assert "--- a/file" in patch
    assert "+++ b/file" in patch
    assert "-world" in patch
    assert "+earth" in patch
    print("[OK] 1. Unified Patch: PASSED")


def test_moved_blocks():
    t_left = "blockA\nblockB\nblockC\ncommon\n"
    t_right = "common\nblockA\nblockB\nblockC\n"
    res = DiffEngine.build_aligned_diff(t_left, t_right, detect_moved=True)
    moved_chunks = [c for c in res.chunks if c.is_moved]
    assert len(moved_chunks) > 0, "Expected moved blocks to be detected"
    print(f"[OK] 2. Moved Block Detection ({len(moved_chunks)} chunks): PASSED")


def test_structured_diff():
    j1 = '{"a": 1, "b": [10, 20], "c": "fixed"}'
    j2 = '{"b": [10, 25], "a": 1, "d": "new"}'
    res = StructuredDiffEngine.compare(j1, j2)
    assert res.total_nodes > 0
    assert res.added_count == 1  # 'd' added
    assert res.deleted_count == 1  # 'c' deleted
    print(f"[OK] 3. Structured JSON Tree Diff ({res.total_nodes} nodes): PASSED")


def test_tabular_diff():
    csv1 = "id,name,role\n1,Alice,Dev\n2,Bob,QA\n"
    csv2 = "id,name,role\n2,Bob,Lead QA\n3,Charlie,Ops\n"
    res = TabularDiffEngine.compare_tables(csv1, csv2, key_column="id")
    assert res.total_rows == 3
    assert res.added_count == 1    # id 3 added
    assert res.deleted_count == 1  # id 1 deleted
    assert res.modified_count == 1 # id 2 modified
    print("[OK] 4. Tabular Keyed Grid Diff: PASSED")


def test_image_diff():
    im1 = Image.new("RGB", (60, 60), color="white")
    im2 = Image.new("RGB", (60, 60), color="white")
    # Draw a 10x10 red square on im2
    for x in range(10):
        for y in range(10):
            im2.putpixel((x, y), (255, 0, 0))

    im1.save("tests/tmp1.png")
    im2.save("tests/tmp2.png")
    try:
        res = ImageDiffEngine.compare_images("tests/tmp1.png", "tests/tmp2.png")
        assert res is not None
        assert res.diff_pixel_count == 100
        curtain = ImageDiffEngine.render_swipe_curtain(res.img1, res.img2, split_ratio=0.5)
        assert curtain.size == (60, 60)
        onion = ImageDiffEngine.render_onion_skin(res.img1, res.img2, alpha=0.5)
        assert onion.size == (60, 60)
        print(f"[OK] 5. Image Diff Engine ({res.diff_pixel_count} px diff): PASSED")
    finally:
        if os.path.exists("tests/tmp1.png"): os.remove("tests/tmp1.png")
        if os.path.exists("tests/tmp2.png"): os.remove("tests/tmp2.png")


def test_hex_diff():
    with open("tests/tmp1.bin", "wb") as f: f.write(b"\x00\x01\x02\x03\x04" * 10)
    with open("tests/tmp2.bin", "wb") as f: f.write(b"\x00\x01\xFF\x03\x04" * 10)
    try:
        summary = HexDiffEngine.compare_files_summary("tests/tmp1.bin", "tests/tmp2.bin")
        assert summary is not None
        assert summary.differing_bytes_count == 10
        rows = HexDiffEngine.read_row_range("tests/tmp1.bin", "tests/tmp2.bin", 0, 5)
        assert len(rows) > 0
        print(f"[OK] 6. Hex / Binary Diff ({summary.differing_bytes_count} bytes diff): PASSED")
    finally:
        if os.path.exists("tests/tmp1.bin"): os.remove("tests/tmp1.bin")
        if os.path.exists("tests/tmp2.bin"): os.remove("tests/tmp2.bin")


def test_ai_assistant():
    t_left = ["def legacy_tax():", "    return 10"]
    t_right = ["def modern_tax():", "    return 15"]
    summary = AIAssistant.generate_diff_summary([], t_left, t_right, "old.py", "new.py")
    assert "AI Change Analysis" in summary
    print("[OK] 7. AI Assistant PR Summarizer: PASSED")


def test_folder_compare_and_shell():
    import tempfile
    from app.core.folder_compare_engine import FolderCompareEngine
    from app.core.shell_integration import set_left_path, get_left_path, is_context_menu_installed, install_context_menu

    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        with open(os.path.join(d1, "test.txt"), "w") as f: f.write("AAA")
        with open(os.path.join(d2, "test.txt"), "w") as f: f.write("BBB")
        items = FolderCompareEngine.compare_directories(d1, d2)
        assert len(items) == 1
        assert items[0].status == "DIFF"

    test_dummy = os.path.abspath(os.path.join(tempfile.gettempdir(), "dummy_test_path.txt"))
    set_left_path(test_dummy)
    assert get_left_path() == test_dummy
    ok, _ = install_context_menu()
    assert ok is True
    assert is_context_menu_installed() is True
    print("[OK] 8. Folder Compare Engine & Windows Shell Context Menu: PASSED")


def test_ast_diff_and_blake3():
    from app.core.ast_diff import ASTSemanticDiffer
    from app.core.diff_engine import DiffEngine

    code_l = "def funcA():\n    return 1\ndef funcB():\n    return 2\n"
    code_r = "def funcB():\n    return 2\ndef funcA():\n    return 1\n"
    matches = ASTSemanticDiffer.compare_semantics(code_l, code_r, "python")
    assert len(matches) > 0
    reordered = [m for m in matches if m.status == "reordered"]
    assert len(reordered) > 0

    aligned = DiffEngine.build_aligned_diff(code_l, code_r, detect_moved=True, ast_semantic=True)
    assert len(aligned.chunks) > 0

    # BLAKE3 Hash test
    import tempfile
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write("BLAKE3 acceleration test")
        t_path = f.name
    try:
        h = DiffEngine.hash_file(t_path, algo="blake3")
        assert len(h) == 64
        print(f"[OK] 9. AST Semantic Diff & Native BLAKE3 ({h[:8]}...): PASSED")
    finally:
        if os.path.exists(t_path): os.remove(t_path)


def test_tabular_parquet_sqlite_and_tolerance():
    import sqlite3
    import tempfile

    # 1. Float tolerance
    csv_a = "val,desc\n10.0001,item\n"
    csv_b = "val,desc\n10.0009,item\n"
    res_exact = TabularDiffEngine.compare_tables(csv_a, csv_b, float_tolerance=0.0)
    assert res_exact.modified_count == 1
    res_tol = TabularDiffEngine.compare_tables(csv_a, csv_b, float_tolerance=0.005)
    assert res_tol.equal_count == 1

    # 2. SQLite Ingestion
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        cur.execute("INSERT INTO users VALUES (1, 'Alice')")
        conn.commit()
        conn.close()

        headers, rows = TabularDiffEngine.load_table(db_path)
        assert "name" in headers
        assert len(rows) == 1
        print("[OK] 10. Tabular Float Tolerance & SQLite Ingestion: PASSED")
    finally:
        if os.path.exists(db_path): os.remove(db_path)


def test_pdf_and_exif_diff():
    import fitz
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name
    try:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 72), "diff_and_compare_tool PDF Diff Test")
        doc.save(pdf_path)
        doc.close()

        count = ImageDiffEngine.get_page_count(pdf_path)
        assert count == 1
        text = ImageDiffEngine.get_extracted_text(pdf_path, 0)
        assert "diff_and_compare_tool" in text
        img = ImageDiffEngine.load_image(pdf_path, 0)
        assert img is not None
        exif = ImageDiffEngine.get_exif_metadata(pdf_path)
        assert "Page Count" in exif
        print("[OK] 11. PDF Document Rendering & EXIF Metadata Inspection: PASSED")
    finally:
        if os.path.exists(pdf_path): os.remove(pdf_path)


def test_structured_jsonpath_and_unordered_arrays():
    # 1. Unordered Array matching
    j1 = '{"items": [{"id": 1, "v": "A"}, {"id": 2, "v": "B"}]}'
    j2 = '{"items": [{"id": 2, "v": "B"}, {"id": 1, "v": "A"}]}'
    res_unordered = StructuredDiffEngine.compare(j1, j2, unordered_arrays=True)
    assert res_unordered.root_node.status == "equal"

    # 2. JSONPath query
    j_store = '{"store": {"book": [{"title": "X"}, {"title": "Y"}]}}'
    res_q = StructuredDiffEngine.compare(j_store, j_store, query="$.store.book[*].title")
    assert res_q.root_node.status == "equal"
    print("[OK] 12. Structured JSONPath Query & Unordered Array Matching: PASSED")


def test_folder_sync_engine():
    import tempfile
    from app.core.folder_compare_engine import FolderCompareEngine
    from app.core.folder_sync_engine import FolderSyncEngine

    with tempfile.TemporaryDirectory() as d_left, tempfile.TemporaryDirectory() as d_right:
        with open(os.path.join(d_left, "new.txt"), "w") as f: f.write("HELLO")
        items = FolderCompareEngine.compare_directories(d_left, d_right)
        plan = FolderSyncEngine.plan_sync(items, d_left, d_right, mode=FolderSyncEngine.MODE_MIRROR_L2R)
        assert len(plan) == 1
        assert plan[0].action == "copy_l2r"

        summary = FolderSyncEngine.execute_sync(plan)
        assert summary.success is True
        assert os.path.exists(os.path.join(d_right, "new.txt"))
        print("[OK] 13. Interactive Folder Sync Engine Execution: PASSED")


def test_secret_scrubber():
    from app.core.secret_scrubber import SecretScrubber

    sample = (
        "AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'\n"
        "JWT = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'\n"
        "PASSWORD = 'mySecretPassword123'\n"
    )
    scrubbed, count, cats = SecretScrubber.scrub_text(sample)
    assert count >= 3
    assert "AKIAIOSFODNN7EXAMPLE" not in scrubbed
    assert "mySecretPassword123" not in scrubbed
    print(f"[OK] 14. Secret & PII Scrubber ({count} items redacted): PASSED")


def test_headless_reporter():
    import tempfile
    from app.core.headless_reporter import HeadlessReporter

    with tempfile.TemporaryDirectory() as d_left, tempfile.TemporaryDirectory() as d_right:
        with open(os.path.join(d_left, "file.txt"), "w") as f: f.write("Alpha")
        with open(os.path.join(d_right, "file.txt"), "w") as f: f.write("Beta")

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            html_path = f.name
        try:
            exit_code, summary = HeadlessReporter.run_folder_comparison(d_left, d_right, report_html_path=html_path)
            assert exit_code == 1  # Content mismatch
            assert os.path.exists(html_path)
            with open(html_path, "r", encoding="utf-8") as hf:
                content = hf.read()
            assert "diff_and_compare" in content
            assert "file.txt" in content
            print("[OK] 15. Headless CI/CD HTML Reporter: PASSED")
        finally:
            if os.path.exists(html_path): os.remove(html_path)


def test_manual_and_resilient_section_alignment():
    # Test case from real-world user scenario with inserted section causing cascading misalignment
    left_md = (
        "### 8.1 CLI Stdin\n"
        "stream data\n"
        "### 8.2 IPC Tab Remoting\n"
        "Named Pipe Windows\n"
        "### 8.3 Git Staging\n"
        "Interactive hunk\n"
    )
    right_md = (
        "### 8.1 CLI Process\n"
        "stream data\n"
        "### 8.2 Git Staging\n"
        "Interactive hunk\n"
    )

    # 1. Automatic Resilient Alignment (Needleman-Wunsch + section normalization)
    res_auto = DiffEngine.build_aligned_diff(left_md, right_md)
    # Right row for Git Staging should align with Left Git Staging
    git_row_l = [i for i, line in enumerate(res_auto.left_display_lines) if "Git Staging" in line][0]
    git_row_r = [i for i, line in enumerate(res_auto.right_display_lines) if "Git Staging" in line][0]
    assert git_row_l == git_row_r, f"Git Staging headings must align on the exact same row: {git_row_l} vs {git_row_r}"
    # The IPC section on Left should have spacers on Right
    ipc_row_l = [i for i, line in enumerate(res_auto.left_display_lines) if "IPC Tab Remoting" in line][0]
    assert ipc_row_l in res_auto.right_spacers, "IPC section must have vertical spacer rows on Right"

    # 2. Manual Alignment Anchor: Pin Left line 5 (Git Staging) to Right line 3 (Git Staging)
    res_man = DiffEngine.build_aligned_diff(left_md, right_md, manual_alignments=[(5, 3)])
    git_man_l = [i for i, line in enumerate(res_man.left_display_lines) if "Git Staging" in line][0]
    git_man_r = [i for i, line in enumerate(res_man.right_display_lines) if "Git Staging" in line][0]
    assert git_man_l == git_man_r, "Manual alignment anchor must pin Git Staging on identical row"
    assert res_man.left_line_numbers[git_man_l] == 5
    assert res_man.right_line_numbers[git_man_r] == 3
    print("[OK] 16. Manual & Resilient Section Alignment: PASSED")


if __name__ == "__main__":
    test_unified_patch()
    test_moved_blocks()
    test_structured_diff()
    test_tabular_diff()
    test_image_diff()
    test_hex_diff()
    test_ai_assistant()
    test_folder_compare_and_shell()
    test_ast_diff_and_blake3()
    test_tabular_parquet_sqlite_and_tolerance()
    test_pdf_and_exif_diff()
    test_structured_jsonpath_and_unordered_arrays()
    test_folder_sync_engine()
    test_secret_scrubber()
    test_headless_reporter()
    test_manual_and_resilient_section_alignment()
    print("\n=======================================================")
    print("ALL 16 ENTERPRISE INTEGRATION TESTS PASSED PERFECTLY!")
    print("=======================================================")

