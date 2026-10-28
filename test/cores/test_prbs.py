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

    def _prbsrx_errors(self, pause, saturation, cycles=40, errors_width=4):
        # Feed data that is not PRBS7 and return the error counter after each cycle; pause is a
        # constant, or a function of the cycle.
        dut     = PRBSRX(width=8, errors_width=errors_width, with_errors_saturation=saturation)
        history = []
        def testbench():
            yield dut.config.eq(PRBS_CONFIG_PRBS7)
            for i in range(cycles):
                yield dut.pause.eq(pause(i) if callable(pause) else pause)
                yield dut.i.eq((i*37) & 0xff)
                yield
                history.append((yield dut.errors))
        run_simulation(dut, testbench())
        return history

    def test_prbs_rx_pause(self):
        # Errors are counted while running...
        self.assertTrue(any(h > 0 for h in self._prbsrx_errors(pause=0, saturation=False)))
        # ...and not while paused.
        self.assertEqual(max(self._prbsrx_errors(pause=1, saturation=False)), 0)
        self.assertEqual(max(self._prbsrx_errors(pause=1, saturation=True)),  0)

    def test_prbs_rx_pause_resume(self):
        # The counter stops during a pause and resumes after it (the pause is synchronized, so the
        # window checked leaves a few cycles on each side).
        history = self._prbsrx_errors(pause=lambda i: 16 <= i < 32, saturation=False, cycles=48, errors_width=8)
        self.assertGreater(history[15], 0)
        self.assertEqual(len(set(history[20:32])), 1)
        self.assertGreater(history[-1], history[32])

    def test_prbs_rx_errors_saturation(self):
        # With saturation, the counter reaches its maximum and stays there.
        saturated = self._prbsrx_errors(pause=0, saturation=True)
        self.assertEqual(saturated[-1], 2**4-1)
        self.assertEqual(saturated, sorted(saturated))
        # Without it, the counter wraps around.
        wrapped = self._prbsrx_errors(pause=0, saturation=False)
        self.assertNotEqual(wrapped, sorted(wrapped))
