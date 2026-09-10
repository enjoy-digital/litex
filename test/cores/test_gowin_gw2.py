#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import ClockDomain, Instance, Signal

from litex.soc.cores.clock.gowin_gw2a import GW2APLL


class TestGW2PLL(unittest.TestCase):
    def test_catalog_devices_and_speed_grades(self):
        # All GW2 device/revision entries in Gowin's rPLL IP catalog.
        devices = (
            "GW2A-18", "GW2A-18C", "GW2A-55", "GW2A-55C",
            "GW2AR-18", "GW2AR-18C", "GW2AN-55C", "GW2ANR-18C",
        )
        for devicename in devices:
            for grade, vco_range, pfd_max in ((7, (400e6, 1000e6), 400e6), (8, (500e6, 1250e6), 500e6)):
                with self.subTest(device=devicename, grade=grade):
                    family, density = GW2APLL.get_device_model(devicename).split("-")
                    device = f"{family}-LV{density}PG256C{grade}/I{grade-1}"
                    pll = GW2APLL(devicename, device)
                    self.assertEqual(pll.vco_freq_range, vco_range)
                    self.assertEqual(pll.pfd_freq_range, (3e6, pfd_max))
                    pll.register_clkin(Signal(), 50e6)
                    pll.create_clkout(ClockDomain("sys"), vco_range[1]/2, margin=0)
                    self.assertEqual(pll.compute_config()["vco"], vco_range[1])
                    fragment = pll.get_fragment()
                    self.assertIn("rPLL", [s.of for s in fragment.specials if isinstance(s, Instance)])
                    self.assertNotIn("i_VREN", pll.params)
                    with self.assertRaisesRegex(ValueError, "Input clock frequency"):
                        pll.register_clkin(Signal(), pfd_max + 1)

    def test_slow_grade_rejects_fast_grade_frequency(self):
        for suffix, valid in (("C7/I6", False), ("C8/I7", True)):
            with self.subTest(suffix=suffix):
                pll = GW2APLL("GW2A-18C", "GW2A-LV18PG256" + suffix)
                pll.register_clkin(Signal(), 50e6)
                pll.create_clkout(ClockDomain("sys"), 600e6, margin=0)
                if valid:
                    self.assertEqual(pll.compute_config()["vco"], 1200e6)
                else:
                    with self.assertRaisesRegex(ValueError, "No PLL config"):
                        pll.compute_config()

    def test_slow_grade_minimum_vco(self):
        pll = GW2APLL("GW2A-18C", "GW2A-LV18PG256C7/I6")
        pll.register_clkin(Signal(), 25e6)
        pll.create_clkout(ClockDomain("sys"), 3.125e6, margin=0)
        self.assertEqual(pll.compute_config()["vco"], 400e6)

    def test_speed_grade_aliases_and_missing_grade(self):
        for suffix in ("C7/I6", "C7", "I6"):
            with self.subTest(suffix=suffix):
                device = "GW2A-LV18PG256" + suffix
                self.assertEqual(GW2APLL.get_vco_freq_range(device), (400e6, 1000e6))
                self.assertEqual(GW2APLL.get_pfd_freq_range(device), (3e6, 400e6))
        pll = GW2APLL("GW2A-18C", "GW2A-18C")
        self.assertEqual(pll.vco_freq_range, (500e6, 1000e6))
        self.assertEqual(pll.pfd_freq_range, (3e6, 400e6))
        for device in ("GW2A-LV18PG256C9/I8", "GW2AR-LV18QN88C9/I8"):
            self.assertEqual(GW2APLL.get_vco_freq_range(device), (500e6, 1250e6))
        with self.assertRaisesRegex(ValueError, "speed grade"):
            GW2APLL("GW2AN-55C", "GW2AN-LV55UG676C9/I8")

    def test_unsupported_devices(self):
        for devicename in ("GW2AN-18X", "GW2AN-9X", "GW2A-180", "GW2AR-55", "GW1N-9"):
            with self.subTest(device=devicename):
                with self.assertRaisesRegex(ValueError, "Unsupported rPLL device"):
                    GW2APLL(devicename, devicename)
