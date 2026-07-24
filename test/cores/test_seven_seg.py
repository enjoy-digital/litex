#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.seven_seg import SevenSegmentDisplay


class TestSevenSegmentDisplay(unittest.TestCase):
    def test_default_active_low_scan(self):
        segments = Signal(8)
        anodes   = Signal(4)
        dut      = SevenSegmentDisplay(
            sys_clk_freq  = 4,
            segments_pads = segments,
            anodes_pads   = anodes,
            refresh_rate  = 1,
        )

        samples = []

        def gen():
            yield dut.values.storage.eq(0x3210)
            for _ in range(8):
                yield
                samples.append(((yield segments), (yield anodes)))

        run_simulation(dut, gen())

        expected = {
            (0xc0, 0b1110), # 0
            (0xf9, 0b1101), # 1
            (0xa4, 0b1011), # 2
            (0xb0, 0b0111), # 3
        }
        self.assertEqual(set(samples), expected)

    def test_active_high_seven_segment_scan(self):
        segments = Signal(7)
        anodes   = Signal(2)
        dut      = SevenSegmentDisplay(
            sys_clk_freq       = 2,
            segments_pads      = segments,
            anodes_pads        = anodes,
            refresh_rate       = 1,
            segment_active_low = False,
            digit_active_low   = False,
        )

        samples = []

        def gen():
            yield dut.values.storage.eq(0xa5)
            for _ in range(4):
                yield
                samples.append(((yield segments), (yield anodes)))

        run_simulation(dut, gen())

        self.assertEqual(set(samples), {
            (0x6d, 0b01), # 5
            (0x77, 0b10), # A
        })

    def test_invalid_arguments(self):
        with self.assertRaises(ValueError):
            SevenSegmentDisplay(100e6, Signal(6), Signal(4))
        with self.assertRaises(ValueError):
            SevenSegmentDisplay(100e6, Signal(7), Signal(4), refresh_rate=0)
        with self.assertRaises(ValueError):
            SevenSegmentDisplay(1, Signal(7), Signal(4), refresh_rate=1e3)


if __name__ == "__main__":
    unittest.main()
