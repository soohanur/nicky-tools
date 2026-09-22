#!/usr/bin/env python3
"""
Open every company.info result for one address and print the evidence, so a
claim about who owns a parcel can be checked instead of assumed.

    python3 scraply/check_one_address.py "Nieuwstad 12 GROENLO"
    HEADED=1 python3 scraply/check_one_address.py "Nieuwstad 12 GROENLO"

For each result: the entity name, its registered address, KVK number and any
phone/email on the page. Whether that entity is the parcel's owner is a
question the kadaster answers, not this site - this only shows what is there.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scraply'))

from scraply.src.modules.browser_automation import BrowserAutomation      # noqa: E402
from scraply.src.modules.companyinfo_searcher import CompanyInfoSearcher  # noqa: E402


def creds():
    out = {}
    for line in (ROOT / 'backend' / '.env').read_text(errors='replace').splitlines():
        if line.startswith(('COMPANYINFO_EMAIL=', 'COMPANYINFO_PASSWORD=')):
            k, _, v = line.partition('=')
            out[k.strip()] = v.strip().strip('"').strip('\r')
    return out.get('COMPANYINFO_EMAIL', ''), out.get('COMPANYINFO_PASSWORD', '')


def main() -> int:
    query = sys.argv[1] if len(sys.argv) > 1 else 'Nieuwstad 12 GROENLO'
    email, password = creds()
    if not email:
        print('ERROR: no credentials in backend/.env')
        return 2

    browser = BrowserAutomation(profile_path=None, profile_name='CHECK',
                                headless=not os.environ.get('HEADED'), implicit_wait=5)
    browser.__enter__()
    try:
        d = browser.driver
        d.set_page_load_timeout(45)
        d.set_script_timeout(30)
        s = CompanyInfoSearcher(browser=browser, base_url='https://company.info',
                                timeout=30, email=email, password=password)
        d.get('https://company.info')
        s._check_and_handle_login(force_check=True)
        time.sleep(2)

        d.get(f"https://company.info/organisations/search?query={quote(query)}")
        s._wait_for_search_results()
        time.sleep(1.5)

        cards = d.execute_script("""
            return Array.from(document.querySelectorAll('[data-cy="search-result"]')).map(e => {
                const a = e.querySelector('a');
                return {text: (e.innerText||'').trim(), href: a ? a.href : ''};
            });
        """) or []
        print(f"\nQUERY: {query}\nresults: {len(cards)}\n" + "=" * 78)
        for n, c in enumerate(cards, 1):
            lines = [l.strip() for l in c['text'].split('\n') if l.strip()]
            print(f"\n#{n}  {lines[0] if lines else '(no name)'}")
            for l in lines[1:6]:
                print(f"      {l}")
            print(f"      url: {c['href']}")

        for n, c in enumerate(cards, 1):
            if not c['href']:
                continue
            d.get(c['href'])
            s._wait_for_search_results()
            time.sleep(2)
            text = d.execute_script("return document.body.innerText || ''")
            kvk = re.search(r'\b(\d{8})\b', text)
            info = s.extract_contact_info()
            print(f"\n--- opened #{n}: {info.get('business') or (c['text'].split(chr(10))[0])}")
            print(f"      KVK    : {kvk.group(1) if kvk else '(not found)'}")
            print(f"      phones : {info.get('phones') or []}")
            print(f"      email  : {info.get('email') or '-'}")
            addr = re.search(r'(?:Vestigingsadres|Bezoekadres|Adres)[:\s]*([^\n]{5,70})', text)
            print(f"      address: {addr.group(1).strip() if addr else '(not parsed)'}")
            for kw in ('Rechtsvorm', 'Statutaire naam', 'Handelsnaam', 'SBI'):
                m = re.search(kw + r'[:\s]*([^\n]{2,70})', text)
                if m:
                    print(f"      {kw:14}: {m.group(1).strip()}")
    finally:
        browser.__exit__(None, None, None)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
