#
# This file is part of LiteX
#
# Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2016-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from functools import reduce
from operator import add

from migen import *

# Helpers ------------------------------------------------------------------------------------------

control_tokens = [0b1101010100, 0b0010101011, 0b0101010100, 0b1010101011]

# TMDS Encoder -------------------------------------------------------------------------------------

class TMDSEncoder(Module):
    def __init__(self):
        self.d   = Signal(8)
        self.c   = Signal(2)
        self.de  = Signal()

        self.out = Signal(10)

        # # #

        # Stage 1 - Count number of 1s in data.
        d   = Signal(8)
        n1d = Signal(max=9)
        self.sync += [
            n1d.eq(reduce(add, [self.d[i] for i in range(8)])),
            d.eq(self.d)
        ]

        # Stage 2 - Add 9th bit.
        q_m    = Signal(9)
        q_m8_n = Signal()
        self.comb += q_m8_n.eq((n1d > 4) | ((n1d == 4) & ~d[0]))
        for i in range(8):
            if i:
                curval = curval ^ d[i] ^ q_m8_n
            else:
                curval = d[0]
            self.sync += q_m[i].eq(curval)
        self.sync += q_m[8].eq(~q_m8_n)

        # Stage 3 - Count number of 1s and 0s in q_m[:8].
        q_m_r = Signal(9)
        n0q_m = Signal(max=9)
        n1q_m = Signal(max=9)
        self.sync += [
            n0q_m.eq(reduce(add, [~q_m[i] for i in range(8)])),
            n1q_m.eq(reduce(add, [q_m[i] for i in range(8)])),
            q_m_r.eq(q_m)
        ]

        # Stage 4 - Final encoding.
        cnt = Signal((6, True))

        s_c  = self.c
        s_de = self.de
        for p in range(3):
            new_c = Signal(2)
            new_de = Signal()
            self.sync += new_c.eq(s_c), new_de.eq(s_de)
            s_c, s_de = new_c, new_de

        self.sync += [
            If(s_de,
                If((cnt == 0) | (n1q_m == n0q_m),
                    self.out[9].eq(~q_m_r[8]),
                    self.out[8].eq(q_m_r[8]),
                    If(q_m_r[8],
                        self.out[:8].eq(q_m_r[:8]),
                        cnt.eq(cnt + n1q_m - n0q_m)
                    ).Else(
                        self.out[:8].eq(~q_m_r[:8]),
                        cnt.eq(cnt + n0q_m - n1q_m)
                    )
                ).Else(
                    If((~cnt[5] & (n1q_m > n0q_m)) | (cnt[5] & (n0q_m > n1q_m)),
                        self.out[9].eq(1),
                        self.out[8].eq(q_m_r[8]),
                        self.out[:8].eq(~q_m_r[:8]),
                        cnt.eq(cnt + Cat(0, q_m_r[8]) + n0q_m - n1q_m)
                    ).Else(
                        self.out[9].eq(0),
                        self.out[8].eq(q_m_r[8]),
                        self.out[:8].eq(q_m_r[:8]),
                        cnt.eq(cnt - Cat(0, ~q_m_r[8]) + n1q_m - n0q_m)
                    )
                )
            ).Else(
                self.out.eq(Array(control_tokens)[s_c]),
                cnt.eq(0)
            )
        ]
