#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.clock.xilinx_usp import USPMMCM


class TestUSPMMCM(unittest.TestCase):
    def test_missing_clocks(self):
        mmcm = USPMMCM()
        with self.assertRaisesRegex(ValueError, "Input clock"):
            mmcm.compute_config()
        mmcm.register_clkin(Signal(), 100e6)
        with self.assertRaisesRegex(ValueError, "output clock"):
            mmcm.compute_config()

    def test_clkout0_divide_by_one(self):
        mmcm = USPMMCM(speedgrade=-3)
        mmcm.register_clkin(Signal(), 101.25e6)
        mmcm.create_clkout(ClockDomain("clkout"), 810e6, margin=0)
        mmcm.get_fragment()
        self.assertEqual(mmcm.params["p_CLKOUT0_DIVIDE_F"], 1)
        self.assertEqual(mmcm.params["p_CLKFBOUT_MULT_F"], 8)

    def test_fractional_feedback_and_output(self):
        mmcm = USPMMCM()
        mmcm.register_clkin(Signal(), 12e6)
        mmcm.create_clkout(ClockDomain("clkout"), 148.5e6, margin=0)
        config = mmcm.compute_config()
        self.assertEqual(config["clkfbout_mult"], 123.75)
        self.assertEqual(config["clkout0_freq"], 148.5e6)

        mmcm = USPMMCM()
        mmcm.register_clkin(Signal(), 100e6)
        mmcm.create_clkout(ClockDomain("clkout0"), 80e6, margin=0)
        mmcm.create_clkout(ClockDomain("clkout1"), 125e6, margin=0)
        config = mmcm.compute_config()
        self.assertEqual(config["clkout0_divide"], 18.75)
        self.assertEqual(config["clkout1_divide"], 12)
        self.assertEqual(config["clkout0_freq"], 80e6)
        self.assertEqual(config["clkout1_freq"], 125e6)

    def test_multiplier_and_divider_endpoints(self):
        mmcm = USPMMCM()
        mmcm.register_clkin(Signal(), 10e6)
        mmcm.create_clkout(ClockDomain("clkout"), 10e6, margin=0)
        config = mmcm.compute_config()
        self.assertEqual(config["clkfbout_mult"], 128)
        self.assertEqual(config["clkout0_divide"], 128)

    def test_no_config_diagnostic(self):
        mmcm = USPMMCM()
        mmcm.register_clkin(Signal(), 100e6)
        mmcm.create_clkout(ClockDomain("clkout"), 1e6, margin=0)
        with self.assertRaisesRegex(ValueError, "No PLL config found.*ClkIn=100.00MHz, ClkOut0=1.00MHz"):
            mmcm.compute_config()
