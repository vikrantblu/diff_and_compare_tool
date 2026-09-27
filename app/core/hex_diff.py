"""
High-Performance Memory-Mapped Hex & Binary Diff Engine
Features:
- Memory-mapped I/O (mmap) for opening multi-gigabyte files with zero memory exhaustion.
- Aligned 16-byte row chunking with offset, hexadecimal, and printable ASCII views.
- Byte-level mismatch tracking and rapid difference seeking.
"""

import os
import mmap
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple


@dataclass
class HexRowDiff:
    offset: int
    left_bytes: bytes
    right_bytes: bytes
    left_hex: str
    right_hex: str
    left_ascii: str
    right_ascii: str
    mismatched_byte_indices: Set[int] = field(default_factory=set)
    is_left_only: bool = False
    is_right_only: bool = False


@dataclass
class HexDiffSummary:
    file1_size: int
    file2_size: int
    total_rows: int
    differing_bytes_count: int
    difference_percentage: float
    mismatched_rows: List[int]  # List of row indices with differences


class HexDiffEngine:
    """Core memory-mapped binary differencing engine."""

    BYTES_PER_ROW = 16

    @classmethod
    def compare_files_summary(cls, path1: str, path2: str) -> Optional[HexDiffSummary]:
        if not os.path.exists(path1) or not os.path.exists(path2):
            return None

        s1 = os.path.getsize(path1)
        s2 = os.path.getsize(path2)
        max_size = max(s1, s2)
        total_rows = (max_size + cls.BYTES_PER_ROW - 1) // cls.BYTES_PER_ROW

        differing_bytes = 0
        mismatched_rows = []

        # Read in 64KB blocks to quickly detect mismatched rows
        block_size = 65536
        with open(path1, "rb") as f1, open(path2, "rb") as f2:
            offset = 0
            while offset < max_size:
                c1 = f1.read(block_size)
                c2 = f2.read(block_size)
                if not c1 and not c2:
                    break

                min_len = min(len(c1), len(c2))
                for i in range(min_len):
                    if c1[i] != c2[i]:
                        differing_bytes += 1
                        r_idx = (offset + i) // cls.BYTES_PER_ROW
                        if not mismatched_rows or mismatched_rows[-1] != r_idx:
                            mismatched_rows.append(r_idx)

                # Tail difference if one file ended earlier
                if len(c1) != len(c2):
                    excess = abs(len(c1) - len(c2))
                    differing_bytes += excess
                    start_tail = offset + min_len
                    for i in range(excess):
                        r_idx = (start_tail + i) // cls.BYTES_PER_ROW
                        if not mismatched_rows or mismatched_rows[-1] != r_idx:
                            mismatched_rows.append(r_idx)

                offset += max(len(c1), len(c2))

        diff_pct = (differing_bytes / max_size * 100.0) if max_size > 0 else 0.0

        return HexDiffSummary(
            file1_size=s1,
            file2_size=s2,
            total_rows=total_rows,
            differing_bytes_count=differing_bytes,
            difference_percentage=diff_pct,
            mismatched_rows=mismatched_rows
        )

    @classmethod
    def read_row_range(
        cls,
        path1: str,
        path2: str,
        start_row: int,
        count: int
    ) -> List[HexRowDiff]:
        """
        Reads a window of rows on-demand using memory-mapping,
        ensuring fast virtual scrolling without loading entire huge files into RAM.
        """
        if not os.path.exists(path1) or not os.path.exists(path2):
            return []

        s1 = os.path.getsize(path1)
        s2 = os.path.getsize(path2)
        results: List[HexRowDiff] = []

        with open(path1, "rb") as f1, open(path2, "rb") as f2:
            mm1 = mmap.mmap(f1.fileno(), 0, access=mmap.ACCESS_READ) if s1 > 0 else None
            mm2 = mmap.mmap(f2.fileno(), 0, access=mmap.ACCESS_READ) if s2 > 0 else None

            try:
                for r in range(start_row, start_row + count):
                    offset = r * cls.BYTES_PER_ROW
                    if offset >= max(s1, s2):
                        break

                    # Slice bytes
                    b1 = b""
                    b2 = b""
                    if mm1 and offset < s1:
                        end1 = min(s1, offset + cls.BYTES_PER_ROW)
                        b1 = mm1[offset:end1]
                    if mm2 and offset < s2:
                        end2 = min(s2, offset + cls.BYTES_PER_ROW)
                        b2 = mm2[offset:end2]

                    # Hex strings
                    hex1_parts = [f"{b:02X}" for b in b1]
                    hex2_parts = [f"{b:02X}" for b in b2]
                    # Space after 8 bytes for readability
                    if len(hex1_parts) > 8:
                        hex1_parts.insert(8, "")
                    if len(hex2_parts) > 8:
                        hex2_parts.insert(8, "")

                    hex1_str = " ".join(hex1_parts)
                    hex2_str = " ".join(hex2_parts)

                    # ASCII strings
                    ascii1 = "".join(chr(b) if 32 <= b <= 126 else "·" for b in b1)
                    ascii2 = "".join(chr(b) if 32 <= b <= 126 else "·" for b in b2)

                    # Mismatches
                    mismatches: Set[int] = set()
                    min_len = min(len(b1), len(b2))
                    for i in range(min_len):
                        if b1[i] != b2[i]:
                            mismatches.add(i)
                    for i in range(min_len, max(len(b1), len(b2))):
                        mismatches.add(i)

                    results.append(HexRowDiff(
                        offset=offset,
                        left_bytes=b1,
                        right_bytes=b2,
                        left_hex=hex1_str,
                        right_hex=hex2_str,
                        left_ascii=ascii1,
                        right_ascii=ascii2,
                        mismatched_byte_indices=mismatches,
                        is_left_only=(len(b1) > 0 and len(b2) == 0),
                        is_right_only=(len(b2) > 0 and len(b1) == 0)
                    ))
            finally:
                if mm1:
                    mm1.close()
                if mm2:
                    mm2.close()

        return results
