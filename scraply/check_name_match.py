#!/usr/bin/env python3
"""
Show what the verified engine reads back for a name search, and why a result
does or does not count as an exact match.

    python3 scraply/check_name_match.py "L. Wolterink B.V." "Fides Holding B.V."
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scraply'))

from scraply.src.modules.browser_automation import BrowserAutomation        # noqa: E402
from scraply.src.modules.verified_searcher import (VerifiedSearcher,        # noqa: E402
                                                   compare_key)


def creds():
    out = {}
    for line in (ROOT / 'backend' / '.env').read_text(errors='replace').splitlines():
        if line.startswith(('COMPANYINFO_EMAIL=', 'COMPANYINFO_PASSWORD=')):
            k, _, v = line.partition('=')
            out[k.strip()] = v.strip().strip('"').strip('\r')
    return out.get('COMPANYINFO_EMAIL', ''), out.get('COMPANYINFO_PASSWORD', '')


def main() -> int:
    names = sys.argv[1:]
    if not names:
        print(__doc__)
        return 2
    email, password = creds()
    browser = BrowserAutomation(profile_path=None, profile_name='NAMECHK',
                                headless=True, implicit_wait=5)
    browser.__enter__()
    try:
        s = VerifiedSearcher(browser, email=email, password=password,
                             max_candidates=4, min_delay=1.0, max_delay=2.0)
        if not s.ensure_login():
            print('login failed')
            return 1
        for want in names:
            got = s._search(want)
            target = compare_key(want)
            print("\n" + "=" * 76)
            print(f"SEARCHED : {want!r}")
            print(f"compare_key(target) = {target!r}")
            print(f"results  : {len(got)}")
            for i, n in enumerate(got[:8]):
                k = compare_key(n)
                print(f"  #{i+1} {n!r}")
                print(f"      compare_key = {k!r}   {'== EXACT MATCH' if k == target else ''}")
            time.sleep(1)
    finally:
        browser.__exit__(None, None, None)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
