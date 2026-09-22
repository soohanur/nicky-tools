#!/usr/bin/env python3
"""
Verify EVERY delivered number against company.info, field by field, with
Playwright - the check a careful person would do by hand, for every row.

    <venv>/bin/python scraply/verify_end_to_end.py FILE.xlsx --out verdicts.xlsx
    ... --limit 10 --headed        try it on a few rows first

For each row that carries a number it reads every relevant column of the sheet,
opens the candidate company.info pages, reads every relevant field of the page,
and compares them:

    sheet                         company.info page
    -----                         -----------------
    owner name                <-> organisation name / statutory name / trade names
    owner name                <-> Management and Eigenaar blocks  (the person)
    owner postcode + house    <-> Adres block postcode + house
    owner street              <-> Adres block street
    parcel address            <-> Adres block  (owner trading AT the property)
    delivered number          <-> tel: links and the Telefoon field

Verdicts, strongest first:

  GENUINE-ENTITY  the deed owner IS this company (exact name) and the number is
                  on its page
  GENUINE-PERSON  the number is on a page at the owner's own address AND the
                  owner is named in Management/Eigenaar - a person, not a word
  GENUINE-ADDR    number on a page at the owner's exact postcode+house, and the
                  owner's name is in the company name
  WEAK            number found, but the link to the owner is only a loose name
                  token - not good enough to call
  REJECT          the number is not on any page we can tie to this owner

Only GENUINE-* rows belong in a call list.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://company.info'
OWN_SWITCHBOARD = {'0202400400', '31202400400'}

LEGAL = re.compile(r'\s*(b\.?\s?v\.?|n\.?\s?v\.?|v\.?o\.?f\.?|c\.?v\.?|u\.?a\.?)\s*$', re.I)
GENERIC = {'beheer', 'holding', 'vastgoed', 'onroerend', 'goed', 'stichting',
           'exploitatie', 'maatschappij', 'bedrijf', 'groep', 'nederland',
           'vereniging', 'eigenaars', 'bouw', 'transport', 'techniek', 'project',
           'projecten', 'management', 'verhuur', 'handel', 'advies', 'service',
           'services', 'invest', 'gebroeders', 'zonen'}
PARTICLES = {'van', 'de', 'den', 'der', 'ter', 'te', 'het', 'op', 'aan', 'in'}


def norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', (s or '').lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9 ]', ' ', s).strip()


def key(s: str) -> str:
    return ' '.join(LEGAL.sub('', (s or '').strip().lower()).replace('.', '').split())


def name_tokens(owner: str, places: set[str]) -> set[str]:
    out = set()
    for w in norm(owner).split():
        if len(w) < 4 or w in GENERIC or w in PARTICLES or w in places:
            continue
        out.add(w)
    return out


def digits(s: str) -> str:
    return ''.join(c for c in (s or '') if c.isdigit())


def phone_key(s: str) -> str:
    d = digits(s)
    if d.startswith('0031'):
        d = '0' + d[4:]
    elif d.startswith('31') and len(d) > 9:
        d = '0' + d[2:]
    return d


def creds() -> tuple[str, str]:
    out = {}
    for line in (ROOT / 'backend' / '.env').read_text(errors='replace').splitlines():
        if line.startswith(('COMPANYINFO_EMAIL=', 'COMPANYINFO_PASSWORD=')):
            k, _, v = line.partition('=')
            out[k.strip()] = v.strip().strip('"').strip('\r')
    return out.get('COMPANYINFO_EMAIL', ''), out.get('COMPANYINFO_PASSWORD', '')


# --------------------------------------------------------------- sheet side

def load_rows(path: Path) -> tuple[list[dict], list[str]]:
    import openpyxl
    ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [str(h).strip() if h is not None else '' for h in rows[1]]
    idx = {h: i for i, h in enumerate(hdr)}

    def pick(*names):
        for n in names:
            if n in idx:
                return idx[n]
        return None

    cols = {
        'owner': pick('OWNER_SURNAME', 'Naam eigenaar', '(Achter)naam - eigenaar 1'),
        'owner_full': pick('Naam eigenaar', '(Achter)naam - eigenaar 1'),
        'given': pick('OWNER_GIVEN', 'Voornaam - eigenaar 1'),
        'street': pick('OWNER_STREET', 'Straat - eigenaar'),
        'house': pick('OWNER_HOUSE', 'Huisnummer - eigenaar'),
        'postcode': pick('OWNER_POSTCODE', 'Postcode - eigenaar'),
        'city': pick('OWNER_CITY', 'Plaats - eigenaar'),
        'p_street': pick('PARCEL_STREET', 'adressen_eerste_adres_straatnaam'),
        'p_house': pick('PARCEL_HOUSE', 'adressen_eerste_adres_huisnummer'),
        'p_city': pick('PARCEL_CITY', 'woonplaats'),
        'num': pick('NUMBER 1'), 'num2': pick('NUMBER 2'), 'email': pick('EMAIL'),
        'company': pick('COMPANY_FOUND'), 'conf': pick('CONFIDENCE'),
        'evidence': pick('EVIDENCE'),
    }
    out = []
    for n, r in enumerate(rows[2:], start=3):
        get = lambda c: (str(r[c]).strip() if c is not None and c < len(r)
                         and r[c] is not None else '')
        if not get(cols['num']):
            continue
        out.append({'row': n, **{k: get(v) for k, v in cols.items()}})
    return out, hdr


# ---------------------------------------------------------------- page side

PAGE_JS = r"""
() => {
  const text = document.body.innerText || '';
  const lines = text.split('\n').map(s => s.trim()).filter(Boolean);
  const after = (label, n) => {
    const i = lines.findIndex(l => l.toLowerCase() === label.toLowerCase());
    return i < 0 ? [] : lines.slice(i + 1, i + 1 + n);
  };
  const field = (label) => {
    const re = new RegExp('^' + label + '\\s*\\t?\\s*(.+)$', 'i');
    for (const l of lines) { const m = l.match(re); if (m) return m[1].trim(); }
    return '';
  };
  const block = (label, n) => {
    const i = lines.findIndex(l => l.toLowerCase().startsWith(label.toLowerCase()));
    if (i < 0) return [];
    const out = [];
    for (let j = i + 1; j < Math.min(i + 1 + n, lines.length); j++) {
      const l = lines[j];
      if (/^(Bekijk|Adresgegevens|Management|Eigenaar|Werknemers|Aandeelhouders|Organisatieoverzicht)/i.test(l)) break;
      out.push(l);
    }
    return out;
  };
  const docTitle = (document.title || '').split('|')[0].trim();
  return {
    title: docTitle,
    firstLines: lines.slice(0, 8),
    tel: Array.from(document.querySelectorAll("a[href^='tel:']")).map(a => a.getAttribute('href')),
    mail: Array.from(document.querySelectorAll("a[href^='mailto:']")).map(a => a.getAttribute('href')),
    adresBlock: after('Adres', 4),
    telefoon: field('Telefoon'),
    kvk: field('KVK'), vestnr: field('Vestnr\\.'), rsin: field('RSIN'),
    rechtsvorm: field('Rechtsvorm'), statutair: field('Vennootsch\\. naam'),
    handelsnamen: block('Handelsnamen', 4),
    management: block('Management', 6),
    eigenaar: block('Eigenaar', 6),
    url: location.href,
  };
}
"""


def parse_page(d: dict) -> dict:
    """Turn the raw page read into comparable fields."""
    street = house = postcode = city = ''
    blk = [x for x in (d.get('adresBlock') or []) if x]
    if len(blk) >= 4:
        street, house, postcode, city = blk[0], blk[1], blk[2], blk[3]
    elif len(blk) >= 2:
        m = re.match(r'^(.*?)\s+(\d+\s?[A-Za-z]?)$', blk[0])
        if m:
            street, house = m.group(1), m.group(2)
        pm = re.search(r'(\d{4})\s?([A-Za-z]{2})\s+(.*)$', blk[1])
        if pm:
            postcode, city = f"{pm.group(1)}{pm.group(2)}", pm.group(3)
    phones = []
    for h in (d.get('tel') or []):
        p = phone_key(h.replace('tel:', ''))
        if p and p not in OWN_SWITCHBOARD and p not in phones:
            phones.append(p)
    if d.get('telefoon'):
        p = phone_key(d['telefoon'])
        if p and p not in OWN_SWITCHBOARD and p not in phones:
            phones.append(p)
    mails = [m.replace('mailto:', '') for m in (d.get('mail') or [])
             if 'company.info' not in m]
    people = [x for x in (d.get('management') or []) + (d.get('eigenaar') or [])
              if x and 'geen data' not in x.lower()]
    # Prefer the labelled statutory name, then the first trade name, then the
    # document title. An earlier version took the 4th line of the page, which on
    # some layouts is a navigation item - one row was "verified" against 'Nieuws'.
    name = (d.get('statutair') or '').strip()
    if not name:
        hn = [x for x in (d.get('handelsnamen') or []) if x]
        name = hn[0] if hn else (d.get('title') or '').strip()
    return {
        'name': name, 'statutair': d.get('statutair', ''),
        'handelsnamen': d.get('handelsnamen') or [],
        'street': street, 'house': house,
        'postcode': re.sub(r'\s+', '', postcode).upper(), 'city': city,
        'phones': phones, 'emails': mails, 'people': people,
        'kvk': d.get('kvk', ''), 'vestnr': d.get('vestnr', ''),
        'rechtsvorm': d.get('rechtsvorm', ''), 'url': d.get('url', ''),
    }


def compare(row: dict, page: dict) -> dict:
    """Every check, so the verdict can be explained field by field."""
    places = set(norm(row['city']).split()) | set(norm(row['p_city']).split())
    toks = name_tokens(row['owner'], places)
    names = [page['name'], page['statutair']] + list(page['handelsnamen'])
    names_l = ' | '.join(norm(n) for n in names if n)

    c = {}
    c['phone_on_page'] = phone_key(row['num']) in page['phones']
    c['email_match'] = bool(row['email']) and row['email'].lower() in [m.lower() for m in page['emails']]
    c['name_exact'] = any(key(n) and key(n) == key(row['owner']) for n in names)
    c['name_token'] = bool(toks) and any(re.search(r'\b' + re.escape(t) + r'\b', names_l) for t in toks)
    people_l = ' | '.join(norm(p) for p in page['people'])
    c['person_match'] = bool(toks) and any(re.search(r'\b' + re.escape(t) + r'\b', people_l) for t in toks)
    c['addr_exact'] = bool(row['postcode']) and bool(page['postcode']) and \
        re.sub(r'\s+', '', row['postcode']).upper() == page['postcode'] and \
        digits(row['house']) == digits(page['house']) and bool(digits(row['house']))
    c['addr_street'] = bool(row['street']) and norm(row['street']) == norm(page['street']) and \
        digits(row['house']) == digits(page['house']) and bool(digits(row['house']))
    c['addr_parcel'] = bool(row['p_street']) and norm(row['p_street']) == norm(page['street']) and \
        digits(row['p_house']) == digits(page['house']) and bool(digits(row['p_house']))
    return c


def verdict_of(c: dict) -> tuple[str, str]:
    if not c['phone_on_page']:
        return 'REJECT', 'the delivered number is not on this page'
    if c['name_exact']:
        return 'GENUINE-ENTITY', 'the deed owner IS this organisation (exact name) and the number is on its page'
    if (c['addr_exact'] or c['addr_street']) and c['person_match']:
        return 'GENUINE-PERSON', 'number on a page at the owner address, owner named in Management/Eigenaar'
    if c['addr_exact'] and c['name_token']:
        return 'GENUINE-ADDR', 'number on a page at the owner exact postcode+house, owner name in the company name'
    if c['addr_parcel'] and c['name_token']:
        return 'GENUINE-ADDR', 'company carrying the owner name trades at the parcel itself, number on its page'
    if c['person_match'] and c['addr_parcel']:
        return 'GENUINE-PERSON', 'owner named in Management/Eigenaar of the company at the parcel address'
    if c['name_token'] or c['person_match'] or c['addr_exact']:
        return 'WEAK', 'number found but the tie to this owner is loose'
    return 'REJECT', 'no field ties this page to the owner'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--out', default='')
    ap.add_argument('--json', default='')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--headed', action='store_true')
    a = ap.parse_args()

    from playwright.sync_api import sync_playwright

    rows, _ = load_rows(Path(a.file))
    if a.start:
        rows = rows[a.start:]
    if a.limit:
        rows = rows[:a.limit]
    email, password = creds()
    print(f"file : {Path(a.file).name}\nrows with a number to verify: {len(rows)}\n")

    out = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not a.headed)
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        page.set_default_timeout(30000)
        page.goto(BASE, wait_until='domcontentloaded')
        page.wait_for_timeout(2500)
        if page.locator('#username').count():
            page.fill('#username', email)
            page.click('#ci-login')
            page.wait_for_timeout(2000)
            if page.locator('#password').count():
                page.fill('#password', password)
                page.click('#ci-login')
            page.wait_for_timeout(4000)
        print(f"login: {'ok' if '/login' not in page.url else 'FAILED'}\n")
        print(f"  {'row':>4}  {'OWNER':24}{'NUMBER':12}{'VERDICT':16}WHY")

        for r in rows:
            queries = [q for q in (
                f"{r['postcode']} {r['house']}".strip(),
                f"{r['street']} {r['house']} {r['postcode']}".strip(),
                f"{r['street']} {r['house']} {r['city']}".strip(),
                r['owner'],
                f"{r['p_street']} {r['p_house']} {r['p_city']}".strip(),
            ) if q and len(q.strip()) > 2]
            best = ('REJECT', 'no company page found for this owner or address', {}, {})
            seen = 0
            rank = {'GENUINE-ENTITY': 4, 'GENUINE-PERSON': 3, 'GENUINE-ADDR': 2,
                    'WEAK': 1, 'REJECT': 0}
            for q in queries:
                try:
                    page.goto(f"{BASE}/organisations/search?query={quote(q)}",
                              wait_until='domcontentloaded')
                    page.wait_for_timeout(2000)
                    hrefs = page.eval_on_selector_all(
                        "li[data-cy='search-result'] a", "els => els.map(e => e.href)") or []
                except Exception:
                    continue
                for href in hrefs[:4]:
                    try:
                        page.goto(href, wait_until='domcontentloaded')
                        page.wait_for_timeout(2200)
                        raw = page.evaluate(PAGE_JS)
                    except Exception:
                        continue
                    seen += 1
                    pg = parse_page(raw)
                    c = compare(r, pg)
                    v, why = verdict_of(c)
                    if rank[v] > rank[best[0]]:
                        best = (v, why, c, pg)
                    if v == 'GENUINE-ENTITY':
                        break
                if best[0] in ('GENUINE-ENTITY', 'GENUINE-PERSON'):
                    break
            v, why, checks, pg = best
            if v == 'REJECT' and seen:
                why = f'checked {seen} page(s); none carries this number for this owner'
            print(f"  {r['row']:>4}  {r['owner'][:22]:24}{r['num']:12}{v:16}{why[:52]}")
            out.append({**r, 'verdict': v, 'why': why, 'checks': checks,
                        'page_name': pg.get('name', ''), 'page_kvk': pg.get('kvk', ''),
                        'page_addr': f"{pg.get('street','')} {pg.get('house','')} "
                                     f"{pg.get('postcode','')} {pg.get('city','')}".strip(),
                        'page_people': ' / '.join(pg.get('people', [])[:3]),
                        'page_url': pg.get('url', '')})
        browser.close()

    from collections import Counter
    tally = Counter(x['verdict'] for x in out)
    print("\n" + "=" * 70)
    for k in ('GENUINE-ENTITY', 'GENUINE-PERSON', 'GENUINE-ADDR', 'WEAK', 'REJECT'):
        if tally.get(k):
            print(f"  {tally[k]:4}  {k}")
    good = sum(tally.get(k, 0) for k in ('GENUINE-ENTITY', 'GENUINE-PERSON', 'GENUINE-ADDR'))
    print(f"\n  callable (GENUINE-*): {good}/{len(out)}")

    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=2, ensure_ascii=False))
        print(f"  verdicts -> {a.json}")
    if a.out:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'verdicts'
        cols = ['row', 'owner', 'num', 'verdict', 'why', 'page_name', 'page_kvk',
                'page_addr', 'page_people', 'conf', 'evidence', 'page_url']
        ws.append(cols)
        for x in out:
            ws.append([x.get(c, '') for c in cols])
        wb.save(a.out)
        print(f"  workbook -> {a.out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
