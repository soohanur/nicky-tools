"""
Ownership-verified CompanyInfo search.

Every rule below exists because the original searcher produced a concrete wrong
answer on a real kadaster export. The failures, and what fixes them:

  1. `_find_exact_name_match` compared the ANCHOR text, which carries the
     address and KVK on following lines, so "van Diessen" never equalled
     "van Diessen\\nDe Run 8274\\n..." and a valid match was discarded as
     NOT FOUND.                                   -> compare the result NAME only.

  2. It returned on the FIRST exact match. "Walle Beheer B.V." has two
     identical entries; #1 has no contact details, #2 holds 0402840576, and the
     row was written off.                         -> try every exact match.

  3. The address fallback clicked result #1 with no verification whatsoever.
     "Briljant 3" returns 25 results; the tool took a dental practice's number
     and filed it under a real-estate lead.       -> require ownership proof.

  4. Duplicate company names were never disambiguated. "ERMA B.V." has 8
     identically named entities.                  -> disambiguate by address.

  5. Matching on a generic Dutch word proves nothing. "STICHTING BEHEER ...
     VAN DER SANDEN" matched "Bouwbedrijf Daamen B.V." on the word 'beheer',
     while the real match (J. van der Sanden Holding B.V.) sat two results
     lower.                                       -> generic words are not evidence.

  6. A >=4 character token rule silently excludes short Dutch surnames. "Bas"
     was graded a tenant even though 'paul bas design B.V.' is his own company.
                                                  -> allow 3-char tokens, but
                                                     only with corroboration.

Nothing here ever writes contact data it cannot attribute. When attribution
fails the row is returned empty with the reason recorded, because a blank cell
is recoverable and a stranger's phone number is not.
"""
from __future__ import annotations

import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .browser_automation import BrowserAutomation
from ..utils.logger import setup_logger

logger = setup_logger('verified_searcher')

BASE = 'https://company.info'

# Trailing legal forms, stripped before comparing company names.
# Deliberately NOT including 'holding' / 'beheer': "X Beheer B.V." and
# "X Holding B.V." are separate legal entities and must never compare equal.
# They are handled as non-identifying words via GENERIC instead.
LEGAL_SUFFIX = r'\s*(b\.?\s?v\.?|n\.?\s?v\.?|v\.?o\.?f\.?|c\.?v\.?)\s*$'

# Dutch name particles - never identifying on their own.
PARTICLES = {"van", "de", "den", "der", "het", "ter", "te", "aan", "in", "op",
             "'t", "d'", "du", "la", "le", "of", "and", "en"}

# Generic corporate words. Matching one of these proves nothing about ownership:
# roughly a third of Dutch company names contain 'beheer' or 'holding'.
GENERIC = {
    # corporate / legal filler
    "beheer", "holding", "vastgoed", "onroerend", "goed", "stichting",
    "exploitatie", "exploitatiemaatschappij", "maatschappij", "bedrijf",
    "bedrijven", "groep", "group", "nederland", "nederlandse", "invest",
    "investment", "investments", "participatie", "participaties", "projecten",
    "project", "ontwikkeling", "vermogen", "management", "service", "services",
    "zonen", "gebroeders", "gebr", "handel", "handels", "verhuur", "diensten",
    "advies", "adviesbureau", "consultancy", "vennootschap", "administratie",
    "kantoor", "immo", "estate", "real", "algemene", "vereniging", "eigenaars",
    # industry words - 'bouw' alone matched an unrelated construction firm and
    # attributed its number to a different company entirely
    "bouw", "bouwbedrijf", "bouwmaatschappij", "aannemer", "aannemers",
    "aannemersbedrijf", "transport", "transporten", "techniek", "technisch",
    "technische", "installatie", "installaties", "auto", "autobedrijf",
    "garage", "makelaar", "makelaardij", "notaris", "advocaten", "interieur",
    "interieurbouw", "metaal", "elektro", "schilder", "dakbedekking", "zorg",
    "recycling", "logistiek", "food", "trading", "retail", "design",
    # English corporate filler - 'netherlands' alone matched "Dream Industrial
    # Netherlands" to an unrelated company and produced two wrong numbers.
    "netherlands", "dutch", "europe", "european", "international", "global",
    "properties", "property", "industrial", "capital", "partners", "ventures",
    "solutions", "systems", "consulting", "enterprise", "enterprises",
    "company", "corporation", "limited", "trust", "asset", "assets", "finance",
    "financial", "development", "developments", "resources",
}

