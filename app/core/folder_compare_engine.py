"""
Deep Folder Comparison & Synchronization Engine
Features:
- Recursive directory scanning with Virtual Archive (ZIP/TAR) support.
- Multi-mode comparison:
  1. Size and Timestamp Match
  2. Byte-by-Byte (SHA-256 / CRC32) Hash Validation
  3. Rules-Based (ignore line endings & whitespace in text files)
- Paired synchronized tree generation.
- Pattern / wildcard filtering (e.g. "*.py", "-*.tmp", "-kb_*.*").
"""

import os
import time
import fnmatch
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from app.core.diff_engine import DiffEngine
from app.core.archive_vfs import ArchiveVFS


@dataclass
class FolderCompareItem:
    """Represents a paired item (folder or file) across left and right sides."""
    rel_path: str                       # e.g. "subfolder/code.py"
    name: str                           # e.g. "code.py"
    is_dir: bool                        # True if folder
    left_path: Optional[str] = None
    right_path: Optional[str] = None
    left_size: Optional[int] = None
    right_size: Optional[int] = None
    left_mtime: Optional[float] = None
    right_mtime: Optional[float] = None
    status: str = "SAME"                # "SAME", "DIFF", "LEFT_ONLY", "RIGHT_ONLY"
    diff_reason: str = ""
    children: List["FolderCompareItem"] = field(default_factory=list)

    @property
    def left_size_str(self) -> str:
        if self.left_size is None:
            return ""
        if self.is_dir:
            return ""
        return f"{self.left_size:,} B"

    @property
    def right_size_str(self) -> str:
        if self.right_size is None:
            return ""
        if self.is_dir:
            return ""
        return f"{self.right_size:,} B"

    @property
    def left_mtime_str(self) -> str:
        if not self.left_mtime:
            return ""
        return time.strftime("%m/%d/%Y %I:%M:%S %p", time.localtime(self.left_mtime))

    @property
    def right_mtime_str(self) -> str:
        if not self.right_mtime:
            return ""
        return time.strftime("%m/%d/%Y %I:%M:%S %p", time.localtime(self.right_mtime))


DEFAULT_EXCLUSION_GLOBS = [
    ".git", ".hg", ".svn", "__pycache__", "node_modules", ".venv", "venv",
    ".idea", ".vscode", ".DS_Store", "Thumbs.db", "*.pyc", "*.pyo"
]


