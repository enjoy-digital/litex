#
# This file is part of LiteX.
#
# Copyright (c) 2022 Wolfgang Nagele <mail@wnagele.com>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.led import WS2812


class TestWS2812(unittest.TestCase):
    test_clk_freqs = [75e6, 50e6, 25e6]

    def generator(self, dut, led_signal, led_data, sys_clk_freq, iterations):
        # Error Margin from WS2812 datasheet.
        error_margin = 150e-9

        # Cap on how long a sequence will be evaluated.
        max_cycles_per_seq = int(dut.trst * sys_clk_freq * 2)

        # Verify initial reset.
        rst_cycles = 0
        for _ in range(max_cycles_per_seq):
            if (yield led_signal) != 0:
                break
            rst_cycles += 1
            yield
        rst_time = rst_cycles / sys_clk_freq
        assert rst_time >= dut.trst

        # Verify generated data pulses.
        length = len(led_data)
        for _ in range(iterations):
            for i_num, num in enumerate(led_data, start=1):
                for idx_bit, bit in enumerate(TestWS2812.to_bits(num), start=1):
                    exp_high, exp_low = {
                        0 : (dut.t0h, dut.t0l),
                        1 : (dut.t1h, dut.t1l)
                    }[bit]

                    # On end of chain, add reset time to exp_low
                    if i_num == length and idx_bit == 24:
                        exp_low += dut.trst

                    # Verify high cycle.
                    high_cycles = 0
                    for _ in range(max_cycles_per_seq):
                        if (yield led_signal) != 1:
                            break
                        high_cycles += 1
                        yield
                    high_time = high_cycles / sys_clk_freq
                    assert high_time >= exp_high - error_margin
                    assert high_time <= exp_high + error_margin

                    # Verify low cycle.
                    low_cycles = 0
                    for _ in range(max_cycles_per_seq):
                        if (yield led_signal) != 0:
                            break
                        low_cycles += 1
                        yield
                    low_time = low_cycles / sys_clk_freq
                    assert low_time >= exp_low - error_margin
                    assert low_time <= exp_low + error_margin

    def to_bits(num, length = 24):
        return ( int(x) for x in bin(num)[2:].zfill(length) )


    def run_test(self, revision, sys_clk_freq):
        led_signal = Signal()
        led_data   = [0x100000, 0x200000, 0x300000, 0x400000, 0x500000, 0x600000, 0x700000, 0x800000, 0x900000]
        iterations = 2
        dut = WS2812(led_signal, len(led_data), sys_clk_freq, revision=revision, init=led_data)
        run_simulation(dut, self.generator(dut, led_signal, led_data, sys_clk_freq, iterations), vcd_name="sim.vcd")

    def test_WS2812_old(self):
        for sys_clk_freq in self.test_clk_freqs:
            self.run_test("old", sys_clk_freq)

    def test_WS2812_new(self):
        for sys_clk_freq in self.test_clk_freqs:
            self.run_test("new", sys_clk_freq)