# company.info's own switchboard, in every normalisation variant.
BLACKLIST_CORE = "202400400"

MAX_PHONES = 2

# Signals that we have been rate limited / challenged.
BLOCK_MARKERS = ["are you a robot", "captcha", "verify you are human",
                 "too many requests", "rate limit", "access denied",
                 "unusual traffic", "cloudflare"]


class BlockedError(Exception):
    """Raised when company.info appears to be challenging or throttling us."""


# --------------------------------------------------------------------- utils

def normalise_phone(raw: str) -> str:
    """+31 6 12345678 / 0031... / 612345678  ->  0612345678"""
    if not raw:
        return ''
    c = re.sub(r'[^\d+]', '', raw)
    if c.startswith('+31'):
        c = '0' + c[3:]
    elif c.startswith('0031'):
        c = '0' + c[4:]
    elif c.startswith('31') and len(c) >= 11:
        c = '0' + c[2:]
    elif not c.startswith('0') and len(c) >= 9:
        c = '0' + c
    return c


def is_own_number(num: str) -> bool:
    d = re.sub(r'\D', '', num or '')
    return d.endswith(BLACKLIST_CORE) and len(d) <= 13


def strip_legal(name: str) -> str:
    return re.sub(LEGAL_SUFFIX, '', (name or '').strip().lower(), flags=re.I).strip()


def compare_key(name: str) -> str:
    """
    Key for deciding 'is this the same company name'.

    Registers and exports punctuate differently for the same entity - a sheet
    may hold "Bouw- en Exploitatiemaatschappij Bem B.V." while company.info
    shows "Bouw- En Exploitatiemaatschappij B.E.M. B.V.". Literal equality
    calls those different and throws the row away, so we drop punctuation and
    collapse whitespace before comparing.

    This only loosens PUNCTUATION. Word content must still match exactly, so
    "Walle Beheer" and "Walle" remain different companies.
    """
    base = strip_legal(name)
    # Dots are DELETED, not spaced out, so initialisms collapse:
    # "B.E.M." -> "bem", which then equals a sheet's "Bem".
    base = base.replace('.', '')
    base = re.sub(r'[^\wÀ-ÿ]+', ' ', base)
    return ' '.join(base.split())


def _split(text: str) -> List[str]:
    return [w for w in re.split(r"[^\wÀ-ÿ']+", strip_legal(text or '')) if w]


def name_tokens(surname_part: str, first_names: str = '') -> Tuple[List[str], List[str], List[str]]:
    """
    Split an owner into (surname_strong, surname_short, given_names).

    The distinction matters. A SURNAME or trade name identifies a company;
    a GIVEN name does not. Matching 'richard' alone attributed a stranger's
    number to R. van den Broek, because 'richard' appears on countless pages.
    Given names are therefore corroboration only, never proof on their own.

    surname_strong : >=4 chars, not a particle, not a generic/industry word
    surname_short  : exactly 3 chars (e.g. 'Bas', 'Ven') - needs corroboration
    given_names    : >=3 chars from the first-name column - corroboration only
    """
    strong, short = [], []
    for w in _split(surname_part):
        if w in PARTICLES:
            continue
        if len(w) >= 4 and w not in GENERIC:
            strong.append(w)
        elif len(w) == 3:
            short.append(w)
    given = [w for w in _split(first_names)
             if len(w) >= 3 and w not in PARTICLES and w not in GENERIC]
    return strong, short, given


