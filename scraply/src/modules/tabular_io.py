"""
Tabular I/O that preserves the caller's original file.

Why this exists
---------------
The original pipeline reads every input with `CSVReader` and writes a brand new
CSV built from a dict of column -> value. That has three consequences we need to
avoid for boss-ready output:

  1. `.xlsx` uploads are parsed as text and produce garbage (ExcelReader is
     disabled in scraply/src/modules/__init__.py).
  2. Duplicate header names collapse. Real kadaster exports contain `adres`
     twice and `adressen_verblijfsobjectidentificatie` three times, so a
     dict-keyed reader silently drops columns.
  3. All original formatting, column order and sheet structure is lost.

This module reads rows positionally (never by header name), keeps a stable
`row_index` on every row, and produces output by COPYING the original file and
appending new columns to it. Parallel workers may finish rows in any order -
results are written back by `row_index`, never by arrival order.
"""
from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..utils.logger import setup_logger

logger = setup_logger('tabular_io')

CSV_ENCODINGS = ['utf-8-sig', 'utf-8', 'cp1252', 'latin-1', 'iso-8859-1']

# Excel caps a cell at 32767 chars; stay well clear.
MAX_CELL_LEN = 3000


def _clean(value: Any) -> str:
    """Normalise a cell to a trimmed string. Ints stay int-looking."""
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    # 'NULL' placeholders from earlier tooling must not survive into output.
    return '' if text.upper() == 'NULL' else text


