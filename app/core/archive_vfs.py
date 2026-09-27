"""
Virtual Archive Filesystem (VFS)
Enables transparent browsing, indexing, and comparison of compressed archives
(.zip, .jar, .tar, .tar.gz, .tgz, .tar.bz2) as standard directory structures
without requiring manual disk decompression.
"""

import os
import zipfile
import tarfile
import io
import time
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple


@dataclass
class ArchiveEntry:
    path: str           # Relative path inside archive, e.g. "src/main.py"
    is_dir: bool
    size: int
    compressed_size: int
    mtime: float
    crc: Optional[str] = None


class ArchiveVFS:
    """Virtual Filesystem handler for compressed archives."""

    SUPPORTED_EXTENSIONS = {".zip", ".jar", ".tar", ".gz", ".tgz", ".bz2", ".tbz2"}

    @classmethod
    def is_archive(cls, path: str) -> bool:
        if not path or not os.path.isfile(path):
            return False
        ext = os.path.splitext(path)[1].lower()
        if ext in cls.SUPPORTED_EXTENSIONS:
            return True
        if path.lower().endswith(".tar.gz") or path.lower().endswith(".tar.bz2"):
            return True
        return False

    @classmethod
    def list_entries(cls, archive_path: str) -> List[ArchiveEntry]:
        """Lists all files and directories inside an archive."""
        if not os.path.exists(archive_path):
            return []

        entries: List[ArchiveEntry] = []

        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path, "r") as z:
                for info in z.infolist():
                    mtime_tuple = info.date_time
                    try:
                        mtime = time.mktime(mtime_tuple + (0, 0, -1))
                    except Exception:
                        mtime = 0.0
                    entries.append(ArchiveEntry(
                        path=info.filename.rstrip("/"),
                        is_dir=info.is_dir(),
                        size=info.file_size,
                        compressed_size=info.compress_size,
                        mtime=mtime,
                        crc=f"{info.CRC:08x}" if info.CRC else None
                    ))
            return entries

        if tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path, "r:*") as t:
                for member in t.getmembers():
                    entries.append(ArchiveEntry(
                        path=member.name.rstrip("/"),
                        is_dir=member.isdir(),
                        size=member.size,
                        compressed_size=member.size,
                        mtime=float(member.mtime),
                        crc=None
                    ))
            return entries

        return []

    @classmethod
    def read_entry_bytes(cls, archive_path: str, entry_path: str) -> Optional[bytes]:
        """Extracts a single file entry into memory as bytes."""
        if not os.path.exists(archive_path):
            return None

        # Normalize relative path
        norm_path = entry_path.replace("\\", "/").lstrip("/")

        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path, "r") as z:
                for name in [norm_path, norm_path + "/"]:
                    if name in z.namelist():
                        return z.read(name)
            return None

        if tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path, "r:*") as t:
                member = t.getmember(norm_path)
                f = t.extractfile(member)
                if f:
                    return f.read()
            return None

        return None

    @classmethod
    def read_entry_text(cls, archive_path: str, entry_path: str, encoding: str = "utf-8") -> Optional[str]:
        """Extracts a single text file entry into memory as a decoded string."""
        raw_bytes = cls.read_entry_bytes(archive_path, entry_path)
        if raw_bytes is None:
            return None
        return raw_bytes.decode(encoding, errors="replace")
