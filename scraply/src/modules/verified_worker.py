"""
Conservative worker for the ownership-verified pipeline.

Differences from the original parallel_worker:

  * 2 workers instead of 3, 2-4s gaps instead of 1-3s. Verification opens
    several candidate pages per row, so request volume per row is higher; the
    lower concurrency keeps the total rate close to the old pipeline's.
  * Detects anti-bot challenges and backs off exponentially instead of
    hammering through them and getting the IP blocked.
  * Results are returned keyed by ROW INDEX. Workers finish out of order, so
    nothing may ever be written back positionally.
  * Never fabricates a row: a failure records the reason, not a guess.
"""
from __future__ import annotations

import random
import time
from threading import Lock
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger(__name__)

BROWSER_RECYCLE_INTERVAL = 30      # rows per browser, lower than before: more pages/row
MAX_CONSECUTIVE_ERRORS = 3
BUILD_ATTEMPTS = 3                 # a browser start can fail transiently (low memory)
BUILD_BACKOFF = 15                 # seconds, multiplied by the attempt number
BLOCK_BACKOFF_BASE = 60            # seconds; doubles per consecutive block
MAX_BLOCK_BACKOFF = 900

OUTPUT_COLUMNS = ['NUMBER 1', 'NUMBER 2', 'EMAIL', 'COMPANY_FOUND',
                  'CONFIDENCE', 'SOURCE', 'EVIDENCE']


class ResultStore:
    """Thread-safe {row_index: {column: value}}."""

    def __init__(self):
        self._lock = Lock()
        self._data: Dict[int, Dict[str, Any]] = {}
        self.processed = 0
        self.verified = 0
        self.empty = 0

    def put(self, row_index: int, values: Dict[str, Any], verified: bool) -> None:
        with self._lock:
            self._data[row_index] = values
            self.processed += 1
            if verified:
                self.verified += 1
            else:
                self.empty += 1

    def snapshot(self) -> Dict[int, Dict[str, Any]]:
        with self._lock:
            return dict(self._data)

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {'processed': self.processed, 'verified': self.verified,
                    'empty': self.empty}


# Call centres and paid service lines. They belong to a switchboard, never to
# the owner of a parcel, so they are not leads however well attributed.
SERVICE_PREFIXES = ('0900', '0800', '088', '085', '0906', '0909')


def is_service_number(num: str) -> bool:
    digits = ''.join(c for c in (num or '') if c.isdigit())
    return digits.startswith(SERVICE_PREFIXES)


def outcome_to_columns(outcome: Dict[str, Any]) -> Dict[str, str]:
    """Map a SearchOutcome onto the output columns. Empty means empty, never 'NULL'."""
    phones = [p for p in (outcome.get('phones') or []) if not is_service_number(p)][:2]
    return {
        'NUMBER 1': phones[0] if len(phones) > 0 else '',
        'NUMBER 2': phones[1] if len(phones) > 1 else '',
        'EMAIL': outcome.get('email') or '',
        'COMPANY_FOUND': outcome.get('company') or '',
        'CONFIDENCE': outcome.get('confidence') or '',
        'SOURCE': outcome.get('source') or '',
        'EVIDENCE': (outcome.get('evidence') or '')[:400],
    }


def _build(worker_id: int, email: str, password: str, max_candidates: int,
           min_delay: float, max_delay: float):
    from .browser_automation import BrowserAutomation
    from .verified_searcher import VerifiedSearcher
    # Starting Chrome can fail for a moment (machine briefly out of memory).
    # One failed start used to end the whole run, so retry before giving up.
    for attempt in range(1, BUILD_ATTEMPTS + 1):
        try:
            browser = BrowserAutomation(profile_path=None, profile_name=f'V{worker_id}',
                                        headless=True, implicit_wait=5)
            browser.__enter__()
            searcher = VerifiedSearcher(browser, email=email, password=password,
                                        max_candidates=max_candidates,
                                        min_delay=min_delay, max_delay=max_delay)
            return browser, searcher
        except Exception as e:
            logger.error(f"worker {worker_id}: browser build failed "
                         f"(attempt {attempt}/{BUILD_ATTEMPTS}) - {e}")
            if attempt < BUILD_ATTEMPTS:
                time.sleep(BUILD_BACKOFF * attempt)
    return None, None


def _close(browser, worker_id: int) -> None:
    if browser:
        try:
            browser.__exit__(None, None, None)
        except Exception as e:
            logger.warning(f"worker {worker_id}: close error ignored - {e}")


