"""
Tests for True 3-Way Folder Merge Studio, Remote Filesystem Profiles (SFTP/S3/FTP),
and GitHub Pages Deployment Configuration.
"""

import gc
import os
import shutil
import sys
import tempfile
import unittest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.file_io import read_text_file
from app.core.folder_compare_engine import FolderCompareEngine
from app.core.folder_merge_engine import FolderMergeEngine
from app.core.remote_vfs import BaseRemoteAdapter, RemoteEntry, RemoteVFS
from app.core.session_manager import SessionManager
from app.ui.dialogs.remote_profile_dialog import RemoteProfileDialog
from app.ui.folder_merge_view import FolderMergeView
from app.ui.main_window import MainWindow


class _MockRemoteAdapter(BaseRemoteAdapter):
    """In-memory remote adapter simulating SFTP/S3 buckets & directories for unit tests."""

    def __init__(self, files_by_profile):
        self.files_by_profile = files_by_profile

    def list_entries(self, profile, sub_path, secret=None):
        pname = profile["name"]
        prefix = sub_path.strip("/")
        entries = []
        for rel_p, data in self.files_by_profile.get(pname, {}).items():
            if prefix and not (rel_p == prefix or rel_p.startswith(prefix + "/")):
                continue
            trimmed = rel_p[len(prefix) + 1:] if (prefix and rel_p.startswith(prefix + "/")) else rel_p
            entries.append(RemoteEntry(path=trimmed, is_dir=False, size=len(data), mtime=1000.0))
        return entries

    def read_file_bytes(self, profile, sub_path, secret=None):
        pname = profile["name"]
        norm = sub_path.strip("/")
        data = self.files_by_profile.get(pname, {}).get(norm)
        if data is None:
            raise FileNotFoundError(norm)
        return data

    def write_file_bytes(self, profile, sub_path, data, secret=None):
        pname = profile["name"]
        self.files_by_profile.setdefault(pname, {})[sub_path.strip("/")] = data

    def test_connection(self, profile, secret=None):
        return True, f"Mock OK ({profile.get('name')})"


