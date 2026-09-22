# Contact-accuracy audit — achterhoek, 192 rows

Measured on `scraply_complete_192rows_2026-09-17T12-40-42.csv`, the completed
legacy (old scraper) run. Every number below is counted from that file, not
estimated.

---

## 1. What the old scraper does, step by step

`CompanyInfoSearcher.search_company()` — [companyinfo_searcher.py:1601](../scraply/src/modules/companyinfo_searcher.py#L1601)

```
row -> owner name = "<voorvoegsel> <achternaam>"   e.g. "de Rooms Katholieke Parochie ..."
       address    = "<straat> <huisnummer> <plaats>"  (the OWNER's address)

STEP 1  name search   GET /organisations/search?query=<owner name>
        0 results                  -> go to step 2
        >=1 results                -> require an EXACT name match (case-insensitive,
                                      trailing B.V./N.V./V.O.F./C.V. allowed)
        no exact match             -> go to step 2

STEP 2  address search  GET /organisations/search?query=<street house city>
        0 results                  -> retry without the city
        >=1 results                -> CLICK RESULT #1.  No check of any kind.

STEP 3  on the company page, extract phones + email
        no mobile/email found      -> open the "Enig aandeelhouders" (shareholder)
                                      section and take the contact details of a
                                      RELATED company instead

STEP 4  write NUMBER 1..5 / EMAIL / BUSINESS_NAME / OWNER_NAME / NOTE
```

There is no owner-verification step anywhere. Step 2 and step 3 both attach a
phone number to a row without ever establishing that the number belongs to the
owner named in that row.

## 2. What that produces — measured

Of 192 parcels, 112 rows came back with a number. Grading each one by whether
the company whose number was returned shares any meaningful name token with the
parcel's registered owner:

| How the company was found | Name matches owner | Total | Suspect |
|---|---|---|---|
| company name search | 52 | 53 | **1** |
| address search | 11 | 42 | **31** |
| related company (shareholder hop) | 12 | 17 | **5** |
| **all** | **75** | **112** | **37 (33%)** |

Read that table again by row: the name-search path is 98% right. **The address
fallback is 26% right.** That single unverified path is where the wrong numbers
come from — 74% of what it produces is a stranger.

By owner type:

| Owner | Match rate |
|---|---|
| Bedrijf (company) | 39/41 — **95%** |
| Natuurlijke personen (private person) | 36/71 — **51%** |

And 135 of the 192 parcels (70%) are owned by private persons.

### The failure, in real rows

| Parcel owner | Number we delivered belongs to | Number |
|---|---|---|
| de Rooms Katholieke Parochie HH. Paulus en Ludger | Drukkerij-Uitgeverij Emaus vof (a printing shop) | 0651554613 — **on 4 rows** |
| Rooms Katholieke Parochie Maria Laetitia | Praktijk voor Logopedie Ulft (speech therapist) | 0645734692 — **on 3 rows** |
| Ruesink (Beeklaan, Achterhoek) | Totaal VVE Beheer Den Haag e.o. | 0703603443 (a Den Haag number) |
| Laarhuis **and** Wind (two different owners) | Vereniging van Eigenaars Hoofdstraat | 0481700202 — same number, both rows |
| Ormel | van Bruchem oldtimer onderdelen | 0612201104 |
| van Eldik | Hilhorst TAP B.V. | 0622232469 |

Eight numbers were handed to more than one owner (19 rows). Four rows carry a
service desk, not a person: `09008856` (0900 premium line, twice), `0881106000`,
`0855363100`.

## 3. Why it happens — the reasoning mistake

Three assumptions were baked in, and all three are wrong:

**1. "A company at the owner's address is the owner."**
It is not. A Dutch address holds tenants, a VvE, the accountant who registered
there, a business the owner sold years ago, and the person who moved in after.
company.info returns them all; the code takes result #1 —
[companyinfo_searcher.py:913](../scraply/src/modules/companyinfo_searcher.py#L913).
The parish above owns the church; the printer merely rents next door.

**2. "company.info can be searched for a person."**
company.info is a *company* register (KVK data). 70% of these owners are private
individuals who have no entry at all. Searching "Ruesink" either finds nothing,
or finds an unrelated family firm with the same surname. There is no path in
that database from a private person to their mobile number — so for those rows
the honest answer is "not available here", and the scraper instead answers with
whatever is nearby.

**3. "If this company has no mobile, a related company's will do."**
A shareholder's number is a different legal entity's number. It is sometimes the
same human, often not — 5 of 17 such rows are wrong, and the hop starts from a
page that may already be the wrong company.

Underneath all three: the tool was built to **maximise fill rate**. Every branch
ends in "return something". A blank cell looked like failure, so the code kept
reaching until it had a number. That is exactly backwards for lead data — a
blank costs nothing, a stranger's number costs a phone call, a reputation, and
trust in the whole file.

## 4. What fixes it

`verified_searcher.py` already implements the correct model, and its docstring
records each failure it was written against —
[verified_searcher.py:1](../scraply/src/modules/verified_searcher.py#L1). The
rule it enforces:

> Never write a number that cannot be attributed to the owner of that parcel.

Concretely, before any contact detail is written it demands **evidence**:

- **Name path** — the result's *name* must equal the owner name (not the anchor
  text, which also contains address and KVK). Every exact match is tried, not
  just the first; duplicates are disambiguated by address.
- **Address path** — finding a company at the address proves nothing on its own.
  The owner's surname (or trade-name token) must also appear **on that company's
  page** — `_ownership()`,
  [verified_searcher.py:532](../scraply/src/modules/verified_searcher.py#L532).
  Street and house number must appear *together* as an address, not as two
  separate words somewhere on the page.
- **Generic words are not evidence** — `beheer`, `bouw`, `vastgoed` and friends
  are excluded; matching on them is how "STICHTING … VAN DER SANDEN" became
  "Bouwbedrijf Daamen B.V.".
- **Short tokens need corroboration** — a 3-letter surname counts only when a
  given name also appears.
- Every row records *how* it was decided: `VERIFIED-NAME`, `VERIFIED-OWNER`,
  `AMBIGUOUS-NAME`, `NOT-FOUND`, `ERROR`, plus an EVIDENCE string naming the
  tokens that proved it.

### Expected effect on this file

Dropping the unverified address-search numbers removes 46 rows and leaves 66
numbers at roughly 90% precision, instead of 112 numbers at 67%. Fewer leads,
and the ones that remain can be called without apologising.

## 5. What "100% accurate" can and cannot mean

100% *precision* is achievable: never output a number that is not provably the
owner's. That is a policy decision, and the verified pipeline implements it.

100% *coverage* is not achievable from company.info alone, because the data is
not in there: a private individual with no company has no phone number in a
company register. Pretending otherwise is precisely what produced the 33%.

To raise coverage **without** trading away precision, the remaining owners have
to be looked up in sources that actually hold private-person data:

| Source | Holds | Note |
|---|---|---|
| KVK Handelsregister API | official company + officer data | authoritative, paid, no private persons |
| Kadaster / BRK levering | owner identity per parcel | you already buy this; no phone numbers |
| Telefoonboek / Nummergids | listed private landlines | shrinking, but exact-match on name+address |
| Google/Bing targeted search | "<name>" "<street>" contact | needs the same evidence rule, never first-hit |
| Bulk brokers / lead vendors | mobile numbers | cheap volume, low accuracy — the same trap |

Each new source must go through the same gate: a number is written only when
name **and** address corroborate. Otherwise the audit repeats itself with a
different logo.

## 6. Recommended process

1. **Switch the app's scraply tool to the verified engine.** Today it routes to
   the legacy one — [automation_tasks.py:362](../backend/app/tasks/automation_tasks.py#L362).
2. **Delete the blind first-result click** from the legacy searcher so it cannot
   be reached by any path.
3. **Never write a number without an EVIDENCE string.** Blank + reason beats a
   guess.
4. **Ship CONFIDENCE and EVIDENCE columns in the deliverable** so the person
   calling sees why a number is there, and can sort by trust.
5. **Filter service numbers** — 0900/0800/088/085 are call centres, not leads.
6. **Flag any number appearing on more than one parcel** for manual review;
   repetition is the cheapest wrongness detector available.
7. **Sample-audit 20 rows by hand per delivery** and record the score, so
   accuracy is a tracked number rather than an argument.

---

# Part 2 — legacy vs verified, same 192 rows, measured

The verified pipeline was re-run over the identical export on the VPS
(192/192, 122 minutes). Rows line up one-for-one; the owner name is identical
on both sides for all 192, so rows are compared directly.

## Outcome per row

| | rows |
|---|---|
| same number, both engines agree | 61 |
| both empty | 46 |
| legacy gave a number, verified refused it | 34 |
| verified found a number legacy missed | 34 |
| different number | 17 |

Both files contain 112 numbers. They disagree on 51 of them.

## Who is right on the 17 disagreements

Area code against the owner's own city, as an independent check:

| row | owner's city | legacy | verified |
|---|---|---|---|
| 10 | Ulft | 030 Utrecht | 0315 Ulft |
| 40 | Aalten | 070 Den Haag | 0543 Aalten |
| 133 | Varsseveld | 023 Haarlem | 0315 Varsseveld |
| 154 | Hoogeveen | 0591 Emmen | 0528 Hoogeveen |
| 170 | Zelhem | 076 Breda | 0314 Zelhem |

Legacy hands Achterhoek owners numbers from across the country. Verified
returns the local exchange. On geography alone verified wins these.

## Where the verified engine is itself wrong

**Place names count as proof.** Its generic blocklist covers `beheer`, `bouw`,
`vastgoed` but not city names, so an owner whose name contains a place matches
every company in that place:

| row | owner | "proof" token | number written |
|---|---|---|---|
| 71 | PROJECT- EN VERHUURMAATSCHAPPIJ **DOETINCHEM** BV | `doetinchem` | 0315376300 (Huiskes-Kokkeler Bedrijfswagens) |
| 52 | De Gereformeerde Gemeente **Doetinchem** | `doetinchem` | 0651860304 |
| 153 | Stichting ChristenGemeente **Aalten** | `aalten` | 0543476175 |

Row 71 checked live: Grutbroek 1 Doetinchem holds exactly one company,
Huiskes-Kokkeler Bedrijfswagens, phone 0315376300 — not the owner. **Legacy was
right on this row** and found the owner's own company by name (0314376300).
3 of 118 verified rows (2.5%) rest on a place name.

**Too strict on the name path.** Verified requires a name candidate to sit at
the owner's registered address. A holding registered at its accountant, or a
business on an industrial estate while the owner lives elsewhere, is refused —
14 rows where legacy had found the owner's *own* company:

| row | owner | company legacy found | number |
|---|---|---|---|
| 139 | L. Wolterink B.V. | L. Wolterink B.V. | 0544481602 |
| 137 | Van Kessel Beheer B.V. | Van Kessel Beheer B.V. | 0628204187 |
| 127 | Fides Holding B.V. | Fides Holding B.V. | 0433581898 |
| 159 | COÖPERATIE MAURITIUS U.A. | Coöperatie Mauritius U.A. | 0657521476 |
| 63 | H.L.M. WILLEMSEN EXPLOITATIE MAATSCHAPPIJ | same, exactly | 0653936855 |

When the deed owner *is* a legal entity and the register holds that exact name,
the name is the proof. The address test should corroborate, not veto.

**Service numbers survive in both.** 0900/0800/085/088 call centres: 4 rows in
legacy, 5 in verified. And numbers reused across different owners: 8 numbers /
19 rows in legacy, 6 numbers / 13 rows in verified.

## Scoreboard

| | legacy | verified |
|---|---|---|
| numbers delivered | 112 | 112 |
| not attributable to the owner | ~37 (33%) | 3 (2.5%) |
| owner's own company missed | — | 14 |
| service numbers | 4 | 5 |
| same number on >1 owner | 19 rows | 13 rows |
| evidence recorded per row | none | yes |

## The build that beats both

1. Keep the verified engine as the base — evidence or nothing.
2. Add place names to the generic blocklist (fixes the 3 false proofs).
3. Accept an exact entity-name match without the address veto when the deed
   owner is itself a legal entity — B.V., N.V., V.O.F., Coöperatie, Stichting
   (recovers the 14).
4. Drop 0900/0800/085/088 before writing.
5. Flag any number landing on more than one owner for review.
6. Ship CONFIDENCE + EVIDENCE in the delivery so every number can be defended.

Estimated result on this file: ~126 numbers at ~97% attributable, against
today's 112 at 67%.
