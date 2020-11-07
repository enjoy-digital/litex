#
# This file is part of LiteX.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from litex.soc.cores.clock import *


class TestClock(unittest.TestCase):
    # Xilinx / Spartan 6
    def test_s6pll(self):
        pll = S6PLL()
        pll.register_clkin(Signal(), 100e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        pll.compute_config()

    def test_s6dcm(self):
        dcm = S6DCM()
        dcm.register_clkin(Signal(), 100e6)
        for i in range(dcm.nclkouts_max):
            dcm.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        dcm.compute_config()

    # Xilinx / 7-Series
    def test_s7pll(self):
        pll = S7PLL()
        pll.register_clkin(Signal(), 100e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        pll.compute_config()

    def test_s7mmcm(self):
        mmcm = S7MMCM()
        mmcm.register_clkin(Signal(), 100e6)
        for i in range(mmcm.nclkouts_max):
            mmcm.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        mmcm.compute_config()

    # Xilinx / Ultrascale
    def test_uspll(self):
        pll = USPLL()
        pll.register_clkin(Signal(), 100e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        pll.compute_config()

    def test_usmmcm(self):
        mmcm = USMMCM()
        mmcm.register_clkin(Signal(), 100e6)
        for i in range(mmcm.nclkouts_max):
            mmcm.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        mmcm.compute_config()

    # Xilinx / Ultrascale Plus
    def test_usppll(self):
        pll = USPPLL()
        pll.register_clkin(Signal(), 100e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        pll.compute_config()

    def test_uspmmcm(self):
        mmcm = USPMMCM()
        mmcm.register_clkin(Signal(), 100e6)
        for i in range(mmcm.nclkouts_max):
            mmcm.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        mmcm.compute_config()

    # Lattice / iCE40
    def test_ice40pll(self):
        pll = USMMCM()
        pll.register_clkin(Signal(), 100e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        pll.compute_config()

    # Lattice / ECP5
    def test_ecp5pll(self):
        pll = ECP5PLL()
        pll.register_clkin(Signal(), 100e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        pll.compute_config()

    # Altera / CycloneIV
    def test_cycloneivpll(self):
        pll = CycloneIVPLL()
        pll.register_clkin(Signal(), 50e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 100e6)
        pll.compute_config()

    # Altera / CycloneV
    def test_cyclonevpll(self):
        pll = CycloneVPLL()
        pll.register_clkin(Signal(), 50e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 100e6)
        pll.compute_config()
