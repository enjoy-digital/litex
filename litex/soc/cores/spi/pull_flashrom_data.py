#!/usr/bin/env python3

import json
import os
import re
import urllib.request

regex_key_replace = re.compile(r'^(\s*)\.([^\s]+)\s+=[\s\n]+([^,\[]*)', re.MULTILINE)
regex_enum = re.compile(":\s*([A-Z][A-Z0-9_]*),")
regex_func = re.compile(":\s*([a-z][a-z0-9_]*),")

flash_parts = []

if not os.path.exists('flashchips.c'):
    uf = urllib.request.urlopen("https://review.coreboot.org/cgit/flashrom.git/plain/flashchips.c")
    wf = open('flashchips.c', 'wb')
    wf.write(uf.read())
    wf.close()
    uf.close()

f = open('flashchips.c', 'r')
lines = iter(f.readlines())
for l in lines:
    l = l.strip()
    if l == 'const struct flashchip flashchips[] = {':
        break

all_enums = set()
all_funcs = set()

current = []
for l in lines:
    ls = l.strip()
    if not ls:
        continue

    if ls.startswith('/*'):
        continue
    if ls.startswith('*'):
        continue
    if ls.startswith('*/'):
        continue

    current.append(l)
    if not ls.endswith(','):
        continue

    s = ''.join(current)

    opening = s.count('{')
    closing = s.count('}')
    if opening > closing:
        continue

    current = []
    if 'BUS_SPI' not in s:
        continue

    p = s.replace('{', '[').replace('}', ']')
    p = regex_key_replace.sub(r"\1'\2': \3", p)
    enums = regex_enum.findall(p)
    for e in enums:
        all_enums.add(e)
    funcs = regex_func.findall(p)
    for f in funcs:
        all_funcs.add(f)

    print("-"*75)
    print(''.join(current))
    print("-"*75)
    print(p)
    print("-"*75)
    print("enums:", enums)
    print("funcs:", funcs)
    print("-"*75)
    continue

all_enums = list(all_enums)
all_enums.sort()

all_funcs = list(all_funcs)
all_funcs.sort()

print("-"*75)
import pprint
pprint.pprint(all_enums)
#pprint.pprint(all_funcs)
print("-"*75)

spi_ids = []
spi_parts = {}

ids = json.load(open("flashrom_ids.jsonpp"))
for man, man_id, desc, parts in ids[3:]:
    man_alt = None
    man_alt_id = None
    cmt = ''
    if parts[0][0] == 'ID_NOPREFIX':
        s, man_alt_id, cmt = parts.pop(0)
        assert s == 'ID_NOPREFIX', s

    if isinstance(man_id, int):
        mid = man_id

    if isinstance(man_alt_id, int):
        mid = man_alt_id

    if man+'_ID' not in all_enums:
        continue

    print('-'*75)
    print([(a, repr(b), c) for a,b,c in parts if type(b) != int])
    assert man not in spi_ids
    spi_parts[man] = {a:("0x%02x" % b, c) for a,b,c in parts}

    spi_ids.append((man, mid, cmt))

pprint.pprint(spi_parts)

print()
print('''\
class SpiNorFlashManufacturerIDs(enum.Enum):
    """Manufacturer IDs for SPI NOR flash chips.

    The first byte returned from the flash after sending opcode SPINor_OP_RDID.
    Sometimes these are the same as CFI IDs, but sometimes they aren't.
    """
''')
for man, mid, cmt in spi_ids:
    print("    %-20s = 0x%04x" % (man, mid), end="")
    if cmt:
        print(' # '+ cmt)
    else:
        print()
print()