class FolderCompareEngine:
    """Scans and synchronizes dual folder trees."""

    @classmethod
    def load_ignore_rules(cls, root_dir: str) -> List[Tuple[bool, str]]:
        """
        Loads rules from .gitignore, .hgignore and default exclusions.
        Returns list of (is_negation, pattern).
        """
        rules: List[Tuple[bool, str]] = []
        for def_glob in DEFAULT_EXCLUSION_GLOBS:
            rules.append((False, def_glob))

        if not root_dir or not os.path.isdir(root_dir):
            return rules

        for fname in (".gitignore", ".hgignore"):
            ignore_path = os.path.join(root_dir, fname)
            if os.path.exists(ignore_path):
                try:
                    with open(ignore_path, "r", encoding="utf-8", errors="replace") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            if line.startswith("!"):
                                rules.append((True, line[1:].strip()))
                            else:
                                rules.append((False, line))
                except Exception:
                    pass
        return rules

    @classmethod
    def is_path_ignored(cls, rel_path: str, is_dir: bool, rules: List[Tuple[bool, str]]) -> bool:
        """Determines if a relative path matches gitignore / exclusion rules."""
        norm = rel_path.replace("\\", "/").strip("/")
        parts = norm.split("/")
        ignored = False

        for is_neg, pat in rules:
            pat_clean = pat.rstrip("/")
            if fnmatch.fnmatch(norm, pat_clean) or any(fnmatch.fnmatch(part, pat_clean) for part in parts):
                ignored = not is_neg
            elif pat.endswith("/") and is_dir and any(fnmatch.fnmatch(part, pat_clean) for part in parts):
                ignored = not is_neg
        return ignored

    @staticmethod
    def compare_directories(
        left_dir: str,
        right_dir: str,
        mode: str = "hash",          # "hash", "timestamp", "rules", "blake3"
        filter_expr: str = "",       # e.g. "*.py", "-*.tmp", "-kb_*.*"
        progress_callback = None,    # Callable[[int, str], None]
        respect_gitignore: bool = True
    ) -> List[FolderCompareItem]:
        """
        Recursively scans left_dir and right_dir, producing a hierarchical
        list of FolderCompareItem trees.
        """
        left_exists = os.path.exists(left_dir) if left_dir else False
        right_exists = os.path.exists(right_dir) if right_dir else False

        if not left_exists and not right_exists:
            return []

        # Collect files from left side
        if progress_callback:
            progress_callback(0, f"Scanning left: {os.path.basename(left_dir)}...")
        left_entries = FolderCompareEngine._scan_target(left_dir, progress_callback, "Left", respect_gitignore=respect_gitignore)

        # Collect files from right side
        if progress_callback:
            progress_callback(len(left_entries), f"Scanning right: {os.path.basename(right_dir)}...")
        right_entries = FolderCompareEngine._scan_target(right_dir, progress_callback, "Right", respect_gitignore=respect_gitignore)

        # Merge all relative paths
        all_rel_paths = set(left_entries.keys()) | set(right_entries.keys())

        # Apply name filters
        filtered_paths = FolderCompareEngine._apply_filters(all_rel_paths, filter_expr)

        total_to_compare = len(filtered_paths)
        if progress_callback:
            progress_callback(0, f"Comparing {total_to_compare:,} files and folders...")

        # Build flat items with comparison
        flat_items: Dict[str, FolderCompareItem] = {}
        processed_count = 0

        for rel_p in filtered_paths:
            processed_count += 1
            if progress_callback and (processed_count % 300 == 0 or processed_count == total_to_compare):
                progress_callback(processed_count, f"Comparing items ({processed_count:,}/{total_to_compare:,})...")

            l_info = left_entries.get(rel_p)
            r_info = right_entries.get(rel_p)

            is_dir = (l_info["is_dir"] if l_info else False) or (r_info["is_dir"] if r_info else False)
            name = os.path.basename(rel_p)

            item = FolderCompareItem(
                rel_path=rel_p,
                name=name,
                is_dir=is_dir,
                left_path=l_info["full_path"] if l_info else None,
                right_path=r_info["full_path"] if r_info else None,
                left_size=l_info["size"] if l_info else None,
                right_size=r_info["size"] if r_info else None,
                left_mtime=l_info["mtime"] if l_info else None,
                right_mtime=r_info["mtime"] if r_info else None
            )

            # Evaluate status
            if l_info and not r_info:
                item.status = "LEFT_ONLY"
                item.diff_reason = "Orphan on Left"
            elif r_info and not l_info:
                item.status = "RIGHT_ONLY"
                item.diff_reason = "Orphan on Right"
            elif is_dir:
                item.status = "SAME"
            else:
                # Compare file contents
                item.status, item.diff_reason = FolderCompareEngine._compare_files(
                    l_info["full_path"], r_info["full_path"],
                    l_info["size"], r_info["size"],
                    l_info["mtime"], r_info["mtime"],
                    mode
                )

            flat_items[rel_p] = item

        # Build hierarchy tree
        return FolderCompareEngine._build_tree(flat_items)

    @staticmethod
    def _scan_target(target_path: str, progress_callback=None, label: str = "", respect_gitignore: bool = True) -> Dict[str, dict]:
        """Scans on-disk directory or virtual archive, returning dict by rel_path."""
        if not target_path or not os.path.exists(target_path):
            return {}

        entries: Dict[str, dict] = {}
        count = 0
        rules = FolderCompareEngine.load_ignore_rules(target_path) if respect_gitignore else []

        # 1. Virtual Archive VFS
        if ArchiveVFS.is_archive(target_path):
            for entry in ArchiveVFS.list_entries(target_path):
                norm_p = entry.path.replace("\\", "/").strip("/")
                if respect_gitignore and FolderCompareEngine.is_path_ignored(norm_p, entry.is_dir, rules):
                    continue
                count += 1
                entries[norm_p] = {
                    "full_path": f"{target_path}#{norm_p}",
                    "is_dir": entry.is_dir,
                    "size": entry.size,
                    "mtime": entry.mtime
                }
                if progress_callback and count % 250 == 0:
                    progress_callback(count, f"Reading archive ({label}): {count:,} items...")
            return entries

        # 2. Local File System Directory
        if os.path.isdir(target_path):
            for root, dirs, files in os.walk(target_path):
                # Prune ignored directories in-place so os.walk avoids scanning subtrees
                if respect_gitignore and rules:
                    dirs[:] = [
                        d for d in dirs
                        if not FolderCompareEngine.is_path_ignored(
                            os.path.relpath(os.path.join(root, d), target_path), True, rules
                        )
                    ]

                # Folders
                for d in dirs:
                    count += 1
                    full_p = os.path.join(root, d)
                    rel_p = os.path.relpath(full_p, target_path).replace("\\", "/")
                    try:
                        stat = os.stat(full_p)
                        entries[rel_p] = {
                            "full_path": full_p,
                            "is_dir": True,
                            "size": 0,
                            "mtime": stat.st_mtime
                        }
                    except OSError:
                        pass

                # Files
                for f in files:
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, target_path).replace("\\", "/")
                    if respect_gitignore and rules and FolderCompareEngine.is_path_ignored(rel_p, False, rules):
                        continue
                    count += 1
                    try:
                        stat = os.stat(full_p)
                        entries[rel_p] = {
                            "full_path": full_p,
                            "is_dir": False,
                            "size": stat.st_size,
                            "mtime": stat.st_mtime
                        }
                    except OSError:
                        pass

                if progress_callback and count % 500 == 0:
                    progress_callback(count, f"Scanning {label}: {count:,} items found...")

        return entries

    @staticmethod
    def _compare_files(
        l_path: str, r_path: str,
        l_size: int, r_size: int,
        l_mtime: float, r_mtime: float,
        mode: str
    ) -> Tuple[str, str]:
        """Compares two files and returns (status, reason)."""
        # Fast Size check
        if mode == "timestamp":
            if l_size != r_size:
                return "DIFF", f"Size differs ({l_size:,} vs {r_size:,})"
            if abs(l_mtime - r_mtime) > 2.0:
                newer = "Left" if l_mtime > r_mtime else "Right"
                return "DIFF", f"Modified date differs ({newer} newer)"
            return "SAME", "Size & timestamp match"

        if mode == "rules":
            # Rules-based: Ignore whitespace and line-endings in text files
            try:
                with open(l_path, "r", encoding="utf-8", errors="replace") as f1, \
                     open(r_path, "r", encoding="utf-8", errors="replace") as f2:
                    t1 = "".join(f1.read().split())
                    t2 = "".join(f2.read().split())
                    if t1 == t2:
                        return "SAME", "Rules match (ignoring whitespace)"
                    return "DIFF", "Content differs"
            except Exception:
                pass

        # Hash mode (BLAKE3 or SHA-256)
        if l_size != r_size:
            return "DIFF", f"Size differs ({l_size:,} vs {r_size:,})"

        algo = "blake3" if mode == "blake3" else "sha256"
        h1 = DiffEngine.hash_file(l_path, algo)
        h2 = DiffEngine.hash_file(r_path, algo)
        if h1 and h2 and h1 == h2:
            return "SAME", f"{algo.upper()} Content Match"
        return "DIFF", f"{algo.upper()} Hash mismatch"

    @staticmethod
    def _apply_filters(paths: Set[str], filter_expr: str) -> Set[str]:
        """Applies inclusion/exclusion patterns like '*.py', '-*.tmp', '-kb_*.*'."""
        if not filter_expr or not filter_expr.strip():
            return paths

        patterns = [p.strip() for p in filter_expr.split(";") if p.strip()]
        result = set()

        for p in paths:
            filename = os.path.basename(p)
            keep = True
            for pat in patterns:
                if pat.startswith("-"):
                    # Exclusion pattern
                    if fnmatch.fnmatch(filename, pat[1:]):
                        keep = False
                        break
                else:
                    # Inclusion pattern
                    if not fnmatch.fnmatch(filename, pat):
                        keep = False
            if keep:
                result.add(p)

        return result

    @staticmethod
    def _sort_tree(items: List[FolderCompareItem]):
        """Sorts folders first (case-insensitive), then files (case-insensitive)."""
        items.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        for it in items:
            if it.children:
                FolderCompareEngine._sort_tree(it.children)

    @staticmethod
    def _build_tree(flat_items: Dict[str, FolderCompareItem]) -> List[FolderCompareItem]:
        """Builds a hierarchical tree from flat relative paths."""
        root_items: List[FolderCompareItem] = []
        path_to_item: Dict[str, FolderCompareItem] = {}

        # Sort paths so parent folders come before children
        sorted_paths = sorted(flat_items.keys())

        for p in sorted_paths:
            item = flat_items[p]
            parent_dir = os.path.dirname(p).replace("\\", "/")
            if not parent_dir:
                root_items.append(item)
            elif parent_dir in path_to_item:
                parent_item = path_to_item[parent_dir]
                parent_item.children.append(item)
                # Only mark parent as DIFF if it exists on BOTH sides!
                if parent_item.left_path and parent_item.right_path:
                    if item.status != "SAME":
                        parent_item.status = "DIFF"
            else:
                root_items.append(item)
            path_to_item[p] = item

        # Organize by folders first, then files
        FolderCompareEngine._sort_tree(root_items)
        return root_items

    @staticmethod
    def find_subfolder_match(left_dir: str, right_dir: str) -> Optional[Tuple[str, str, str]]:
        """
        Detects if one side contains a subfolder that matches the opposite root.
        Returns ('left', full_subfolder_path, subfolder_name) or ('right', full_subfolder_path, subfolder_name).
        """
        if not left_dir or not right_dir:
            return None
        if not os.path.isdir(left_dir) or not os.path.isdir(right_dir):
            return None

        left_base = os.path.basename(os.path.abspath(left_dir)).lower()
        right_base = os.path.basename(os.path.abspath(right_dir)).lower()

        # Check left subfolders matching right
        try:
            for item in os.listdir(left_dir):
                full_sub = os.path.join(left_dir, item)
                if os.path.isdir(full_sub):
                    item_low = item.lower()
                    if item_low == right_base or item_low in right_base or right_base in item_low:
                        return ("left", full_sub, item)
        except OSError:
            pass

        # Check right subfolders matching left
        try:
            for item in os.listdir(right_dir):
                full_sub = os.path.join(right_dir, item)
                if os.path.isdir(full_sub):
                    item_low = item.lower()
                    if item_low == left_base or item_low in left_base or left_base in item_low:
                        return ("right", full_sub, item)
        except OSError:
            pass

        return None