class TabularFile:
    """
    A read/write handle over a CSV or Excel input.

    Usage:
        tf = TabularFile(input_path)
        rows = tf.read_rows()              # each row: {'row_index': int, headers..., }
        ...
        tf.write_output(out_path, NEW_COLS, {row_index: {col: val}})
    """

    def __init__(self, path: Path, sheet: Optional[str] = None):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"File not found: {self.path}")
        self.suffix = self.path.suffix.lower()
        if self.suffix not in ('.csv', '.xlsx', '.xlsm', '.xls'):
            raise ValueError(f"Unsupported file type: {self.suffix}")
        self.sheet = sheet
        self.headers: List[str] = []
        self._encoding: Optional[str] = None
        self._dialect: Optional[Any] = None
        self._row_count = 0

    # ------------------------------------------------------------------ read

    def read_rows(self) -> List[Dict[str, Any]]:
        if self.suffix == '.csv':
            rows = self._read_csv()
        else:
            rows = self._read_excel()
        self._row_count = len(rows)
        logger.info(f"Read {len(rows)} rows, {len(self.headers)} columns from {self.path.name}")
        return rows

    def _read_csv(self) -> List[Dict[str, Any]]:
        last_err = None
        for enc in CSV_ENCODINGS:
            try:
                with open(self.path, 'r', encoding=enc, newline='') as f:
                    sample = f.read(64 * 1024)
                    f.seek(0)
                    try:
                        self._dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
                    except Exception:
                        self._dialect = csv.excel
                    reader = csv.reader(f, self._dialect)
                    raw = list(reader)
                self._encoding = enc
                break
            except UnicodeDecodeError as e:
                last_err = e
                continue
        else:
            raise ValueError(f"Could not decode {self.path}: {last_err}")

        if not raw:
            self.headers = []
            return []

        self.headers = [str(h).strip() for h in raw[0]]
        rows = []
        for i, values in enumerate(raw[1:]):
            rows.append(self._build_row(i, values))
        return rows

    def _read_excel(self) -> List[Dict[str, Any]]:
        import openpyxl
        wb = openpyxl.load_workbook(self.path, read_only=True, data_only=True)
        ws = wb[self.sheet] if self.sheet else wb[wb.sheetnames[0]]
        self.sheet = ws.title
        grid = list(ws.iter_rows(values_only=True))
        wb.close()
        if not grid:
            self.headers = []
            return []
        self.headers = [_clean(h) for h in grid[0]]
        rows = []
        for i, values in enumerate(grid[1:]):
            rows.append(self._build_row(i, list(values)))
        return rows

    def _build_row(self, index: int, values: Sequence[Any]) -> Dict[str, Any]:
        """
        Positional row. Duplicate header names are preserved by suffixing the
        later occurrences, so no column is ever silently dropped.
        """
        row: Dict[str, Any] = {'row_index': index}
        seen: Dict[str, int] = {}
        cells = []
        for col_i, header in enumerate(self.headers):
            val = _clean(values[col_i]) if col_i < len(values) else ''
            cells.append(val)
            key = header or f"column_{col_i + 1}"
            if key in seen:
                seen[key] += 1
                key = f"{key}__{seen[key]}"
            else:
                seen[key] = 0
            row[key] = val
        row['_cells'] = cells
        return row

    @staticmethod
    def is_blank(row: Dict[str, Any]) -> bool:
        return not any(c for c in row.get('_cells', []))

    # ----------------------------------------------------------------- write

    def write_output(
        self,
        out_path: Path,
        new_columns: List[str],
        results: Dict[int, Dict[str, Any]],
    ) -> int:
        """
        Copy the original file and append `new_columns`, filling each row from
        `results[row_index]`. Rows with no result are left blank (never 'NULL').

        Returns the number of rows populated.
        """
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if self.suffix == '.csv':
            return self._write_csv(out_path, new_columns, results)
        return self._write_excel(out_path, new_columns, results)

    def _write_csv(self, out_path: Path, new_columns, results) -> int:
        with open(self.path, 'r', encoding=self._encoding or 'utf-8-sig', newline='') as f:
            raw = list(csv.reader(f, self._dialect or csv.excel))
        if not raw:
            shutil.copyfile(self.path, out_path)
            return 0

        out = [raw[0] + list(new_columns)]
        filled = 0
        for i, values in enumerate(raw[1:]):
            res = results.get(i)
            extra = [_clean(res.get(c)) if res else '' for c in new_columns]
            if res:
                filled += 1
            out.append(list(values) + extra)

        with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
            csv.writer(f, lineterminator='\r\n').writerows(out)
        logger.info(f"Wrote CSV {out_path.name}: {filled} rows populated")
        return filled

    def _write_excel(self, out_path: Path, new_columns, results) -> int:
        """
        Copy the workbook so ALL original sheets, styles, column widths and
        number formats survive, then append the new columns to the data sheet.
        """
        import openpyxl
        from copy import copy
        from openpyxl.styles import Font

        shutil.copyfile(self.path, out_path)
        wb = openpyxl.load_workbook(out_path)
        ws = wb[self.sheet] if self.sheet in wb.sheetnames else wb[wb.sheetnames[0]]

        start = len(self.headers) + 1
        # Copy the sheet's OWN header style (fill + font + borders) onto the new
        # column headers so they look native — same yellow/bold/etc. as the rest
        # of the header row, instead of a plain pasted-on look.
        hdr_src = ws.cell(row=1, column=max(1, len(self.headers)))
        for j, name in enumerate(new_columns):
            c = ws.cell(row=1, column=start + j, value=name)
            try:
                if hdr_src.has_style:
                    c._style = copy(hdr_src._style)
                else:
                    c.font = Font(bold=True)
            except Exception:
                c.font = Font(bold=True)

        filled = 0
        for i in range(self._row_count):
            res = results.get(i)
            if not res:
                continue
            excel_row = i + 2                      # +1 header, +1 to 1-based
            for j, name in enumerate(new_columns):
                text = _clean(res.get(name))
                if len(text) > MAX_CELL_LEN:
                    text = text[:MAX_CELL_LEN]
                cell = ws.cell(row=excel_row, column=start + j)
                cell.value = text or None          # blank, never the string NULL
                if name.upper().startswith('NUMBER') and text:
                    cell.number_format = '@'       # keep leading zero on 06...
            filled += 1

        wb.save(out_path)
        logger.info(f"Wrote Excel {out_path.name}: {filled} rows populated, "
                    f"columns {start}..{start + len(new_columns) - 1}")
        return filled
