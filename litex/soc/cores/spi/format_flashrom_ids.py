#!/usr/bin/env python3
import json
ids = json.load(open("flashrom_ids.jsonpp"))
import pprint
pprint.pprint(ids)

for man, man_id, desc, parts in ids[3:]:
    man_alt = None
    man_alt_id = None
    cmt = None
    if parts[0][0] == 'ID_NOPREFIX':
        s, man_alt_id, cmt = parts.pop(0)
        assert s == 'ID_NOPREFIX', s
    if isinstance(man_id, int):
        man_id = "0x%04x" % (man_id,)
    if isinstance(man_alt_id, int):
        man_alt_id = "0x%04x" % (man_alt_id,)
    print("%20s" % (man,), man_id, man_alt_id, cmt) #, repr(desc), parts)
