#!/usr/bin/env python3
"""
Independently cross-check a verified output file, without trusting the engine
that produced it.

    python3 scraply/crosscheck.py verified.xlsx              # layers 1-3, offline
    python3 scraply/crosscheck.py verified.xlsx --live 25    # + layer 4 on 25 rows

Four layers, cheapest first:

  L1 hygiene    service lines, malformed numbers, one number on several owners
  L2 evidence   is the proof token a real name token of THIS owner, or is it a
                place name / generic word that proves nothing
  L3 geography  does the landline's area code belong anywhere near the owner's
                own town (mobiles carry no geography and are skipped)
  L4 live       re-open the company page and confirm, independently, that the
                delivered number is on that page AND an owner token is on that
                page. This is the manual check a person would do, automated.

A row only passes if every layer that applies to it passes.
"""
from __future__ import annotations

import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scraply'))

SERVICE = ('0900', '0800', '088', '085', '0906', '0909')

# Dutch landline area codes -> the town/region they belong to. Only the codes
# that turn up in these exports; anything unknown is reported as unknown rather
# than counted against the row.
AREA = {
    '0314': 'doetinchem', '0315': 'ulft/varsseveld', '0316': 'zevenaar',
    '0543': 'winterswijk/aalten', '0544': 'groenlo/lichtenvoorde',
    '0545': 'ruurlo', '0573': 'lochem/borculo', '0575': 'zutphen/warnsveld',
    '0313': 'dieren', '0481': 'elst', '0488': 'zetten', '0487': 'druten',
    '0486': 'grave', '026': 'arnhem', '024': 'nijmegen', '0342': 'barneveld',
    '0344': 'tiel', '0345': 'culemborg', '055': 'apeldoorn', '0578': 'epe',
    '038': 'zwolle', '053': 'enschede', '074': 'hengelo', '0547': 'goor',
    '0546': 'almelo', '0541': 'oldenzaal', '0521': 'steenwijk',
    '0528': 'hoogeveen', '0591': 'emmen', '0598': 'hoogezand', '0592': 'assen',
    '030': 'utrecht', '070': 'den haag', '020': 'amsterdam', '010': 'rotterdam',
    '076': 'breda', '013': 'tilburg', '040': 'eindhoven', '043': 'maastricht',
    '023': 'haarlem', '0299': 'purmerend', '0413': 'veghel', '0492': 'helmond',
    '072': 'alkmaar', '071': 'leiden', '079': 'zoetermeer', '033': 'amersfoort',
    '036': 'almere', '050': 'groningen', '058': 'leeuwarden', '045': 'heerlen',
    '077': 'venlo', '073': 'den bosch', '0172': 'alphen', '0182': 'gouda',
}
# Codes whose region sits in or next to the Achterhoek / east Gelderland.
NEARBY = {'0314', '0315', '0316', '0543', '0544', '0545', '0573', '0575',
          '0313', '026', '0545', '0547', '053', '074', '0546', '024', '0481'}

GENERIC = {'beheer', 'holding', 'vastgoed', 'onroerend', 'goed', 'stichting',
           'exploitatie', 'maatschappij', 'bedrijf', 'groep', 'nederland',
           'vereniging', 'eigenaars', 'bouw', 'transport', 'techniek',
           'project', 'projecten', 'management', 'verhuur', 'handel'}


def norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', (s or '').lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9 ]', ' ', s)


def words(s: str) -> set:
    return {w for w in norm(s).split() if len(w) > 2}


def area_of(num: str) -> str | None:
    d = ''.join(c for c in (num or '') if c.isdigit())
    if d.startswith('06'):
        return None                      # mobile: no geography
    for n in (4, 3):
        if d[:n] in AREA:
            return d[:n]
    return None


