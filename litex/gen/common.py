#
# This file is part of LiteX.
#
# This file is Copyright (c) 2018 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *


def reverse_bits(s):
    return s[::-1]


def reverse_bytes(s):
    n = (len(s) + 7)//8
    return Cat(*[s[i*8:min((i + 1)*8, len(s))]
        for i in reversed(range(n))])
