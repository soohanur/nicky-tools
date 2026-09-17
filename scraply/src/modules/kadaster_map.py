"""
Auto-detect the sheet, header row and owner/parcel columns of a kadaster export.

Uploads arrive in several shapes: one header row or a group-label row above it,
owner fields named `naam` / `Naam eigenaar` / `tenaamstellingen.0.naam`. Asking
the user to map nine columns by hand is error-prone, so we recognise them.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# field -> accepted header names, best first
CANDIDATES: Dict[str, List[str]] = {
    'company':      ['naam', 'Naam eigenaar', 'tenaamstellingen.0.naam',
                     '(Achter)naam - eigenaar 1', 'Achternaam - eigenaar 1'],
    'name_prefix':  ['voorvoegsel', 'Voorvoegsel eigenaar', 'tenaamstellingen.0.voorvoegsel',
                     'Voorvoegsel - achternaam 1'],
    'first_names':  ['voornamen', 'Voornaam eigenaar', 'tenaamstellingen.0.voornamen',
                     'Voornaam - eigenaar 1'],
    'street':       ['Straat', 'Straat eigenaar', 'tenaamstellingen.0.adressen.0.openbareRuimteNaam',
                     'Straat - eigenaar'],
    'house_number': ['Huisnummer', 'Huisnummer eigenaar', 'tenaamstellingen.0.adressen.0.huisnummer',
                     'Huisnummer - eigenaar'],
    'city':         ['Plaats', 'Plaats eigenaar', 'tenaamstellingen.0.adressen.0.plaats',
                     'Plaats - eigenaar'],
    'alt_street':   ['adressen_eerste_adres_straatnaam'],
    'alt_house':    ['adressen_eerste_adres_huisnummer'],
    'alt_city':     ['woonplaats', 'woonplaats (bestand)'],
}
REQUIRED = ('company',)
MAX_HEADER_ROW = 6          # how far down we look for the header row


def _norm(v: Any) -> str:
    return str(v).strip() if v is not None else ''


def _match(headers: List[str]) -> Dict[str, str]:
    """field -> actual header name present in this row."""
    lower = {h.lower(): h for h in headers if h}
    found = {}
    for field, names in CANDIDATES.items():
        for want in names:
            hit = lower.get(want.lower())
            if hit:
                found[field] = hit
                break
    return found


def detect(path, sheet: Optional[str] = None) -> Dict[str, Any]:
    """Return {sheet, header_row, fields, matched, columns, data_rows}."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheets = [sheet] if sheet else wb.sheetnames
        best = None
        for name in sheets:
            ws = wb[name]
            head = []
            for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
                head.append([_norm(v) for v in row])
                if i >= MAX_HEADER_ROW:
                    break
            for hr, headers in enumerate(head, start=1):
                fields = _match(headers)
                if not all(f in fields for f in REQUIRED):
                    continue
                named = sum(1 for h in headers if h)
                score = (len(fields), named)
                if best is None or score > best['score']:
                    best = {'sheet': name, 'header_row': hr, 'fields': fields,
                            'score': score, 'columns': named}
        if best is None:
            raise ValueError(
                "Could not find owner columns. Expected a column named one of: "
                + ", ".join(CANDIDATES['company'])
            )
        ws = wb[best['sheet']]
        best['data_rows'] = max(0, ws.max_row - best['header_row'])
        best['matched'] = len(best['fields'])
        best.pop('score')
        return best
    finally:
        wb.close()


def _read_csv_head(path, rows: int = MAX_HEADER_ROW) -> List[List[str]]:
    """First few rows of a CSV, tolerant about encoding and delimiter."""
    import csv as _csv

    for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1', 'iso-8859-1'):
        try:
            with open(path, 'r', encoding=enc, newline='') as f:
                sample = f.read(64 * 1024)
                f.seek(0)
                try:
                    dialect = _csv.Sniffer().sniff(sample, delimiters=',;\t|')
                except Exception:
                    dialect = _csv.excel
                reader = _csv.reader(f, dialect)
                out = []
                for i, row in enumerate(reader):
                    out.append([_norm(v) for v in row])
                    if i + 1 >= rows:
                        break
                return out
        except UnicodeDecodeError:
            continue
    return []


def detect_any(path, sheet: Optional[str] = None) -> Dict[str, Any]:
    """
    Detect header row + owner columns for EITHER a CSV or an Excel file.

    Returns {file_type, sheet, header_row, headers, fields, matched, data_rows}.
    `fields` is a suggestion: the UI shows it pre-filled and the user can change
    any of it before starting.
    """
    from pathlib import Path as _Path

    suffix = _Path(path).suffix.lower()
    if suffix in ('.xlsx', '.xlsm', '.xls'):
        det = detect(path, sheet=sheet)
        det['headers'] = headers_of(path, det['sheet'], det['header_row'])
        det['file_type'] = 'excel'
        return det

    head = _read_csv_head(path)
    if not head:
        raise ValueError('Could not read the file (encoding or format not recognised)')
    best = None
    for hr, headers in enumerate(head, start=1):
        fields = _match(headers)
        named = sum(1 for h in headers if h)
        score = (len(fields), named)
        if best is None or score > best[0]:
            best = (score, hr, headers, fields)
    _, hr, headers, fields = best
    # A CSV almost always has its header on row 1; only move down if that row
    # matched nothing and a later one did.
    if hr != 1 and not _match(head[0]):
        pass
    elif hr != 1:
        hr, headers, fields = 1, head[0], _match(head[0])
    return {'file_type': 'csv', 'sheet': None, 'header_row': hr,
            'headers': headers, 'fields': fields, 'matched': len(fields),
            'data_rows': 0}


def headers_of(path, sheet: str, header_row: int) -> List[str]:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[sheet]
        for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
            if i == header_row:
                return [_norm(v) for v in row]
        return []
    finally:
        wb.close()