class TestFolderMergeAndRemote(unittest.TestCase):

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
        RemoteVFS.reset_default_adapters()
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

    def test_3way_folder_merge_all_classifications_and_execution(self):
        with tempfile.TemporaryDirectory() as td:
            d_base = os.path.join(td, "base")
            d_left = os.path.join(td, "mine")
            d_right = os.path.join(td, "theirs")
            d_out = os.path.join(td, "merged")

            def put(root, rel, text):
                p = os.path.join(root, rel.replace("/", os.sep))
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    f.write(text)

            # 1. Identical across all 3
            for r in (d_base, d_left, d_right):
                put(r, "same.txt", "unchanged")
            # 2. Modified only on Left (Mine)
            put(d_base, "src/l_mod.py", "v0")
            put(d_left, "src/l_mod.py", "v_mine")
            put(d_right, "src/l_mod.py", "v0")
            # 3. Modified only on Right (Theirs)
            put(d_base, "src/r_mod.py", "v0")
            put(d_left, "src/r_mod.py", "v0")
            put(d_right, "src/r_mod.py", "v_theirs")
            # 4. Left & Right both added differently -> CONFLICT
            put(d_left, "conflict.txt", "mine_val")
            put(d_right, "conflict.txt", "theirs_val")
            # 5. Converged identical edit
            put(d_base, "conv.txt", "old")
            put(d_left, "conv.txt", "new_same")
            put(d_right, "conv.txt", "new_same")
            # 6. Deleted in Theirs only (Left unchanged -> auto delete)
            put(d_base, "obsolete.txt", "bye")
            put(d_left, "obsolete.txt", "bye")
            put(d_out, "obsolete.txt", "stale_out")

            tree = FolderMergeEngine.compare_3way_folders(d_left, d_base, d_right, mode="hash")
            files = {it.rel_path: it for it in FolderMergeEngine.flatten_files(tree)}

            self.assertEqual(files["same.txt"].status, "IDENTICAL")
            self.assertEqual(files["src/l_mod.py"].status, "LEFT_MODIFIED")
            self.assertEqual(files["src/r_mod.py"].status, "RIGHT_MODIFIED")
            self.assertEqual(files["conflict.txt"].status, "CONFLICT")
            self.assertEqual(files["conv.txt"].status, "CONVERGED")
            self.assertEqual(files["obsolete.txt"].status, "RIGHT_DELETED")

            # Resolve conflict manually to Theirs
            files["conflict.txt"].resolution = "take_right"
            summary = FolderMergeEngine.execute_merge(tree, d_out, skip_conflicts=True)
            self.assertTrue(summary.success)
            self.assertEqual(summary.deleted_count, 1)
            self.assertFalse(os.path.exists(os.path.join(d_out, "obsolete.txt")))

            with open(os.path.join(d_out, "src", "l_mod.py"), "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "v_mine")
            with open(os.path.join(d_out, "conflict.txt"), "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "theirs_val")

    def test_folder_merge_view_ui_and_signal(self):
        with tempfile.TemporaryDirectory() as td:
            b = os.path.join(td, "b")
            l = os.path.join(td, "l")
            r = os.path.join(td, "r")
            os.makedirs(b); os.makedirs(l); os.makedirs(r)
            for root, val in ((b, "0"), (l, "1"), (r, "2")):
                with open(os.path.join(root, "app.py"), "w", encoding="utf-8") as f:
                    f.write(val)

            items = FolderMergeEngine.compare_3way_folders(l, b, r)
            fmv = FolderMergeView()
            fmv.set_merge_items(items)
            self.assertIn("1 Conflicts", fmv.lbl_stats.text())

            captured = []
            fmv.open3WayFileMergeRequested.connect(lambda *a: captured.append(a))
            top = fmv.tree.topLevelItem(0)
            fmv._on_item_double_clicked(top, 0)
            self.assertEqual(len(captured), 1)

            csv_p = os.path.join(td, "merge.csv")
            FolderMergeEngine.export_csv_report(items, csv_p)
            self.assertTrue(os.path.isfile(csv_p))
            fmv.close()

    def test_remote_vfs_profiles_and_mock_sftp_s3_comparison(self):
        SessionManager.save_remote_profile("prod-sftp", {
            "protocol": "sftp",
            "host": "sftp.example.com",
            "base_path": "repo",
            "username": "deploy",
            "password": "SHOULD_NOT_BE_SAVED",
        })
        saved = SessionManager.get_remote_profiles()
        self.assertIn("prod-sftp", saved)
        self.assertNotIn("password", saved["prod-sftp"])

        SessionManager.save_remote_profile("staging-s3", {
            "protocol": "s3",
            "bucket": "my-bucket",
            "base_path": "repo",
        })

        mock = _MockRemoteAdapter({
            "prod-sftp": {"src/main.py": b"print('v1')\n", "src/extra.py": b"ok\n"},
            "staging-s3": {"src/main.py": b"print('v2')\n", "src/extra.py": b"ok\n"},
        })
        RemoteVFS.register_adapter("sftp", mock)
        RemoteVFS.register_adapter("s3", mock)

        items = FolderCompareEngine.compare_directories("sftp://prod-sftp/src", "s3://staging-s3/src", mode="hash")
        by_name = {it.name: it.status for it in items}
        self.assertEqual(by_name.get("main.py"), "DIFF")
        self.assertEqual(by_name.get("extra.py"), "SAME")

        txt, enc, _ = read_text_file("sftp://prod-sftp/src/main.py")
        self.assertIn("v1", txt)
        self.assertEqual(enc, "UTF-8")

        dlg = RemoteProfileDialog()
        dlg.txt_name.setText("qa-ftp")
        dlg.combo_proto.setCurrentText("ftp")
        dlg.txt_host.setText("ftp.example.com")
        uri = dlg.load_into_side("left")
        self.assertEqual(uri, "ftp://qa-ftp")
        dlg.close()

    def test_github_pages_workflow_exists(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        wf = os.path.join(root, ".github", "workflows", "pages.yml")
        self.assertTrue(os.path.isfile(wf))
        with open(wf, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("deploy-pages", content)
        self.assertIn('path: "docs"', content)


if __name__ == "__main__":
    unittest.main()
