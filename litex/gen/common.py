#
# This file is part of LiteX.
#
# This file is Copyright (c) 2018-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

# Generic Helpers ----------------------------------------------------------------------------------

def colorer(s, color="bright"):
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
    return s[::-1]


def reverse_bytes(s):
    n = (len(s) + 7)//8
    return Cat(*[s[i*8:min((i + 1)*8, len(s))]
        for i in reversed(range(n))])

# Signals ------------------------------------------------------------------------------------------

class Open(Signal): pass

class Unsigned(Signal):
    def __init__(self, bits=1, *args, **kwargs):
        assert isinstance(bits, int)
        Signal.__init__(self, bits_sign=(bits, 0), *args, **kwargs)

class Signed(Signal):
    def __init__(self, bits=1, *args, **kwargs):
        assert isinstance(bits, int)
        Signal.__init__(self, bits_sign=(bits, 1), *args, **kwargs)

# Reduction ----------------------------------------------------------------------------------------

from functools import reduce
from operator import and_, or_, not_, xor, add

def Reduce(operator, value):
    # List of supported Operators.
    operators = {
        "AND"  : and_,
        "OR"   : or_,
        "NOR"  : not_,
        "XOR"  : xor,
        "ADD"  : add,
    }

    # Switch to upper-case.
    operator = operator.upper()

    # Check if provided operator is supported.
    if operator not in operators.keys():
        supported = ", ".join(operators.keys())
        raise ValueError(f"Reduce does not support {operator} operator; supported: {supported}.")

    # Return Python's reduction.
    return reduce(operators[operator], value)
