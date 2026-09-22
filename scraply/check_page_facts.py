#!/usr/bin/env python3
"""
Dump the raw facts from one company.info page: the labelled KVK number and the
actual tel:/mailto: hrefs. No regex guessing over body text.

    python3 scraply/check_page_facts.py <url> [<url> ...]
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

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
    urls = sys.argv[1:]
    if not urls:
        print(__doc__)
        return 2
    email, password = creds()
    browser = BrowserAutomation(profile_path=None, profile_name='FACTS',
                                headless=True, implicit_wait=5)
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

        for url in urls:
            d.get(url)
            time.sleep(3)
            data = d.execute_script("""
                const tel = Array.from(document.querySelectorAll('a[href^="tel:"]')).map(a => a.getAttribute('href'));
                const mail = Array.from(document.querySelectorAll('a[href^="mailto:"]')).map(a => a.getAttribute('href'));
                const h1 = document.querySelector('h1');
                return {tel, mail, title: h1 ? h1.innerText.trim() : '', text: document.body.innerText};
            """)
            text = data['text']
            print("\n" + "=" * 78)
            print(f"URL   : {url.split('?')[0]}")
            print(f"TITLE : {data['title']}")
            print(f"tel:  hrefs -> {data['tel']}")
            print(f"mailto hrefs -> {data['mail']}")
            # Labelled fields only: find the label, then the value after it.
            for label in ('KvK-nummer', 'KVK-nummer', 'KvK nummer', 'Vestigingsnummer',
                          'Rechtsvorm', 'Statutaire naam', 'Vestigingsadres', 'Telefoon'):
                m = re.search(re.escape(label) + r'\s*\n?\s*([^\n]{1,60})', text)
                if m:
                    print(f"  {label:16}: {m.group(1).strip()}")
    finally:
        browser.__exit__(None, None, None)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
