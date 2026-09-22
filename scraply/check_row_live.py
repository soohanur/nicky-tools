#!/usr/bin/env python3
"""
Run the verified engine against a single row and print the verdict plus the
evidence it rests on. Use it to check a change before spending two hours on a
full run.

    python3 scraply/check_row_live.py "OWNER|FIRST|STREET|HOUSE|CITY|POSTCODE|ALTSTREET|ALTHOUSE|ALTCITY"
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scraply'))

from scraply.src.modules.browser_automation import BrowserAutomation    # noqa: E402
from scraply.src.modules.verified_searcher import VerifiedSearcher      # noqa: E402


def creds():
    out = {}
    for line in (ROOT / 'backend' / '.env').read_text(errors='replace').splitlines():
        if line.startswith(('COMPANYINFO_EMAIL=', 'COMPANYINFO_PASSWORD=')):
            k, _, v = line.partition('=')
            out[k.strip()] = v.strip().strip('"').strip('\r')
    return out.get('COMPANYINFO_EMAIL', ''), out.get('COMPANYINFO_PASSWORD', '')


def main() -> int:
    specs = [a.split('|') for a in sys.argv[1:]]
    if not specs:
        print(__doc__)
        return 2
    email, password = creds()
    browser = BrowserAutomation(profile_path=None, profile_name='ROWCHK',
                                headless=True, implicit_wait=5)
    browser.__enter__()
    try:
        s = VerifiedSearcher(browser, email=email, password=password,
                             max_candidates=4, min_delay=1.5, max_delay=2.5)
        for spec in specs:
            f = (spec + [''] * 9)[:9]
            owner, first, street, house, city, postcode, a_st, a_hs, a_ct = f
            alt = [(a_st, a_hs, a_ct, '')] if a_st else []
            print("\n" + "=" * 76)
            print(f"OWNER    : {owner!r}  ({street} {house}, {postcode} {city})")
            out = s.search(owner, first, street, house, city,
                           postcode=postcode, alt_addresses=alt)
            print(f"CONF     : {out.get('confidence')}")
            print(f"PHONES   : {out.get('phones')}   EMAIL: {out.get('email')!r}")
            print(f"COMPANY  : {out.get('company')!r}")
            print(f"SOURCE   : {out.get('source')}")
            print(f"EVIDENCE : {out.get('evidence')}")
    finally:
        browser.__exit__(None, None, None)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
