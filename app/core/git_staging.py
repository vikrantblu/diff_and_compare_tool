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
from typing import Optional, Tuple, List, Dict
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

    @staticmethod
    def get_working_tree_changes(repo_path: str) -> List[Dict[str, str]]:
        """
        Lists modified, staged, untracked, and conflicted files in the Git repository
        enclosing `repo_path`, for quick opening in DiffView (HEAD vs Working Copy).
        """
        root = GitStagingManager.find_git_root(repo_path)
        if not root:
            return []

        try:
            res = subprocess.run(
                ["git", "status", "--porcelain=v1", "-uall", "-z"],
                cwd=root,
                capture_output=True,
                check=False
            )
            if res.returncode != 0:
                return []

            raw_tokens = res.stdout.split(b"\x00")
            changes: List[Dict[str, str]] = []
            idx = 0
            while idx < len(raw_tokens):
                tok = raw_tokens[idx]
                idx += 1
                if not tok:
                    continue
                entry = tok.decode("utf-8", errors="replace")
                if len(entry) < 4:
                    continue
                xy = entry[:2]
                rel_path = entry[3:].replace("\\", "/")
                # Renamed/copied porcelain -z records emit a second NUL-delimited original path token
                if xy[0] in ("R", "C") or xy[1] in ("R", "C"):
                    if idx < len(raw_tokens):
                        idx += 1

                if xy == "??":
                    label = "Untracked"
                elif "U" in xy or xy in ("AA", "DD"):
                    label = "Conflict"
                elif xy[0] != " " and xy[1] != " ":
                    label = "Staged + Modified"
                elif xy[0] == "D" or xy[1] == "D":
                    label = "Deleted"
                elif xy[0] == "A":
                    label = "Staged (Added)"
                elif xy[0] in ("M", "R"):
                    label = "Staged"
                else:
                    label = "Modified"

                abs_path = os.path.normpath(os.path.join(root, rel_path))
                changes.append({
                    "status": xy,
                    "rel_path": rel_path,
                    "abs_path": abs_path,
                    "label": label,
                    "repo_root": root,
                })
            return changes
        except Exception:
            return []

    @staticmethod
    def get_git_tool_config_status(scope: str = "global", cwd: Optional[str] = None) -> Dict[str, str]:
        """Reads current git difftool / mergetool configuration values for UI inspection."""
        scope_flag = "--local" if scope == "local" else "--global"
        keys = [
            "diff.tool",
            "difftool.diff_and_compare.cmd",
            "merge.tool",
            "mergetool.diff_and_compare.cmd",
        ]
        result: Dict[str, str] = {}
        for k in keys:
            try:
                res = subprocess.run(
                    ["git", "config", scope_flag, "--get", k],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                result[k] = res.stdout.strip() if res.returncode == 0 else ""
            except Exception:
                result[k] = ""
        return result

    @staticmethod
    def configure_git_difftool_mergetool(
        exe_command: Optional[str] = None,
        scope: str = "global",
        cwd: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Registers diff_and_compare_tool as Git's difftool and 3-way mergetool."""
        if not exe_command:
            from app.core.shell_integration import get_executable_command
            exe_command = get_executable_command()

        # Normalize backslashes so MSYS/Git bash executes Windows paths cleanly
        cmd_prefix = exe_command.replace("\\", "/")
        scope_flag = "--local" if scope == "local" else "--global"

        diff_cmd = f'{cmd_prefix} --diff "$LOCAL" "$REMOTE"'
        merge_cmd = f'{cmd_prefix} --merge "$LOCAL" "$BASE" "$REMOTE" --output "$MERGED"'

        settings = [
            ("diff.tool", "diff_and_compare"),
            ("difftool.diff_and_compare.cmd", diff_cmd),
            ("difftool.prompt", "false"),
            ("merge.tool", "diff_and_compare"),
            ("mergetool.diff_and_compare.cmd", merge_cmd),
            ("mergetool.diff_and_compare.trustExitCode", "true"),
            ("mergetool.prompt", "false"),
        ]

        try:
            for key, val in settings:
                res = subprocess.run(
                    ["git", "config", scope_flag, key, val],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode != 0:
                    err = res.stderr.strip() or res.stdout.strip()
                    return False, f"Failed setting {key}: {err}"
            return True, f"Configured Git {scope} diff.tool & merge.tool -> diff_and_compare."
        except Exception as e:
            return False, str(e)
