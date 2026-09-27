"""
Interactive Folder Synchronization Engine
Supports signature folder sync operations:
1. Mirror Left-to-Right (overwrite targets, prune orphans on right).
2. Bi-directional Sync (propagate newest modification timestamps both ways).
3. Update Left (copy only missing or newer files from right to left).
4. Update Right (copy only missing or newer files from left to right).
"""

import os
import shutil
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable
from app.core.folder_compare_engine import FolderCompareItem


@dataclass
class SyncActionItem:
    action: str         # 'copy_l2r', 'copy_r2l', 'delete_r', 'delete_l', 'skip'
    rel_path: str
    source_path: Optional[str]
    target_path: Optional[str]
    is_dir: bool
    size: int
    reason: str


@dataclass
class SyncExecutionSummary:
    total_actions: int
    copied_count: int
    deleted_count: int
    errors: List[str] = field(default_factory=list)
    success: bool = True


class FolderSyncEngine:
    """Plans and executes dual-tree filesystem synchronization."""

    MODE_MIRROR_L2R = "mirror_l2r"
    MODE_BIDIRECTIONAL = "bidirectional"
    MODE_UPDATE_LEFT = "update_left"
    MODE_UPDATE_RIGHT = "update_right"

    @classmethod
    def flatten_items(cls, items: List[FolderCompareItem]) -> List[FolderCompareItem]:
        flat: List[FolderCompareItem] = []
        for it in items:
            flat.append(it)
            if it.children:
                flat.extend(cls.flatten_items(it.children))
        return flat

    @classmethod
    def plan_sync(
        cls,
        items: List[FolderCompareItem],
        left_dir: str,
        right_dir: str,
        mode: str = "mirror_l2r"
    ) -> List[SyncActionItem]:
        """Analyzes comparison items and generates an exact list of actions."""
        all_items = cls.flatten_items(items)
        plan: List[SyncActionItem] = []

        for it in all_items:
            # We operate primarily on files; directories are created/pruned as needed
            if it.is_dir:
                continue

            rel_p = it.rel_path
            dest_right = os.path.join(right_dir, rel_p.replace("/", os.sep))
            dest_left = os.path.join(left_dir, rel_p.replace("/", os.sep))
            l_path = it.left_path or dest_left
            r_path = it.right_path or dest_right
            l_size = it.left_size or 0
            r_size = it.right_size or 0
            l_mtime = it.left_mtime or 0.0
            r_mtime = it.right_mtime or 0.0

            if mode == cls.MODE_MIRROR_L2R:
                if it.status == "LEFT_ONLY":
                    plan.append(SyncActionItem(
                        action="copy_l2r",
                        rel_path=rel_p,
                        source_path=l_path,
                        target_path=dest_right,
                        is_dir=False,
                        size=l_size,
                        reason="Copy missing file to Right"
                    ))
                elif it.status == "DIFF":
                    plan.append(SyncActionItem(
                        action="copy_l2r",
                        rel_path=rel_p,
                        source_path=l_path,
                        target_path=dest_right,
                        is_dir=False,
                        size=l_size,
                        reason="Overwrite Right with Left version"
                    ))
                elif it.status == "RIGHT_ONLY":
                    plan.append(SyncActionItem(
                        action="delete_r",
                        rel_path=rel_p,
                        source_path=None,
                        target_path=r_path,
                        is_dir=False,
                        size=r_size,
                        reason="Prune orphan on Right"
                    ))

            elif mode == cls.MODE_BIDIRECTIONAL:
                if it.status == "LEFT_ONLY":
                    plan.append(SyncActionItem(
                        action="copy_l2r",
                        rel_path=rel_p,
                        source_path=l_path,
                        target_path=dest_right,
                        is_dir=False,
                        size=l_size,
                        reason="Propagate missing file to Right"
                    ))
                elif it.status == "RIGHT_ONLY":
                    plan.append(SyncActionItem(
                        action="copy_r2l",
                        rel_path=rel_p,
                        source_path=r_path,
                        target_path=dest_left,
                        is_dir=False,
                        size=r_size,
                        reason="Propagate missing file to Left"
                    ))
                elif it.status == "DIFF":
                    if l_mtime > r_mtime:
                        plan.append(SyncActionItem(
                            action="copy_l2r",
                            rel_path=rel_p,
                            source_path=l_path,
                            target_path=dest_right,
                            is_dir=False,
                            size=l_size,
                            reason="Left is newer (propagate to Right)"
                        ))
                    elif r_mtime > l_mtime:
                        plan.append(SyncActionItem(
                            action="copy_r2l",
                            rel_path=rel_p,
                            source_path=r_path,
                            target_path=dest_left,
                            is_dir=False,
                            size=r_size,
                            reason="Right is newer (propagate to Left)"
                        ))
                    else:
                        plan.append(SyncActionItem(
                            action="copy_l2r",
                            rel_path=rel_p,
                            source_path=l_path,
                            target_path=dest_right,
                            is_dir=False,
                            size=l_size,
                            reason="Timestamps equal: default overwrite Right"
                        ))

            elif mode == cls.MODE_UPDATE_LEFT:
                if it.status == "RIGHT_ONLY":
                    plan.append(SyncActionItem(
                        action="copy_r2l",
                        rel_path=rel_p,
                        source_path=r_path,
                        target_path=dest_left,
                        is_dir=False,
                        size=r_size,
                        reason="Copy missing file from Right to Left"
                    ))
                elif it.status == "DIFF" and r_mtime > l_mtime:
                    plan.append(SyncActionItem(
                        action="copy_r2l",
                        rel_path=rel_p,
                        source_path=r_path,
                        target_path=dest_left,
                        is_dir=False,
                        size=r_size,
                        reason="Right is newer (update Left)"
                    ))

            elif mode == cls.MODE_UPDATE_RIGHT:
                if it.status == "LEFT_ONLY":
                    plan.append(SyncActionItem(
                        action="copy_l2r",
                        rel_path=rel_p,
                        source_path=l_path,
                        target_path=dest_right,
                        is_dir=False,
                        size=l_size,
                        reason="Copy missing file from Left to Right"
                    ))
                elif it.status == "DIFF" and l_mtime > r_mtime:
                    plan.append(SyncActionItem(
                        action="copy_l2r",
                        rel_path=rel_p,
                        source_path=l_path,
                        target_path=dest_right,
                        is_dir=False,
                        size=l_size,
                        reason="Left is newer (update Right)"
                    ))

        return plan

    @classmethod
    def execute_sync(
        cls,
        plan: List[SyncActionItem],
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> SyncExecutionSummary:
        """Executes synchronization actions safely with timestamp preservation."""
        total = len(plan)
        copied = 0
        deleted = 0
        errors: List[str] = []

        for idx, item in enumerate(plan):
            if progress_callback:
                progress_callback(idx + 1, total, f"Processing {item.rel_path} ({item.action})...")

            try:
                if item.action in ("copy_l2r", "copy_r2l"):
                    if not item.source_path or not os.path.exists(item.source_path):
                        errors.append(f"Source file not found: {item.source_path}")
                        continue
                    if not item.target_path:
                        continue

                    target_dir = os.path.dirname(item.target_path)
                    os.makedirs(target_dir, exist_ok=True)

                    # Copy content and preserve timestamps
                    shutil.copy2(item.source_path, item.target_path)
                    copied += 1

                elif item.action in ("delete_r", "delete_l"):
                    if item.target_path and os.path.exists(item.target_path):
                        if os.path.isdir(item.target_path):
                            shutil.rmtree(item.target_path, ignore_errors=True)
                        else:
                            os.remove(item.target_path)
                        deleted += 1

            except Exception as e:
                errors.append(f"Error {item.action} on {item.rel_path}: {e}")

        # Clean empty folders after prune
        return SyncExecutionSummary(
            total_actions=total,
            copied_count=copied,
            deleted_count=deleted,
            errors=errors,
            success=len(errors) == 0
        )
