#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.prbs import *


class PRBSModel:
    def __init__(self, n_state=23, taps=[17, 22]):
        self.n_state = n_state
        self.taps = taps
        self.state = 1

    def getbit(self):
        feedback = 0
        for tap in self.taps:
            feedback = feedback ^ (self.state >> tap) & 0x1
        self.state = (self.state << 1) & (2**self.n_state-1) | feedback
        return feedback

    def getbits(self, n):
        v = 0
        for i in range(n):
            v <<= 1
            v |= self.getbit()
        return v


class PRBS7Model(PRBSModel):
    def __init__(self):
        PRBSModel.__init__(self, n_state=7,  taps=[5, 6])


class PRBS15Model(PRBSModel):
    def __init__(self):
        PRBSModel.__init__(self, n_state=15,  taps=[13, 14])


class PRBS31Model(PRBSModel):
    def __init__(self):
        PRBSModel.__init__(self, n_state=31,  taps=[27, 30])


class TestPRBS(unittest.TestCase):
    def test_prbs_generator(self):
        duts = {
            "prbs7":  PRBS7Generator(8),
            "prbs15": PRBS15Generator(16),
            "prbs31": PRBS31Generator(32),
        }
        models = {
            "prbs7":  PRBS7Model(),
            "prbs15": PRBS15Model(),
            "prbs31": PRBS31Model(),
        }
        errors = 0
        for test in ["prbs7", "prbs15", "prbs31"]:
            dut = duts[test]
            dut._errors = 0
            model = models[test]
            def checker(dut, cycles):
                yield
                # Let the generator run and check values against model.
                for i in range(cycles):
                    if (yield dut.o) != model.getbits(len(dut.o)):
                        dut._errors += 1
                    yield
            run_simulation(dut, checker(dut, 1024))
            self.assertEqual(dut._errors, 0)

    def test_prbs_checker(self):
        duts = {
            "prbs7":  PRBS7Checker(8),
            "prbs15": PRBS15Checker(16),
            "prbs31": PRBS31Checker(32),
        }
        models = {
            "prbs7":  PRBS7Model(),
            "prbs15": PRBS15Model(),
            "prbs31": PRBS31Model(),
        }
        errors = 0
        for test in ["prbs7", "prbs15", "prbs31"]:
            dut = duts[test]
            dut._errors = 0
            model = models[test]
            @passive
            def generator(dut):
                # Inject PRBS values from model.
                while True:
                    yield dut.i.eq(model.getbits(len(dut.i)))
                    yield
            def checker(dut, cycles):
                # Wait PRBS synchronization.
                for i in range(8):
                    yield
                # Check that no errors are reported.
                for i in range(cycles):
                    if (yield dut.errors) != 0:
                        dut._errors += 1
                    yield
            run_simulation(dut, [generator(dut), checker(dut, 1024)])
            self.assertEqual(dut._errors, 0)
