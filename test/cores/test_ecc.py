#
# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import random
from itertools import combinations

from migen import *

from litex.soc.cores.ecc import (
    ECCEncoder, ECCDecoder, compute_m_n, compute_syndrome_positions,
    compute_data_positions, compute_cover_positions,
)


class TestECC(unittest.TestCase):
    def test_all_single_bits_and_small_double_bit_pairs(self):
        for k in [1, 4, 8, 15, 32, 64]:
            with self.subTest(k=k):
                class DUT(Module):
                    def __init__(self):
                        self.submodules.encoder = ECCEncoder(k)
                        self.submodules.decoder = ECCDecoder(k)
                        self.flip = Signal(len(self.encoder.o))
                        self.comb += self.decoder.i.eq(self.encoder.o ^ self.flip)
                dut = DUT()
                width = len(dut.flip)
                flips = [(0, 0)] + [(1 << bit, 1) for bit in range(width)]
                if k <= 8:
                    flips += [((1 << a) | (1 << b), 2) for a, b in combinations(range(width), 2)]

                def gen():
                    for value in [0, (1 << k) - 1, ((1 << k) - 1)//3]:
                        yield dut.encoder.i.eq(value)
                        for flip, nerrors in flips:
                            yield dut.decoder.enable.eq(1)
                            yield dut.flip.eq(flip)
                            yield
                            if nerrors <= 1:
                                self.assertEqual((yield dut.decoder.o), value)
                            self.assertEqual((yield dut.decoder.sec), nerrors == 1)
                            self.assertEqual((yield dut.decoder.ded), nerrors == 2)

                            # Disabling ECC preserves the raw payload and suppresses both flags.
                            yield dut.decoder.enable.eq(0)
                            yield
                            word = (yield dut.encoder.o) ^ flip
                            raw = sum(((word >> position) & 1) << bit
                                      for bit, position in enumerate(compute_data_positions(width - 1)))
                            self.assertEqual((yield dut.decoder.o), raw)
                            self.assertEqual((yield dut.decoder.sec), 0)
                            self.assertEqual((yield dut.decoder.ded), 0)
                run_simulation(dut, gen())

    def test_m_n(self):
        m, n = compute_m_n(15)
        self.assertEqual(m, 5)
        self.assertEqual(n, 20)

    def test_syndrome_positions(self):
        p_pos = compute_syndrome_positions(20)
        p_pos_ref = [1, 2, 4, 8, 16]
        self.assertEqual(p_pos, p_pos_ref)

    def test_data_positions(self):
        d_pos = compute_data_positions(20)
        d_pos_ref = [3, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20]
        self.assertEqual(d_pos, d_pos_ref)

    def test_cover_positions(self):
        c_pos_ref = {
            0 : [1, 3, 5, 7, 9, 11, 13, 15, 17, 19],
            1 : [2, 3, 6, 7, 10, 11, 14, 15, 18, 19],
            2 : [4, 5, 6, 7, 12, 13, 14, 15, 20],
            3 : [8, 9, 10, 11, 12, 13, 14, 15],
            4 : [16, 17, 18, 19, 20]
        }
        for i in range(5):
            c_pos = compute_cover_positions(20, 2**i)
            self.assertEqual(c_pos, c_pos_ref[i])

    def test_ecc(self, k=15):
        class DUT(Module):
            def __init__(self, k):
                m, n = compute_m_n(k)
                self.flip = Signal(n + 1)

                # # #

                self.submodules.encoder = ECCEncoder(k)
                self.submodules.decoder = ECCDecoder(k)

                self.comb += self.decoder.i.eq(self.encoder.o ^ self.flip)

        def generator(dut, k, nvalues, nerrors):
            dut.errors = 0
            prng = random.Random(42)
            yield dut.decoder.enable.eq(1)
            for i in range(nvalues):
                data = prng.randrange(2**k)
                yield dut.encoder.i.eq(data)
                if nerrors == 1:
                    flip_bit1 = prng.randrange(len(dut.flip))
                    yield dut.flip.eq(1<<flip_bit1)
                elif nerrors == 2:
                    flip_bit1, flip_bit2 = prng.sample(range(len(dut.flip)), 2)
                    yield dut.flip.eq((1<<flip_bit1) | (1<<flip_bit2))
                yield
                # if less than 2 errors, check data
                if nerrors < 2:
                    if (yield dut.decoder.o) != data:
                        dut.errors += 1
                # if 0 error, verify sec == 0 / ded == 0
                if nerrors == 0:
                    if (yield dut.decoder.sec) != 0:
                        dut.errors += 1
                    if (yield dut.decoder.ded) != 0:
                        dut.errors += 1
                # if 1 error, verify sec == 1 / dec == 0
                elif nerrors == 1:
                    if (yield dut.decoder.sec) != 1:
                        dut.errors += 1
                    if (yield dut.decoder.ded) != 0:
                        dut.errors += 1
                # if 2 errors, verify sec == 0 / ded == 1
                elif nerrors == 2:
                    if (yield dut.decoder.sec) != 0:
                        dut.errors += 1
                    if (yield dut.decoder.ded) != 1:
                        dut.errors += 1

        for i in range(3):
            dut = DUT(k)
            run_simulation(dut, generator(dut, k, 128, i))
            self.assertEqual(dut.errors, 0)
