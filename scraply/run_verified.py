#!/usr/bin/env python3
"""
Standalone runner for the ownership-verified pipeline.

    python scraply/run_verified.py INPUT.xlsx --company naam --street adres \
        --house huisnummer --city plaats [--first-names voornamen] \
        [--workers 2] [--limit 10] [--out OUTPUT.xlsx]

Input may be .xlsx or .csv. Output is a COPY of the input with these columns
appended, so the file you hand over keeps its original layout:

    NUMBER 1, NUMBER 2, EMAIL, COMPANY_FOUND, CONFIDENCE, SOURCE, EVIDENCE

CONFIDENCE values:
    VERIFIED-NAME   exact company-name match (address-disambiguated if needed)
    VERIFIED-OWNER  found by address AND the owner is named on the company page
    AMBIGUOUS-NAME  several identically named entities, address could not decide
    NOT-FOUND       nothing that could be attributed to this owner
    ERROR           technical failure, reason in EVIDENCE
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scraply'))

from scraply.src.modules.tabular_io import TabularFile            # noqa: E402
from scraply.src.modules.verified_worker import (                  # noqa: E402
    OUTPUT_COLUMNS, ResultStore, process_rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('input')
    p.add_argument('--company', required=True, help='column holding the owner / company name')
    p.add_argument('--street', required=True)
    p.add_argument('--house', required=True)
    p.add_argument('--city', required=True)
    p.add_argument('--first-names', default='', help='optional column with given names')
    p.add_argument('--name-prefix', default='',
                   help="optional column with the Dutch name particle (e.g. 'voorvoegsel'); "
                        "composed as '<prefix> <company>' before searching")
    p.add_argument('--alt-street', default='', help='optional secondary address column (e.g. parcel street)')
    p.add_argument('--alt-house', default='')
    p.add_argument('--alt-city', default='')
    p.add_argument('--sheet', default=None)
    p.add_argument('--out', default=None)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--limit', type=int, default=0, help='process only the first N non-blank rows')
    p.add_argument('--max-candidates', type=int, default=4)
    p.add_argument('--min-delay', type=float, default=2.0)
    p.add_argument('--max-delay', type=float, default=4.0)
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
    tf = TabularFile(src, sheet=args.sheet)
    rows = tf.read_rows()

    wanted = [args.company, args.street, args.house, args.city,
              args.first_names, args.name_prefix,
              args.alt_street, args.alt_house, args.alt_city]
    missing = [c for c in wanted if c and c not in tf.headers]
    if missing:
        print(f'ERROR: column(s) not in file: {missing}')
        print(f'available: {tf.headers[:40]}{" ..." if len(tf.headers) > 40 else ""}')
        return 2

    work = [r for r in rows if not TabularFile.is_blank(r)]
    if args.limit:
        work = work[:args.limit]
    print(f'file      : {src.name}  ({len(rows)} rows, {len(tf.headers)} cols)')
    print(f'to process: {len(work)}')
    print(f'workers   : {args.workers}   candidates/row: {args.max_candidates}   '
          f'delay: {args.min_delay}-{args.max_delay}s')

    fields = {'company': args.company, 'street': args.street,
              'house_number': args.house, 'city': args.city,
              'first_names': args.first_names, 'name_prefix': args.name_prefix,
              'alt_street': args.alt_street, 'alt_house': args.alt_house,
              'alt_city': args.alt_city}
    store = ResultStore()
    cancel = Event()

    # Round-robin so a slow patch of rows does not strand one worker.
    chunks = [work[i::args.workers] for i in range(args.workers)]
    started = time.time()
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = [ex.submit(process_rows, i + 1, chunks[i], fields, email, password,
                                 store, cancel, args.max_candidates,
                                 args.min_delay, args.max_delay)
                       for i in range(args.workers) if chunks[i]]
            last = 0
            while any(not f.done() for f in futures):
                time.sleep(10)
                s = store.stats()
                if s['processed'] != last:
                    last = s['processed']
                    el = time.time() - started
                    rate = s['processed'] / el * 60 if el else 0
                    print(f"  {s['processed']}/{len(work)}  verified={s['verified']}  "
                          f"empty={s['empty']}  ({rate:.1f} rows/min)", flush=True)
            for f in futures:
                f.result()
    except KeyboardInterrupt:
        print('\ninterrupted - writing what we have')
        cancel.set()

    out = Path(args.out) if args.out else src.with_name(f'{src.stem} MET CONTACTGEGEVENS{src.suffix}')
    filled = tf.write_output(out, OUTPUT_COLUMNS, store.snapshot())

    s = store.stats()
    print(f'\nwrote {out}')
    print(f'  rows populated : {filled}')
    print(f'  verified       : {s["verified"]}')
    print(f'  no attribution : {s["empty"]}')
    print(f'  elapsed        : {(time.time() - started) / 60:.1f} min')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
