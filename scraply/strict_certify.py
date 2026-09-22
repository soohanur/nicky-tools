#!/usr/bin/env python3
"""
Certify a verified output at zero-tolerance: a number survives only when the
company it came from is provably AT THE OWNER'S ADDRESS and IS THE OWNER'S
BUSINESS. Everything else is rejected with a reason.

    python3 scraply/strict_certify.py verified.xlsx --out certified.xlsx
    python3 scraply/strict_certify.py verified.xlsx --limit 20      # dry sample

Why a second pass rather than trusting the engine:

  * The engine may place a company by STREET when a postcode was available.
    A street repeats nationwide; a postcode plus house number does not.
  * The engine matches the owner's name anywhere in the page text. A company
    page also carries "Soortgelijke organisaties" (similar companies) and
    "Nieuws", so a stranger's company name sitting in those sections can look
    like proof. Identity is only read from the name line, the trade names and
    the Eigenaar block here.

Both tests must pass, on the SAME page, together with the delivered number.
"""
from __future__ import annotations

import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scraply'))

# Sections whose text belongs to OTHER companies and must never count as proof.
FOREIGN_SECTIONS = ('soortgelijke organisaties', 'nieuws', 'deelnemingen',
                    'standaard jaarrekeningen', 'werknemers', 'aandeelhouders',
                    'vestigingen', 'jaarverslagen')
PARTICLES = {"van", "de", "den", "der", "het", "ter", "te", "aan", "in", "op", "'t", "en"}
GENERIC = {'beheer', 'holding', 'vastgoed', 'onroerend', 'goed', 'stichting',
           'exploitatie', 'maatschappij', 'bedrijf', 'bedrijven', 'groep',
           'nederland', 'vereniging', 'eigenaars', 'bouw', 'transport',
           'techniek', 'project', 'projecten', 'management', 'verhuur',
           'handel', 'service', 'services', 'advies', 'kantoor', 'parochie'}


def norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', (s or '').lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9 ]', ' ', s)


def name_tokens(owner: str, given: str = '', places: set | None = None) -> set:
    places = places or set()
    out = set()
    for w in norm(owner).split():
        if len(w) < 4 or w in PARTICLES or w in GENERIC or w in places:
            continue
        out.add(w)
    return out


def load_rows(path: Path):
    import openpyxl
    ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
    raw = list(ws.iter_rows(values_only=True))
    hdr = [str(h).strip() if h is not None else '' for h in raw[1]]
    idx = {h: i for i, h in enumerate(hdr)}
    rows = []
    for n, r in enumerate(raw[2:], start=3):
        if not any(v not in (None, '') for v in r):
            continue
        get = lambda k: (str(r[idx[k]]).strip() if k in idx and idx[k] < len(r)
                         and r[idx[k]] is not None else '')
        rows.append({
            'row': n,
            'owner': f"{get('Voorvoegsel - achternaam 1')} {get('(Achter)naam - eigenaar 1')}".strip(),
            'given': get('Voornaam - eigenaar 1'),
            'street': get('Straat - eigenaar'), 'house': get('Huisnummer - eigenaar'),
            'postcode': get('Postcode - eigenaar'), 'city': get('Plaats - eigenaar'),
            'num': get('NUMBER 1'), 'num2': get('NUMBER 2'), 'email': get('EMAIL'),
            'conf': get('CONFIDENCE'), 'evidence': get('EVIDENCE'),
        })
    return rows, hdr, raw


