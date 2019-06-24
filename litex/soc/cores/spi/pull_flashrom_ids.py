#!/usr/bin/env python3

import re
import urllib.request

id_regex = re.compile(r'#define\s+([^\s]+)\s+([^\s]+)\s*(/\* (.*) \*/)?$')

flash = [('???', '???', None, [])]


f = urllib.request.urlopen("https://review.coreboot.org/cgit/flashrom.git/plain/flashchips.h")
for l in f.readlines():
    l = l.decode('utf-8').strip()
    if not l.startswith('#define '):
        continue
    m = id_regex.match(l)
    if not m:
        print("Bad line?:", l)
        continue
    name_id, hex_id, _, comment = m.groups()
    try:
        hex_id = int(hex_id, 16)
    except ValueError:
        pass
    manufacturer, part = name_id.split('_', 1)
    if part in ('ID', 'ID_PREFIX'):
        flash.append((manufacturer, hex_id, comment, []))
    else:
        flash[-1][-1].append((part, hex_id, comment))

import json
with open('flashrom_ids.json', 'w') as f:
    f.write(json.dumps(flash))
