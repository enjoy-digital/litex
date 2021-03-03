#
# This file is part of LiteX.
#
# Copyright (c) 2018-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""
Error Correcting Code

Hamming codes with additional parity (SECDED):
- Single Error Correction
- Double Error Detection
"""

from functools import reduce
from operator import xor

from migen import *

# Helpers ------------------------------------------------------------------------------------------

def compute_m_n(k):
    m = 1
    while (2**m < (m + k + 1)):
        m = m + 1;
    n = m + k
    return m, n

def compute_syndrome_positions(m):
    r = []
    i = 1
    while i <= m:
        r.append(i)
        i = i << 1
    return r

def compute_data_positions(m):
    r = []
    e = compute_syndrome_positions(m)
    for i in range(1, m + 1):
        if not i in e:
            r.append(i)
    return r

def compute_cover_positions(m, p):
    r = []
    i = p
    while i <= m:
        for j in range(min(p, m - i + 1)):
            r.append(i + j)
        i += 2*p
    return r

# SECDED (Single Error Correction, Double Error Detection) -----------------------------------------

class SECDED:
    def place_data(self, data, codeword):
        d_pos = compute_data_positions(len(codeword))
        for i, d in enumerate(d_pos):
            self.comb += codeword[d-1].eq(data[i])

    def extract_data(self, codeword, data):
        d_pos = compute_data_positions(len(codeword))
        for i, d in enumerate(d_pos):
            self.comb += data[i].eq(codeword[d-1])

    def compute_syndrome(self, codeword, syndrome):
        p_pos = compute_syndrome_positions(len(codeword))
        for i, p in enumerate(p_pos):
            pn = Signal()
            c_pos = compute_cover_positions(len(codeword), 2**i)
            for c in c_pos:
                new_pn = Signal()
                self.comb += new_pn.eq(pn ^ codeword[c-1])
                pn = new_pn
            self.comb += syndrome[i].eq(pn)

    def place_syndrome(self, syndrome, codeword):
        p_pos = compute_syndrome_positions(len(codeword))
        for i, p in enumerate(p_pos):
            self.comb += codeword[p-1].eq(syndrome[i])

    def compute_parity(self, codeword, parity):
        self.comb += parity.eq(reduce(xor,
            [codeword[i] for i in range(len(codeword))]))

# ECC Encoder --------------------------------------------------------------------------------------

class ECCEncoder(SECDED, Module):
    def __init__(self, k):
        m, n = compute_m_n(k)

        self.i = i = Signal(k)
        self.o = o = Signal(n + 1)

        # # #

        syndrome     = Signal(m)
        parity       = Signal()
        codeword_d   = Signal(n)
        codeword_d_p = Signal(n)
        codeword     = Signal(n + 1)

        # Place data bits in codeword.
        self.place_data(i, codeword_d)

        # Compute and place syndrome bits.
        self.compute_syndrome(codeword_d, syndrome)
        self.comb += codeword_d_p.eq(codeword_d)
        self.place_syndrome(syndrome, codeword_d_p)

        # Compute parity.
        self.compute_parity(codeword_d_p, parity)

        # Output codeword + parity.
        self.comb += o.eq(Cat(parity, codeword_d_p))

# ECC Decoder --------------------------------------------------------------------------------------

class ECCDecoder(SECDED, Module):
    def __init__(self, k):
        m, n = compute_m_n(k)

        self.enable = Signal()
        self.i = i  = Signal(n + 1)
        self.o = o  = Signal(k)

        self.sec = sec = Signal()
        self.ded = ded = Signal()

        # # #

        syndrome   = Signal(m)
        parity     = Signal()
        codeword   = Signal(n)
        codeword_c = Signal(n)

        # Input codeword + parity.
        self.compute_parity(i, parity)
        self.comb += codeword.eq(i[1:])

        # Compute_syndrome
        self.compute_syndrome(codeword, syndrome)
        self.comb += If(~self.enable, syndrome.eq(0))

        # Locate/correct codeword error bit if any and flip it.
        cases = {}
        cases["default"] = codeword_c.eq(codeword)
        for i in range(1, 2**len(syndrome)):
            cases[i] = codeword_c.eq(codeword ^ (1<<(i-1)))
        self.comb += Case(syndrome, cases)

        # Extract data / status.
        self.extract_data(codeword_c, o)
        self.comb += [
            If(syndrome != 0,
                # Double error detected.
                If(~parity,
                    ded.eq(1)
                # Single error corrected.
                ).Else(
                    sec.eq(1)
                )
            )
        ]
