#
# This file is part of LiteX.
#
# This file is Copyright (c) 2018-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

# Coloring Helpers ---------------------------------------------------------------------------------

def colorer(s, color="bright"):
    """Apply ANSI colors to a string."""
    header  = {
        "bright": "\x1b[1m",
        "green":  "\x1b[32m",
        "cyan":   "\x1b[36m",
        "red":    "\x1b[31m",
        "yellow": "\x1b[33m",
        "underline": "\x1b[4m"}[color]
    trailer = "\x1b[0m"
    return header + str(s) + trailer

# Bit/Bytes Reversing ------------------------------------------------------------------------------

def reverse_bits(s):
    """Return a signal with reversed bit order."""
    return s[::-1]

def reverse_bytes(s):
    """Return a signal with reversed byte order."""
    n = (len(s) + 7)//8
    return Cat(*[s[i*8:min((i + 1)*8, len(s))]
        for i in reversed(range(n))])
