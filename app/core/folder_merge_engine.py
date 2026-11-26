"""
True Ancestor-Based 3-Way Folder Merge Engine
Compares Mine (Left), Base (Ancestor), and Theirs (Right) directory/archive/remote trees,
classifies non-conflicting vs conflicting changes, supports per-file resolution overrides,
and executes merged directory output.
"""

import csv
import os
import shutil
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable

from app.core.folder_compare_engine import FolderCompareEngine
from app.core.file_io import is_virtual_path, read_vfs_or_file_bytes


@dataclass
class FolderMergeItem:
    """Single node (file or directory) inside a 3-way folder merge comparison."""
    rel_path: str
    name: str
    is_dir: bool
    status: str              # IDENTICAL, CONVERGED, LEFT_MODIFIED, RIGHT_MODIFIED, LEFT_ADDED, RIGHT_ADDED, LEFT_DELETED, RIGHT_DELETED, CONFLICT, AUTO_MERGE
    resolution: str          # keep_same, take_left, take_right, take_base, delete, skip, unresolved
    left_path: Optional[str] = None
    base_path: Optional[str] = None
    right_path: Optional[str] = None
    left_size: Optional[int] = None
    base_size: Optional[int] = None
    right_size: Optional[int] = None
    left_mtime: Optional[float] = None
    base_mtime: Optional[float] = None
    right_mtime: Optional[float] = None
    reason: str = ""
    children: List['FolderMergeItem'] = field(default_factory=list)


@dataclass
class FolderMergeExecutionSummary:
    """Result telemetry after executing a 3-way folder merge to an output directory."""
    total_files: int = 0
    written_count: int = 0
    deleted_count: int = 0
    skipped_conflicts: int = 0
    errors: List[str] = field(default_factory=list)
    success: bool = True


