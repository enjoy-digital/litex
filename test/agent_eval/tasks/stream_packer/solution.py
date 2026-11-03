#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Reference solution: the skid buffer stores the payload of the word but not last (last is not
# part of a stream payload): a last word that goes through the skid buffer (output back-pressured
# when the word completes) loses its last and the packet merges with the next one. Store last too.

import os

def solve(workdir):
    filename = os.path.join(workdir, "packer.py")
    with open(filename) as f:
        content = f.read()
    content = content.replace(
        "                skid.payload.eq(word.payload),\n",
        "                skid.payload.eq(word.payload),\n                skid.last.eq(word.last),\n")
    with open(filename, "w") as f:
        f.write(content)
