#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.clock.xilinx_s6 import S6DCM


class TestS6DCM(unittest.TestCase):
    def test_full_multiplier_and_divider_ranges(self):
        for clkin_freq, clkout_freq, multiplier, divider in [
            (  1e6,       256e6, 256,   1),
            (100e6, 6.640625e6,  17, 256),
        ]:
            with self.subTest(clkin_freq=clkin_freq, clkout_freq=clkout_freq):
                dcm = S6DCM(speedgrade=-2)
                dcm.register_clkin(Signal(), clkin_freq)
                dcm.create_clkout(ClockDomain("clkout"), clkout_freq, margin=0)
                dcm.get_fragment()
                self.assertEqual(dcm.params["p_CLKFX_MULTIPLY"], multiplier)
                self.assertEqual(dcm.params["p_CLKFX_DIVIDE"], divider)

    def test_low_input_frequency_locking(self):
        for clkin_freq in [1e6, 12e6, 51e6, 52e6]:
            with self.subTest(clkin_freq=clkin_freq):
                dcm = S6DCM()
                dcm.register_clkin(Signal(), clkin_freq)
                dcm.create_clkout(ClockDomain("clkout"), 12e6, margin=0)
                config = dcm.compute_config()
                self.assertEqual(config["clkout0_freq"], 12e6)
                if clkin_freq < 52e6:
                    self.assertLess(config["clkout0_divide"], clkin_freq/0.5e6)

    def test_output_frequency_limits(self):
        for speedgrade, max_freq in [(-1, 200e6), (-2, 333e6), (-3, 375e6)]:
            for freq in [4e6, max_freq + 1e6]:
                with self.subTest(speedgrade=speedgrade, freq=freq):
                    dcm = S6DCM(speedgrade=speedgrade)
                    dcm.register_clkin(Signal(), 100e6)
                    with self.assertRaisesRegex(ValueError, "Output clock frequency"):
                        dcm.create_clkout(ClockDomain("clkout"), freq)

    def test_low_input_frequency_threshold(self):
        for clkin_freq in [51e6, 52e6]:
            dcm = S6DCM()
            dcm.register_clkin(Signal(), clkin_freq)
            dcm.create_clkout(ClockDomain("clkout"), clkin_freq*25/128, margin=0)
            if clkin_freq < 52e6:
                with self.assertRaisesRegex(ValueError, "No PLL config found"):
                    dcm.compute_config()
            else:
                config = dcm.compute_config()
                self.assertEqual(config["clkfbout_mult"], 25)
                self.assertEqual(config["clkout0_divide"], 128)

    def test_margin_does_not_relax_output_limits(self):
        dcm = S6DCM()
        dcm.register_clkin(Signal(), 27.123e6)
        dcm.create_clkout(ClockDomain("clkout"), 200e6, margin=1e-2)
        config = dcm.compute_config()
        self.assertLessEqual(config["clkout0_freq"], 200e6)
        self.assertAlmostEqual(config["clkout0_freq"], 200e6, delta=2e6)

    def test_unsupported_phase(self):
        dcm = S6DCM()
        with self.assertRaisesRegex(ValueError, "phase"):
            dcm.create_clkout(ClockDomain("clkout"), 100e6, phase=90)
