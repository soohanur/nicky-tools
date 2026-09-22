# Verified Owner-Contact Scrape — Runbook

How to take a kadaster / percelen Excel file, find the owners' phone numbers and
emails on company.info, and hand back **the same file, same style, with the
scraped columns added**. Written from the Limburg run (`limburg meerdere
adressen.xlsx`, 320 parcels, September 2026) so the next run is one clean pass.

---

## 1. What the tool does

`scraply/run_verified.py` reads each row of one sheet, builds the owner's name
and addresses from it, and searches **company.info** (the Dutch company
register, paid login) in a headless Chrome. It only writes a phone/email when it
can **prove** the company belongs to that owner. Otherwise the cells stay blank
and the reason goes into `EVIDENCE`.

Output is a **copy of the input file**. Every sheet, style and value stays as it
was. Seven columns are added at the end of the sheet you read from.

| File | Role |
|---|---|
| `scraply/run_verified.py` | CLI runner (arguments, progress, writes output) |
| `scraply/src/modules/verified_searcher.py` | The search + ownership-proof logic |
| `scraply/src/modules/verified_worker.py` | Worker loop, browser recycling, block backoff |
| `scraply/src/modules/tabular_io.py` | Reads rows by position, copies the workbook, appends columns (new headers copy the sheet's own header style) |
| `backend/.env` | `COMPANYINFO_EMAIL` / `COMPANYINFO_PASSWORD` (gitignored — never commit) |

---

## 2. Prerequisites

- `python3` with `selenium` (4.41 used), `openpyxl`, `webdriver_manager`
- `google-chrome` installed (runs headless, no display needed)
- Network access (the Chrome driver is downloaded by webdriver_manager)
- Valid company.info credentials in `backend/.env`

company.info login is a **Keycloak two-step page**: username page → password
page. If the password is wrong or stale, every row comes back
`CONFIDENCE = ERROR`, `EVIDENCE = login failed`. **Always run the 2-row test in
step 5 first.**

---

## 3. The input file

The Limburg file had three sheets:

| Sheet | Rows × cols | Notes |
|---|---|---|
| `percelen _ selectie` | 320 × 46 | First tab (opens by default). Yellow bold headers. Owner fields have friendly names. |
| `percelen origineel` | 320 × 117 | Full kadaster export. Owner **and** parcel address are split into separate columns. |
| `tmp id 1e pakken` | 320 × 2 | Helper sheet, ignore. |

Both data sheets hold the same 320 parcels in the same order.

**Row key:** `verblijfsobject_id`. It is unique and has the same value on both
sheets. `Compleet_adres` is **not** a safe cross-sheet key — on `percelen
origineel` it is `"Middelstestraat 46  "`, on `percelen _ selectie` it is
`"Middelstestraat 46 Weert"`.

---

## 4. Field mapping

### Recommended: scrape from `percelen origineel`

This sheet has everything split out, including the parcel address used as a
fallback. This is the validated mapping.

| Tool argument | Column | Example | Purpose |
|---|---|---|---|
| `--company` | `tenaamstellingen.0.naam` | `Haeren` / `Van Den Elzen Erp Onroerend Goed BV` | Owner surname **or** company name — the search term |
| `--name-prefix` | `tenaamstellingen.0.voorvoegsel` | `van` | Joined in front: `van Haeren` |
| `--first-names` | `tenaamstellingen.0.voornamen` | `Philippus Hendrikus…` | Supporting evidence only, never proof by itself |
| `--street` | `tenaamstellingen.0.adressen.0.openbareRuimteNaam` | `Wieldijkje` | Owner's **registered** address (primary) |
| `--house` | `tenaamstellingen.0.adressen.0.huisnummer` | `11` | |
| `--city` | `tenaamstellingen.0.adressen.0.plaats` | `BOXMEER` | |
| `--alt-street` | `adressen_eerste_adres_straatnaam` | `Steenstraat` | **Parcel** address (fallback) |
| `--alt-house` | `adressen_eerste_adres_huisnummer` | `61` | |
| `--alt-city` | `woonplaats` | `Boxmeer` | |

**Do not** feed `Compleet_adres` or `eigen_naam` as the name. Those are property
address strings, not a person or company.

### Alternative: `percelen _ selectie`

Owner fields exist (`Naam eigenaar`, `Voorvoegsel eigenaar`, `Voornaam
eigenaar`, `Straat eigenaar`, `Huisnummer eigenaar`, `Plaats eigenaar`), but the
parcel address is only in the combined `Compleet_adres`. You lose the fallback,
so fewer owners get found. Better: scrape from `percelen origineel`, then copy
the results onto `percelen _ selectie` (step 9).

### How the name is used

The value in the owner column is searched as-is:

- **Owner is a company** (BV, Stichting…) → it is the company name → direct exact match.
- **Owner is a private person** → only found if they run a company named after
  them, or a company at their address lists their surname.
- **Private person with no company** → not in company.info at all → `NOT-FOUND`.
  This is most of the blanks, and it is expected.

### Files with two header rows (`--header-row 2`)

Some exports put a group-label row above the real column names — e.g.
`transformatie werkendam … combined (1).xlsx`: row 1 = `Bron data` / `Eigenaar`,
row 2 = column names, data from row 3. Without `--header-row 2` the tool reads
the labels as column names (mapping fails) and would write results **one row
off**. With it, results land on the right rows, the new headers go in row 2 and a
`Contactgegevens (company.info)` label is written in row 1 with the same style as
`Eigenaar`.

Mapping used for the tab `Percelen met eigenaar vanaf DQ` (owner block from column DQ):

| Tool argument | Column |
|---|---|
| `--company` / `--name-prefix` / `--first-names` | `naam` / `voorvoegsel` / `voornamen` |
| `--street` / `--house` / `--city` | `Straat` / `Huisnummer` / `Plaats` (owner) |
| `--alt-street` / `--alt-house` / `--alt-city` | `adressen_eerste_adres_straatnaam` / `adressen_eerste_adres_huisnummer` / `woonplaats` (parcel) |

Key for matching rows across tabs: `adressen_verblijfsobjectidentificatie` (unique;
often a comma-separated list, compare it as text). The retry/merge snippets in
step 8 assume one header row: with two, data row *i* is Excel row `i + 2`.

---

## 5. Pre-flight checks (do both)

Run everything from the repo root. Load the credentials into the shell (the
password never goes on the command line or into a file):

```bash
cd "/home/soohanur/Desktop/nicky tools"
export COMPANYINFO_EMAIL="$(grep -E '^COMPANYINFO_EMAIL=' backend/.env | cut -d= -f2- | tr -d '"')"
export COMPANYINFO_PASSWORD="$(grep -E '^COMPANYINFO_PASSWORD=' backend/.env | cut -d= -f2- | tr -d '"')"
```

### 5a. Validate the column mapping (no browser)

```python
import sys; sys.path[:0] = [".", "scraply"]
from scraply.src.modules.tabular_io import TabularFile

tf = TabularFile("INPUT.xlsx", sheet="percelen origineel")
rows = tf.read_rows()
m = {
    "company": "tenaamstellingen.0.naam",
    "name_prefix": "tenaamstellingen.0.voorvoegsel",
    "first_names": "tenaamstellingen.0.voornamen",
    "street": "tenaamstellingen.0.adressen.0.openbareRuimteNaam",
    "house": "tenaamstellingen.0.adressen.0.huisnummer",
    "city": "tenaamstellingen.0.adressen.0.plaats",
    "alt_street": "adressen_eerste_adres_straatnaam",
    "alt_house": "adressen_eerste_adres_huisnummer",
    "alt_city": "woonplaats",
}
print("missing:", [c for c in m.values() if c not in tf.headers] or "none")
g = lambda r, k: (r.get(m[k]) or "").strip()
for r in rows[:5]:
    lead = f"{g(r,'name_prefix')} {g(r,'company')}".strip()
    print(lead, "|", g(r,"street"), g(r,"house"), g(r,"city"), "| parcel:", g(r,"alt_street"), g(r,"alt_house"))
```

`missing: none` and sensible names/addresses → mapping is right.

### 5b. Two-row live test (proves the login works)

```bash
python3 scraply/run_verified.py "INPUT.xlsx" --sheet "percelen origineel" \
  --company "tenaamstellingen.0.naam" --name-prefix "tenaamstellingen.0.voorvoegsel" \
  --first-names "tenaamstellingen.0.voornamen" \
  --street "tenaamstellingen.0.adressen.0.openbareRuimteNaam" \
  --house "tenaamstellingen.0.adressen.0.huisnummer" \
  --city "tenaamstellingen.0.adressen.0.plaats" \
  --alt-street "adressen_eerste_adres_straatnaam" --alt-house "adressen_eerste_adres_huisnummer" \
  --alt-city "woonplaats" \
  --workers 1 --limit 2 --out "/tmp/test_out.xlsx"
```

Open `/tmp/test_out.xlsx` and read `CONFIDENCE` / `EVIDENCE`. `login failed` →
fix the password before going further. Real `VERIFIED-*` or `NOT-FOUND` with
search details → good to go.

---

## 6. Start the full scrape

Same command as 5b, without `--limit`, with a real output path, in the
background with a log:

```bash
nohup python3 scraply/run_verified.py "INPUT.xlsx" --sheet "percelen origineel" \
  --company "tenaamstellingen.0.naam" --name-prefix "tenaamstellingen.0.voorvoegsel" \
  --first-names "tenaamstellingen.0.voornamen" \
  --street "tenaamstellingen.0.adressen.0.openbareRuimteNaam" \
  --house "tenaamstellingen.0.adressen.0.huisnummer" \
  --city "tenaamstellingen.0.adressen.0.plaats" \
  --alt-street "adressen_eerste_adres_straatnaam" --alt-house "adressen_eerste_adres_huisnummer" \
  --alt-city "woonplaats" \
  --workers 1 \
  --out "INPUT MET CONTACTGEGEVENS.xlsx" > scrape.log 2>&1 &

# progress (prints every ~10 s)
grep -E "[0-9]+/[0-9]+ " scrape.log | tail -3
```

- **Always `--workers 1`.** Two workers = two Chromes; they crashed on memory
  around row 180 and the run stopped silently with a partial file and exit 0.
- Speed: about **1.2–2.5 rows/min** with one worker. 320 rows ≈ 2.5–4 hours.
- **Do not interrupt it.** A `kill -INT` did not write any output — every result
  from that run was lost. Let it finish, then retry what's missing (step 8).
- Leave `--max-candidates` at the default 4. A deeper pass with 8 over the 134
  empty rows found only 1 new contact in 111 rows — not worth the hours.

---

## 7. The output file

`INPUT MET CONTACTGEGEVENS.xlsx`, next to the input. The input itself is never
modified. Seven columns are appended to the end of the `--sheet` you read from:

| Column | Content |
|---|---|
| `NUMBER 1` | Phone (mobile first), stored as text so the leading 0 survives |
| `NUMBER 2` | Second phone, if any |
| `EMAIL` | First real email on the company page |
| `COMPANY_FOUND` | Company name the contact came from |
| `CONFIDENCE` | See below |
| `SOURCE` | Which path matched (name match, address match, candidate #) |
| `EVIDENCE` | Exactly what was searched and why it matched or didn't |

| `CONFIDENCE` | Meaning | Use it? |
|---|---|---|
| `VERIFIED-OWNER` | Company sits at the owner's address **and** the owner is named on its page | Yes — strongest |
| `VERIFIED-NAME` | Exact company-name match (disambiguated by address if duplicates) | Yes |
| `AMBIGUOUS-NAME` | Several identically named entities; address couldn't pick the right one | Check `EVIDENCE` first |
| `NOT-FOUND` | Nothing that can be attributed to this owner | Blank on purpose |
| `ERROR` | Technical failure, reason in `EVIDENCE` | Retry |

On a sheet with ~117 columns the new ones sit far off to the right. Jump there
with the Name Box (e.g. `DN1`), and make sure you are on the right tab — the
file opens on the first tab.

---

## 8. Check the run and retry what failed

**Important:** a network error mid-run does **not** show up as `ERROR`. The
search catches it and the row ends up `NOT-FOUND` with the error text inside
`EVIDENCE` (`net::ERR_NAME_NOT_RESOLVED`). In the Limburg run, 49 of the 165
"not found" rows were really network failures, and 27 of them had a verified
contact on retry.

### 8a. List rows that need another pass

Unprocessed rows (blank `CONFIDENCE`) plus rows whose `EVIDENCE` contains
`error`:

```python
import json, openpyxl
ws = openpyxl.load_workbook("INPUT MET CONTACTGEGEVENS.xlsx", data_only=True)["percelen origineel"]
h = [c.value for c in ws[1]]
ic, ie = h.index("CONFIDENCE") + 1, h.index("EVIDENCE") + 1
todo = [r - 1 for r in range(2, ws.max_row + 1)
        if not ws.cell(r, ic).value or "error" in (ws.cell(r, ie).value or "").lower()]
print(len(todo), todo[:20])
json.dump(todo, open("todo_idx.json", "w"))   # 1-based data-row numbers
```

### 8b. Build a subset file from the ORIGINAL input

```python
import json, openpyxl
todo = json.load(open("todo_idx.json"))
ws = openpyxl.load_workbook("INPUT.xlsx", data_only=True)["percelen origineel"]
out = openpyxl.Workbook(); o = out.active; o.title = "percelen origineel"
o.append([c.value for c in ws[1]])
for di in todo:                                    # data row di = excel row di+1
    o.append([ws.cell(di + 1, c).value for c in range(1, ws.max_column + 1)])
out.save("subset.xlsx")
```

Run step 6 on `subset.xlsx` with `--out subset_out.xlsx`.

### 8c. Merge the retry back

Maps subset row *i* to data row `todo[i]`, checks the address matches, and never
overwrites a good row with an unprocessed or errored one:

```python
import json, openpyxl
NEW = ['NUMBER 1','NUMBER 2','EMAIL','COMPANY_FOUND','CONFIDENCE','SOURCE','EVIDENCE']
todo = json.load(open("todo_idx.json"))
MAIN = "INPUT MET CONTACTGEGEVENS.xlsx"
wbm = openpyxl.load_workbook(MAIN); wsm = wbm["percelen origineel"]; hm = [c.value for c in wsm[1]]
wss = openpyxl.load_workbook("subset_out.xlsx", data_only=True)["percelen origineel"]; hs = [c.value for c in wss[1]]
mi = {n: hm.index(n) + 1 for n in NEW}; si = {n: hs.index(n) + 1 for n in NEW}
km, ks = hm.index("Compleet_adres") + 1, hs.index("Compleet_adres") + 1
assert wss.max_row - 1 == len(todo)
done = bad = 0
for i, di in enumerate(todo):
    se, me = i + 2, di + 1
    if str(wss.cell(se, ks).value or "").strip() != str(wsm.cell(me, km).value or "").strip():
        bad += 1; continue
    conf = wss.cell(se, si["CONFIDENCE"]).value
    if not conf or "error" in (wss.cell(se, si["EVIDENCE"]).value or "").lower():
        continue                                   # keep what's already there
    for n in NEW:
        v = wss.cell(se, si[n]).value
        cell = wsm.cell(me, mi[n]); cell.value = v if v not in (None, "") else None
        if n.startswith("NUMBER") and v: cell.number_format = "@"
    done += 1
print("merged", done, "mismatches", bad)
if bad == 0: wbm.save(MAIN)
```

Repeat 8a–8c until no `error` rows are left.

---

## 9. Deliver into the user's own file, on the tab they use

The user wanted **their** file back — same file, same style — with the columns
on the tab they actually look at (`percelen _ selectie`). Append at the end of
that sheet, match by `verblijfsobject_id`, and copy the sheet's header style.
Existing cells are never touched, so nothing shifts and no style breaks.

```python
import openpyxl
from copy import copy
NEW = ['NUMBER 1','NUMBER 2','EMAIL','COMPANY_FOUND','CONFIDENCE','SOURCE','EVIDENCE']
SRC = "INPUT MET CONTACTGEGEVENS.xlsx"      # has the results on 'percelen origineel'
TGT = "USER_FILE.xlsx"                      # the clean file the user gave you (back it up first)
TAB = "percelen _ selectie"                 # or "percelen origineel"

s = openpyxl.load_workbook(SRC, data_only=True)["percelen origineel"]; hs = [c.value for c in s[1]]
si = {n: hs.index(n) + 1 for n in NEW}; vs = hs.index("verblijfsobject_id") + 1
data = {str(s.cell(r, vs).value or "").strip(): [s.cell(r, si[n]).value for n in NEW]
        for r in range(2, s.max_row + 1)}

wb = openpyxl.load_workbook(TGT); ws = wb[TAB]; h = [c.value for c in ws[1]]
assert not any(n in h for n in NEW), "columns already present"
vt = h.index("verblijfsobject_id") + 1
start = ws.max_column + 1
for j, n in enumerate(NEW):
    c = ws.cell(1, start + j, n); c._style = copy(ws.cell(1, 1)._style)   # same header look
miss = 0
for r in range(2, ws.max_row + 1):
    vals = data.get(str(ws.cell(r, vt).value or "").strip())
    if vals is None: miss += 1; continue
    for j, n in enumerate(NEW):
        cell = ws.cell(r, start + j); cell.value = vals[j] if vals[j] not in (None, "") else None
        if n.startswith("NUMBER") and vals[j]: cell.number_format = "@"
print("unmatched", miss)
if miss == 0: wb.save(TGT)
```

If the user wants the columns as **A–G** instead of at the end, every original
column must shift right — rebuild the sheet cell by cell copying each cell's
`_style` and the column widths. Appending at the end is the only way to leave
the original cells literally untouched, so default to that.

---

## 10. Verify before handing over

1. **Nothing original changed** — compare every original cell of the input with
   the output. Treat `None == ""` and numbers within 1e-6 as equal: openpyxl
   rewrites floats to ~14 significant digits on save (value unchanged).
   Expect **0 real differences**.
2. **Right row** — the `EVIDENCE` text contains the searched name
   (`name 'van Haeren': …`). It must equal that row's `voorvoegsel + naam`.
   Limburg: **186/186** matched.
3. **Spot-check a few `NOT-FOUND` by hand** — log in and search the owner name +
   full address. For Geens, Schreurs, Veldpaus and Heesemans company.info
   returned **0 results**, which confirms they are private owners with no
   company, not misses.
4. Tell the user **which tab** and **which columns** hold the data. They kept
   opening the first tab or had an old copy open — close the file completely and
   reopen after any write.

---

## 11. Pitfalls we hit

| Symptom | Cause | Fix |
|---|---|---|
| Every row `ERROR` / `login failed` | Stale password in `backend/.env` | Update it; rerun the 2-row test |
| Run stops at ~180 rows, exit 0, partial file | Two Chrome workers ran out of memory | `--workers 1`; retry the blank rows |
| Too many `NOT-FOUND` in one stretch | Network outage; errors hidden in `EVIDENCE` | Step 8a picks up `error` rows; retry |
| Results lost after stopping the run | `kill -INT` did not flush output | Never interrupt; retry afterwards instead |
| "I can't see the columns" | Wrong tab, columns far right, or file still open in Excel/LibreOffice | Name the tab + cell (e.g. `DN1`); close and reopen |
| Cross-sheet merge matches nothing | `Compleet_adres` format differs per sheet | Match on `verblijfsobject_id` |
| `.xlsx` with owner data about to be committed | `*.xlsx` wasn't ignored | Now in `.gitignore`; stage code files by name, never `git add .` |

---

## 12. Reference: the Limburg run

- Input: 320 parcels, 3 sheets. Scraped from `percelen origineel`.
- Pass 1 (2 workers): stopped at 180/320 after 61 min (Chrome crash).
- Pass 2 (1 worker): rows 181–320, 116 min.
- Retry of 49 network-error rows: 27 verified recovered.
- Deep recheck (8 candidates) of 134 empty rows: 1 new in 111 — stopped.

**Final:** 186 of 320 rows with contact (165 phone, 91 email).
129 `VERIFIED-OWNER`, 33 `VERIFIED-NAME`, 24 `AMBIGUOUS-NAME`, 133 `NOT-FOUND`,
1 unsearchable (no name or address).

Delivered as the user's own `limburg meerdere adressen (1).xlsx`, columns
appended on `percelen _ selectie` (AU–BA) and `percelen origineel` (DN–DT).

**Next time:** pre-flight (5) → one `--workers 1` run (6) → retry `error`/blank
rows until clean (8) → append into the user's file on their tab (9) → verify (10).

---

## Related

- Hostinger VPS: `nicky-server` (`76.13.145.229`, `srv1319082.hstgr.cloud`)
  runs the Nicky Tools platform at `/var/www/datainfo`. This runbook is the local
  CLI path; the scrape above ran on the workstation, not the VPS.