def find_tokens(haystack: str, tokens: List[str]) -> List[str]:
    low = (haystack or '').lower()
    return [t for t in tokens if re.search(r'\b' + re.escape(t) + r'\b', low)]


def address_tokens(street: str, house: str) -> Tuple[List[str], str]:
    """
    Street words in order, plus the house number.

    Keeps short words: Dutch street names are full of them ("De Run",
    "Hout oost"). An earlier >=4-char filter emptied "De Run" entirely, so the
    address check silently returned False for every parcel on that street.
    Order is preserved because the words are matched as a phrase, which is what
    makes 'de' or 'run' safe to include.
    """
    st = [w for w in re.split(r"[^\wÀ-ÿ']+", (street or '').lower()) if len(w) >= 2]
    return st, re.sub(r'\D', '', house or '')


def address_regex(street: str, house: str) -> Optional[re.Pattern]:
    """
    Pattern that matches "<street> <number>" as a real address.

    The street words are matched as a PHRASE so short words like 'de' or 'run'
    are safe to include, with room for abbreviations between them
    ("Willem v Konijnenburgln"). The house number must follow within a few
    characters, which is what stops 'hout' here and '13' over there from
    counting as "Hout oost 13".
    """
    tokens, hnum = address_tokens(street, house)
    if not tokens:
        return None
    gap = r'(?:\s+\S{1,4})*\s+'
    phrase = gap.join(re.escape(t) for t in tokens)
    if not hnum:
        return re.compile(r'\b' + phrase + r'\b', re.I)
    # allow "12", "12 A", "12-3", "12," directly after the street
    return re.compile(r'\b' + phrase + r'\b[^\w]{0,4}\w{0,3}[^\w]{0,4}\b'
                      + re.escape(hnum) + r'\b', re.I)


class SearchOutcome(dict):
    """phones / email / company / confidence / source / evidence"""

    @classmethod
    def empty(cls, confidence: str, evidence: str) -> 'SearchOutcome':
        return cls(phones=[], email='', company='', confidence=confidence,
                   source='', evidence=evidence)


# ------------------------------------------------------------------- searcher

