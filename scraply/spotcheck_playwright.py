#!/usr/bin/env python3
"""
Randomly spot-check delivered numbers against company.info with Playwright
(chromium, headless), independently of the Selenium engine that produced them.

    <venv>/bin/python scraply/spotcheck_playwright.py FILE.xlsx --n 12 [--seed 7]
    ... --headed          watch it happen

For each sampled row it repeats what a person would do by hand:

  1. search the owner's postcode + house number
  2. open each result
  3. confirm the delivered number is on that page
  4. confirm the owner is named on that SAME page

A row passes only when 3 and 4 hold together on one page. Using a second
browser stack on purpose: a bug shared with the scraper would otherwise confirm
its own mistake.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://company.info'


def norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', (s or '').lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9 ]', ' ', s)


def owner_tokens(owner: str, given: str = '') -> set:
    stop = {'bv', 'nv', 'vof', 'cv', 'holding', 'beheer', 'vastgoed', 'stichting',
            'exploitatie', 'maatschappij', 'onroerend', 'goed', 'van', 'den', 'der',
            'de', 'het', 'ter', 'groep', 'nederland', 'projecten', 'project'}
    toks = {w for w in norm(owner).split() if len(w) > 3 and w not in stop}
    return toks or {w for w in norm(owner).split() if len(w) > 2 and w not in stop}


def creds() -> tuple[str, str]:
    out = {}
    for line in (ROOT / 'backend' / '.env').read_text(errors='replace').splitlines():
        if line.startswith(('COMPANYINFO_EMAIL=', 'COMPANYINFO_PASSWORD=')):
            k, _, v = line.partition('=')
            out[k.strip()] = v.strip().strip('"').strip('\r')
    return out.get('COMPANYINFO_EMAIL', ''), out.get('COMPANYINFO_PASSWORD', '')


def load_rows(path: Path) -> list[dict]:
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

    c_owner = pick('OWNER_SURNAME', 'Naam eigenaar', '(Achter)naam - eigenaar 1')
    c_given = pick('OWNER_GIVEN', 'Voornaam - eigenaar 1')
    c_post = pick('OWNER_POSTCODE', 'Postcode - eigenaar')
    c_house = pick('OWNER_HOUSE', 'Huisnummer - eigenaar')
    c_street = pick('OWNER_STREET', 'Straat - eigenaar')
    c_city = pick('OWNER_CITY', 'Plaats - eigenaar')
    c_num = pick('NUMBER 1')
    c_conf = pick('CONFIDENCE')
    c_ev = pick('EVIDENCE')

    out = []
    for n, r in enumerate(rows[2:], start=3):
        get = lambda c: (str(r[c]).strip() if c is not None and c < len(r)
                         and r[c] is not None else '')
        if not get(c_num):
            continue
        out.append({'row': n, 'owner': get(c_owner), 'given': get(c_given),
                    'postcode': get(c_post), 'house': get(c_house),
                    'street': get(c_street), 'city': get(c_city),
                    'num': get(c_num), 'conf': get(c_conf), 'evidence': get(c_ev)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--n', type=int, default=12)
    ap.add_argument('--seed', type=int, default=None)
    ap.add_argument('--headed', action='store_true')
    ap.add_argument('--json', default='', help='write the per-row verdicts here')
    a = ap.parse_args()

    from playwright.sync_api import sync_playwright

    rows = load_rows(Path(a.file))
    if not rows:
        print('no rows with a number in that file')
        return 1
    rnd = random.Random(a.seed)
    sample = rnd.sample(rows, min(a.n, len(rows)))
    email, password = creds()
    print(f"file   : {Path(a.file).name}")
    print(f"pool   : {len(rows)} rows carry a number | sampling {len(sample)}"
          + (f" (seed {a.seed})" if a.seed is not None else ""))

    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not a.headed)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.set_default_timeout(30000)

        # log in once
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
        print(f"login  : {'ok' if 'login' not in page.url else 'FAILED'}\n")
        print(f"  {'row':>4}  {'OWNER':26}{'NUMBER':13}{'VERDICT':10}WHERE")

        for r in sample:
            queries = [q for q in (
                f"{r['postcode']} {r['house']}".strip(),
                f"{r['street']} {r['house']} {r['postcode']}".strip(),
                f"{r['street']} {r['house']} {r['city']}".strip(),
                r['owner'],
            ) if q and len(q) > 2]
            tail = ''.join(c for c in r['num'] if c.isdigit())[-7:]
            toks = owner_tokens(r['owner'], r['given'])
            verdict, where = 'NOT FOUND', ''
            for q in queries:
                page.goto(f"{BASE}/organisations/search?query={quote(q)}",
                          wait_until='domcontentloaded')
                page.wait_for_timeout(2200)
                hrefs = page.eval_on_selector_all(
                    "li[data-cy='search-result'] a", "els => els.map(e => e.href)")
                for href in (hrefs or [])[:4]:
                    page.goto(href, wait_until='domcontentloaded')
                    page.wait_for_timeout(2200)
                    text = page.inner_text('body')
                    digits = re.sub(r'\D', '', text)
                    has_num = bool(tail) and tail in digits
                    low = text.lower()
                    has_own = any(re.search(r'\b' + re.escape(t) + r'\b', low) for t in toks)
                    if has_num and has_own:
                        verdict = 'CONFIRMED'
                        where = href.split('?')[0].rsplit('/', 1)[-1]
                        break
                    if has_num and verdict == 'NOT FOUND':
                        verdict = 'number only'
                    elif has_own and verdict == 'NOT FOUND':
                        verdict = 'owner only'
                if verdict == 'CONFIRMED':
                    break
            print(f"  {r['row']:>4}  {r['owner'][:24]:26}{r['num']:13}{verdict:10}{where}")
            results.append({**r, 'verdict': verdict, 'page': where})
        browser.close()

    ok = sum(1 for x in results if x['verdict'] == 'CONFIRMED')
    part = sum(1 for x in results if x['verdict'] in ('number only', 'owner only'))
    print(f"\n  CONFIRMED {ok}/{len(results)} | partial {part} | "
          f"not corroborated {len(results)-ok-part}")
    if a.json:
        Path(a.json).write_text(json.dumps(results, indent=2))
        print(f"  verdicts written to {a.json}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
