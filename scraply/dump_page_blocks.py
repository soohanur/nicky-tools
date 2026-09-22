#!/usr/bin/env python3
"""
Dump the identity-bearing parts of a company.info page: the name block, the
address block, and the people/owner blocks. Used to decide what a strict
"same address AND same business" test can actually rest on.

    python3 scraply/dump_page_blocks.py <url>
"""
from __future__ import annotations

import re
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
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    email, password = creds()
    browser = BrowserAutomation(profile_path=None, profile_name='BLOCKS',
                                headless=True, implicit_wait=5)
    browser.__enter__()
    try:
        s = VerifiedSearcher(browser, email=email, password=password)
        s.ensure_login()
        d = browser.driver
        for url in sys.argv[1:]:
            d.get(url)
            time.sleep(3.5)
            text = d.execute_script("return document.body.innerText || ''") or ''
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            print("\n" + "=" * 78)
            print(f"URL: {url.split('?')[0]}")
            print(f"total lines: {len(lines)}")
            print("\n--- first 30 lines (name + address block) ---")
            for l in lines[:30]:
                print(f"   {l[:78]}")
            print("\n--- lines around people/owner headings ---")
            for i, l in enumerate(lines):
                if re.fullmatch(r'(Management|Eigenaar|Aandeelhouders?|Bestuurders?|'
                                r'Functionarissen|Vennoten|Enig aandeelhouder)', l, re.I):
                    print(f"   [{l}]")
                    for x in lines[i + 1:i + 7]:
                        print(f"       {x[:70]}")
    finally:
        browser.__exit__(None, None, None)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
