"""
Git Chunk Staging & Interactive Repository Operations
Enables live partial commit hunk staging directly from the diff view:
- Stage Hunk to Git Index (git apply --cached --unidiff-zero)
- Unstage Hunk from Index (git apply --cached --reverse --unidiff-zero)
- Discard Hunk from Working Copy (git apply --reverse --unidiff-zero)
- Auto-fetch Git HEAD content for instant side-by-side comparison
"""

import os
import subprocess
from typing import Optional, Tuple, List
from app.core.diff_engine import DiffChunk


class GitStagingManager:
    """Manages Git operations, hunk patch formatting, and partial index staging."""

    @staticmethod
    def find_git_root(path: str) -> Optional[str]:
        """Finds the root directory of the Git repository enclosing path."""
        if not path or not os.path.exists(path):
            return None

        cwd = path if os.path.isdir(path) else os.path.dirname(os.path.abspath(path))
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                return os.path.normpath(res.stdout.strip())
        except Exception:
            pass
        return None

    @staticmethod
    def is_git_tracked(file_path: str) -> bool:
        """Returns True if the file is tracked in Git."""
        root = GitStagingManager.find_git_root(file_path)
        if not root:
            return False
        try:
            rel = os.path.relpath(file_path, root).replace("\\", "/")
            res = subprocess.run(
                ["git", "ls-files", "--error-unmatch", rel],
                cwd=root,
                capture_output=True,
                check=False
            )
            return res.returncode == 0
        except Exception:
            return False

    @staticmethod
    def get_git_head_content(file_path: str) -> Optional[str]:
        """Retrieves the clean committed content of the file from Git HEAD."""
        root = GitStagingManager.find_git_root(file_path)
        if not root:
            return None
        try:
            rel = os.path.relpath(file_path, root).replace("\\", "/")
            res = subprocess.run(
                ["git", "show", f"HEAD:{rel}"],
                cwd=root,
                capture_output=True,
                check=False
            )
            if res.returncode == 0:
                # Decode bytes handling possible CRLF/LF and encodings
                return res.stdout.decode("utf-8", errors="replace")
        except Exception:
            pass
        return None

    @staticmethod
    def build_hunk_patch(
        file_path: str,
        chunk: DiffChunk,
        left_lines: List[str],
        right_lines: List[str]
    ) -> Optional[str]:
        """
        Builds a unidiff-zero formatted unified patch for the given chunk difference.
        Assumes left_lines corresponds to the base/index/HEAD and right_lines to working copy.
        """
        root = GitStagingManager.find_git_root(file_path)
        if not root:
            return None

        rel_path = os.path.relpath(file_path, root).replace("\\", "/")
        left_slice = left_lines[chunk.left_start:chunk.left_end]
        right_slice = right_lines[chunk.right_start:chunk.right_end]

        left_len = len(left_slice)
        right_len = len(right_slice)

        if left_len == 0:
            a_start = 0 if chunk.left_start == 0 else chunk.left_start
            a_count = 0
        else:
            a_start = chunk.left_start + 1
            a_count = left_len

        if right_len == 0:
            b_start = 0 if chunk.right_start == 0 else chunk.right_start
            b_count = 0
        else:
            b_start = chunk.right_start + 1
            b_count = right_len

        lines = [
            f"--- a/{rel_path}",
            f"+++ b/{rel_path}",
            f"@@ -{a_start},{a_count} +{b_start},{b_count} @@"
        ]

        for line in left_slice:
            clean = line.rstrip("\r\n")
            lines.append(f"-{clean}")

        for line in right_slice:
            clean = line.rstrip("\r\n")
            lines.append(f"+{clean}")

        # Git patches require a trailing newline
        return "\n".join(lines) + "\n"

    @staticmethod
    def stage_hunk(
        file_path: str,
        chunk: DiffChunk,
        left_lines: List[str],
        right_lines: List[str]
    ) -> Tuple[bool, str]:
        """
        Stages a specific hunk to Git's index via `git apply --cached --unidiff-zero -`.
        Returns (success, message).
        """
        root = GitStagingManager.find_git_root(file_path)
        if not root:
            return False, "Not inside a Git repository."

        patch = GitStagingManager.build_hunk_patch(file_path, chunk, left_lines, right_lines)
        if not patch:
            return False, "Failed to construct patch for hunk."

        try:
            res = subprocess.run(
                ["git", "apply", "--cached", "--unidiff-zero", "-"],
                input=patch.encode("utf-8"),
                cwd=root,
                capture_output=True,
                check=False
            )
            if res.returncode == 0:
                return True, "Hunk successfully staged to Git index."
            else:
                err = res.stderr.decode("utf-8", errors="replace").strip()
                return False, f"Git apply failed: {err}"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def unstage_hunk(
        file_path: str,
        chunk: DiffChunk,
        left_lines: List[str],
        right_lines: List[str]
    ) -> Tuple[bool, str]:
        """
        Unstages a specific hunk from Git's index via `git apply --cached --reverse --unidiff-zero -`.
        Returns (success, message).
        """
        root = GitStagingManager.find_git_root(file_path)
        if not root:
            return False, "Not inside a Git repository."

        patch = GitStagingManager.build_hunk_patch(file_path, chunk, left_lines, right_lines)
        if not patch:
            return False, "Failed to construct patch for hunk."

        try:
            res = subprocess.run(
                ["git", "apply", "--cached", "--reverse", "--unidiff-zero", "-"],
                input=patch.encode("utf-8"),
                cwd=root,
                capture_output=True,
                check=False
            )
            if res.returncode == 0:
                return True, "Hunk successfully unstaged from Git index."
            else:
                err = res.stderr.decode("utf-8", errors="replace").strip()
                return False, f"Git unstage failed: {err}"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def discard_hunk(
        file_path: str,
        chunk: DiffChunk,
        left_lines: List[str],
        right_lines: List[str]
    ) -> Tuple[bool, str]:
        """
        Discards a hunk from the working copy via `git apply --reverse --unidiff-zero -`.
        Returns (success, message).
        """
        root = GitStagingManager.find_git_root(file_path)
        if not root:
            return False, "Not inside a Git repository."

        patch = GitStagingManager.build_hunk_patch(file_path, chunk, left_lines, right_lines)
        if not patch:
            return False, "Failed to construct patch for hunk."

        try:
            res = subprocess.run(
                ["git", "apply", "--reverse", "--unidiff-zero", "-"],
                input=patch.encode("utf-8"),
                cwd=root,
                capture_output=True,
                check=False
            )
            if res.returncode == 0:
                return True, "Hunk changes discarded from working copy."
            else:
                err = res.stderr.decode("utf-8", errors="replace").strip()
                return False, f"Git discard failed: {err}"
        except Exception as e:
            return False, str(e)