def process_rows(
    worker_id: int,
    rows: List[Dict[str, Any]],
    fields: Dict[str, str],
    email: str,
    password: str,
    store: ResultStore,
    cancel=None,
    max_candidates: int = 4,
    min_delay: float = 2.0,
    max_delay: float = 4.0,
    progress_cb=None,
) -> Dict[str, Any]:
    """
    fields maps logical name -> source column name:
        company, first_names (optional), street, house_number, city
    """
    from .verified_searcher import BlockedError

    logger.info(f"worker {worker_id}: starting on {len(rows)} rows")
    if worker_id > 1:
        time.sleep(random.uniform(3, 6) * (worker_id - 1))     # stagger logins

    browser, searcher = _build(worker_id, email, password, max_candidates, min_delay, max_delay)
    if not searcher:
        for r in rows:
            store.put(r['row_index'],
                      {**{c: '' for c in OUTPUT_COLUMNS},
                       'CONFIDENCE': 'ERROR', 'EVIDENCE': 'browser could not start'},
                      verified=False)
        return {'worker_id': worker_id, 'status': 'error'}

    since_recycle = 0
    consecutive_errors = 0
    block_hits = 0

    try:
        for row in rows:
            if cancel is not None and cancel.is_set():
                logger.warning(f"worker {worker_id}: cancelled")
                return {'worker_id': worker_id, 'status': 'cancelled'}

            if since_recycle >= BROWSER_RECYCLE_INTERVAL:
                logger.info(f"worker {worker_id}: recycling browser")
                _close(browser, worker_id)
                time.sleep(2)
                browser, searcher = _build(worker_id, email, password,
                                           max_candidates, min_delay, max_delay)
                if not searcher:
                    # A failed rebuild used to end the run silently and leave the
                    # rest of the file blank. Wait out whatever starved the
                    # machine and keep trying before giving up.
                    for wait in (30, 60, 120, 240):
                        if cancel is not None and cancel.is_set():
                            return {'worker_id': worker_id, 'status': 'cancelled'}
                        logger.warning(f"worker {worker_id}: rebuild failed, retrying in {wait}s")
                        time.sleep(wait)
                        browser, searcher = _build(worker_id, email, password,
                                                   max_candidates, min_delay, max_delay)
                        if searcher:
                            break
                if not searcher:
                    logger.error(f"worker {worker_id}: repeated rebuild failures, stopping")
                    break
                since_recycle = 0

            def col(key: str) -> str:
                return (row.get(fields.get(key, '')) or '').strip()

            # Dutch surnames carry the particle in a separate column
            # ('voorvoegsel'). Searching "Diessen" instead of "van Diessen"
            # finds nothing, so the name is composed, not taken raw.
            prefix = col('name_prefix')
            base = col('company')
            lead = f"{prefix} {base}".strip() if prefix else base
            first = col('first_names')
            street, house, city = col('street'), col('house_number'), col('city')

            postcode = col('postcode')
            alt = []
            alt_street, alt_house, alt_city = (col('alt_street'), col('alt_house'),
                                               col('alt_city'))
            alt_post = col('alt_postcode')
            if alt_street and (alt_street, alt_house) != (street, house):
                alt.append((alt_street, alt_house, alt_city or city, alt_post))

            if not lead and not street and not alt:
                store.put(row['row_index'],
                          {**{c: '' for c in OUTPUT_COLUMNS},
                           'CONFIDENCE': '', 'EVIDENCE': ''},
                          verified=False)
                continue

            try:
                outcome = searcher.search(lead, first, street, house, city,
                                          postcode=postcode, alt_addresses=alt)
                consecutive_errors = 0
                block_hits = 0
            except BlockedError as be:
                block_hits += 1
                wait = min(BLOCK_BACKOFF_BASE * (2 ** (block_hits - 1)), MAX_BLOCK_BACKOFF)
                logger.warning(f"worker {worker_id}: BLOCKED ({be}) - backing off {wait}s")
                _close(browser, worker_id)
                slept = 0
                while slept < wait:
                    if cancel is not None and cancel.is_set():
                        return {'worker_id': worker_id, 'status': 'cancelled'}
                    time.sleep(5)
                    slept += 5
                browser, searcher = _build(worker_id, email, password,
                                           max_candidates, min_delay, max_delay)
                since_recycle = 0
                if not searcher:
                    break
                continue                     # retry this row on the next loop pass
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"worker {worker_id} row {row['row_index']}: {e}")
                outcome = {'phones': [], 'email': '', 'company': '',
                           'confidence': 'ERROR', 'source': '',
                           'evidence': str(e)[:200]}
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.warning(f"worker {worker_id}: {consecutive_errors} errors, restarting browser")
                    _close(browser, worker_id)
                    time.sleep(5)
                    browser, searcher = _build(worker_id, email, password,
                                               max_candidates, min_delay, max_delay)
                    since_recycle = 0
                    consecutive_errors = 0
                    if not searcher:
                        break

            cols = outcome_to_columns(outcome)
            store.put(row['row_index'], cols,
                      verified=cols['CONFIDENCE'].startswith('VERIFIED'))
            since_recycle += 1
            if progress_cb:
                try:
                    progress_cb(store.stats())
                except Exception:
                    pass

        return {'worker_id': worker_id, 'status': 'completed', **store.stats()}
    finally:
        _close(browser, worker_id)
