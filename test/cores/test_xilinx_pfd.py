#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.clock import S6PLL, S7PLL, S7MMCM, USMMCM, USPMMCM


class TestXilinxPFD(unittest.TestCase):
    def test_rejects_configs_below_minimum_pfd(self):
        # These ratios require DIVCLK_DIVIDE=2, with an out-of-spec PFD frequency.
        for pll_cls, clkin_freq, clkout_freq in [
            (S6PLL,     19e6,    9.3515625e6),
            (S7PLL,     30e6,   14.765625e6),
            (S7MMCM,    19e6, 4.74072265625e6),
            (USMMCM,  19.5e6,  4.798828125e6),
            (USPMMCM,   19e6, 9.49072265625e6),
        ]:
            with self.subTest(pll=pll_cls.__name__):
                pll = pll_cls()
                pll.register_clkin(Signal(), clkin_freq)
                pll.create_clkout(ClockDomain("clkout"), clkout_freq, margin=0)
                with self.assertRaisesRegex(ValueError, "No PLL config found"):
                    pll.compute_config()

    def test_divides_input_above_maximum_pfd(self):
        for pll_cls in [S6PLL, S7PLL, S7MMCM, USMMCM, USPMMCM]:
            max_freqs = [300e6, 400e6, 500e6] if pll_cls is S6PLL else [450e6, 500e6, 550e6]
            for speedgrade, max_freq in zip([-1, -2, -3], max_freqs):
                with self.subTest(pll=pll_cls.__name__, speedgrade=speedgrade):
                    clkin_freq = max_freq + 1e6
                    pll = pll_cls(speedgrade=speedgrade)
                    pll.register_clkin(Signal(), clkin_freq)
                    pll.create_clkout(ClockDomain("clkout"), clkin_freq/4, margin=0)
                    config = pll.compute_config()
                    self.assertLessEqual(clkin_freq/config["divclk_divide"], max_freq)
                    self.assertEqual(config["clkout0_freq"], clkin_freq/4)

    def test_accepts_pfd_boundaries(self):
        for pll_cls, min_freq, max_freq in [
            (S6PLL,   19e6, 300e6),
            (S7PLL,   19e6, 450e6),
            (S7MMCM,  10e6, 450e6),
            (USMMCM,  10e6, 450e6),
            (USPMMCM, 10e6, 450e6),
        ]:
            for clkin_freq in [min_freq, max_freq]:
                with self.subTest(pll=pll_cls.__name__, clkin_freq=clkin_freq):
                    pll = pll_cls()
                    pll.divclk_divide_range = (1, 2)
                    pll.register_clkin(Signal(), clkin_freq)
                    pll.create_clkout(ClockDomain("clkout"), clkin_freq, margin=0)
                    config = pll.compute_config()
                    self.assertEqual(config["divclk_divide"], 1)
                    self.assertEqual(config["clkout0_freq"], clkin_freq)
