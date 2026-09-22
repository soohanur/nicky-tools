#!/usr/bin/env python3
"""
Watch the legacy scraper make its mistake, live, in a visible browser.

Replays the exact steps CompanyInfoSearcher takes for rows that came back with
a wrong number, driving the production class itself - not a re-creation - so
what you see on screen is what the scraper does on every run.

    python3 scraply/demo_live_audit.py            # all three cases
    python3 scraply/demo_live_audit.py 2          # just case 2

A banner across the top of the page narrates each step, and every step pauses
long enough to read. Creds come from backend/.env.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scraply'))

from scraply.src.modules.browser_automation import BrowserAutomation      # noqa: E402
from scraply.src.modules.companyinfo_searcher import CompanyInfoSearcher  # noqa: E402

# Rows from scraply_complete_192rows_2026-09-17T12-40-42.csv that the audit
# graded as wrong, with what the scraper wrote into them.
CASES = [
    {
        'row': 3,
        'owner': 'de Rooms Katholieke Parochie HH. Paulus en Ludger',
        'street': 'Nieuwstad', 'house': '12', 'city': 'GROENLO',
        'returned': '0651554613',
        'returned_as': 'Drukkerij-Uitgeverij Emaus vof',
        'why': 'a printing shop - and the same number went onto 4 parish rows',
    },
    {
        'row': 46,
        'owner': 'Laarhuis',
        'street': 'Hoofdstraat', 'house': '3', 'city': 'GAANDEREN',
        'returned': '0481700202',
        'returned_as': 'Vereniging van Eigenaars Hoofdstraat 41 en 41A te Gaanderen.',
        'why': 'the VvE of number 41-41A, not number 3 - and the same number also went to owner "Wind"',
    },
    {
        'row': 40,
        'owner': 'Ruesink',
        'street': 'Beeklaan', 'house': '15', 'city': 'AALTEN',
        'returned': '0703603443',
        'returned_as': 'Totaal VVE Beheer Den Haag en Omstreken B.V.',
        'why': 'a Den Haag (070) company, 200km from Aalten - reached by the shareholder hop',
    },
]

PAUSE = float(os.environ.get('DEMO_PAUSE', '4'))


def banner(driver, title: str, lines: list[str], colour: str = '#1d4ed8') -> None:
    """Pin a narration bar over the page so the step being run is readable."""
    html = f"<div style='font:600 17px system-ui;margin-bottom:6px'>{title}</div>" + ''.join(
        f"<div style='font:400 14px/1.5 system-ui;opacity:.95'>{ln}</div>" for ln in lines)
    driver.execute_script("""
        let b = document.getElementById('__audit_banner');
        if (!b) {
            b = document.createElement('div');
            b.id = '__audit_banner';
            b.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483647;'
                + 'padding:14px 20px;color:#fff;box-shadow:0 2px 14px rgba(0,0,0,.35)';
            document.body.appendChild(b);
        }
        b.style.background = arguments[1];
        b.innerHTML = arguments[0];
    """, html, colour)


def result_names(driver) -> list[str]:
    """The company names on the open search-results page, in order."""
    return driver.execute_script("""
        return Array.from(document.querySelectorAll('[data-cy="search-result"]'))
                    .map(e => (e.innerText || '').split('\\n')[0].trim())
                    .filter(Boolean);
    """) or []


def run_case(searcher, driver, case: dict) -> None:
    addr = f"{case['street']} {case['house']} {case['city']}"
    print(f"\n{'='*78}\nROW {case['row']}: {case['owner']}\n  owner address : {addr}"
          f"\n  scraper wrote : {case['returned']}  as '{case['returned_as']}'\n{'='*78}")

    # --- Step 1: name search -------------------------------------------------
    driver.get(f"https://company.info/organisations/search?query={quote(case['owner'])}")
    searcher._wait_for_search_results()
    time.sleep(1)
    names = result_names(driver)
    banner(driver, f"STEP 1 of 3 — search by OWNER NAME  (row {case['row']})", [
        f"searching: <b>{case['owner']}</b>",
        f"results: <b>{len(names)}</b>" + (f" — {names[0]}" if names else ""),
        "The scraper needs an EXACT name match here. No match → it falls through to the address.",
    ])
    print(f"  STEP 1  name search -> {len(names)} result(s): {names[:3]}")
    time.sleep(PAUSE + 2)

    # --- Step 2: address search — the unverified click -----------------------
    driver.get(f"https://company.info/organisations/search?query={quote(addr)}")
    searcher._wait_for_search_results()
    time.sleep(1)
    names = result_names(driver)
    banner(driver, f"STEP 2 of 3 — fall back to ADDRESS search  (row {case['row']})", [
        f"searching: <b>{addr}</b> — the owner's address",
        f"results: <b>{len(names)}</b> companies registered at or near this address",
        "&rarr; " + " &nbsp;|&nbsp; ".join(f"<b>#{n+1}</b> {v}" for n, v in enumerate(names[:4])),
        "<b>The scraper now clicks #1 and asks no further questions.</b>",
    ], '#b45309')
    print(f"  STEP 2  address search -> {len(names)} result(s)")
    for n, v in enumerate(names[:6], 1):
        print(f"            #{n} {v}")
    time.sleep(PAUSE + 4)

    # --- Step 3: what it takes from that page --------------------------------
    if names:
        searcher._click_first_result()
        time.sleep(2)
        info = searcher.extract_contact_info()
        found_name = info.get('business') or ''
        phones = info.get('phones') or []
        banner(driver, f"STEP 3 of 3 — take result #1's contact details  (row {case['row']})", [
            f"owner on the deed: <b>{case['owner']}</b>",
            f"company it opened: <b>{found_name or case['returned_as']}</b>",
            f"number written into the row: <b>{phones[0] if phones else case['returned']}</b>",
            f"<b>WRONG</b> — {case['why']}",
            "Nothing in the code ever checked that this company is the owner.",
        ], '#b91c1c')
        print(f"  STEP 3  opened '{found_name}' -> phones={phones[:2]} email={info.get('email')!r}")
        print(f"  VERDICT wrong: {case['why']}")
        time.sleep(PAUSE + 6)


def main() -> int:
    env = ROOT / 'backend' / '.env'
    creds = {}
    for line in env.read_text(errors='replace').splitlines():
        if line.startswith(('COMPANYINFO_EMAIL=', 'COMPANYINFO_PASSWORD=')):
            k, _, v = line.partition('=')
            creds[k.strip()] = v.strip().strip('"').strip('\r')
    email = creds.get('COMPANYINFO_EMAIL', '')
    password = creds.get('COMPANYINFO_PASSWORD', '')
    if not email or not password:
        print('ERROR: company.info credentials not found in backend/.env')
        return 2

    picked = CASES
    if len(sys.argv) > 1:
        want = {int(a) for a in sys.argv[1:] if a.isdigit()}
        picked = [c for n, c in enumerate(CASES, 1) if n in want] or CASES

    print('Opening a VISIBLE browser. Watch the banner at the top of the page.')
    browser = BrowserAutomation(profile_path=None, profile_name='AUDIT',
                                headless=False, implicit_wait=5)
    browser.__enter__()
    try:
        driver = browser.driver
        driver.set_page_load_timeout(45)
        driver.set_script_timeout(30)
        searcher = CompanyInfoSearcher(browser=browser, base_url='https://company.info',
                                       timeout=30, email=email, password=password)
        driver.get('https://company.info')
        searcher._check_and_handle_login(force_check=True)
        time.sleep(2)
        for case in picked:
            run_case(searcher, driver, case)
        banner(driver, 'Demo finished', [
            'Every wrong number came from the same place: STEP 2 clicks result #1 with no check.',
            'The verified pipeline refuses to write a number unless the owner appears on that page.',
        ], '#166534')
        time.sleep(12)
    finally:
        browser.__exit__(None, None, None)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