def load(path: Path):
    import openpyxl
    ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [str(h).strip() if h is not None else '' for h in rows[1]]
    idx = {h: i for i, h in enumerate(hdr)}
    out = []
    for n, r in enumerate(rows[2:], start=3):
        if not any(v not in (None, '') for v in r):
            continue
        get = lambda k: (str(r[idx[k]]).strip() if k in idx and idx[k] < len(r)
                         and r[idx[k]] is not None else '')
        out.append({
            'row': n,
            'owner': f"{get('Voorvoegsel - achternaam 1')} {get('(Achter)naam - eigenaar 1')}".strip(),
            'given': get('Voornaam - eigenaar 1'),
            'city': get('Plaats - eigenaar') or get('woonplaats'),
            'street': get('Straat - eigenaar'),
            'house': get('Huisnummer - eigenaar'),
            'alt': f"{get('adressen_eerste_adres_straatnaam')} {get('adressen_eerste_adres_huisnummer')} {get('woonplaats')}".strip(),
            'num': get('NUMBER 1'), 'num2': get('NUMBER 2'), 'email': get('EMAIL'),
            'conf': get('CONFIDENCE'), 'evidence': get('EVIDENCE'), 'source': get('SOURCE'),
        })
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    live_n = 0
    if '--live' in sys.argv:
        i = sys.argv.index('--live')
        live_n = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else 25

    rows = load(path)
    withnum = [r for r in rows if r['num']]
    print(f"file      : {path.name}")
    print(f"rows      : {len(rows)} | with a number: {len(withnum)}")

    problems = defaultdict(list)

    # ---- L1 hygiene -----------------------------------------------------
    seen = defaultdict(list)
    for r in withnum:
        d = ''.join(c for c in r['num'] if c.isdigit())
        if d.startswith(SERVICE):
            problems['L1 service/switchboard number'].append((r['row'], r['owner'], r['num']))
        if not (9 <= len(d) <= 11):
            problems['L1 malformed number'].append((r['row'], r['owner'], r['num']))
        seen[d].append(r)
    for d, rs in seen.items():
        if len(rs) > 1 and len({norm(x['owner']) for x in rs}) > 1:
            problems['L1 same number, different owners'].append(
                (rs[0]['row'], ' | '.join(x['owner'][:18] for x in rs), d))

    # ---- L2 evidence ----------------------------------------------------
    for r in withnum:
        m = re.search(r"owner token\(s\) \[([^\]]*)\]", r['evidence'] or '')
        if not m:
            continue                      # name-match rows carry their own proof
        toks = {t.strip().strip("'\"") for t in m.group(1).split(',') if t.strip()}
        own = words(r['owner']) | words(r['given'])
        place = words(r['city'])
        if toks and toks <= place:
            problems['L2 proved only by a place name'].append((r['row'], r['owner'], str(sorted(toks))))
        elif toks and toks <= GENERIC:
            problems['L2 proved only by a generic word'].append((r['row'], r['owner'], str(sorted(toks))))
        elif toks and not (toks & own):
            problems['L2 proof token is not in the owner name'].append(
                (r['row'], r['owner'], str(sorted(toks))))

    # ---- L3 geography ---------------------------------------------------
    unknown = 0
    for r in withnum:
        code = area_of(r['num'])
        if code is None:
            unknown += 1
            continue
        region = AREA.get(code, '')
        city = norm(r['city'])
        if city and city.split() and city.split()[0] in region:
            continue                      # exact town match
        if code in NEARBY:
            continue                      # same corner of the country
        problems['L3 area code far from the owner town'].append(
            (r['row'], f"{r['owner'][:24]} ({r['city'][:14]})", f"{r['num']} -> {region or code}"))

    # ---- report ---------------------------------------------------------
    print(f"\n{'='*74}\nCROSS-CHECK (mobiles skipped in L3: {unknown})\n{'='*74}")
    total = 0
    for k in sorted(problems):
        v = problems[k]
        total += len(v)
        print(f"\n{k}  ({len(v)})")
        for row, who, what in v[:12]:
            print(f"    row {row:>4}  {who[:46]:48}{what}")
        if len(v) > 12:
            print(f"    ... {len(v)-12} more")
    if not total:
        print("\n  no problems found by layers 1-3")
    print(f"\nrows flagged by L1-L3: {total} of {len(withnum)} numbers")

    # ---- L4 live --------------------------------------------------------
    if live_n:
        live_check(withnum[:live_n])
    return 0


