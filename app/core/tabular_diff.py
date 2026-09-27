"""
Tabular and Spreadsheet Diff Engine (CSV, TSV, Excel)
Features:
- Keyed row alignment (designate a Primary Key column to match rows despite reordering).
- Cell-level mutation detection.
- Column header alignment.
- Support for CSV, TSV, and Excel (.xlsx).
"""

import csv
import io
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Set


@dataclass
class CellDiff:
    col_idx: int
    col_name: str
    left_val: str
    right_val: str
    status: str  # 'equal', 'modified'


@dataclass
class RowDiff:
    row_key: str
    status: str  # 'equal', 'modified', 'added', 'deleted'
    left_row_idx: Optional[int]
    right_row_idx: Optional[int]
    left_cells: List[str]
    right_cells: List[str]
    modified_cols: Set[int] = field(default_factory=set)


@dataclass
class TabularDiffResult:
    headers: List[str]
    rows: List[RowDiff]
    total_rows: int
    added_count: int
    deleted_count: int
    modified_count: int
    equal_count: int
    key_column: Optional[str]


class TabularDiffEngine:
    """Core evaluation engine for tabular CSV, TSV, and spreadsheet data."""

    @classmethod
    def load_table(cls, path_or_content: str, delimiter: str = "auto", table_name: Optional[str] = None) -> Tuple[List[str], List[List[str]]]:
        """Loads a table from a file path (CSV, TSV, Excel, Parquet, SQLite) or raw text string."""
        if os.path.exists(path_or_content):
            ext = os.path.splitext(path_or_content)[1].lower()
            if ext in (".xlsx", ".xlsm", ".xltx"):
                return cls._load_excel(path_or_content)
            elif ext == ".parquet":
                return cls._load_parquet(path_or_content)
            elif ext in (".db", ".sqlite", ".sqlite3"):
                return cls._load_sqlite(path_or_content, table_name)
            with open(path_or_content, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        else:
            content = path_or_content

        # Determine delimiter
        if delimiter == "auto":
            first_line = content.splitlines()[0] if content else ""
            if "\t" in first_line:
                delimiter = "\t"
            elif ";" in first_line and "," not in first_line:
                delimiter = ";"
            else:
                delimiter = ","

        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        raw_rows = list(reader)
        if not raw_rows:
            return [], []

        headers = raw_rows[0]
        rows = raw_rows[1:]
        return headers, rows

    @staticmethod
    def _load_excel(filepath: str) -> Tuple[List[str], List[List[str]]]:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
            sheet = wb.active
            rows = []
            for row in sheet.iter_rows(values_only=True):
                str_row = ["" if v is None else str(v) for v in row]
                rows.append(str_row)
            if not rows:
                return [], []
            return rows[0], rows[1:]
        except Exception:
            return ["Column1"], [["Error loading Excel file"]]

    @staticmethod
    def _load_parquet(filepath: str) -> Tuple[List[str], List[List[str]]]:
        try:
            import pyarrow.parquet as pq
            pf = pq.ParquetFile(filepath)
            schema = pf.schema_arrow
            headers = [str(field.name) for field in schema]

            rows = []
            max_rows = 50000  # Cap table viewport at 50,000 rows to keep UI responsive
            # Stream record batches with batch_size=5000
            for batch in pf.iter_batches(batch_size=5000, columns=headers):
                pydict = batch.to_pydict()
                batch_len = len(next(iter(pydict.values()))) if pydict else 0
                for i in range(batch_len):
                    row = ["" if pydict[h][i] is None else str(pydict[h][i]) for h in headers]
                    rows.append(row)
                    if len(rows) >= max_rows:
                        break
                if len(rows) >= max_rows:
                    break
            return headers, rows
        except Exception as e:
            return ["Column1"], [[f"Error loading Parquet file: {e}"]]

    @staticmethod
    def list_sqlite_tables(filepath: str) -> List[str]:
        try:
            import sqlite3
            conn = sqlite3.connect(filepath)
            try:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                tables = [r[0] for r in cur.fetchall()]
                return tables
            finally:
                conn.close()
        except Exception:
            return []

    @staticmethod
    def _load_sqlite(filepath: str, table_name: Optional[str] = None) -> Tuple[List[str], List[List[str]]]:
        try:
            import sqlite3
            conn = sqlite3.connect(filepath)
            try:
                cur = conn.cursor()
                tables = TabularDiffEngine.list_sqlite_tables(filepath)
                if not tables:
                    return ["Table"], [["No user tables found in database"]]
                target_table = table_name if (table_name and table_name in tables) else tables[0]
                # Safely escape closing brackets in SQLite identifiers
                escaped_table = target_table.replace("]", "]]")

                # Check PRAGMA table_info to inspect column names & types safely
                cur.execute(f"PRAGMA table_info([{escaped_table}])")  # nosec B608
                info = cur.fetchall()
                if info:
                    headers = [str(col[1]) for col in info]
                else:
                    headers = ["Col 1"]

                # Stream records using cursor fetchmany in chunks of 5,000
                cur.execute(f"SELECT * FROM [{escaped_table}]")  # nosec B608
                rows = []
                max_rows = 50000
                while len(rows) < max_rows:
                    batch = cur.fetchmany(5000)
                    if not batch:
                        break
                    for r in batch:
                        rows.append([str(v) if v is not None else "" for v in r])
                        if len(rows) >= max_rows:
                            break
                return headers, rows
            finally:
                conn.close()
        except Exception as e:
            return ["Column1"], [[f"Error loading SQLite table: {e}"]]

    @staticmethod
    def _are_cells_equal(v1: str, v2: str, float_tolerance: float = 0.0, ignore_case: bool = False) -> bool:
        if v1 == v2:
            return True
        if ignore_case and v1.lower() == v2.lower():
            return True
        if float_tolerance > 0.0:
            try:
                f1 = float(v1)
                f2 = float(v2)
                if abs(f1 - f2) <= float_tolerance:
                    return True
            except (ValueError, TypeError):
                pass
        return False

    @classmethod
    def compare_tables(
        cls,
        left_source: str,
        right_source: str,
        key_column: Optional[str] = None,
        delimiter: str = "auto",
        ignore_case: bool = False,
        float_tolerance: float = 0.0
    ) -> TabularDiffResult:
        """
        Performs tabular comparison with optional primary key alignment and numerical float tolerance.
        """
        l_headers, l_rows = cls.load_table(left_source, delimiter)
        r_headers, r_rows = cls.load_table(right_source, delimiter)

        # Combined headers
        all_headers = list(l_headers)
        for h in r_headers:
            if h not in all_headers:
                all_headers.append(h)
        if not all_headers:
            all_headers = ["Col 1"]

        # Find key column index
        l_key_idx = -1
        r_key_idx = -1
        if key_column:
            if key_column in l_headers:
                l_key_idx = l_headers.index(key_column)
            if key_column in r_headers:
                r_key_idx = r_headers.index(key_column)

        # If key column valid on both sides, do Keyed Alignment
        if l_key_idx != -1 and r_key_idx != -1:
            return cls._compare_keyed(
                l_headers, l_rows, l_key_idx,
                r_headers, r_rows, r_key_idx,
                all_headers, key_column, ignore_case, float_tolerance
            )
        else:
            return cls._compare_sequential(
                l_headers, l_rows,
                r_headers, r_rows,
                all_headers, ignore_case, float_tolerance
            )

    @classmethod
    def _compare_keyed(
        cls,
        l_headers: List[str],
        l_rows: List[List[str]],
        l_key_idx: int,
        r_headers: List[str],
        r_rows: List[List[str]],
        r_key_idx: int,
        all_headers: List[str],
        key_column: str,
        ignore_case: bool,
        float_tolerance: float = 0.0
    ) -> TabularDiffResult:
        l_map: Dict[str, Tuple[int, List[str]]] = {}
        for idx, row in enumerate(l_rows):
            k = row[l_key_idx] if l_key_idx < len(row) else f"_row_{idx}"
            if ignore_case:
                k = k.lower()
            l_map[k] = (idx, row)

        r_map: Dict[str, Tuple[int, List[str]]] = {}
        for idx, row in enumerate(r_rows):
            k = row[r_key_idx] if r_key_idx < len(row) else f"_row_{idx}"
            if ignore_case:
                k = k.lower()
            r_map[k] = (idx, row)

        # Union of keys preserving encounter order
        all_keys = list(l_map.keys())
        for k in r_map.keys():
            if k not in all_keys:
                all_keys.append(k)

        diff_rows: List[RowDiff] = []
        counts = {"added": 0, "deleted": 0, "modified": 0, "equal": 0}

        for k in all_keys:
            in_left = k in l_map
            in_right = k in r_map

            if in_left and not in_right:
                l_idx, l_r = l_map[k]
                l_norm = cls._align_row_to_headers(l_r, l_headers, all_headers)
                diff_rows.append(RowDiff(
                    row_key=k, status="deleted",
                    left_row_idx=l_idx, right_row_idx=None,
                    left_cells=l_norm, right_cells=[""] * len(all_headers)
                ))
                counts["deleted"] += 1

            elif in_right and not in_left:
                r_idx, r_r = r_map[k]
                r_norm = cls._align_row_to_headers(r_r, r_headers, all_headers)
                diff_rows.append(RowDiff(
                    row_key=k, status="added",
                    left_row_idx=None, right_row_idx=r_idx,
                    left_cells=[""] * len(all_headers), right_cells=r_norm
                ))
                counts["added"] += 1

            else:
                l_idx, l_r = l_map[k]
                r_idx, r_r = r_map[k]
                l_norm = cls._align_row_to_headers(l_r, l_headers, all_headers)
                r_norm = cls._align_row_to_headers(r_r, r_headers, all_headers)

                modified_cols = set()
                for c_idx in range(len(all_headers)):
                    v1 = l_norm[c_idx]
                    v2 = r_norm[c_idx]
                    if not cls._are_cells_equal(v1, v2, float_tolerance, ignore_case):
                        modified_cols.add(c_idx)

                status = "modified" if modified_cols else "equal"
                counts[status] += 1
                diff_rows.append(RowDiff(
                    row_key=k, status=status,
                    left_row_idx=l_idx, right_row_idx=r_idx,
                    left_cells=l_norm, right_cells=r_norm,
                    modified_cols=modified_cols
                ))

        return TabularDiffResult(
            headers=all_headers,
            rows=diff_rows,
            total_rows=len(diff_rows),
            added_count=counts["added"],
            deleted_count=counts["deleted"],
            modified_count=counts["modified"],
            equal_count=counts["equal"],
            key_column=key_column
        )

    @classmethod
    def _compare_sequential(
        cls,
        l_headers: List[str],
        l_rows: List[List[str]],
        r_headers: List[str],
        r_rows: List[List[str]],
        all_headers: List[str],
        ignore_case: bool,
        float_tolerance: float = 0.0
    ) -> TabularDiffResult:
        max_rows = max(len(l_rows), len(r_rows))
        diff_rows: List[RowDiff] = []
        counts = {"added": 0, "deleted": 0, "modified": 0, "equal": 0}

        for idx in range(max_rows):
            in_left = idx < len(l_rows)
            in_right = idx < len(r_rows)

            l_r = l_rows[idx] if in_left else []
            r_r = r_rows[idx] if in_right else []
            l_norm = cls._align_row_to_headers(l_r, l_headers, all_headers)
            r_norm = cls._align_row_to_headers(r_r, r_headers, all_headers)

            if in_left and not in_right:
                diff_rows.append(RowDiff(
                    row_key=f"Row {idx+1}", status="deleted",
                    left_row_idx=idx, right_row_idx=None,
                    left_cells=l_norm, right_cells=[""] * len(all_headers)
                ))
                counts["deleted"] += 1
            elif in_right and not in_left:
                diff_rows.append(RowDiff(
                    row_key=f"Row {idx+1}", status="added",
                    left_row_idx=None, right_row_idx=idx,
                    left_cells=[""] * len(all_headers), right_cells=r_norm
                ))
                counts["added"] += 1
            else:
                mod_cols = set()
                for c_idx in range(len(all_headers)):
                    v1, v2 = l_norm[c_idx], r_norm[c_idx]
                    if not cls._are_cells_equal(v1, v2, float_tolerance, ignore_case):
                        mod_cols.add(c_idx)

                st = "modified" if mod_cols else "equal"
                counts[st] += 1
                diff_rows.append(RowDiff(
                    row_key=f"Row {idx+1}", status=st,
                    left_row_idx=idx, right_row_idx=idx,
                    left_cells=l_norm, right_cells=r_norm,
                    modified_cols=mod_cols
                ))

        return TabularDiffResult(
            headers=all_headers,
            rows=diff_rows,
            total_rows=len(diff_rows),
            added_count=counts["added"],
            deleted_count=counts["deleted"],
            modified_count=counts["modified"],
            equal_count=counts["equal"],
            key_column=None
        )

    @staticmethod
    def _align_row_to_headers(row: List[str], row_headers: List[str], all_headers: List[str]) -> List[str]:
        aligned = []
        for h in all_headers:
            if h in row_headers:
                h_idx = row_headers.index(h)
                val = row[h_idx] if h_idx < len(row) else ""
            else:
                val = ""
            aligned.append(val)
        return aligned
