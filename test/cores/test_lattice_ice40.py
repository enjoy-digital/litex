#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import ClockDomain, Signal

from litex.soc.cores.clock.lattice_ice40 import iCE40PLL


class TestiCE40PLL(unittest.TestCase):
    def test_divided_reference_stays_in_pfd_range(self):
        for clkin, clkout in ((12e6, 40e6), (16e6, 125e6), (24e6, 16e6), (48e6, 74.25e6)):
            with self.subTest(clkin=clkin, clkout=clkout):
                pll = iCE40PLL()
                pll.register_clkin(Signal(), clkin)
                pll.create_clkout(ClockDomain("sys"), clkout)
                config = pll.compute_config()
                self.assertGreaterEqual(clkin/(config["divr"] + 1), 10e6)
                self.assertLessEqual(clkin/(config["divr"] + 1), 133e6)
                self.assertLessEqual(abs(config["clkout_freq"]/clkout - 1), 1e-2)

    def test_exact_frequency_requiring_invalid_pfd_is_rejected(self):
        pll = iCE40PLL()
        pll.register_clkin(Signal(), 24e6)
        pll.create_clkout(ClockDomain("sys"), 16e6, margin=0)
        with self.assertRaisesRegex(ValueError, "No PLL config"):
            pll.compute_config()

    def test_margin_does_not_relax_hardware_output_limits(self):
        for clkin in (12e6, 27e6, 48e6, 133e6):
            for clkout in (16e6, 275e6):
                with self.subTest(clkin=clkin, clkout=clkout):
                    pll = iCE40PLL()
                    pll.register_clkin(Signal(), clkin)
                    pll.create_clkout(ClockDomain("sys"), clkout, margin=0.05)
                    config = pll.compute_config()
                    self.assertGreaterEqual(config["clkout_freq"], 16e6)
                    self.assertLessEqual(config["clkout_freq"], 275e6)

    def test_emitted_dividers_and_filter(self):
        for primitive in ("SB_PLL40_CORE", "SB_PLL40_PAD"):
            with self.subTest(primitive=primitive):
                pll = iCE40PLL(primitive=primitive)
                pll.register_clkin(Signal(), 12e6)
                pll.create_clkout(ClockDomain("sys"), 40e6)
                config = pll.compute_config()
                pll.get_fragment()
                actual = 12e6*(pll.params["p_DIVF"] + 1)/(pll.params["p_DIVR"] + 1)/2**pll.params["p_DIVQ"]
                self.assertEqual(actual, config["clkout_freq"])
                self.assertEqual(pll.params["p_FILTER_RANGE"], 1)
                self.assertIn("i_REFERENCECLK" if primitive == "SB_PLL40_CORE" else "i_PACKAGEPIN", pll.params)
