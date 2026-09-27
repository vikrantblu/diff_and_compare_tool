"""
Unit Tests for Folder Compare Engine & Shell Integration
"""

import os
import sys
import tempfile
import unittest

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.folder_compare_engine import FolderCompareEngine
from app.core.shell_integration import (
    set_left_path, get_left_path, clear_state,
    is_context_menu_installed, install_context_menu
)


class TestFolderAndShell(unittest.TestCase):

    def test_folder_compare_engine(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            # Create identical file
            with open(os.path.join(d1, "same.txt"), "w") as f:
                f.write("Identical content")
            with open(os.path.join(d2, "same.txt"), "w") as f:
                f.write("Identical content")

            # Create differing file
            with open(os.path.join(d1, "diff.txt"), "w") as f:
                f.write("Left version of content")
            with open(os.path.join(d2, "diff.txt"), "w") as f:
                f.write("Right version of modified content")

            # Create left orphan
            with open(os.path.join(d1, "left_only.txt"), "w") as f:
                f.write("Only in d1")

            # Create right orphan
            with open(os.path.join(d2, "right_only.txt"), "w") as f:
                f.write("Only in d2")

            items = FolderCompareEngine.compare_directories(d1, d2, mode="hash")
            self.assertEqual(len(items), 4)

            item_map = {it.name: it for it in items}
            self.assertIn("same.txt", item_map)
            self.assertEqual(item_map["same.txt"].status, "SAME")

            self.assertIn("diff.txt", item_map)
            self.assertEqual(item_map["diff.txt"].status, "DIFF")

            self.assertIn("left_only.txt", item_map)
            self.assertEqual(item_map["left_only.txt"].status, "LEFT_ONLY")

            self.assertIn("right_only.txt", item_map)
            self.assertEqual(item_map["right_only.txt"].status, "RIGHT_ONLY")

    def test_folder_orphan_status_and_sorting(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            # Create subfolder in d1 only with a file inside
            os.makedirs(os.path.join(d1, "orphan_folder", "sub"), exist_ok=True)
            with open(os.path.join(d1, "orphan_folder", "sub", "file1.txt"), "w") as f:
                f.write("hello")
            # Create file in d1 root
            with open(os.path.join(d1, "root_file.txt"), "w") as f:
                f.write("root")

            # Create subfolder in d2 only
            os.makedirs(os.path.join(d2, "right_folder"), exist_ok=True)
            with open(os.path.join(d2, "right_folder", "file2.txt"), "w") as f:
                f.write("right")

            items = FolderCompareEngine.compare_directories(d1, d2, mode="timestamp")
            item_map = {it.name: it for it in items}

            # orphan_folder must NOT be corrupted to DIFF; must be LEFT_ONLY
            self.assertEqual(item_map["orphan_folder"].status, "LEFT_ONLY")
            self.assertEqual(item_map["right_folder"].status, "RIGHT_ONLY")

            # Folders must sort before files
            is_dirs = [it.is_dir for it in items]
            # All directories should precede non-directories
            first_file_idx = next((i for i, d in enumerate(is_dirs) if not d), len(is_dirs))
            for i in range(first_file_idx, len(is_dirs)):
                self.assertFalse(is_dirs[i], "Files must not precede folders in sorted tree")

    def test_subfolder_matcher(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            # d1 contains subfolder 'my_module'
            os.makedirs(os.path.join(d1, "my_module"), exist_ok=True)
            with open(os.path.join(d1, "my_module", "app.py"), "w") as f:
                f.write("print(1)")

            # d2 is named 'my_module_backup'
            sub_d2 = os.path.join(d2, "my_module_backup")
            os.makedirs(sub_d2, exist_ok=True)

            match = FolderCompareEngine.find_subfolder_match(d1, sub_d2)
            self.assertIsNotNone(match)
            self.assertEqual(match[0], "left")
            self.assertEqual(match[2], "my_module")

    def test_shell_integration_cache(self):
        test_path = os.path.abspath(__file__)
        set_left_path(test_path)
        self.assertEqual(get_left_path(), test_path)
        clear_state()
        self.assertIsNone(get_left_path())

    @unittest.skipUnless(sys.platform == "win32", "Windows registry tests require Windows OS")
    def test_shell_context_menu_installed(self):
        ok, msg = install_context_menu()
        self.assertTrue(ok)
        self.assertTrue(is_context_menu_installed())

    @unittest.skipUnless(sys.platform == "win32", "Windows registry tests require Windows OS")
    def test_reg_file_generation(self):
        from app.core.shell_integration import generate_reg_content, export_reg_file
        content = generate_reg_content(target_exe=sys.executable)
        self.assertIn("Windows Registry Editor Version 5.00", content)
        self.assertIn("DiffAndCompareToolCompare", content)
        self.assertIn("App Paths", content)
        self.assertIn("Uninstall", content)

        with tempfile.TemporaryDirectory() as td:
            reg_path = os.path.join(td, "test.reg")
            ok, msg = export_reg_file(reg_path, target_exe=sys.executable)
            self.assertTrue(ok)
            self.assertTrue(os.path.isfile(reg_path))

    @unittest.skipUnless(sys.platform == "win32", "Windows registry tests require Windows OS")
    def test_app_paths_and_uninstall_registration(self):
        from app.core.shell_integration import (
            install_app_paths, uninstall_app_paths,
            install_uninstall_entry, uninstall_uninstall_entry
        )
        ok, msg = install_app_paths(target_exe=sys.executable)
        self.assertTrue(ok)
        ok, msg = uninstall_app_paths()
        self.assertTrue(ok)

        ok, msg = install_uninstall_entry(target_exe=sys.executable)
        self.assertTrue(ok)
        ok, msg = uninstall_uninstall_entry()
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()

