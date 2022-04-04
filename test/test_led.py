#
# This file is part of LiteX.
#
# Copyright (c) 2022 Wolfgang Nagele <mail@wnagele.com>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.led import WS2812


TEST_CLK_FREQS = (20e6, 16e6, 15e6, 10e6)


class TestWS2812(unittest.TestCase):
    def generator(self, dut, led_signal, led_data, sys_clk_freq, iterations):
        error_margin = 0.15e-6 # defined in datasheet

        # cap on how long a sequence will be evaluated
        max_cycles_per_seq = int(dut.trst * sys_clk_freq * 2)

        # initial reset
        rst_cycles = 0
        for _ in range(max_cycles_per_seq):
            if (yield led_signal) != 0:
                break
            rst_cycles += 1
            yield
        rst_time = rst_cycles / sys_clk_freq
        assert rst_time >= dut.trst

        length = len(led_data)
        for _ in range(iterations):
            for i_num, num in enumerate(led_data, start = 1):
                for idx_bit, bit in enumerate(TestWS2812.to_bits(num), start = 1):
                    exp_high, exp_low = (dut.t0h, dut.t0l) if bit == 0 else (dut.t1h, dut.t1l)

                    # end of chain reset
                    if i_num == length and idx_bit == 24:
                        exp_low += dut.trst

                    high_cycles = 0
                    for _ in range(max_cycles_per_seq):
                        if (yield led_signal) != 1:
                            break
                        high_cycles += 1
                        yield
                    high_time = high_cycles / sys_clk_freq
                    assert high_time >= exp_high - error_margin
                    assert high_time <= exp_high + error_margin

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


    def run_test(self, hardware_revision, sys_clk_freq):
        led_signal = Signal()
        led_data = [ 0x100000, 0x200000, 0x300000, 0x400000, 0x500000, 0x600000, 0x700000, 0x800000, 0x900000 ]
        iterations = 3
        dut = WS2812(led_signal, len(led_data), sys_clk_freq, hardware_revision = hardware_revision, test_data = led_data)
        run_simulation(dut, self.generator(dut, led_signal, led_data, sys_clk_freq, iterations))


    def test_WS2812_old(self):
        for sys_clk_freq in TEST_CLK_FREQS:
            self.run_test("old", sys_clk_freq)

    def test_WS2812_new(self):
        for sys_clk_freq in TEST_CLK_FREQS:
            self.run_test("new", sys_clk_freq)