class FolderMergeEngine:
    """Evaluates and executes 3-way ancestor-based directory merges."""

    RESOLUTION_LABELS = {
        "keep_same": "= Keep Identical",
        "take_left": "← Take Mine",
        "take_right": "→ Take Theirs",
        "take_base": "○ Revert to Base",
        "delete": "✕ Delete in Output",
        "skip": "— Skip",
        "unresolved": "⚠ Conflict (Unresolved)",
    }

    @staticmethod
    def _entries_same(a: dict, b: dict, mode: str, timestamp_tolerance_sec: float) -> bool:
        st, _ = FolderCompareEngine._compare_files(
            a["full_path"], b["full_path"],
            a.get("size") or 0, b.get("size") or 0,
            a.get("mtime") or 0.0, b.get("mtime") or 0.0,
            mode=mode,
            timestamp_tolerance_sec=timestamp_tolerance_sec,
        )
        return st == "SAME"

    @classmethod
    def compare_3way_folders(
        cls,
        left_dir: str,
        base_dir: str,
        right_dir: str,
        mode: str = "hash",
        filter_expr: str = "",
        respect_gitignore: bool = True,
        timestamp_tolerance_sec: float = 2.0,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> List[FolderMergeItem]:
        """Scans Mine (Left), Base, and Theirs (Right) and produces a 3-way FolderMergeItem tree."""
        if progress_callback:
            progress_callback(0, "Scanning Left (Mine) directory...")
        left_entries = FolderCompareEngine._scan_target(left_dir, progress_callback, "Mine", respect_gitignore=respect_gitignore)

        if progress_callback:
            progress_callback(0, "Scanning Base (Ancestor) directory...")
        base_entries = FolderCompareEngine._scan_target(base_dir, progress_callback, "Base", respect_gitignore=respect_gitignore)

        if progress_callback:
            progress_callback(0, "Scanning Right (Theirs) directory...")
        right_entries = FolderCompareEngine._scan_target(right_dir, progress_callback, "Theirs", respect_gitignore=respect_gitignore)

        all_paths = set(left_entries.keys()) | set(base_entries.keys()) | set(right_entries.keys())
        if not all_paths:
            return []

        dir_paths = {
            p for p in all_paths
            if (left_entries.get(p, {}).get("is_dir")
                or base_entries.get(p, {}).get("is_dir")
                or right_entries.get(p, {}).get("is_dir"))
        }
        filtered_paths = FolderCompareEngine._apply_filters(all_paths, filter_expr, dir_paths=dir_paths)

        flat_items: Dict[str, FolderMergeItem] = {}
        total = len(filtered_paths)
        for idx, rel_p in enumerate(sorted(filtered_paths), 1):
            l_inf = left_entries.get(rel_p)
            b_inf = base_entries.get(rel_p)
            r_inf = right_entries.get(rel_p)

            is_dir = bool(
                (l_inf and l_inf["is_dir"])
                or (b_inf and b_inf["is_dir"])
                or (r_inf and r_inf["is_dir"])
            )
            name = os.path.basename(rel_p)

            if is_dir:
                item = FolderMergeItem(
                    rel_path=rel_p,
                    name=name,
                    is_dir=True,
                    status="IDENTICAL",
                    resolution="keep_same",
                    left_path=l_inf["full_path"] if l_inf else None,
                    base_path=b_inf["full_path"] if b_inf else None,
                    right_path=r_inf["full_path"] if r_inf else None,
                )
            else:
                status, resolution, reason = cls._classify_file(
                    l_inf, b_inf, r_inf, mode, timestamp_tolerance_sec
                )
                item = FolderMergeItem(
                    rel_path=rel_p,
                    name=name,
                    is_dir=False,
                    status=status,
                    resolution=resolution,
                    left_path=l_inf["full_path"] if l_inf else None,
                    base_path=b_inf["full_path"] if b_inf else None,
                    right_path=r_inf["full_path"] if r_inf else None,
                    left_size=l_inf["size"] if l_inf else None,
                    base_size=b_inf["size"] if b_inf else None,
                    right_size=r_inf["size"] if r_inf else None,
                    left_mtime=l_inf["mtime"] if l_inf else None,
                    base_mtime=b_inf["mtime"] if b_inf else None,
                    right_mtime=r_inf["mtime"] if r_inf else None,
                    reason=reason,
                )

            flat_items[rel_p] = item
            if progress_callback and (idx % 250 == 0 or idx == total):
                progress_callback(idx, f"Evaluating 3-way merge ({idx:,}/{total:,})...")

        return cls._build_tree(flat_items)

    @classmethod
    def _classify_file(
        cls,
        l_inf: Optional[dict],
        b_inf: Optional[dict],
        r_inf: Optional[dict],
        mode: str,
        tol: float,
    ) -> tuple:
        has_l, has_b, has_r = l_inf is not None, b_inf is not None, r_inf is not None

        if has_b and not has_l and not has_r:
            return "CONVERGED", "delete", "Deleted on both Mine and Theirs"
        if has_l and not has_b and not has_r:
            return "LEFT_ADDED", "take_left", "Added only in Mine"
        if has_r and not has_b and not has_l:
            return "RIGHT_ADDED", "take_right", "Added only in Theirs"

        if has_l and has_b and not has_r:
            if cls._entries_same(l_inf, b_inf, mode, tol):
                return "RIGHT_DELETED", "delete", "Unchanged in Mine, deleted in Theirs"
            return "CONFLICT", "unresolved", "Modified in Mine, deleted in Theirs"

        if has_r and has_b and not has_l:
            if cls._entries_same(r_inf, b_inf, mode, tol):
                return "LEFT_DELETED", "delete", "Deleted in Mine, unchanged in Theirs"
            return "CONFLICT", "unresolved", "Deleted in Mine, modified in Theirs"

        if has_l and has_r and not has_b:
            if cls._entries_same(l_inf, r_inf, mode, tol):
                return "CONVERGED", "take_left", "Identical addition in both Mine & Theirs"
            return "CONFLICT", "unresolved", "Divergent additions with no Base ancestor"

        # Present in all three: Mine, Base, Theirs
        l_eq_b = cls._entries_same(l_inf, b_inf, mode, tol)
        r_eq_b = cls._entries_same(r_inf, b_inf, mode, tol)
        if l_eq_b and r_eq_b:
            return "IDENTICAL", "keep_same", "Unchanged across Mine, Base, and Theirs"
        if cls._entries_same(l_inf, r_inf, mode, tol):
            return "CONVERGED", "take_left", "Convergent identical changes in Mine & Theirs"
        if not l_eq_b and r_eq_b:
            return "LEFT_MODIFIED", "take_left", "Modified only in Mine"
        if l_eq_b and not r_eq_b:
            return "RIGHT_MODIFIED", "take_right", "Modified only in Theirs"
        return "CONFLICT", "unresolved", "Conflicting edits in both Mine and Theirs"

    @classmethod
    def _propagate_dir_status(cls, items: List[FolderMergeItem]) -> str:
        """Rolls child conflict / auto-merge statuses upward cleanly."""
        worst = "IDENTICAL"
        for it in items:
            if it.is_dir and it.children:
                child_st = cls._propagate_dir_status(it.children)
                it.status = child_st
            if it.status == "CONFLICT" or it.resolution == "unresolved":
                worst = "CONFLICT"
            elif it.status != "IDENTICAL" and worst != "CONFLICT":
                worst = "AUTO_MERGE"
        return worst

    @classmethod
    def _build_tree(cls, flat_items: Dict[str, FolderMergeItem]) -> List[FolderMergeItem]:
        roots: List[FolderMergeItem] = []
        lookup: Dict[str, FolderMergeItem] = {}
        for p in sorted(flat_items.keys()):
            item = flat_items[p]
            parent_dir = os.path.dirname(p).replace("\\", "/")
            if parent_dir and parent_dir in lookup:
                lookup[parent_dir].children.append(item)
            else:
                roots.append(item)
            lookup[p] = item

        cls._propagate_dir_status(roots)
        FolderCompareEngine._sort_tree(roots)
        return roots

    @classmethod
    def flatten_files(cls, items: List[FolderMergeItem]) -> List[FolderMergeItem]:
        leaves: List[FolderMergeItem] = []

        def _walk(nodes: List[FolderMergeItem]):
            for n in nodes:
                if n.is_dir:
                    _walk(n.children)
                else:
                    leaves.append(n)

        _walk(items)
        return leaves

    @classmethod
    def execute_merge(
        cls,
        items: List[FolderMergeItem],
        output_dir: str,
        skip_conflicts: bool = True,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> FolderMergeExecutionSummary:
        """Writes resolved 3-way folder merge outputs cleanly into `output_dir`."""
        summary = FolderMergeExecutionSummary()
        if not output_dir:
            summary.success = False
            summary.errors.append("Output directory cannot be empty.")
            return summary

        os.makedirs(output_dir, exist_ok=True)
        files = cls.flatten_files(items)
        summary.total_files = len(files)

        for idx, it in enumerate(files, 1):
            dest = os.path.join(output_dir, it.rel_path.replace("/", os.sep))
            if it.resolution == "unresolved":
                summary.skipped_conflicts += 1
                if not skip_conflicts:
                    summary.errors.append(f"Unresolved conflict skipped: {it.rel_path}")
                continue
            if it.resolution == "skip":
                continue

            if it.resolution == "delete":
                try:
                    if os.path.isfile(dest):
                        os.remove(dest)
                        summary.deleted_count += 1
                except Exception as e:
                    summary.errors.append(f"Delete failed for {it.rel_path}: {e}")
                continue

            src = None
            if it.resolution == "keep_same":
                src = it.left_path or it.base_path or it.right_path
            elif it.resolution == "take_left":
                src = it.left_path
            elif it.resolution == "take_right":
                src = it.right_path
            elif it.resolution == "take_base":
                src = it.base_path

            if not src:
                summary.errors.append(f"No source file available for {it.rel_path} ({it.resolution})")
                continue

            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                if is_virtual_path(src):
                    data = read_vfs_or_file_bytes(src)
                    with open(dest, "wb") as f:
                        f.write(data)
                else:
                    shutil.copy2(src, dest)
                summary.written_count += 1
            except Exception as e:
                summary.errors.append(f"Copy failed for {it.rel_path}: {e}")

            if progress_callback and (idx % 100 == 0 or idx == summary.total_files):
                progress_callback(idx, f"Writing merged files ({idx:,}/{summary.total_files:,})...")

        summary.success = len(summary.errors) == 0
        return summary

    @classmethod
    def export_csv_report(cls, items: List[FolderMergeItem], output_file: str) -> None:
        files = cls.flatten_files(items)
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["RelativePath", "ThreeWayStatus", "Resolution", "Reason"])
            for it in files:
                writer.writerow([it.rel_path, it.status, it.resolution, it.reason])
