"""
High-Performance Core Diff & 3-Way Merge Engine
Features:
- Myers / SequenceMatcher line comparison.
- diff_match_patch semantic intraline character/word precision.
- AlignedDiffBuilder: Horizontal spacer line insertion for side-by-side alignment.
- 3-Way Merge conflict detector and reconciler.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any, Set
import difflib
import re
import hashlib
import os

try:
    import diff_match_patch as dmp_module
    DMP = dmp_module.diff_match_patch()
except ImportError:
    DMP = None

import mmap
import zlib

try:
    import blake3
    HAS_BLAKE3 = True
except ImportError:
    HAS_BLAKE3 = False

from app.core.ast_diff import ASTSemanticDiffer


NOISE_REGEX_PRESETS = {
    "Timestamps / ISO Dates": (r"\b\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b", "<TIMESTAMP>"),
    "UUIDs / GUIDs": (r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", "<GUID>"),
    "Git Commit Hashes": (r"\b[0-9a-fA-F]{40}\b|\b[0-9a-fA-F]{7,10}\b", "<COMMIT_HASH>"),
    "C/C++/Java/JS Comments": (r"//.*?$|/\*[\s\S]*?\*/", ""),
    "Python/Shell Comments": (r"#.*?$", ""),
    "Memory Addresses": (r"0x[0-9a-fA-F]{6,16}", "<ADDR>"),
}


@dataclass
class CharDiffSpan:
    """Character-level difference span within a line."""
    op: int  # -1: delete, 0: equal, 1: insert
    text: str
    start: int
    end: int


@dataclass
class DiffChunk:
    """A contiguous block difference between two text files."""
    tag: str  # 'equal', 'replace', 'insert', 'delete', 'moved'
    left_start: int
    left_end: int
    right_start: int
    right_end: int
    left_char_spans: Dict[int, List[CharDiffSpan]] = field(default_factory=dict)
    right_char_spans: Dict[int, List[CharDiffSpan]] = field(default_factory=dict)
    is_moved: bool = False
    moved_partner_chunk_idx: Optional[int] = None
    moved_to_line: Optional[int] = None
    semantic_match_info: Optional[str] = None



@dataclass
class AlignedDiffResult:
    """Aligned comparison output with matching visual row indices across Left and Right."""
    left_display_lines: List[str]
    right_display_lines: List[str]
    left_spacers: Set[int]
    right_spacers: Set[int]
    left_line_numbers: Dict[int, int]   # display_idx -> real_file_line (1-indexed)
    right_line_numbers: Dict[int, int]  # display_idx -> real_file_line (1-indexed)
    chunks: List[DiffChunk]
    raw_left_text: str
    raw_right_text: str


@dataclass
class MergeConflictChunk:
    """A chunk in a 3-way merge representing clean changes or conflicts."""
    is_conflict: bool
    base_lines: List[str]
    left_lines: List[str]   # Mine
    right_lines: List[str]  # Theirs
    resolved_lines: List[str] = field(default_factory=list)
    resolution_state: str = "unresolved"  # 'mine', 'theirs', 'base', 'both', 'custom', 'auto'


class DiffEngine:
    """Core evaluation engine for 2-way diffs and 3-way merges."""

    @staticmethod
    def normalize_text(text: str, ignore_whitespace: str = "none", ignore_case: bool = False, regex_rules: Optional[List[Tuple[str, str]]] = None) -> List[str]:
        if regex_rules:
            for pattern, repl in regex_rules:
                try:
                    text = re.sub(pattern, repl, text)
                except re.error:
                    pass

        lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        normalized = []
        for line in lines:
            cur = line
            if ignore_case:
                cur = cur.lower()
            if ignore_whitespace == "all":
                cur = re.sub(r'\s+', '', cur)
            elif ignore_whitespace == "leading_trailing":
                cur = cur.strip()
            normalized.append(cur)
        return normalized

    @classmethod
    def compute_2way_diff(
        cls,
        left_text: str,
        right_text: str,
        ignore_whitespace: str = "none",
        ignore_case: bool = False,
        regex_rules: Optional[List[Tuple[str, str]]] = None,
        detect_moved: bool = True,
        ast_semantic: bool = False,
        language: str = "python"
    ) -> Tuple[List[DiffChunk], List[str], List[str]]:
        left_raw = left_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        right_raw = right_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')

        left_norm = cls.normalize_text(left_text, ignore_whitespace, ignore_case, regex_rules)
        right_norm = cls.normalize_text(right_text, ignore_whitespace, ignore_case, regex_rules)

        matcher = difflib.SequenceMatcher(None, left_norm, right_norm)
        opcodes = matcher.get_opcodes()

        chunks: List[DiffChunk] = []
        for tag, i1, i2, j1, j2 in opcodes:
            chunk = DiffChunk(
                tag=tag,
                left_start=i1,
                left_end=i2,
                right_start=j1,
                right_end=j2
            )
            if tag == 'replace':
                cls._compute_intraline_spans(chunk, left_raw[i1:i2], right_raw[j1:j2])
            chunks.append(chunk)

        if detect_moved:
            cls.detect_moved_blocks(chunks, left_raw, right_raw)

        if ast_semantic:
            cls.apply_ast_semantic_diff(chunks, left_text, right_text, language)

        return chunks, left_raw, right_raw

    @classmethod
    def strip_section_number(cls, s: str) -> str:
        """Strips leading markdown heading tokens and section numbers (e.g. '### 8.2 ...')."""
        return re.sub(r'^[#\s]*\d+(\.\d+)*\s*', '', s.strip()).lower().strip()

    @classmethod
    def align_replace_block(cls, l_lines: List[str], r_lines: List[str]) -> List[Tuple[Optional[int], Optional[int]]]:
        """
        Dynamically aligns sub-lines within a replace block using Needleman-Wunsch
        alignment with section/header normalization.
        Prevents cascading alignment mismatches when sections are inserted or renumbered.
        """
        M = len(l_lines)
        N = len(r_lines)
        if M == 1 and N == 1:
            return [(0, 0)]
        if M == 0:
            return [(None, j) for j in range(N)]
        if N == 0:
            return [(i, None) for i in range(M)]

        if M > 250 or N > 250:
            max_len = max(M, N)
            return [(k if k < M else None, k if k < N else None) for k in range(max_len)]

        def line_sim(l: str, r: str) -> float:
            if l == r:
                return 1.0
            ls = l.strip()
            rs = r.strip()
            if not ls and not rs:
                return 1.0
            if not ls or not rs:
                return 0.0
            r1 = difflib.SequenceMatcher(None, ls, rs).ratio()
            r2 = difflib.SequenceMatcher(None, cls.strip_section_number(l), cls.strip_section_number(r)).ratio()
            return max(r1, r2)

        gap_penalty = -0.2
        dp = [[0.0] * (N + 1) for _ in range(M + 1)]
        for i in range(1, M + 1):
            dp[i][0] = i * gap_penalty
        for j in range(1, N + 1):
            dp[0][j] = j * gap_penalty

        for i in range(1, M + 1):
            l = l_lines[i - 1]
            for j in range(1, N + 1):
                r = r_lines[j - 1]
                sim = line_sim(l, r)
                if sim >= 0.4:
                    match_score = (sim - 0.3) * 2.0
                else:
                    match_score = -0.6

                diag = dp[i - 1][j - 1] + match_score
                up = dp[i - 1][j] + gap_penalty
                left = dp[i][j - 1] + gap_penalty
                dp[i][j] = max(diag, up, left)

        i = M
        j = N
        pairs = []
        while i > 0 or j > 0:
            if i > 0 and j > 0:
                l = l_lines[i - 1]
                r = r_lines[j - 1]
                sim = line_sim(l, r)
                match_score = (sim - 0.3) * 2.0 if sim >= 0.4 else -0.6
                if abs(dp[i][j] - (dp[i - 1][j - 1] + match_score)) < 1e-6:
                    pairs.append((i - 1, j - 1))
                    i -= 1
                    j -= 1
                    continue
            if i > 0 and abs(dp[i][j] - (dp[i - 1][j] + gap_penalty)) < 1e-6:
                pairs.append((i - 1, None))
                i -= 1
            else:
                pairs.append((None, j - 1))
                j -= 1

        pairs.reverse()
        return pairs

    @classmethod
    def _compute_line_intraline(cls, l_line: str, r_line: str) -> Tuple[List[CharDiffSpan], List[CharDiffSpan]]:
        left_spans: List[CharDiffSpan] = []
        right_spans: List[CharDiffSpan] = []

        if DMP:
            diffs = DMP.diff_main(l_line, r_line)
            DMP.diff_cleanupSemantic(diffs)
            l_cursor = 0
            r_cursor = 0
            for op, data in diffs:
                length = len(data)
                if op == -1:
                    left_spans.append(CharDiffSpan(op=-1, text=data, start=l_cursor, end=l_cursor + length))
                    l_cursor += length
                elif op == 1:
                    right_spans.append(CharDiffSpan(op=1, text=data, start=r_cursor, end=r_cursor + length))
                    r_cursor += length
                else:
                    l_cursor += length
                    r_cursor += length
        else:
            s = difflib.SequenceMatcher(None, l_line, r_line)
            for op, li1, li2, ri1, ri2 in s.get_opcodes():
                if op in ('delete', 'replace'):
                    left_spans.append(CharDiffSpan(op=-1, text=l_line[li1:li2], start=li1, end=li2))
                if op in ('insert', 'replace'):
                    right_spans.append(CharDiffSpan(op=1, text=r_line[ri1:ri2], start=ri1, end=ri2))

        return left_spans, right_spans

    @classmethod
    def build_aligned_diff(
        cls,
        left_text: str,
        right_text: str,
        ignore_whitespace: str = "none",
        ignore_case: bool = False,
        regex_rules: Optional[List[Tuple[str, str]]] = None,
        detect_moved: bool = True,
        ast_semantic: bool = False,
        language: str = "python",
        manual_alignments: Optional[List[Tuple[int, int]]] = None
    ) -> AlignedDiffResult:
        """
        Builds perfectly aligned side-by-side lines with spacer padding.
        Ensures row N in Left is horizontally aligned to row N in Right.
        Supports manual alignment anchors [(left_line_1idx, right_line_1idx), ...]
        and automatic sub-block alignment to prevent cascading misalignments.
        """
        left_raw = left_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        right_raw = right_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')

        def build_slice(l_slice: List[str], r_slice: List[str], start_l_real: int, start_r_real: int, cur_disp_row: int):
            slice_l_text = "\n".join(l_slice)
            slice_r_text = "\n".join(r_slice)
            chunks, _, _ = cls.compute_2way_diff(
                slice_l_text, slice_r_text, ignore_whitespace, ignore_case, regex_rules,
                detect_moved=detect_moved, ast_semantic=ast_semantic, language=language
            )

            l_disp: List[str] = []
            r_disp: List[str] = []
            l_spacers: Set[int] = set()
            r_spacers: Set[int] = set()
            l_nums: Dict[int, int] = {}
            r_nums: Dict[int, int] = {}
            aligned_chunks: List[DiffChunk] = []

            l_counter = start_l_real
            r_counter = start_r_real
            row = cur_disp_row

            for chunk in chunks:
                tag = chunk.tag
                sub_l = l_slice[chunk.left_start:chunk.left_end]
                sub_r = r_slice[chunk.right_start:chunk.right_end]
                c_start = row
                c_left_spans: Dict[int, List[CharDiffSpan]] = {}
                c_right_spans: Dict[int, List[CharDiffSpan]] = {}

                if tag == 'equal':
                    for line in sub_l:
                        l_disp.append(line)
                        r_disp.append(line)
                        l_nums[row] = l_counter
                        r_nums[row] = r_counter
                        l_counter += 1
                        r_counter += 1
                        row += 1

                elif tag == 'replace':
                    pairs = cls.align_replace_block(sub_l, sub_r)
                    for li, ri in pairs:
                        line_l = sub_l[li] if li is not None else ""
                        line_r = sub_r[ri] if ri is not None else ""

                        if li is not None:
                            l_disp.append(line_l)
                            l_nums[row] = l_counter
                            l_counter += 1
                        else:
                            l_disp.append("")
                            l_spacers.add(row)

                        if ri is not None:
                            r_disp.append(line_r)
                            r_nums[row] = r_counter
                            r_counter += 1
                        else:
                            r_disp.append("")
                            r_spacers.add(row)

                        if li is not None and ri is not None and line_l != line_r:
                            sp_l, sp_r = cls._compute_line_intraline(line_l, line_r)
                            rel_k = row - c_start
                            if sp_l:
                                c_left_spans[rel_k] = sp_l
                            if sp_r:
                                c_right_spans[rel_k] = sp_r

                        row += 1

                elif tag == 'delete':
                    for line in sub_l:
                        l_disp.append(line)
                        r_disp.append("")
                        l_nums[row] = l_counter
                        r_spacers.add(row)
                        l_counter += 1
                        row += 1

                elif tag == 'insert':
                    for line in sub_r:
                        l_disp.append("")
                        r_disp.append(line)
                        l_spacers.add(row)
                        r_nums[row] = r_counter
                        r_counter += 1
                        row += 1

                aligned_chunks.append(DiffChunk(
                    tag=tag,
                    left_start=c_start,
                    left_end=row,
                    right_start=c_start,
                    right_end=row,
                    left_char_spans=c_left_spans,
                    right_char_spans=c_right_spans,
                    is_moved=chunk.is_moved,
                    moved_partner_chunk_idx=chunk.moved_partner_chunk_idx,
                    moved_to_line=chunk.moved_to_line,
                    semantic_match_info=chunk.semantic_match_info
                ))

            return l_disp, r_disp, l_spacers, r_spacers, l_nums, r_nums, aligned_chunks, l_counter, r_counter, row

        valid_anchors = []
        if manual_alignments:
            valid_anchors = sorted(
                [(l, r) for l, r in manual_alignments if 1 <= l <= len(left_raw) and 1 <= r <= len(right_raw)],
                key=lambda x: x[0]
            )

        if not valid_anchors:
            ld, rd, ls, rs, ln, rn, ac, _, _, _ = build_slice(left_raw, right_raw, 1, 1, 0)
            return AlignedDiffResult(
                left_display_lines=ld,
                right_display_lines=rd,
                left_spacers=ls,
                right_spacers=rs,
                left_line_numbers=ln,
                right_line_numbers=rn,
                chunks=ac,
                raw_left_text=left_text,
                raw_right_text=right_text
            )

        # Multi-segment anchor partitioning
        all_ld: List[str] = []
        all_rd: List[str] = []
        all_ls: Set[int] = set()
        all_rs: Set[int] = set()
        all_ln: Dict[int, int] = {}
        all_rn: Dict[int, int] = {}
        all_chunks: List[DiffChunk] = []

        cur_row = 0
        cur_l_real = 1
        cur_r_real = 1
        prev_l = 0
        prev_r = 0

        for l_anc, r_anc in valid_anchors:
            l_idx = l_anc - 1
            r_idx = r_anc - 1
            seg_l = left_raw[prev_l:l_idx]
            seg_r = right_raw[prev_r:r_idx]

            ld, rd, ls, rs, ln, rn, ac, cur_l_real, cur_r_real, cur_row = build_slice(
                seg_l, seg_r, cur_l_real, cur_r_real, cur_row
            )
            all_ld.extend(ld)
            all_rd.extend(rd)
            all_ls.update(ls)
            all_rs.update(rs)
            all_ln.update(ln)
            all_rn.update(rn)
            all_chunks.extend(ac)

            # Pad spacers above anchor so left and right meet at the exact same row
            diff_len = len(all_ld) - len(all_rd)
            if diff_len > 0:
                for _ in range(diff_len):
                    all_rd.append("")
                    all_rs.add(cur_row)
                    cur_row += 1
            elif diff_len < 0:
                for _ in range(abs(diff_len)):
                    all_ld.append("")
                    all_ls.add(cur_row)
                    cur_row += 1

            # Emit anchor row
            anchor_l_line = left_raw[l_idx]
            anchor_r_line = right_raw[r_idx]
            all_ld.append(anchor_l_line)
            all_rd.append(anchor_r_line)
            all_ln[cur_row] = l_anc
            all_rn[cur_row] = r_anc

            tag = 'equal' if anchor_l_line == anchor_r_line else 'replace'
            anc_l_spans = {}
            anc_r_spans = {}
            if tag == 'replace':
                sp_l, sp_r = cls._compute_line_intraline(anchor_l_line, anchor_r_line)
                if sp_l: anc_l_spans[0] = sp_l
                if sp_r: anc_r_spans[0] = sp_r

            all_chunks.append(DiffChunk(
                tag=tag,
                left_start=cur_row,
                left_end=cur_row + 1,
                right_start=cur_row,
                right_end=cur_row + 1,
                left_char_spans=anc_l_spans,
                right_char_spans=anc_r_spans
            ))
            cur_row += 1
            cur_l_real = l_anc + 1
            cur_r_real = r_anc + 1
            prev_l = l_idx + 1
            prev_r = r_idx + 1

        # Final segment
        seg_l = left_raw[prev_l:]
        seg_r = right_raw[prev_r:]
        ld, rd, ls, rs, ln, rn, ac, _, _, _ = build_slice(
            seg_l, seg_r, cur_l_real, cur_r_real, cur_row
        )
        all_ld.extend(ld)
        all_rd.extend(rd)
        all_ls.update(ls)
        all_rs.update(rs)
        all_ln.update(ln)
        all_rn.update(rn)
        all_chunks.extend(ac)

        return AlignedDiffResult(
            left_display_lines=all_ld,
            right_display_lines=all_rd,
            left_spacers=all_ls,
            right_spacers=all_rs,
            left_line_numbers=all_ln,
            right_line_numbers=all_rn,
            chunks=all_chunks,
            raw_left_text=left_text,
            raw_right_text=right_text
        )

    @classmethod
    def _compute_intraline_spans(cls, chunk: DiffChunk, left_lines: List[str], right_lines: List[str]):
        max_lines = max(len(left_lines), len(right_lines))
        for k in range(max_lines):
            l_line = left_lines[k] if k < len(left_lines) else ""
            r_line = right_lines[k] if k < len(right_lines) else ""

            if DMP:
                diffs = DMP.diff_main(l_line, r_line)
                DMP.diff_cleanupSemantic(diffs)
                
                left_spans: List[CharDiffSpan] = []
                right_spans: List[CharDiffSpan] = []
                l_cursor = 0
                r_cursor = 0
                for op, data in diffs:
                    length = len(data)
                    if op == -1:
                        left_spans.append(CharDiffSpan(op=-1, text=data, start=l_cursor, end=l_cursor + length))
                        l_cursor += length
                    elif op == 1:
                        right_spans.append(CharDiffSpan(op=1, text=data, start=r_cursor, end=r_cursor + length))
                        r_cursor += length
                    else:
                        l_cursor += length
                        r_cursor += length

                if k < len(left_lines) and left_spans:
                    chunk.left_char_spans[k] = left_spans
                if k < len(right_lines) and right_spans:
                    chunk.right_char_spans[k] = right_spans
            else:
                s = difflib.SequenceMatcher(None, l_line, r_line)
                left_spans = []
                right_spans = []
                for op, li1, li2, ri1, ri2 in s.get_opcodes():
                    if op in ('delete', 'replace') and k < len(left_lines):
                        left_spans.append(CharDiffSpan(op=-1, text=l_line[li1:li2], start=li1, end=li2))
                    if op in ('insert', 'replace') and k < len(right_lines):
                        right_spans.append(CharDiffSpan(op=1, text=r_line[ri1:ri2], start=ri1, end=ri2))
                if left_spans:
                    chunk.left_char_spans[k] = left_spans
                if right_spans:
                    chunk.right_char_spans[k] = right_spans

    @classmethod
    def compute_3way_merge(cls, base_text: str, left_text: str, right_text: str) -> List[MergeConflictChunk]:
        base_lines = base_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        left_lines = left_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        right_lines = right_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')

        s_left = difflib.SequenceMatcher(None, base_lines, left_lines)
        s_right = difflib.SequenceMatcher(None, base_lines, right_lines)

        left_ops = list(s_left.get_opcodes())
        right_ops = list(s_right.get_opcodes())

        merge_chunks: List[MergeConflictChunk] = []

        if left_text == right_text:
            return [MergeConflictChunk(
                is_conflict=False,
                base_lines=base_lines,
                left_lines=left_lines,
                right_lines=right_lines,
                resolved_lines=left_lines,
                resolution_state="auto"
            )]

        b_pos = 0
        while b_pos < len(base_lines):
            l_op = next((op for op in left_ops if op[1] <= b_pos < op[2]), None)
            r_op = next((op for op in right_ops if op[1] <= b_pos < op[2]), None)

            if not l_op and not r_op:
                merge_chunks.append(MergeConflictChunk(
                    is_conflict=False,
                    base_lines=[base_lines[b_pos]],
                    left_lines=[base_lines[b_pos]],
                    right_lines=[base_lines[b_pos]],
                    resolved_lines=[base_lines[b_pos]],
                    resolution_state="auto"
                ))
                b_pos += 1
                continue

            b_end = max(l_op[2] if l_op else b_pos + 1, r_op[2] if r_op else b_pos + 1)
            cur_base = base_lines[b_pos:b_end]
            cur_left = left_lines[l_op[3]:l_op[4]] if l_op else cur_base
            cur_right = right_lines[r_op[3]:r_op[4]] if r_op else cur_base

            if cur_left == cur_right:
                merge_chunks.append(MergeConflictChunk(
                    is_conflict=False,
                    base_lines=cur_base,
                    left_lines=cur_left,
                    right_lines=cur_right,
                    resolved_lines=cur_left,
                    resolution_state="auto"
                ))
            elif cur_left == cur_base and cur_right != cur_base:
                merge_chunks.append(MergeConflictChunk(
                    is_conflict=False,
                    base_lines=cur_base,
                    left_lines=cur_left,
                    right_lines=cur_right,
                    resolved_lines=cur_right,
                    resolution_state="auto"
                ))
            elif cur_right == cur_base and cur_left != cur_base:
                merge_chunks.append(MergeConflictChunk(
                    is_conflict=False,
                    base_lines=cur_base,
                    left_lines=cur_left,
                    right_lines=cur_right,
                    resolved_lines=cur_left,
                    resolution_state="auto"
                ))
            else:
                merge_chunks.append(MergeConflictChunk(
                    is_conflict=True,
                    base_lines=cur_base,
                    left_lines=cur_left,
                    right_lines=cur_right,
                    resolved_lines=[],
                    resolution_state="unresolved"
                ))

            b_pos = b_end

        l_tail = [op for op in left_ops if op[1] >= len(base_lines) and op[0] == 'insert']
        r_tail = [op for op in right_ops if op[1] >= len(base_lines) and op[0] == 'insert']
        for op in l_tail:
            merge_chunks.append(MergeConflictChunk(
                is_conflict=False,
                base_lines=[],
                left_lines=left_lines[op[3]:op[4]],
                right_lines=[],
                resolved_lines=left_lines[op[3]:op[4]],
                resolution_state="auto"
            ))
        for op in r_tail:
            merge_chunks.append(MergeConflictChunk(
                is_conflict=False,
                base_lines=[],
                left_lines=[],
                right_lines=right_lines[op[3]:op[4]],
                resolved_lines=right_lines[op[3]:op[4]],
                resolution_state="auto"
            ))

        return merge_chunks

    @classmethod
    def detect_moved_blocks(
        cls,
        chunks: List[DiffChunk],
        left_raw: List[str],
        right_raw: List[str],
        min_lines: int = 1,
        similarity_threshold: float = 0.75
    ):
        """
        Identifies code/text blocks that were moved across the document.
        Pairs delete chunks on the left with insert chunks on the right that have
        matching or highly similar content, marking them as 'moved'.
        Normalizes section numbers to recognize renumbered headings.
        """
        delete_chunks = [(idx, c) for idx, c in enumerate(chunks) if c.tag == 'delete' and (c.left_end - c.left_start) >= min_lines]
        insert_chunks = [(idx, c) for idx, c in enumerate(chunks) if c.tag == 'insert' and (c.right_end - c.right_start) >= min_lines]

        for d_idx, d_chunk in delete_chunks:
            if d_chunk.is_moved:
                continue
            d_text = "\n".join(left_raw[d_chunk.left_start:d_chunk.left_end]).strip()
            if not d_text:
                continue

            best_match_idx = None
            best_sim = 0.0

            d_norm = "\n".join([cls.strip_section_number(l) for l in left_raw[d_chunk.left_start:d_chunk.left_end]]).strip()

            for i_idx, i_chunk in insert_chunks:
                if i_chunk.is_moved:
                    continue
                i_text = "\n".join(right_raw[i_chunk.right_start:i_chunk.right_end]).strip()
                if not i_text:
                    continue

                if d_text == i_text:
                    best_match_idx = i_idx
                    best_sim = 1.0
                    break

                matcher_raw = difflib.SequenceMatcher(None, d_text, i_text)
                sim_raw = matcher_raw.ratio()

                i_norm = "\n".join([cls.strip_section_number(l) for l in right_raw[i_chunk.right_start:i_chunk.right_end]]).strip()
                matcher_norm = difflib.SequenceMatcher(None, d_norm, i_norm)
                sim_norm = matcher_norm.ratio()

                sim = max(sim_raw, sim_norm)

                if sim >= similarity_threshold and sim > best_sim:
                    best_sim = sim
                    best_match_idx = i_idx

            if best_match_idx is not None and best_sim >= similarity_threshold:
                i_chunk = chunks[best_match_idx]
                d_chunk.tag = 'moved'
                d_chunk.is_moved = True
                d_chunk.moved_partner_chunk_idx = best_match_idx
                d_chunk.moved_to_line = i_chunk.right_start + 1

                i_chunk.tag = 'moved'
                i_chunk.is_moved = True
                i_chunk.moved_partner_chunk_idx = d_idx
                i_chunk.moved_to_line = d_chunk.left_start + 1

    @classmethod
    def apply_ast_semantic_diff(
        cls,
        chunks: List[DiffChunk],
        left_text: str,
        right_text: str,
        language: str = "python"
    ):
        """
        Uses Tree-sitter / AST semantic parsing to detect reordered functions/classes
        and docstring-only updates, annotating chunks and eliminating false-positive diffs.
        """
        try:
            matches = ASTSemanticDiffer.compare_semantics(left_text, right_text, language)
            for m in matches:
                if m.status in ("reordered", "docstring_only"):
                    l_sym = m.left_symbol
                    r_sym = m.right_symbol
                    if l_sym and r_sym:
                        matching_delete = None
                        matching_insert = None
                        for idx, c in enumerate(chunks):
                            if c.tag in ('delete', 'replace', 'moved') and not (c.left_end <= l_sym.start_line or c.left_start >= l_sym.end_line):
                                matching_delete = (idx, c)
                            if c.tag in ('insert', 'replace', 'moved') and not (c.right_end <= r_sym.start_line or c.right_start >= r_sym.end_line):
                                matching_insert = (idx, c)

                        if matching_delete and matching_insert:
                            d_idx, d_c = matching_delete
                            i_idx, i_c = matching_insert
                            d_c.tag = 'moved'
                            d_c.is_moved = True
                            d_c.moved_partner_chunk_idx = i_idx
                            d_c.moved_to_line = r_sym.start_line + 1
                            d_c.semantic_match_info = m.explanation

                            i_c.tag = 'moved'
                            i_c.is_moved = True
                            i_c.moved_partner_chunk_idx = d_idx
                            i_c.moved_to_line = l_sym.start_line + 1
                            i_c.semantic_match_info = m.explanation
        except Exception:
            pass

    @staticmethod
    def normalize_ast(code: str, language: str = "python") -> str:
        """
        Structural AST normalization. Strips formatting variations, comments,
        quote differences and standardizes indentation.
        """
        lang = language.lower()
        if lang == "python":
            try:
                import ast
                tree = ast.parse(code)
                return ast.unparse(tree)
            except Exception:
                return code
        elif lang in ("json", "yaml"):
            try:
                import json
                data = json.loads(code)
                return json.dumps(data, indent=2, sort_keys=True)
            except Exception:
                return code
        return code

    @staticmethod
    def generate_unified_patch(
        left_text: str,
        right_text: str,
        left_filename: str = "a/file",
        right_filename: str = "b/file"
    ) -> str:
        """Generates standard POSIX / Git unified diff patch format."""
        left_lines = left_text.replace('\r\n', '\n').replace('\r', '\n').splitlines(keepends=True)
        right_lines = right_text.replace('\r\n', '\n').replace('\r', '\n').splitlines(keepends=True)
        left_lines = [l if l.endswith('\n') else l + '\n' for l in left_lines]
        right_lines = [r if r.endswith('\n') else r + '\n' for r in right_lines]
        diff = difflib.unified_diff(
            left_lines, right_lines,
            fromfile=left_filename,
            tofile=right_filename
        )
        return "".join(diff)

    @staticmethod
    def hash_file(filepath: str, algo: str = 'sha256') -> Optional[str]:
        """
        High-performance file hashing supporting sha256, md5, sha1, and crc32.
        Uses mmap for files > 10MB to achieve native NVMe streaming speeds.
        """
        try:
            size = os.path.getsize(filepath)
            if size == 0:
                return "0" * (64 if algo == 'sha256' else 32)

            if algo.lower() in ('blake3', 'b3') and HAS_BLAKE3:
                hasher = blake3.blake3(max_threads=blake3.blake3.AUTO)
                with open(filepath, 'rb') as f:
                    if size > 10 * 1024 * 1024:
                        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                            hasher.update(mm)
                    else:
                        for chunk in iter(lambda: f.read(262144), b""):
                            hasher.update(chunk)
                return hasher.hexdigest()

            if algo.lower() == 'crc32':
                crc = 0
                with open(filepath, 'rb') as f:
                    for chunk in iter(lambda: f.read(1048576), b""):
                        crc = zlib.crc32(chunk, crc)
                return f"{crc & 0xffffffff:08x}"

            h = hashlib.new(algo)
            with open(filepath, 'rb') as f:
                if size > 10 * 1024 * 1024:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        h.update(mm)
                else:
                    for chunk in iter(lambda: f.read(65536), b""):
                        h.update(chunk)
            return h.hexdigest()
        except Exception:
            return None

    @staticmethod
    def compare_files_metadata(file1: str, file2: str) -> Optional[Dict[str, Any]]:
        try:
            s1 = os.stat(file1)
            s2 = os.stat(file2)
            return {
                'size_match': s1.st_size == s2.st_size,
                'time_match': abs(s1.st_mtime - s2.st_mtime) < 1.0,
                'size1': s1.st_size,
                'size2': s2.st_size,
                'mtime1': s1.st_mtime,
                'mtime2': s2.st_mtime,
            }
        except Exception:
            return None