class VerifiedSearcher:
    """
    Conservative, attribution-first searcher.

    max_candidates caps how many company pages we open per row. Every page open
    is an HTTP request to company.info; the cap plus `pause()` keeps request
    volume close to a human browsing rate so we do not get the IP blocked.
    """

    def __init__(
        self,
        browser: BrowserAutomation,
        email: str = '',
        password: str = '',
        max_candidates: int = 4,
        min_delay: float = 2.0,
        max_delay: float = 4.0,
    ):
        self.browser = browser
        self.driver = browser.driver
        self.email = email
        self.password = password
        self.max_candidates = max_candidates
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.logged_in = False
        self.pages_opened = 0
        # BrowserAutomation defaults to 5s for both page load and async script,
        # which is far too tight here: company.info pages are heavy and a script
        # timeout kills the renderer outright (ERR_CONNECTION_REFUSED for every
        # request afterwards). Widen them on our own driver.
        try:
            self.driver.set_page_load_timeout(45)
            self.driver.set_script_timeout(30)
        except Exception as e:
            logger.debug(f"could not widen timeouts: {e}")

    # ---------------------------------------------------------------- infra

    def pause(self) -> None:
        """Human-ish gap between requests (anti-bot)."""
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def _check_blocked(self) -> None:
        try:
            body = self.driver.page_source.lower()
        except Exception:
            return
        for marker in BLOCK_MARKERS:
            if marker in body:
                raise BlockedError(f"block signal on page: '{marker}'")

    def _goto(self, url: str, settle: float = 1.4) -> None:
        self.driver.get(url)
        try:
            WebDriverWait(self.driver, 12).until(
                lambda d: d.execute_script("return document.readyState") in ('interactive', 'complete'))
        except Exception:
            pass
        time.sleep(settle)
        self.pages_opened += 1
        self._check_blocked()

    def ensure_login(self) -> bool:
        if self.logged_in:
            return True
        try:
            self._goto(f'{BASE}/login')
            if not self.driver.find_elements(By.ID, 'username'):
                self.logged_in = True          # already authenticated via session
                return True
            self.driver.find_element(By.ID, 'username').send_keys(self.email)
            self.driver.find_element(By.ID, 'ci-login').click()
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='password']")))
            self.driver.find_element(By.XPATH, "//input[@type='password']").send_keys(self.password)
            for by, sel in [(By.ID, 'ci-login'), (By.XPATH, "//button[@type='submit']")]:
                try:
                    WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((by, sel))).click()
                    break
                except Exception:
                    continue
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.invisibility_of_element_located((By.XPATH, "//input[@type='password']")))
            except Exception:
                pass
            self.logged_in = not self.driver.find_elements(By.XPATH, "//input[@type='password']")
            logger.info(f"login {'OK' if self.logged_in else 'FAILED'}")
            return self.logged_in
        except BlockedError:
            raise
        except Exception as e:
            logger.error(f"login error: {e}")
            return False

    # --------------------------------------------------------------- reading

    # Selenium's `element.text` returns only RENDERED text, so a result below
    # the fold yields ''. That made exact-name matching non-deterministic
    # between runs - the same query matched once and missed the next time.
    # innerText read through JS is layout-independent, and one call for the
    # whole list is far cheaper than N round-trips.
    _RESULT_NAMES_JS = """
        return Array.from(document.querySelectorAll("li[data-cy='search-result']"))
            .map(function (li) {
                var t = li.innerText || li.textContent || '';
                return t.split('\\n').map(function (s) { return s.trim(); })
                        .filter(function (s) { return s.length; })[0] || '';
            });
    """

    def _results(self) -> List[str]:
        """Company name of each result currently listed."""
        try:
            names = self.driver.execute_script(self._RESULT_NAMES_JS)
            return [str(n).strip() for n in (names or [])]
        except Exception as e:
            logger.debug(f"result read failed, falling back to .text: {e}")
            out = []
            for el in self.driver.find_elements(By.CSS_SELECTOR, "li[data-cy='search-result']"):
                try:
                    out.append((el.text or '').split('\n')[0].strip())
                except Exception:
                    out.append('')
            return out

    # company.info is a Svelte app: after navigation the DOM briefly exists as
    # a shell with no company data in it. Reading then yields no owner tokens
    # and no address, so the SAME page verified on one run and failed on the
    # next. Wait for real content instead of guessing with a sleep.
    # NB: company.info company pages have NO <h1>. An earlier version waited for
    # one, timed out on every page, and skipped every candidate - deterministic
    # and deterministically wrong. Wait for the text to STOP GROWING instead,
    # which is what "hydrated" actually looks like here.
    _CONTENT_PROBE_JS = """
        return {len: ((document.body && document.body.textContent) || '').length,
                ready: document.readyState,
                links: document.querySelectorAll("a[href^='tel:'],a[href^='mailto:']").length};
    """
    MIN_CONTENT_CHARS = 4000

    def _wait_content(self, timeout: int = 15) -> bool:
        deadline = time.time() + timeout
        last, stable = -1, 0
        while time.time() < deadline:
            try:
                probe = self.driver.execute_script(self._CONTENT_PROBE_JS) or {}
            except Exception as e:
                logger.debug(f"content probe failed: {e}")
                return False
            size = int(probe.get('len') or 0)
            if probe.get('ready') == 'complete' and size >= self.MIN_CONTENT_CHARS:
                if size == last:
                    stable += 1
                    if stable >= 2:
                        return True
                else:
                    stable = 0
                last = size
            time.sleep(0.35)
        # Lenient tail: substantial content is good enough even if it never
        # settled, because rejecting it means a false NOT-FOUND.
        return last >= self.MIN_CONTENT_CHARS

    def _open_result(self, index: int) -> bool:
        items = self.driver.find_elements(By.CSS_SELECTOR, "li[data-cy='search-result']")
        if index >= len(items):
            return False
        try:
            href = items[index].find_element(By.TAG_NAME, 'a').get_attribute('href')
        except Exception:
            return False
        if not href:
            return False
        self._goto(href if href.startswith('http') else BASE + href, settle=0.3)
        # Never evaluate ownership against a half-rendered page.
        return self._wait_content()

    def _search(self, query: str) -> List[str]:
        """
        Run a search and wait until the list has actually rendered.

        A fixed sleep is not enough: reading too early returns a skeleton row
        whose name is empty, which then fails exact matching and silently
        discards a valid company. Wait for a real result or an explicit
        'no results' before reading.
        """
        url = f'{BASE}/organisations/search?query={quote(query)}'
        ready_js = (
            "var li = document.querySelectorAll(\"li[data-cy='search-result']\");"
            "for (var i = 0; i < li.length; i++) {"
            "  var s = (li[i].innerText || li[i].textContent || '').trim();"
            "  if (s.length) return true; }"
            "var b = ((document.body && document.body.textContent) || '').toLowerCase();"
            "return b.indexOf('geen resultaten') >= 0 || b.indexOf('0 resultaten') >= 0;")

        for attempt in (1, 2):
            self._goto(url, settle=0.4)
            try:
                WebDriverWait(self.driver, 15).until(lambda d: d.execute_script(ready_js))
            except Exception:
                logger.debug(f"search page did not settle for '{query}' (attempt {attempt})")
            names = self._results()
            # A list of EMPTY names means the list rendered but the rows had
            # not hydrated. `['']` is truthy, so an earlier version returned it
            # as "1 result" whose name matched nothing - that alone cost seven
            # rows in a full run ("1 results, 0 exact" on obvious companies).
            if any(n.strip() for n in names):
                return names
            # An empty list is only trustworthy when the page SAYS there are no
            # results. Otherwise the app simply had not rendered, and returning
            # [] here manufactures a false NOT-FOUND.
            try:
                explicit_none = self.driver.execute_script(
                    "var b = ((document.body && document.body.textContent) || '').toLowerCase();"
                    "return b.indexOf('geen resultaten') >= 0 || b.indexOf('0 resultaten') >= 0;")
            except Exception:
                explicit_none = False
            if explicit_none:
                return []
            if attempt == 1:
                logger.debug(f"empty result list with no 'geen resultaten' for '{query}' - retrying")
                time.sleep(1.5)
        return []

    def _contacts(self) -> Tuple[List[str], str]:
        """(<=MAX_PHONES phone numbers, mobile first), first real email)."""
        tels, mails = [], []
        try:
            for a in self.driver.find_elements(By.XPATH, "//a[starts-with(@href,'tel:')]"):
                n = normalise_phone((a.get_attribute('href') or '').replace('tel:', ''))
                if n and not is_own_number(n) and n not in tels:
                    tels.append(n)
            for a in self.driver.find_elements(By.XPATH, "//a[starts-with(@href,'mailto:')]"):
                m = (a.get_attribute('href') or '').replace('mailto:', '').strip()
                if m and '@' in m and 'company.info' not in m.lower() and m not in mails:
                    mails.append(m)
        except Exception as e:
            logger.debug(f"contact read error: {e}")
        mobile = [t for t in tels if t.startswith('06')]
        other = [t for t in tels if not t.startswith('06')]
        return (mobile + other)[:MAX_PHONES], (mails[0] if mails else '')

    # textContent (not Selenium's .text) so owner names inside collapsed
    # 'Management' / 'Aandeelhouders' panels are still seen - that is exactly
    # where ownership is proved. Whitespace is collapsed and the result is
    # capped IN THE BROWSER: shipping a multi-megabyte string over the
    # WebDriver wire blows the script timeout and kills the renderer.
    _PAGE_TEXT_JS = """
        var t = (document.body && document.body.textContent) || '';
        t = t.replace(/\\s+/g, ' ');
        return t.length > 200000 ? t.slice(0, 200000) : t;
    """

    def _page_text(self) -> str:
        try:
            return self.driver.execute_script(self._PAGE_TEXT_JS) or ''
        except Exception as e:
            logger.debug(f"page text read failed: {e}")
            try:
                return self.driver.find_element(By.TAG_NAME, 'body').text
            except Exception:
                return ''

    def _company_name(self, fallback: str = '') -> str:
        """
        Company pages carry no <h1>, so the name comes from the search result we
        clicked (passed in as `fallback`), with the document title as backup.
        """
        if fallback:
            return fallback
        title = (self.driver.title or '').replace(' - Company.info', '').strip()
        return '' if title.lower() in ('company.info', 'organisaties', '') else title

    # ----------------------------------------------------------- evaluation

    def _address_matches(self, street: str, house: str) -> bool:
        """
        Does the open company page sit at this address?

        The street name and the house number must appear TOGETHER, as an
        address does. An earlier version accepted them appearing anywhere on
        the page independently, so a page containing 'hout' in one place and
        '13' in another "matched" Hout oost 13 - which certified an unrelated
        company and wrote its phone number into the wrong row.
        """
        rx = address_regex(street, house)
        if rx is None:
            return False
        return rx.search(self._page_text()) is not None

    def _ownership(
        self,
        strong: List[str],
        short: List[str],
        given: List[str],
    ) -> Tuple[bool, List[str]]:
        """
        Is the owner demonstrably connected to the open company?

        Accepted:
          - any strong surname / trade-name token          ('broek', 'sanden')
          - a short surname token WITH a given name        ('bas' + 'paul')

        Rejected:
          - given names alone       ('richard' matched an unrelated company)
          - generic/industry words  ('bouw', 'beheer' - see GENERIC)
          - a lone 3-char token, which is too weak to carry a row by itself
        """
        text = self._page_text()
        hit_strong = find_tokens(text, strong)
        hit_short = find_tokens(text, short)
        hit_given = find_tokens(text, given)

        if hit_strong:
            return True, hit_strong + hit_short + hit_given
        if hit_short and hit_given:
            return True, hit_short + hit_given
        return False, hit_short + hit_given

    # ------------------------------------------------------------------ API

    def search(
        self,
        lead_name: str,
        first_names: str = '',
        street: str = '',
        house: str = '',
        city: str = '',
        alt_addresses: Optional[List[Tuple[str, str, str]]] = None,
    ) -> SearchOutcome:
        """
        alt_addresses: extra (street, house, city) triples to try after the
        primary one - typically the parcel address, which is where an owner's
        business often sits even when their registered address yields nothing.
        Safe to include because every address hit must still prove ownership.
        """
        lead_name = (lead_name or '').strip()
        strong, short, given = name_tokens(lead_name, first_names)
        notes: List[str] = []

        if not self.ensure_login():
            return SearchOutcome.empty('ERROR', 'login failed')

        # ---------------- pass 1: exact company-name match ----------------
        if lead_name:
            try:
                names = self._search(lead_name)
                target = compare_key(lead_name)
                exact = [i for i, n in enumerate(names) if compare_key(n) == target]
                notes.append(f"name '{lead_name}': {len(names)} results, {len(exact)} exact")

                if len(exact) > 1 and street:
                    # Duplicate legal names are common; the address decides.
                    for i in exact[:self.max_candidates]:
                        if not self._open_result(i):
                            continue
                        if self._address_matches(street, house):
                            phones, mail = self._contacts()
                            if phones or mail:
                                return SearchOutcome(
                                    phones=phones, email=mail, company=self._company_name(names[i]),
                                    confidence='VERIFIED-NAME', source='name match + address',
                                    evidence=f"{notes[-1]}; disambiguated by address "
                                             f"{street} {house}".strip())
                        self.pause()
                        self._search(lead_name)
                    notes.append('no exact match sits at the given address')

                for rank, i in enumerate(exact[:self.max_candidates], 1):
                    if not self._open_result(i):
                        continue
                    phones, mail = self._contacts()
                    if phones or mail:
                        conf = 'VERIFIED-NAME' if len(exact) == 1 else 'AMBIGUOUS-NAME'
                        ev = notes[-1] if len(exact) == 1 else \
                            f"{len(exact)} identically named entities; opened #{rank}, " \
                            f"address could not disambiguate"
                        return SearchOutcome(
                            phones=phones, email=mail, company=self._company_name(names[i]),
                            confidence=conf, source=f'name match #{rank}', evidence=ev)
                    self.pause()
                    self._search(lead_name)
                if exact:
                    notes.append('every exact name match lacked contact details')

                # No exact match. Typical for a PERSON: the kadaster holds
                # "van Diessen" while the register holds "van Diessen Beheer
                # B.V.". Verifying the surname on a page we found BY that
                # surname is circular, so the corroboration has to come from
                # somewhere independent - the address.
                if not exact and names:
                    for i in range(min(len(names), self.max_candidates)):
                        if not self._open_result(i):
                            continue
                        at_primary = street and self._address_matches(street, house)
                        at_alt = any(self._address_matches(a_st, a_hs)
                                     for a_st, a_hs, _ in (alt_addresses or [])
                                     if a_st)
                        if at_primary or at_alt:
                            phones, mail = self._contacts()
                            if phones or mail:
                                where = f"{street} {house}".strip() if at_primary else 'parcel address'
                                return SearchOutcome(
                                    phones=phones, email=mail, company=self._company_name(names[i]),
                                    confidence='VERIFIED-OWNER',
                                    source=f'name search candidate #{i + 1} at owner address',
                                    evidence=f"{notes[0]}; candidate #{i + 1} sits at {where}")
                        self.pause()
                        self._search(lead_name)
                    notes.append('no name-search candidate sits at the owner address')
            except BlockedError:
                raise
            except Exception as e:
                notes.append(f'name pass error: {str(e)[:70]}')

        # ---------------- pass 2: address + ownership proof ----------------
        # Primary (registered) address first, then any alternates (parcel
        # address). Ownership is proved for every hit, so a wider address net
        # cannot introduce tenants - it only finds owners we would have missed.
        triples = [(street, house, city)] + list(alt_addresses or [])
        queries, seen_q = [], set()
        for st, hs, ct in triples:
            for q in (' '.join(x for x in (st, hs, ct) if x),
                      ' '.join(x for x in (st, hs) if x)):
                q = q.strip()
                if q and q.lower() not in seen_q:
                    seen_q.add(q.lower())
                    queries.append((q, st, hs))
        for q, q_street, q_house in queries:
            try:
                self.pause()
                names = self._search(q)
                if not names:
                    notes.append(f"addr '{q}': 0 results")
                    continue
                notes.append(f"addr '{q}': {len(names)} results")
                for i in range(min(len(names), self.max_candidates)):
                    if not self._open_result(i):
                        continue
                    # Two independent conditions must hold: the company must
                    # sit at the address we searched (dropping the city can
                    # return 25 unrelated hits), AND the owner must be named
                    # on its page.
                    at_address = self._address_matches(q_street, q_house)
                    owned, hits = self._ownership(strong, short, given)
                    if at_address and owned:
                        phones, mail = self._contacts()
                        if phones or mail:
                            return SearchOutcome(
                                phones=phones, email=mail, company=self._company_name(names[i]),
                                confidence='VERIFIED-OWNER',
                                source=f'address match, result #{i + 1}',
                                evidence=f"{notes[-1]}; at {q_street} {q_house}; "
                                         f"owner token(s) {hits} on page")
                    self.pause()
                    self._search(q)
                notes.append(f"none of the first {min(len(names), self.max_candidates)} "
                             f"is linked to the owner")
            except BlockedError:
                raise
            except Exception as e:
                notes.append(f"addr pass error: {str(e)[:70]}")

        return SearchOutcome.empty('NOT-FOUND', '; '.join(notes)[:400] or 'no results')
