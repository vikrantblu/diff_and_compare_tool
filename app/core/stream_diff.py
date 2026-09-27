"""
Stream and Process Substitution Diff Resolver
Enables piping directly from stdin via '-' flag:
    git show HEAD~1:main.py | diff_and_compare.exe --diff - main.py
    docker logs c1 | diff_and_compare.exe --diff - <(docker logs c2)
"""

import sys
import os
import tempfile
import atexit
from typing import Tuple, Optional


def resolve_stream_input(path: str, opposing_path: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """
    Checks if path is '-' (stdin). If so, reads the incoming stream into
    a temporary file matching the opposing file's extension (so syntax highlighting
    and AST semantic diffing activate automatically), and registers cleanup on exit.

    Returns:
        (resolved_file_path, display_title_or_none)
    """
    if path != "-":
        return path, None

    # Derive extension from opposing path if available
    ext = ".txt"
    if opposing_path and opposing_path != "-":
        cand_ext = os.path.splitext(opposing_path)[1]
        if cand_ext:
            ext = cand_ext

    # Read bytes from stdin
    try:
        raw_bytes = sys.stdin.buffer.read()
    except Exception:
        try:
            raw_bytes = sys.stdin.read().encode("utf-8", errors="replace")
        except Exception:
            raw_bytes = b""

    temp_dir = os.path.join(tempfile.gettempdir(), "diff_and_compare", "streams")
    os.makedirs(temp_dir, exist_ok=True)

    temp_fd, temp_path = tempfile.mkstemp(prefix=f"stdin_{os.getpid()}_", suffix=ext, dir=temp_dir)
    with os.fdopen(temp_fd, "wb") as f:
        f.write(raw_bytes)

    def _cleanup():
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass

    atexit.register(_cleanup)
    return temp_path, "(Standard Input)"
