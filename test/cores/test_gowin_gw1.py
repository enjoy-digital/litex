#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import ClockDomain, Instance, Signal

from litex.soc.cores.clock.gowin_gw1n import GW1NPLL
from litex.soc.cores.clock.gowin_gw2a import GW2APLL


class TestGW1PLL(unittest.TestCase):
    def test_device_primitives(self):
        # Gowin rPLL/PLLVR IP catalog device/revision names.
        rpll_devices = (
            "GW1N-1", "GW1N-1S", "GW1N-4", "GW1N-4B", "GW1N-4D", "GW1N-9", "GW1N-9C",
            "GW1NR-1", "GW1NR-4", "GW1NR-4B", "GW1NR-4D", "GW1NR-9", "GW1NR-9C",
            "GW1NRF-4B", "GW1NS-2", "GW1NS-2C", "GW1NSR-2", "GW1NSR-2C", "GW1NSE-2C",
            "GW1NZ-1", "GW1NZ-1C", "GW1A-1A", "GW1AN-1C",
        )
        pllvr_devices = ("GW1NS-4", "GW1NS-4C", "GW1NSR-4", "GW1NSR-4C", "GW1NSER-4C")
        for primitive, devices in (("rPLL", rpll_devices), ("PLLVR", pllvr_devices)):
            for devicename in devices:
                with self.subTest(device=devicename):
                    family, density = GW1NPLL.get_device_model(devicename).split("-")
                    device = f"{family}-LV{density}QN48C6/I5"
                    pll = GW1NPLL(devicename, device)
                    pll.register_clkin(Signal(), 50e6)
                    pll.create_clkout(ClockDomain("sys"), 100e6)
                    fragment = pll.get_fragment()
                    self.assertIn(primitive, [s.of for s in fragment.specials if isinstance(s, Instance)])
                    self.assertEqual("i_VREN" in pll.params, primitive == "PLLVR")

    def test_documented_limits(self):
        cases = [
            ("GW1N-1",     "GW1N-LV1QN48C5/I4",    (320e6, 720e6), 320e6),
            ("GW1N-4B",    "GW1N-LV4LQ144C6/I5",   (400e6, 1000e6), 400e6),
            ("GW1NR-9C",   "GW1NR-LV9QN88PC6/I5",  (400e6, 1200e6), 400e6),
            ("GW1NRF-4B",  "GW1NRF-LV4BQN48C5/I4", (320e6, 800e6), 320e6),
            ("GW1N-1S",    "GW1N-LV1SQN48C5/I4",   (320e6, 960e6), 320e6),
            ("GW1NS-2C",   "GW1NS-LV2CQN48C6/I5",  (400e6, 1200e6), 400e6),
            ("GW1NSR-4C",  "GW1NSR-LV4CQN48PC6/I5", (600e6, 1200e6), 400e6),
            ("GW1NSER-4C", "GW1NSER-LV4CQN48C5/I4", (320e6, 960e6), 320e6),
            ("GW1NZ-1C",   "GW1NZ-LV1QN48C5/I4",   (320e6, 640e6), 320e6),
            ("GW1NZ-1C",   "GW1NZ-ZV1QN48C5/I4",   (200e6, 400e6), 200e6),
            ("GW1NZ-1C",   "GW1NZ-ZV1QN48I3",      (150e6, 300e6), 150e6),
            ("GW1NZ-1C",   "GW1NZ-ZV1QN48I2",      (100e6, 200e6), 100e6),
        ]
        for devicename, device, vco_range, pfd_max in cases:
            with self.subTest(device=device):
                pll = GW1NPLL(devicename, device)
                self.assertEqual(pll.vco_freq_range, vco_range)
                self.assertEqual(pll.pfd_freq_range, (3e6, pfd_max))
                # The highest output requires the documented maximum VCO.
                pll.register_clkin(Signal(), vco_range[1]/20)
                pll.create_clkout(ClockDomain("sys"), vco_range[1]/2, margin=0)
                self.assertEqual(pll.compute_config()["vco"], vco_range[1])
                with self.assertRaisesRegex(ValueError, "Input clock frequency"):
                    pll.register_clkin(Signal(), pfd_max + 1)

    def test_high_frequency_on_9k(self):
        pll = GW1NPLL("GW1NR-9C", "GW1NR-LV9QN88PC6/I5")
        pll.register_clkin(Signal(), 50e6)
        pll.create_clkout(ClockDomain("sys"), 600e6, margin=0)
        self.assertEqual(pll.compute_config()["vco"], 1200e6)

    def test_slow_grade_rejects_fast_grade_frequency(self):
        for suffix, valid in (("C5/I4", False), ("C6/I5", True)):
            with self.subTest(suffix=suffix):
                pll = GW1NPLL("GW1N-1", "GW1N-LV1QN48" + suffix)
                pll.register_clkin(Signal(), 50e6)
                pll.create_clkout(ClockDomain("sys"), 400e6, margin=0)
                if valid:
                    self.assertEqual(pll.compute_config()["vco"], 800e6)
                else:
                    with self.assertRaisesRegex(ValueError, "No PLL config"):
                        pll.compute_config()

    def test_speed_grade_aliases_and_missing_grade(self):
        for suffix in ("C5/I4", "C5", "I4"):
            with self.subTest(suffix=suffix):
                pll = GW1NPLL("GW1N-1", "GW1N-LV1QN48" + suffix)
                self.assertEqual(pll.vco_freq_range, (320e6, 720e6))
        pll = GW1NPLL("GW1N-1", "GW1N-1")
        self.assertEqual(pll.vco_freq_range, (400e6, 720e6))
        self.assertEqual(pll.pfd_freq_range, (3e6, 320e6))
        with self.assertRaisesRegex(ValueError, "speed grade"):
            GW1NPLL("GW1N-1", "GW1N-LV1QN48C6/I4")

    def test_fdly_uses_devicename(self):
        for devicename, device, fdly in (
            ("GW1N-1", "GW1N-LV1QN48C6/I5", 0),
            ("GW1N-1S", "GW1N-LV1SQN48C6/I5", 0),
            ("GW1NR-9C", "GW1NR-LV9QN88PC6/I5", 15),
        ):
            with self.subTest(device=devicename):
                pll = GW1NPLL(devicename, device)
                pll.register_clkin(Signal(), 50e6)
                pll.create_clkout(ClockDomain("sys"), 100e6)
                pll.get_fragment()
                self.assertEqual(pll.params["i_FDLY"].value, fdly)

    def test_incompatible_primitives_are_rejected(self):
        for device in ("GW1N-2", "GW1N-1P5", "GW1NR-2", "GW1NZ-2C", "GW1N-90"):
            with self.subTest(device=device):
                with self.assertRaisesRegex(ValueError, "Unsupported"):
                    GW1NPLL(device, device)

    def test_gw2_subclass_compatibility(self):
        pll = GW2APLL("GW2AR-18C", "GW2AR-LV18QN88C8/I7")
        pll.register_clkin(Signal(), 27e6)
        pll.create_clkout(ClockDomain("sys"), 54e6)
        fragment = pll.get_fragment()
        self.assertEqual(pll.vco_freq_range, (500e6, 1250e6))
        self.assertIn("rPLL", [s.of for s in fragment.specials if isinstance(s, Instance)])
