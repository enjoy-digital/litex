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

This module contains modules for SECDED (Single Error Correction, Double Error Detection) ECC encoding
and decoding.
"""

from migen import *

from litex.gen import *

# Helpers ------------------------------------------------------------------------------------------

def compute_m_n(k):
    """
    Compute the number of syndrome and data bits.

    This function computes the number of syndrome bits, `m`, and data bits, `n`, given the length of
    the input binary string, `k`.

    Args:
        k (int): The length of the input binary string.

    Returns:
        tuple: A tuple containing the number of syndrome and data bits.
    """
    m = 1
    while (2**m < (m + k + 1)):
        m = m + 1;
    n = m + k
    return m, n

def compute_syndrome_positions(m):
    """
    Compute the positions of the syndrome bits.

    This function computes the positions of the syndrome bits in the codeword, given the number of
    syndrome bits, `m`.

    Args:
        m (int): The number of syndrome bits.

    Returns:
        list: A list of the positions of the syndrome bits in the codeword.
    """
    r = []
    i = 1
    while i <= m:
        r.append(i)
        i = i << 1
    return r

def compute_data_positions(m):
    """
    Compute the positions of the data bits.

    This function computes the positions of the data bits in the codeword, given the number of
    syndrome bits, `m`.

    Args:
        m (int): The number of syndrome bits.

    Returns:
        list: A list of the positions of the data bits in the codeword.
    """
    r = []
    e = compute_syndrome_positions(m)
    for i in range(1, m + 1):
        if not i in e:
            r.append(i)
    return r

def compute_cover_positions(m, p):
    """
    Compute the positions of the bits covered by a syndrome bit.

    This function computes the positions of the bits covered by a syndrome bit in the codeword, given
    the number of syndrome bits, `m`, and the position of the syndrome bit, `p`.

    Args:
        m (int): The number of syndrome bits.
        p (int): The position of the syndrome bit.

    Returns:
        list: A list of the positions of the bits covered by the syndrome bit in the codeword.
    """
    r = []
    i = p
    while i <= m:
        for j in range(min(p, m - i + 1)):
            r.append(i + j)
        i += 2*p
    return r

# SECDED (Single Error Correction, Double Error Detection) -----------------------------------------

class SECDED:
    """
    The SECDED class provides methods for encoding and decoding data using the SECDED (Single Error
    Correction, Double Error Detection) method.
    """
    def place_data(self, data, codeword):
        """
        Place the data bits in the codeword.

        This method places the input data bits in the codeword, setting the values of the data bits
        in the codeword.

        Args:
            data (list)     : A list of the data bits to be placed in the codeword.
            codeword (list) : A list of the codeword bits.
        """
        d_pos = compute_data_positions(len(codeword))
        for i, d in enumerate(d_pos):
            self.comb += codeword[d-1].eq(data[i])

    def extract_data(self, codeword, data):
        """
        Extract the data bits from the codeword.

        This method extracts the data bits from the codeword, setting the values of the data bits to
        be the values of the data bits in the codeword.

        Args:
            codeword (list) : A list of the codeword bits.
            data (list)     : A list of the data bits to be extracted from the codeword.
        """
        d_pos = compute_data_positions(len(codeword))
        for i, d in enumerate(d_pos):
            self.comb += data[i].eq(codeword[d-1])

    def compute_syndrome(self, codeword, syndrome):
        """
        Compute the syndrome bits for the codeword.

        This method computes the syndrome bits for the given codeword, setting the values of the
        syndrome bits.

        Args:
            codeword (list): A list of the codeword bits.
            syndrome (list): A list of the syndrome bits to be computed.
        """
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
        """
        Place the syndrome bits in the codeword.

        This method places the input syndrome bits in the codeword, setting the values of the syndrome
        bits in the codeword.

        Args:
            syndrome (list): A list of the syndrome bits to be placed in the codeword.
            codeword (list): A list of the codeword bits.
        """
        p_pos = compute_syndrome_positions(len(codeword))
        for i, p in enumerate(p_pos):
            self.comb += codeword[p-1].eq(syndrome[i])

    def compute_parity(self, codeword, parity):
        """
        Compute the parity bit of the input data.

        This function computes the parity bit of the input data, given the length of the input data,
        data`, and the parity bit, `parity`.

        Args:
            data (list)     : The input data.
            parity (Signal) : The parity bit.

        Returns:
            Signal: The computed parity bit.
        """
        self.comb += parity.eq(Reduce("XOR", [codeword[i] for i in range(len(codeword))]))

# ECC Encoder --------------------------------------------------------------------------------------

class ECCEncoder(SECDED, LiteXModule):
    """
    ECCEncoder

    This module does the ECC (Error Correcting Code) encoding using the SECDED (Single Error Correction,
    Double Error Detection) method. This class provides methods for encoding data, computing
    the parity bits, and generating the codeword.

    Generates the codeword and parity bits for the input data.
    """
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

class ECCDecoder(SECDED, LiteXModule):
    """
    ECCDecoder

    This modules does the ECC (Error Correcting Code) decoding using the SECDED (Single Error Correction,
    Double Error Detection) method.

    Generates output data from codeword + parity bits  + sed/dec detection.
    """
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
