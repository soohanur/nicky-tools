#!/usr/bin/env python3
"""
Split a combined Dutch address column into street / house / postcode / city so
the verified searcher can use the postcode, which is its strongest address key.

    python3 scraply/prep_owner_address.py IN.xlsx OUT.xlsx \
        --address "Adres eigenaar" --parcel "Adres bron" --header-row 2

Writes a copy with the parsed columns appended. The original columns are left
exactly as they are; results are merged back onto the original file later.

Dutch addresses put the house number after the street and the postcode before
the town: "Agro Business Park 85 6708PV WAGENINGEN". The house number may carry
a letter or an addition ("8 A 3", "20-B"), and a fair number of rows carry no
postcode at all, so every field is optional and nothing is invented.
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

POSTCODE = re.compile(r'\b(\d{4})\s?([A-Za-z]{2})\b')
# street ... number(+ letter/addition), taking the LAST number group so that
# street names containing digits ("Plein 1945 12") still split correctly.
STREET_NUM = re.compile(r'^(?P<street>.*?)\s+(?P<house>\d+[A-Za-z]?(?:[-\s]?[A-Za-z0-9]{1,4})?)\s*$')

NEW = ['OWNER_STREET', 'OWNER_HOUSE', 'OWNER_POSTCODE', 'OWNER_CITY',
       'PARCEL_STREET', 'PARCEL_HOUSE', 'PARCEL_CITY',
       'OWNER_SURNAME', 'OWNER_GIVEN']

# Dutch name particles belong to the surname: "Aart Jan van Dam" is Mr van Dam.
PARTICLES = {'van', 'de', 'den', 'der', 'ter', 'te', 'het', "'t", 'op', 'aan',
             'in', 'du', 'la', 'le', 'ten', 'thoe', 'uit', 'von'}
ENTITY = re.compile(r'\b(b\.?v\.?|n\.?v\.?|v\.?o\.?f\.?|c\.?v\.?|u\.?a\.?|stichting|'
                    r'co[oö]peratie|maatschap|vereniging|kerkgenootschap|gemeente)\b', re.I)


def split_person_name(name: str) -> tuple[str, str]:
    """
    Surname and given names out of a full personal name.

    A company name is returned whole as the "surname", because the entity name
    IS the identity. For a person the surname is the last word plus any Dutch
    particles in front of it, and everything before that is given names - which
    the searcher treats as corroboration only, never as proof. Leaving
    "Marcellinus Gerardus Leliveld" as one blob would let the page word
    'Gerardus' certify a stranger's company.
    """
    text = re.sub(r'\s+', ' ', (name or '').strip())
    if not text or ENTITY.search(text):
        return text, ''
    tokens = text.split()
    if len(tokens) < 2:
        return text, ''
    i = len(tokens) - 1
    while i > 0 and tokens[i - 1].lower().strip('.') in PARTICLES:
        i -= 1
    return ' '.join(tokens[i:]), ' '.join(tokens[:i])


def _split_street_house(before: str) -> tuple[str, str]:
    """
    Street and house number out of "Agro Business Park 85" or "Breudijk 8 A 3".

    The house number is the first numeric token that is not part of the street
    name itself. Dutch street names do contain numbers ("Plein 1945"), so a
    four-digit token followed by another number is treated as street, not house.
    Letters and short additions after the number belong to the house number.
    """
    tokens = [t for t in before.replace(',', ' ').split() if t]
    if not tokens:
        return '', ''
    num_at = None
    for i, t in enumerate(tokens):
        if i == 0:
            continue                       # a street never starts with its number
        if re.fullmatch(r'\d+[A-Za-z]?', t):
            looks_like_year = re.fullmatch(r'\d{4}', t) and i + 1 < len(tokens) \
                and re.fullmatch(r'\d+[A-Za-z]?', tokens[i + 1])
            if not looks_like_year:
                num_at = i
                break
    if num_at is None:
        return ' '.join(tokens), ''
    street = ' '.join(tokens[:num_at])
    house = tokens[num_at]
    for extra in tokens[num_at + 1:]:      # "8 A 3" -> house "8 A 3"
        # An addition is a single letter ("8 A") or carries a digit ("8 bis 3").
        # Anything else starts the town: "20 De Meern" must not become house
        # "20 De" and city "Meern".
        if re.fullmatch(r'[A-Za-z]', extra) or re.search(r'\d', extra):
            house += ' ' + extra
        else:
            break
    return street, house


def parse(addr: str) -> dict:
    """Return street/house/postcode/city for one combined address string."""
    out = {'street': '', 'house': '', 'postcode': '', 'city': ''}
    text = re.sub(r'\s+', ' ', (addr or '').strip())
    if not text:
        return out

    m = POSTCODE.search(text)
    if m:
        out['postcode'] = f"{m.group(1)}{m.group(2).upper()}"
        before = text[:m.start()].strip(' ,')
        out['city'] = text[m.end():].strip(' ,')
        out['street'], out['house'] = _split_street_house(before)
        return out

    # No postcode. Split on the house number instead: whatever follows the
    # number and its additions is the town, which keeps multi-word towns
    # ("De Meern", "Den Bosch") intact - taking the last word alone turned
    # "Molensteijn 20 De Meern" into city "Meern".
    street, house = _split_street_house(text)
    out['street'], out['house'] = street, house
    if house:
        tail = text[text.index(house) + len(house):].strip(' ,') if house in text else ''
        out['city'] = tail
    else:
        parts = text.rsplit(' ', 1)
        out['street'] = parts[0] if len(parts) > 1 else text
        out['city'] = parts[1] if len(parts) > 1 else ''
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--address', required=True, help='combined owner address column')
    ap.add_argument('--parcel', default='', help='combined parcel address column')
    ap.add_argument('--name', default='', help='owner name column, split into surname + given names')
    ap.add_argument('--header-row', type=int, default=2)
    ap.add_argument('--sheet', default=None)
    a = ap.parse_args()

    import openpyxl
    shutil.copy(a.input, a.output)
    wb = openpyxl.load_workbook(a.output)
    ws = wb[a.sheet] if a.sheet and a.sheet in wb.sheetnames else wb.worksheets[0]
    hr = a.header_row
    hdr = [str(c.value).strip() if c.value is not None else ''
           for c in next(ws.iter_rows(min_row=hr, max_row=hr))]
    if a.address not in hdr:
        print(f"ERROR: column {a.address!r} not found. Available: {hdr}")
        return 2
    ai = hdr.index(a.address) + 1
    pi = hdr.index(a.parcel) + 1 if a.parcel and a.parcel in hdr else 0
    ni = hdr.index(a.name) + 1 if a.name and a.name in hdr else 0

    start = ws.max_column + 1
    for j, name in enumerate(NEW):
        ws.cell(row=hr, column=start + j, value=name)

    filled = Counter = 0
    withpc = 0
    for r in range(hr + 1, ws.max_row + 1):
        owner_addr = ws.cell(row=r, column=ai).value
        if owner_addr is None and (not pi or ws.cell(row=r, column=pi).value is None):
            continue
        o = parse(str(owner_addr or ''))
        p = parse(str(ws.cell(row=r, column=pi).value or '')) if pi else \
            {'street': '', 'house': '', 'city': ''}
        surname, given = split_person_name(
            str(ws.cell(row=r, column=ni).value or '')) if ni else ('', '')
        values = [o['street'], o['house'], o['postcode'], o['city'],
                  p['street'], p['house'], p['city'], surname, given]
        if any(values):
            filled += 1
        if o['postcode']:
            withpc += 1
        for j, v in enumerate(values):
            if v:
                c = ws.cell(row=r, column=start + j, value=v)
                if NEW[j] in ('OWNER_HOUSE', 'OWNER_POSTCODE', 'PARCEL_HOUSE'):
                    c.number_format = '@'
    wb.save(a.output)
    print(f"wrote {a.output}")
    print(f"  rows with a parsed address : {filled}")
    print(f"  of which carry a postcode  : {withpc}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