def live_check(rows) -> None:
    """Re-open each company page and confirm the number and an owner token."""
    from scraply.src.modules.browser_automation import BrowserAutomation
    from scraply.src.modules.verified_searcher import VerifiedSearcher
    from urllib.parse import quote

    env = ROOT / 'backend' / '.env'
    creds = {}
    for line in env.read_text(errors='replace').splitlines():
        if line.startswith(('COMPANYINFO_EMAIL=', 'COMPANYINFO_PASSWORD=')):
            k, _, v = line.partition('=')
            creds[k.strip()] = v.strip().strip('"').strip('\r')

    print(f"\n{'='*74}\nL4 LIVE RE-CHECK of {len(rows)} rows\n{'='*74}")
    browser = BrowserAutomation(profile_path=None, profile_name='XCHECK',
                                headless=True, implicit_wait=5)
    browser.__enter__()
    ok = bad = skip = 0
    try:
        s = VerifiedSearcher(browser, email=creds.get('COMPANYINFO_EMAIL', ''),
                             password=creds.get('COMPANYINFO_PASSWORD', ''),
                             max_candidates=4, min_delay=1.0, max_delay=2.0)
        if not s.ensure_login():
            print("  login failed - L4 skipped")
            return
        d = browser.driver
        for r in rows:
            # Open the actual company pages behind this address and look for the
            # delivered number AND an owner token on the SAME page. Reading the
            # results list instead proves nothing: search cards carry no phones.
            # Reproduce the engine's own queries, in the same order it tries
            # them: full owner address WITH house number, then the owner name,
            # then the parcel address. Dropping the house number turns a
            # one-company lookup into a street-wide one and proves nothing.
            grab = """
                return Array.from(document.querySelectorAll("li[data-cy='search-result'] a"))
                            .map(function (a) { return a.href; }).filter(Boolean).slice(0, 4);
            """
            queries = [q for q in (
                f"{r['street']} {r['house']} {r['city']}".strip(),
                r['owner'],
                r['alt'],
            ) if q and q.strip()]
            links = []
            for q in queries:
                d.get(f"https://company.info/organisations/search?query={quote(q)}")
                time.sleep(2.0)
                links = d.execute_script(grab) or []
                if links:
                    break

            digits = ''.join(c for c in r['num'] if c.isdigit())
            tail = digits[-7:]
            own = words(r['owner'])
            hit_num = hit_own = False
            where = ''
            for href in links:
                d.get(href)
                time.sleep(2.0)
                page = (d.execute_script("return document.body.innerText || ''") or '')
                low = page.lower()
                nums = re.sub(r'\D', '', page)
                n_ok = tail and tail in nums
                o_ok = any(re.search(r'\b' + re.escape(t) + r'\b', low) for t in own)
                if n_ok and o_ok:
                    hit_num = hit_own = True
                    where = href.split('?')[0].rsplit('/', 1)[-1]
                    break
                hit_num = hit_num or n_ok
                hit_own = hit_own or o_ok
            mark = 'OK ' if (hit_num and hit_own and where) else ('?? ' if hit_num or hit_own else 'BAD')
            if mark == 'OK ':
                ok += 1
            elif mark == 'BAD':
                bad += 1
            else:
                skip += 1
            print(f"  {mark} row {r['row']:>4}  {r['owner'][:24]:26}{r['num']:13}"
                  f"pages={len(links)} number={hit_num!s:5} owner={hit_own!s:5} {where}")
            time.sleep(0.5)
    finally:
        browser.__exit__(None, None, None)
    print(f"\n  L4: {ok} confirmed | {skip} partial | {bad} not corroborated")


if __name__ == '__main__':
    raise SystemExit(main())
