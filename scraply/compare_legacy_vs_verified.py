#!/usr/bin/env python3
"""
Diff what the legacy scraper delivered against what the verified pipeline can
actually prove, row by row, on the same 192 parcels.

    python3 scraply/compare_legacy_vs_verified.py LEGACY.csv VERIFIED.xlsx

Both files carry the same rows in the same order (same source export), so rows
are compared positionally and checked on the owner name before anything is
reported.
"""
from __future__ import annotations

import csv
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

LEGACY_COLS = ['NUMBER 1', 'NUMBER 2', 'EMAIL', 'BUSINESS_NAME', 'NOTE']
VERIFIED_COLS = ['NUMBER 1', 'NUMBER 2', 'EMAIL', 'COMPANY_FOUND', 'CONFIDENCE', 'SOURCE', 'EVIDENCE']
STOP = {'bv', 'b', 'v', 'vof', 'nv', 'n', 'cv', 'holding', 'beheer', 'de', 'den', 'der',
        'van', 'het', 'en', 'maatschap', 'stichting', 'exploitatie', 'vastgoed'}


def toks(s: str) -> set:
    s = unicodedata.normalize('NFKD', (s or '').lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return {t for t in re.sub(r'[^a-z0-9 ]', ' ', s).split() if len(t) > 2 and t not in STOP}


def read_legacy(path: Path):
    with open(path, encoding='utf-8-sig', newline='') as fh:
        rows = list(csv.reader(fh))
    hdr = rows[1]
    idx = {h: i for i, h in enumerate(hdr)}
    out = []
    for r in rows[2:]:
        get = lambda k: (r[idx[k]] or '').strip() if k in idx and idx[k] < len(r) else ''
        out.append({
            'owner': f"{get('Voorvoegsel - achternaam 1')} {get('(Achter)naam - eigenaar 1')}".strip(),
            'street': get('Straat - eigenaar'), 'house': get('Huisnummer - eigenaar'),
            'city': get('Plaats - eigenaar'),
            'num': get('NUMBER 1'), 'email': get('EMAIL'),
            'company': get('BUSINESS_NAME'), 'note': get('NOTE'),
        })
    return out


def read_verified(path: Path):
    import openpyxl
    ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [str(h).strip() if h is not None else '' for h in rows[1]]
    idx = {h: i for i, h in enumerate(hdr)}
    out = []
    for r in rows[2:]:
        if not any(v not in (None, '') for v in r):
            continue
        get = lambda k: str(r[idx[k]]).strip() if k in idx and idx[k] < len(r) and r[idx[k]] is not None else ''
        out.append({
            'owner': f"{get('Voorvoegsel - achternaam 1')} {get('(Achter)naam - eigenaar 1')}".strip(),
            'num': get('NUMBER 1'), 'email': get('EMAIL'),
            'company': get('COMPANY_FOUND'), 'conf': get('CONFIDENCE'),
            'source': get('SOURCE'), 'evidence': get('EVIDENCE'),
        })
    return out


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    leg = read_legacy(Path(sys.argv[1]))
    ver = read_verified(Path(sys.argv[2]))
    n = min(len(leg), len(ver))
    print(f"legacy rows {len(leg)} | verified rows {len(ver)} | comparing {n}")

    aligned = sum(1 for i in range(n) if toks(leg[i]['owner']) == toks(ver[i]['owner']))
    print(f"owner name identical on both sides: {aligned}/{n}"
          f"{'  (aligned)' if aligned == n else '  <-- ROWS DO NOT LINE UP'}")

    buckets = Counter()
    disagree = []
    for i in range(n):
        L, V = leg[i], ver[i]
        ln, vn = L['num'], V['num']
        owner = toks(L['owner'])
        if ln and vn:
            key = 'same number, both agree' if ln == vn else 'DIFFERENT number'
        elif ln and not vn:
            key = 'legacy had a number, verified refused it'
        elif vn and not ln:
            key = 'verified found one legacy missed'
        else:
            key = 'both empty'
        buckets[key] += 1
        if key in ('DIFFERENT number', 'legacy had a number, verified refused it'):
            disagree.append((i + 3, L['owner'], L['company'], ln, V['company'], vn,
                             V['conf'], (V['evidence'] or '')[:70], L['note'][:40]))

    print("\n=== row-by-row outcome ===")
    for k, v in buckets.most_common():
        print(f"  {v:4}  {k}")

    lnum = sum(1 for r in leg[:n] if r['num'])
    vnum = sum(1 for r in ver[:n] if r['num'])
    lok = sum(1 for r in leg[:n] if r['num'] and toks(r['owner']) & toks(r['company']))
    vok = sum(1 for r in ver[:n] if r['num'] and toks(r['owner']) & toks(r['company']))
    print("\n=== numbers delivered, and how many are attributable to the owner ===")
    print(f"  legacy   : {lnum:3} numbers | {lok:3} match the owner name ({lok/lnum*100:.0f}%)" if lnum else "  legacy: none")
    print(f"  verified : {vnum:3} numbers | {vok:3} match the owner name ({vok/vnum*100:.0f}%)" if vnum else "  verified: none")

    print("\n=== verified CONFIDENCE breakdown ===")
    for k, v in Counter(r['conf'] or '(blank)' for r in ver[:n]).most_common():
        print(f"  {v:4}  {k}")

    print(f"\n=== rows where the verified engine contradicts the delivered file ({len(disagree)}) ===")
    print(f"  {'row':>4}  {'OWNER':30}{'LEGACY COMPANY':32}{'LEGACY NUM':12}{'VERIFIED':30}{'VER NUM':12}CONF")
    for d in disagree[:40]:
        print(f"  {d[0]:>4}  {d[1][:28]:30}{(d[2] or '-')[:30]:32}{(d[3] or '-'):12}"
              f"{(d[4] or '-')[:28]:30}{(d[5] or '-'):12}{d[6]}")
    if len(disagree) > 40:
        print(f"  ... and {len(disagree)-40} more")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
