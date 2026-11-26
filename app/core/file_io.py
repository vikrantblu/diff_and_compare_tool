"""
File I/O, Encoding, Line-Ending Detection, and Virtual Archive Path Utilities.
Supports local filesystem files and ArchiveVFS virtual paths (e.g. `bundle.zip#src/main.py`).
"""

import os
from typing import Tuple
from app.core.archive_vfs import ArchiveVFS


def is_vfs_path(path: str) -> bool:
    """Returns True if path points to an entry inside a supported archive (`archive.zip#inner/file`)."""
    if not path or "#" not in path:
        return False
    archive_part, inner = path.split("#", 1)
    return bool(inner) and ArchiveVFS.is_archive(archive_part)


def split_vfs_path(path: str) -> Tuple[str, str]:
    """Splits a VFS path `archive.zip#inner/path` into `(archive_path, inner_entry_path)`."""
    if "#" not in path:
        return path, ""
    archive_part, inner = path.split("#", 1)
    return archive_part, inner.replace("\\", "/").lstrip("/")


def read_vfs_or_file_bytes(path: str) -> bytes:
    """Reads raw bytes from either a local file or an ArchiveVFS virtual entry."""
    if is_vfs_path(path):
        archive_part, inner = split_vfs_path(path)
        data = ArchiveVFS.read_entry_bytes(archive_part, inner)
        if data is None:
            raise FileNotFoundError(f"Archive entry not found: {path}")
        return data
    with open(path, "rb") as f:
        return f.read()


def detect_encoding(raw_bytes: bytes) -> str:
    """Detects text encoding from BOM or valid UTF-8 decoding, falling back to CP1252."""
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw_bytes.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if raw_bytes.startswith(b"\xfe\xff"):
        return "utf-16-be"
    try:
        raw_bytes.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"


def format_encoding_label(encoding: str) -> str:
    """Returns human-readable encoding label for UI headers."""
    mapping = {
        "utf-8": "UTF-8",
        "utf-8-sig": "UTF-8 BOM",
        "utf-16-le": "UTF-16 LE",
        "utf-16-be": "UTF-16 BE",
        "cp1252": "Windows-1252",
    }
    return mapping.get(encoding.lower(), encoding.upper())


def detect_eol(text: str) -> str:
    """Detects dominant line endings in decoded text: CRLF, LF, CR, or Mixed."""
    crlf_count = text.count("\r\n")
    stripped = text.replace("\r\n", "")
    lf_count = stripped.count("\n")
    cr_count = stripped.count("\r")

    kinds = sum(1 for c in (crlf_count, lf_count, cr_count) if c > 0)
    if kinds > 1:
        return "Mixed"
    if crlf_count > 0:
        return "CRLF"
    if cr_count > 0:
        return "CR"
    return "LF"


def read_text_file(path: str) -> Tuple[str, str, str]:
    """
    Reads a local or VFS text file and returns `(decoded_text, encoding_label, eol_label)`.
    Preserves UTF-8 BOM / UTF-16 / CP1252 detection for faithful saving.
    """
    raw_bytes = read_vfs_or_file_bytes(path)
    enc = detect_encoding(raw_bytes)
    if enc == "utf-16-le":
        text = raw_bytes[2:].decode("utf-16-le", errors="replace")
    elif enc == "utf-16-be":
        text = raw_bytes[2:].decode("utf-16-be", errors="replace")
    else:
        text = raw_bytes.decode(enc, errors="replace")
    eol = detect_eol(text)
    return text, format_encoding_label(enc), eol


def write_text_file(path: str, text: str, encoding_label: str = "UTF-8", eol_label: str = "LF") -> None:
    """Writes text back to disk using the specified encoding and line-ending style."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if eol_label == "CRLF":
        normalized = normalized.replace("\n", "\r\n")
    elif eol_label == "CR":
        normalized = normalized.replace("\n", "\r")

    enc_map = {
        "UTF-8": "utf-8",
        "UTF-8 BOM": "utf-8-sig",
        "UTF-16 LE": "utf-16-le",
        "UTF-16 BE": "utf-16-be",
        "WINDOWS-1252": "cp1252",
    }
    codec = enc_map.get(encoding_label.upper(), "utf-8")

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if codec == "utf-16-le":
        data = b"\xff\xfe" + normalized.encode("utf-16-le", errors="replace")
    elif codec == "utf-16-be":
        data = b"\xfe\xff" + normalized.encode("utf-16-be", errors="replace")
    else:
        data = normalized.encode(codec, errors="replace")

    with open(path, "wb") as f:
        f.write(data)
