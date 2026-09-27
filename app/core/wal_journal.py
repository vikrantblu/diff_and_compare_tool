"""
Write-Ahead Log (WAL) Crash Recovery Journal
Ensures zero data loss for in-place text and code editing:
- Append-only journal logging every buffer mutation to disk
- On unexpected shutdown/crash/power failure, detects uncommitted buffers
- Provides instant snapshot reconstruction for prompt recovery
- Automatically truncates and removes journal on clean application exit
"""

import os
import sys
import time
import json
import glob
from typing import Optional, List, Dict, Any


class WALJournal:
    """Manages append-only write-ahead log journaling for active editor buffers."""

    def __init__(self, session_id: Optional[str] = None):
        self.storage_dir = self.get_wal_dir()
        self.session_id = session_id or f"session_{int(time.time())}_{os.getpid()}"
        self.wal_path = os.path.join(self.storage_dir, f"{self.session_id}.wal")
        self._file_handle = None
        self._init_journal()

    @classmethod
    def get_wal_dir(cls) -> str:
        app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
        wal_dir = os.path.join(app_data, "diff_and_compare", "wal")
        os.makedirs(wal_dir, exist_ok=True)
        return wal_dir

    def _init_journal(self):
        try:
            self._file_handle = open(self.wal_path, "a", encoding="utf-8")
            start_record = {
                "type": "SESSION_START",
                "session_id": self.session_id,
                "time": time.time(),
                "pid": os.getpid()
            }
            self._write_record(start_record)
        except Exception:
            self._file_handle = None

    def _write_record(self, record: Dict[str, Any]):
        if self._file_handle and not self._file_handle.closed:
            try:
                line = json.dumps(record, ensure_ascii=False) + "\n"
                self._file_handle.write(line)
                self._file_handle.flush()
                # On Windows, os.fsync ensures physical persistence to disk
                os.fsync(self._file_handle.fileno())
            except Exception:
                pass

    def checkpoint(self, pane: str, file_path: str, content: str, is_dirty: bool = True):
        """Logs an active buffer mutation checkpoint to the WAL journal."""
        record = {
            "type": "CHECKPOINT",
            "pane": pane,
            "file_path": file_path or "untitled",
            "content": content,
            "is_dirty": is_dirty,
            "time": time.time()
        }
        self._write_record(record)

    def commit_save(self, pane: str, file_path: str):
        """Logs that a buffer has been committed/saved to disk."""
        record = {
            "type": "SAVED",
            "pane": pane,
            "file_path": file_path or "untitled",
            "time": time.time()
        }
        self._write_record(record)

    def clean_exit(self):
        """Marks the session as cleanly terminated and prunes the WAL file."""
        if self._file_handle and not self._file_handle.closed:
            try:
                self._write_record({"type": "CLEAN_EXIT", "time": time.time()})
                self._file_handle.close()
            except Exception:
                pass
            self._file_handle = None

        # Cleanly remove the journal file upon graceful shutdown
        try:
            if os.path.exists(self.wal_path):
                os.remove(self.wal_path)
        except Exception:
            pass

    @classmethod
    def get_unrecovered_sessions(cls) -> List[Dict[str, Any]]:
        """
        Scans for unclosed WAL journals from prior crashes or abnormal terminations.
        Returns a list of uncommitted buffer snapshots ready for user recovery.
        """
        wal_dir = cls.get_wal_dir()
        wal_files = glob.glob(os.path.join(wal_dir, "*.wal"))
        candidates: List[Dict[str, Any]] = []

        current_pid = os.getpid()

        for wal_file in wal_files:
            # Skip journals belonging to the currently running process
            if f"_{current_pid}.wal" in wal_file:
                continue

            try:
                with open(wal_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception:
                continue

            if not lines:
                continue

            # Check if session ended with CLEAN_EXIT
            has_clean_exit = False
            buffers_state: Dict[str, Dict[str, Any]] = {}

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue

                rtype = rec.get("type")
                if rtype == "CLEAN_EXIT":
                    has_clean_exit = True
                    break
                elif rtype == "CHECKPOINT":
                    pane = rec.get("pane", "main")
                    buffers_state[pane] = rec
                elif rtype == "SAVED":
                    pane = rec.get("pane", "main")
                    if pane in buffers_state:
                        buffers_state[pane]["is_dirty"] = False

            if not has_clean_exit:
                # Find all dirty buffers in this aborted session
                for pane, info in buffers_state.items():
                    if info.get("is_dirty", False) and info.get("content"):
                        candidates.append({
                            "wal_file": wal_file,
                            "session_id": info.get("session_id", os.path.basename(wal_file)),
                            "pane": pane,
                            "file_path": info.get("file_path", "untitled"),
                            "content": info.get("content", ""),
                            "time": info.get("time", 0)
                        })

        return candidates

    @classmethod
    def discard_wal(cls, wal_file: str):
        """Deletes a specific WAL journal file."""
        try:
            if os.path.exists(wal_file):
                os.remove(wal_file)
        except Exception:
            pass

    @classmethod
    def discard_all_unrecovered(cls):
        """Prunes all unclosed WAL journals."""
        wal_dir = cls.get_wal_dir()
        for f in glob.glob(os.path.join(wal_dir, "*.wal")):
            try:
                os.remove(f)
            except Exception:
                pass
