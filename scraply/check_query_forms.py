#!/usr/bin/env python3
"""
Compare how company.info answers the same address written different ways, so the
search query can be chosen on evidence rather than habit.

    python3 scraply/check_query_forms.py "Nieuwstad|12|7141BD|GROENLO" ...

Each argument is street|house|postcode|city.
"""
from __future__ import annotations

import sys
import time
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
    items = [a.split('|') for a in sys.argv[1:]]
    if not items:
        print(__doc__)
        return 2
    email, password = creds()
    browser = BrowserAutomation(profile_path=None, profile_name='QFORM',
                                headless=True, implicit_wait=5)
    browser.__enter__()
    try:
        s = VerifiedSearcher(browser, email=email, password=password,
                             max_candidates=4, min_delay=1.0, max_delay=2.0)
        if not s.ensure_login():
            print('login failed')
            return 1
        for street, house, postcode, city in items:
            forms = [
                ('street house city',      f"{street} {house} {city}"),
                ('street house postcode',  f"{street} {house} {postcode}"),
                ('postcode house',         f"{postcode} {house}"),
                ('postcode only',          f"{postcode}"),
                ('street house',           f"{street} {house}"),
            ]
            print("\n" + "=" * 76)
            print(f"ADDRESS: {street} {house}, {postcode} {city}")
            for label, q in forms:
                try:
                    names = s._search(q)
                except Exception as e:
                    print(f"  {label:24} ERROR {e}")
                    continue
                shown = ', '.join(n[:26] for n in names[:3])
                print(f"  {label:24} {len(names):>3} results   {shown}")
                time.sleep(1.2)
    finally:
        browser.__exit__(None, None, None)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
