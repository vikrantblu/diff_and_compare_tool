"""
Unit and integration tests for WALJournal crash recovery.
"""

import unittest
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.wal_journal import WALJournal


class TestWALJournal(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.original_get_wal_dir = WALJournal.get_wal_dir
        WALJournal.get_wal_dir = classmethod(lambda cls: self.tmp_dir)

    def tearDown(self):
        WALJournal.get_wal_dir = self.original_get_wal_dir
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_clean_exit_removes_wal(self):
        wal = WALJournal(session_id="test_session_clean")
        wal.checkpoint("left", "doc.txt", "Hello World", is_dirty=True)
        self.assertTrue(os.path.exists(wal.wal_path))
        wal.clean_exit()
        self.assertFalse(os.path.exists(wal.wal_path))

    def test_crash_recovery_detects_dirty_buffer(self):
        # Simulate abnormal termination (no clean_exit)
        # Use fake pid in session_id so get_unrecovered_sessions doesn't skip it
        wal = WALJournal(session_id="crash_session_999999")
        wal.checkpoint("left", "important_file.py", "def critical(): return True", is_dirty=True)
        # Close file handle without writing clean exit
        wal._file_handle.close()

        unrecovered = WALJournal.get_unrecovered_sessions()
        self.assertEqual(len(unrecovered), 1)
        self.assertEqual(unrecovered[0]["pane"], "left")
        self.assertEqual(unrecovered[0]["file_path"], "important_file.py")
        self.assertEqual(unrecovered[0]["content"], "def critical(): return True")

    def test_saved_buffer_is_not_recovered_as_dirty(self):
        wal = WALJournal(session_id="saved_session_999998")
        wal.checkpoint("right", "saved_file.py", "saved text", is_dirty=True)
        wal.commit_save("right", "saved_file.py")
        wal._file_handle.close()

        unrecovered = WALJournal.get_unrecovered_sessions()
        self.assertEqual(len(unrecovered), 0)


if __name__ == "__main__":
    unittest.main()
