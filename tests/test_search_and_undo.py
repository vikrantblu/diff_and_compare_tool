import unittest
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

app = QApplication.instance() or QApplication(sys.argv)

from app.ui.dir_compare_view import DirCompareView
from app.ui.diff_view import DiffView
from app.core.diff_engine import DiffEngine


class TestSearchAndUndo(unittest.TestCase):

    def setUp(self):
        self.dir_view = DirCompareView()
        self.diff_view = DiffView()
        self.dir_view.show()
        self.diff_view.show()

    def tearDown(self):
        self.dir_view.close()
        self.diff_view.close()

    def test_explorer_search_box_exists_and_filters(self):
        # 1. Search box in path bar exists
        self.assertTrue(hasattr(self.dir_view, "txt_explorer_search"))
        self.assertEqual(self.dir_view.txt_explorer_search.placeholderText(), "🔍 Search files & folders... (Ctrl+F)")

        # 2. Typing into search box triggers filtering
        self.dir_view.txt_explorer_search.setText("sample")
        self.assertEqual(self.dir_view.txt_explorer_search.text(), "sample")

        # Clear search
        self.dir_view._clear_search()
        self.assertEqual(self.dir_view.txt_explorer_search.text(), "")

    def test_diff_view_undo_redo_on_chunk_transfer(self):
        # Initial state has no undo
        self.assertFalse(self.diff_view.btn_undo.isEnabled())
        self.assertFalse(self.diff_view.btn_redo.isEnabled())

        initial_right = self.diff_view._raw_right

        # Find first non-equal chunk (chunk 1 is 'insert' - logging)
        diff_chunk_idx = next(i for i, c in enumerate(self.diff_view.chunks) if c.tag != 'equal')

        # Perform chunk transfer
        self.diff_view.transfer_left_to_right(diff_chunk_idx)
        self.assertTrue(self.diff_view.btn_undo.isEnabled())
        self.assertNotEqual(self.diff_view._raw_right, initial_right)

        # Trigger Undo
        self.diff_view.undo()
        self.assertEqual(self.diff_view._raw_right, initial_right)
        self.assertTrue(self.diff_view.btn_redo.isEnabled())

        # Trigger Redo
        self.diff_view.redo()
        self.assertNotEqual(self.diff_view._raw_right, initial_right)
        self.assertTrue(self.diff_view.btn_undo.isEnabled())

    def test_diff_view_find_bar(self):
        # 1. Find button and Find bar exist
        self.assertTrue(hasattr(self.diff_view, "btn_find"))
        self.assertTrue(hasattr(self.diff_view, "find_bar"))
        self.assertTrue(self.diff_view.find_bar.isHidden())

        # 2. Open Find Bar
        self.diff_view.open_find_bar()
        self.assertFalse(self.diff_view.find_bar.isHidden())

        # 3. Search query
        self.diff_view.txt_find.setText("calculate_tax")
        self.assertGreater(len(self.diff_view._find_matches), 0)
        self.assertIn("1 of", self.diff_view.lbl_find_status.text())

        # 4. Next and Prev
        prev_idx = self.diff_view._current_find_match_idx
        self.diff_view.find_next()
        self.assertNotEqual(self.diff_view._current_find_match_idx, prev_idx)
        self.diff_view.find_prev()
        self.assertEqual(self.diff_view._current_find_match_idx, prev_idx)

        # 5. Close Find Bar
        self.diff_view.close_find_bar()
        self.assertTrue(self.diff_view.find_bar.isHidden())
        self.assertEqual(len(self.diff_view._find_matches), 0)


if __name__ == "__main__":
    unittest.main()
