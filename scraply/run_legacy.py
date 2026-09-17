#!/usr/bin/env python3
"""
Legacy CompanyInfo runner - the ORIGINAL searcher, our same-file writer.

Drives the pre-existing CompanyInfoSearcher (the engine behind the nicky.tools
jobs) but writes like run_verified.py does: the output is a COPY of the input
workbook with columns appended, so every sheet, row and bit of styling survives.

    python scraply/run_legacy.py INPUT.xlsx [--out OUT.xlsx] [--limit N]

Sheet, header row and the owner/address columns are detected automatically, so
the same command works whether the header is on row 1 or under a group-label
row. Appended columns (the legacy set):

    NUMBER 1..NUMBER 5, EMAIL, BUSINESS_NAME, OWNER_NAME, NOTE
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scraply'))

from scraply.src.modules.kadaster_map import detect              # noqa: E402
from scraply.src.modules.tabular_io import TabularFile           # noqa: E402

OUTPUT_COLUMNS = ['NUMBER 1', 'NUMBER 2', 'NUMBER 3', 'NUMBER 4', 'NUMBER 5',
                  'EMAIL', 'BUSINESS_NAME', 'OWNER_NAME', 'NOTE']
BUILD_ATTEMPTS = 3
RECYCLE_EVERY = 40


def _build(email: str, password: str, timeout: int):
    """Start Chrome + the legacy searcher, retrying a transient failure."""
    from scraply.src.modules.browser_automation import BrowserAutomation
    from scraply.src.modules.companyinfo_searcher import CompanyInfoSearcher
    for attempt in range(1, BUILD_ATTEMPTS + 1):
        try:
            browser = BrowserAutomation(profile_path=None, profile_name='LEGACY',
                                        headless=True, implicit_wait=5)
            browser.__enter__()
            # BrowserAutomation defaults to a 5s page-load timeout. company.info's
            # login page is heavier than that, so navigation timed out and every
            # row came back empty. Use the same budget as the verified pipeline.
            try:
                browser.driver.set_page_load_timeout(45)
                browser.driver.set_script_timeout(30)
            except Exception as e:
                print(f'  could not widen timeouts: {e}', flush=True)
            searcher = CompanyInfoSearcher(browser=browser, base_url='https://company.info',
                                           timeout=timeout, email=email, password=password)
            return browser, searcher
        except Exception as e:
            print(f'  browser start failed ({attempt}/{BUILD_ATTEMPTS}): {e}', flush=True)
            if attempt < BUILD_ATTEMPTS:
                time.sleep(15 * attempt)
    return None, None


def _close(browser):
    if browser:
        try:
            browser.__exit__(None, None, None)
        except Exception:
            pass


def _columns(info: dict) -> dict:
    """Legacy result -> output columns. Empty stays empty (never the text NULL)."""
    if info.get('skip'):
        return {'NOTE': info.get('note') or 'SKIPPED: Too many businesses'}
    phones = info.get('phones') or []
    out = {f'NUMBER {i}': (phones[i - 1] if i <= len(phones) else '') for i in range(1, 6)}
    out['EMAIL'] = info.get('email') or ''
    out['BUSINESS_NAME'] = info.get('business') or ''
    out['OWNER_NAME'] = info.get('owner') or ''
    out['NOTE'] = info.get('note') or ''
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('input')
    p.add_argument('--sheet', default=None)
    p.add_argument('--header-row', type=int, default=0, help='0 = detect')
    p.add_argument('--company', default='')
    p.add_argument('--street', default='')
    p.add_argument('--house', default='')
    p.add_argument('--city', default='')
    p.add_argument('--out', default=None)
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--timeout', type=int, default=30)
    p.add_argument('--min-delay', type=float, default=1.0)
    p.add_argument('--max-delay', type=float, default=3.0)
    p.add_argument('--email', default='')
    p.add_argument('--password', default='')
    args = p.parse_args()

    import os
    email = args.email or os.environ.get('COMPANYINFO_EMAIL', '')
    password = args.password or os.environ.get('COMPANYINFO_PASSWORD', '')
    if not email or not password:
        print('ERROR: set --email/--password or COMPANYINFO_EMAIL/COMPANYINFO_PASSWORD')
        return 2

    src = Path(args.input)
    det = detect(src, sheet=args.sheet)
    sheet = args.sheet or det['sheet']
    header_row = args.header_row or det['header_row']
    f = det['fields']
    col_company = args.company or f.get('company', '')
    col_prefix = f.get('name_prefix', '')
    col_street = args.street or f.get('street', '')
    col_house = args.house or f.get('house_number', '')
    col_city = args.city or f.get('city', '')

    tf = TabularFile(src, sheet=sheet, header_row=header_row)
    rows = [r for r in tf.read_rows() if not TabularFile.is_blank(r)]
    if args.limit:
        rows = rows[:args.limit]

    print(f'file      : {src.name}')
    print(f'sheet     : {sheet!r}  header row {header_row}')
    print(f'columns   : name={col_company!r} prefix={col_prefix!r} '
          f'street={col_street!r} house={col_house!r} city={col_city!r}')
    print(f'to process: {len(rows)}', flush=True)

    browser, searcher = _build(email, password, args.timeout)
    if not searcher:
        print('ERROR: browser could not start')
        return 1

    results, found, empty = {}, 0, 0
    started = time.time()
    since_recycle = 0
    try:
        for n, row in enumerate(rows, 1):
            get = lambda c: (row.get(c) or '').strip() if c else ''
            name = f"{get(col_prefix)} {get(col_company)}".strip()
            street, house, city = get(col_street), get(col_house), get(col_city)
            if not name and not street:
                results[row['row_index']] = {}
                empty += 1
                continue

            if since_recycle >= RECYCLE_EVERY:
                _close(browser)
                time.sleep(2)
                browser, searcher = _build(email, password, args.timeout)
                if not searcher:
                    print('browser could not be restarted - stopping early', flush=True)
                    break
                since_recycle = 0

            try:
                info = searcher.search_company(company_name=name, street=street,
                                               house_number=house, city=city)
            except Exception as e:
                # A crashed browser must not end the run: restart and retry once.
                print(f'  row {n} error: {str(e)[:80]}', flush=True)
                _close(browser)
                time.sleep(3)
                browser, searcher = _build(email, password, args.timeout)
                since_recycle = 0
                if not searcher:
                    break
                try:
                    info = searcher.search_company(company_name=name, street=street,
                                                   house_number=house, city=city)
                except Exception as e2:
                    info = {'phones': [], 'email': '', 'business': '', 'owner': '',
                            'note': f'ERROR: {str(e2)[:80]}'}

            cols = _columns(info)
            results[row['row_index']] = cols
            if cols.get('NUMBER 1') or cols.get('EMAIL'):
                found += 1
            else:
                empty += 1
            since_recycle += 1

            el = time.time() - started
            rate = n / el * 60 if el else 0
            print(f'  {n}/{len(rows)}  found={found}  empty={empty}  ({rate:.1f} rows/min)',
                  flush=True)
            time.sleep(random.uniform(args.min_delay, args.max_delay))
    except KeyboardInterrupt:
        print('\ninterrupted - writing what we have', flush=True)
    finally:
        _close(browser)

    out = Path(args.out) if args.out else src.with_name(f'{src.stem} LEGACY{src.suffix}')
    filled = tf.write_output(out, OUTPUT_COLUMNS, results)
    print(f'\nwrote {out}')
    print(f'  rows populated : {filled}')
    print(f'  with contact   : {found}')
    print(f'  without        : {empty}')
    print(f'  elapsed        : {(time.time() - started) / 60:.1f} min')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
