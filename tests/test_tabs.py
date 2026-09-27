"""
Unit Tests for Tab Lifecycle and Session Opening
Ensures comparison studios open correctly from Home cards, can be closed,
and can be reopened without failing.
"""

import os
import sys
import unittest
from PySide6.QtWidgets import QApplication, QTabBar

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ui.main_window import MainWindow
from app.ui.image_diff_view import ImageDiffView
from app.ui.diff_view import DiffView
from app.ui.dir_compare_view import DirCompareView
from app.ui.tabular_diff_view import TabularDiffView
from app.ui.structured_diff_view import StructuredDiffView
from app.ui.hex_diff_view import HexDiffView
from app.ui.merge_view import MergeView


class TestTabLifecycle(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Disable modal crash recovery dialog during automated testing
        self._orig_recovery = MainWindow._check_crash_recovery
        MainWindow._check_crash_recovery = lambda self: None
        self.win = MainWindow()

    def tearDown(self):
        MainWindow._check_crash_recovery = self._orig_recovery

    def test_startup_has_only_home_tab(self):
        """At startup, only the Home dashboard tab should be open."""
        self.assertEqual(self.win.tabs.count(), 1)
        self.assertEqual(self.win.tabs.widget(0), self.win.home_tab)
        # Home tab should not have a close button
        btn = self.win.tabs.tabBar().tabButton(0, QTabBar.ButtonPosition.RightSide)
        self.assertIsNone(btn)

    def test_home_tab_cannot_be_closed(self):
        """Attempting to close the Home tab should be a no-op."""
        self.win._on_tab_close(0)
        self.assertEqual(self.win.tabs.count(), 1)
        self.assertEqual(self.win.tabs.widget(0), self.win.home_tab)

    def test_open_and_reopen_image_diff(self):
        """Image diff opens from Home card, can be closed, and can be reopened."""
        # Click Image Diff Studio on Home
        self.win._on_home_session_selected("image")
        self.assertEqual(self.win.tabs.count(), 2)
        self.assertIsInstance(self.win.tabs.currentWidget(), ImageDiffView)
        self.assertIn("Image Diff", self.win.tabs.tabText(self.win.tabs.currentIndex()))

        # Close the Image Diff tab
        self.win._on_tab_close(1)
        self.assertEqual(self.win.tabs.count(), 1)
        self.assertEqual(self.win.tabs.widget(0), self.win.home_tab)

        # Reopen Image Diff from Home card — must open!
        self.win._on_home_session_selected("image")
        self.assertEqual(self.win.tabs.count(), 2)
        self.assertIsInstance(self.win.tabs.currentWidget(), ImageDiffView)

    def test_all_session_modes_open_from_home(self):
        """Every session mode must open a functional tab when triggered from Home."""
        modes = [
            ("folder", DirCompareView),
            ("folder_merge", DirCompareView),
            ("folder_sync", DirCompareView),
            ("text", DiffView),
            ("merge", MergeView),
            ("table", TabularDiffView),
            ("structured", StructuredDiffView),
            ("hex", HexDiffView),
            ("image", ImageDiffView),
        ]
        for mode_id, expected_class in modes:
            with self.subTest(mode=mode_id):
                self.win.show_home_tab()
                self.win._on_home_session_selected(mode_id)
                self.assertEqual(self.win.tabs.count(), 2)
                self.assertIsInstance(self.win.tabs.currentWidget(), expected_class)
                # Close it again
                self.win._on_tab_close(1)
                self.assertEqual(self.win.tabs.count(), 1)

    def test_smart_open_comparison_opens_tabs(self):
        """smart_open_comparison correctly routes to new tabs."""
        # Image
        self.win.smart_open_comparison("photo1.png", "photo2.png")
        self.assertEqual(self.win.tabs.count(), 2)
        self.assertIsInstance(self.win.tabs.currentWidget(), ImageDiffView)

        # Text
        self.win.smart_open_comparison("code1.py", "code2.py")
        self.assertEqual(self.win.tabs.count(), 3)
        self.assertIsInstance(self.win.tabs.currentWidget(), DiffView)

        # Table
        self.win.smart_open_comparison("data1.csv", "data2.csv")
        self.assertEqual(self.win.tabs.count(), 4)
        self.assertIsInstance(self.win.tabs.currentWidget(), TabularDiffView)

    def test_dynamic_properties_never_stale(self):
        """Accessing properties like win.image_tab always returns an attached tab."""
        # No image tab open yet
        self.assertEqual(self.win.tabs.count(), 1)
        img_tab = self.win.image_tab
        self.assertIsNotNone(img_tab)
        self.assertEqual(self.win.tabs.count(), 2)
        self.assertIn(img_tab, [self.win.tabs.widget(i) for i in range(self.win.tabs.count())])


if __name__ == "__main__":
    unittest.main()