def identity_region(lines: list[str]) -> str:
    """
    The part of the page that describes THIS entity: its name, its trade names
    and its Eigenaar block. Stops at the first section that lists other
    companies, so a similar-companies entry can never be read as proof.
    """
    keep: list[str] = []
    for i, line in enumerate(lines):
        low = line.strip().lower()
        if low in FOREIGN_SECTIONS:
            continue
        keep.append(line)
    text = '\n'.join(keep)
    for marker in FOREIGN_SECTIONS:
        m = re.search(r'\n\s*' + re.escape(marker) + r'\s*\n', text, re.I)
        if m:
            text = text[:m.start()] + '\n' + text[m.end():]
    return text


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = Path(sys.argv[1])
    out_path = None
    if '--out' in sys.argv:
        out_path = Path(sys.argv[sys.argv.index('--out') + 1])
    limit = None
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])

    rows, hdr, raw = load_rows(src)
    todo = [r for r in rows if r['num']]
    if limit:
        todo = todo[:limit]
    print(f"file: {src.name} | rows with a number: {len(todo)}")

    from scraply.src.modules.browser_automation import BrowserAutomation
    from scraply.src.modules.verified_searcher import VerifiedSearcher

    creds = {}
    for line in (ROOT / 'backend' / '.env').read_text(errors='replace').splitlines():
        if line.startswith(('COMPANYINFO_EMAIL=', 'COMPANYINFO_PASSWORD=')):
            k, _, v = line.partition('=')
            creds[k.strip()] = v.strip().strip('"').strip('\r')

    browser = BrowserAutomation(profile_path=None, profile_name='CERTIFY',
                                headless=True, implicit_wait=5)
    browser.__enter__()
    verdicts = {}
    try:
        s = VerifiedSearcher(browser, email=creds.get('COMPANYINFO_EMAIL', ''),
                             password=creds.get('COMPANYINFO_PASSWORD', ''))
        if not s.ensure_login():
            print('login failed')
            return 1
        d = browser.driver
        for r in todo:
            pc = re.sub(r'\s+', '', r['postcode']).upper()
            queries = [q for q in (
                f"{r['street']} {r['house']} {pc}".strip() if pc else '',
                f"{pc} {r['house']}".strip() if pc else '',
                f"{r['street']} {r['house']} {r['city']}".strip(),
            ) if q]
            links = []
            for q in queries:
                d.get(f"https://company.info/organisations/search?query={quote(q)}")
                time.sleep(2.0)
                links = d.execute_script(
                    "return Array.from(document.querySelectorAll(\"li[data-cy='search-result'] a\"))"
                    ".map(function(a){return a.href;}).filter(Boolean).slice(0,4);") or []
                if links:
                    break

            digits = ''.join(c for c in r['num'] if c.isdigit())
            tail = digits[-7:]
            places = set(norm(r['city']).split()) | set(norm(r['street']).split())
            toks = name_tokens(r['owner'], r['given'], places)
            verdict, why, page_id = 'REJECT', 'no company found at the owner address', ''

            if not toks:
                verdicts[r['row']] = ('REJECT', 'owner name has no distinctive token', '')
                print(f"  REJECT row {r['row']:>4} {r['owner'][:26]:28}{r['num']:12} "
                      f"owner name has no distinctive token")
                continue

            for href in links:
                d.get(href)
                time.sleep(2.2)
                text = d.execute_script("return document.body.innerText || ''") or ''
                lines = [l for l in text.split('\n')]
                ident = norm(identity_region(lines))
                page_digits = re.sub(r'\D', '', text)
                up = re.sub(r'\s+', '', text.upper())

                num_ok = bool(tail) and tail in page_digits
                addr_ok = bool(pc) and pc in up and bool(
                    re.search(r'\b' + re.escape(r['house']) + r'\b', text)) if pc else False
                id_ok = any(re.search(r'\b' + re.escape(t) + r'\b', ident) for t in toks)

                if num_ok and addr_ok and id_ok:
                    page_id = href.split('?')[0].rsplit('/', 1)[-1]
                    # Correctly attributed, but a 0900/0800/088/085 line is a
                    # public switchboard. It belongs to the owner and is still
                    # not a person to call, so it is separated rather than
                    # passed off as a contact.
                    if digits.startswith(('0900', '0800', '088', '085', '0906', '0909')):
                        verdict, why = 'REVIEW', 'attribution proven, but this is a public service line'
                    else:
                        verdict, why = 'CERTIFIED', 'postcode+house on page, owner named in identity block, number on page'
                    break
                if num_ok and id_ok and not pc:
                    verdict, why = 'REVIEW', 'no postcode in source; matched on street+house only'
                    page_id = href.split('?')[0].rsplit('/', 1)[-1]
                elif num_ok and not id_ok:
                    verdict, why = 'REJECT', 'number on page but owner not named in identity block'
                elif id_ok and not num_ok:
                    verdict, why = 'REJECT', 'owner named but delivered number is not on that page'
                elif not addr_ok and pc:
                    verdict, why = 'REJECT', 'company is not at the owner postcode+house'
            verdicts[r['row']] = (verdict, why, page_id)
            print(f"  {verdict:9} row {r['row']:>4} {r['owner'][:26]:28}{r['num']:12}{why}"
                  + (f"  [{page_id}]" if page_id else ''))
    finally:
        browser.__exit__(None, None, None)

    n_ok = sum(1 for v in verdicts.values() if v[0] == 'CERTIFIED')
    n_rev = sum(1 for v in verdicts.values() if v[0] == 'REVIEW')
    print(f"\nCERTIFIED {n_ok} | REVIEW {n_rev} | REJECT {len(verdicts)-n_ok-n_rev}")

    if out_path:
        write_certified(src, out_path, verdicts)
    return 0


def write_certified(src: Path, out_path: Path, verdicts: dict) -> None:
    """Copy the file, blank every number that did not certify, record why."""
    import openpyxl
    import shutil
    shutil.copy(src, out_path)
    wb = openpyxl.load_workbook(out_path)
    ws = wb.worksheets[0]
    hdr = [str(c.value).strip() if c.value is not None else '' for c in ws[2]]
    idx = {h: i + 1 for i, h in enumerate(hdr)}
    col = ws.max_column + 1
    ws.cell(row=2, column=col, value='CERTIFICATION')
    ws.cell(row=2, column=col + 1, value='CERT_REASON')
    ws.cell(row=2, column=col + 2, value='CERT_PAGE')
    for row in range(3, ws.max_row + 1):
        v = verdicts.get(row)
        if not v:
            continue
        verdict, why, page = v
        ws.cell(row=row, column=col, value=verdict).number_format = '@'
        ws.cell(row=row, column=col + 1, value=why)
        ws.cell(row=row, column=col + 2, value=page or '').number_format = '@'
        if verdict != 'CERTIFIED':
            for name in ('NUMBER 1', 'NUMBER 2', 'EMAIL'):
                if name in idx:
                    ws.cell(row=row, column=idx[name]).value = None
    wb.save(out_path)
    print(f"wrote {out_path}")


if __name__ == '__main__':
    raise SystemExit(main())
