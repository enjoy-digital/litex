#
# This file is part of LiteX.
#
# Copyright (c) 2022 Wolfgang Nagele <mail@wnagele.com>
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.led import LedChaser, WS2812


# WS2812 ----------------------------------------------------------------------------------------

class TestWS2812(unittest.TestCase):
    # Previously the only content of this file was a reference generator with all test methods
    # commented out — effectively zero coverage. Re-enable the generator and call it from a
    # small set of actually-executing test methods with trimmed parameters so they complete in
    # well under a second.

    test_led_data = [0x100000, 0x200000, 0x700000]  # Small chain: keep sim time reasonable.

    @staticmethod
    def to_bits(num, length=24):
        return (int(x) for x in bin(num)[2:].zfill(length))

    def _check_waveform(self, dut, led_signal, led_data, sys_clk_freq, iterations):
        error_margin       = 150e-9
        max_cycles_per_seq = int(dut.trst*sys_clk_freq*2)

        # Verify initial reset.
        rst_cycles = 0
        for _ in range(max_cycles_per_seq):
            if (yield led_signal) != 0:
                break
            rst_cycles += 1
            yield
        self.assertGreaterEqual(rst_cycles/sys_clk_freq, dut.trst)

        # Verify generated data pulses.
        length = len(led_data)
        for _ in range(iterations):
            for i_num, num in enumerate(led_data, start=1):
                for idx_bit, bit in enumerate(self.to_bits(num), start=1):
                    exp_high, exp_low = {
                        0 : (dut.t0h, dut.t0l),
                        1 : (dut.t1h, dut.t1l),
                    }[bit]
                    if i_num == length and idx_bit == 24:
                        exp_low += dut.trst

                    high_cycles = 0
                    for _ in range(max_cycles_per_seq):
                        if (yield led_signal) != 1:
                            break
                        high_cycles += 1
                        yield
                    high_time = high_cycles/sys_clk_freq
                    self.assertGreaterEqual(high_time, exp_high - error_margin)
                    self.assertLessEqual(   high_time, exp_high + error_margin)

                    low_cycles = 0
                    for _ in range(max_cycles_per_seq):
                        if (yield led_signal) != 0:
                            break
                        low_cycles += 1
                        yield
                    low_time = low_cycles/sys_clk_freq
                    self.assertGreaterEqual(low_time, exp_low - error_margin)
                    self.assertLessEqual(   low_time, exp_low + error_margin)

    def _run_test(self, revision, sys_clk_freq, led_data, iterations=1):
        led_signal = Signal()
        dut = WS2812(led_signal, len(led_data), sys_clk_freq, revision=revision, init=led_data)
        run_simulation(dut, self._check_waveform(dut, led_signal, led_data, sys_clk_freq, iterations))

    def test_ws2812_new(self):
        # "new" revision: large 280µs reset. Small chain + single iteration to keep sim quick.
        self._run_test("new", sys_clk_freq=75e6, led_data=self.test_led_data)

    def test_ws2812_old(self):
        # "old" revision uses a 50µs reset, much faster per frame.
        self._run_test("old", sys_clk_freq=75e6, led_data=self.test_led_data)

    def test_ws2812_single_led(self):
        self._run_test("old", sys_clk_freq=50e6, led_data=[0xA5A5A5])


# LedChaser ---------------------------------------------------------------------------------------

class TestLedChaser(unittest.TestCase):
    def test_csr_override_takes_control(self):
        # Writing to `_out` switches the core out of chaser mode and into control mode — pads
        # then track the CSR directly.
        pads = Signal(4)
        dut  = LedChaser(pads=pads, sys_clk_freq=1e6)

        def gen():
            # Before any CSR write, the core runs the chaser pattern; allow a few cycles.
            for _ in range(8):
                yield
            # Write a CSR value; on the next cycle the core switches mode.
            yield from dut._out.write(0b1010)
            yield
            yield
            self.assertEqual((yield pads), 0b1010)
            # And another value — pads track it.
            yield from dut._out.write(0b0101)
            yield
            yield
            self.assertEqual((yield pads), 0b0101)
        run_simulation(dut, gen())

    def test_polarity_inverts_output(self):
        # With polarity=1 the pads are the inverted mask of the leds signal.
        pads = Signal(4)
        dut  = LedChaser(pads=pads, sys_clk_freq=1e6, polarity=1)

        def gen():
            yield from dut._out.write(0b1010)
            yield
            yield
            # Inverted: pads = ~leds = 0b0101.
            self.assertEqual((yield pads), 0b0101)
            yield from dut._out.write(0b1111)
            yield
            yield
            self.assertEqual((yield pads), 0b0000)
        run_simulation(dut, gen())

    def test_chaser_pattern_advances(self):
        # Without a CSR write the LedChaser cycles a chaser pattern at a rate set by `period`.
        # Just confirm that the pad value changes over time (without asserting exact pattern).
        pads = Signal(4)
        # period=1e-3 at sys_clk_freq=1e6 → timer = 1000/(2*4) = 125 cycles per step.
        dut  = LedChaser(pads=pads, sys_clk_freq=1e6, period=1e-3)
        samples = set()

        def gen():
            for _ in range(2000):
                samples.add((yield pads))
                yield
        run_simulation(dut, gen())
        # Chaser should produce at least 2 distinct pad values.
        self.assertGreaterEqual(len(samples), 2)


if __name__ == "__main__":
    unittest.main()
