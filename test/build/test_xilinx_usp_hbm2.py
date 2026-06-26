#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
from types import SimpleNamespace

from migen import Module

from litex.soc.cores.ram.xilinx_usp_hbm2 import (
    USPHBM2_HIGH_BASE,
    USPHBM2_CHANNEL_SIZE,
    add_usphbm2_pseudochannels,
    parse_usphbm2_channels,
    usphbm2_channel_origin,
    usphbm2_channel_origins,
    usphbm2_window_end,
)
from litex.soc.interconnect.axi import AXIInterface


class _FakeBus:
    address_width = 32

    def __init__(self):
        self.slaves = {}
        self.regions = {}

    def add_slave(self, name, bus, region):
        self.slaves[name] = (bus, region)

    def add_region(self, name, region):
        self.regions[name] = region


class _FakeSoC(Module):
    def __init__(self):
        self.bus = _FakeBus()
        self.constants = {}

    def add_constant(self, name, value):
        self.constants[name] = value


def _fake_hbm():
    return SimpleNamespace(axi=[
        AXIInterface(data_width=256, address_width=33, id_width=6)
        for _ in range(32)
    ])

# Tests --------------------------------------------------------------------------------------------

class TestUSPHBM2Helpers(unittest.TestCase):
    def test_channel_parser_accepts_lists_ranges_and_all(self):
        self.assertEqual(parse_usphbm2_channels("0,1,2,3"), (0, 1, 2, 3))
        self.assertEqual(parse_usphbm2_channels("0-3,8"), (0, 1, 2, 3, 8))
        self.assertEqual(parse_usphbm2_channels("all"), tuple(range(32)))

    def test_channel_parser_rejects_invalid_channels(self):
        for channels in ["", "3-1", "0,0", "32"]:
            with self.subTest(channels=channels):
                with self.assertRaises(ValueError):
                    parse_usphbm2_channels(channels)

    def test_channel_origin_map_keeps_low_window_and_moves_upper_channels_high(self):
        self.assertEqual(usphbm2_channel_origin(0), 0x4000_0000)
        self.assertEqual(usphbm2_channel_origin(3), 0x7000_0000)
        self.assertEqual(usphbm2_channel_origin(4), USPHBM2_HIGH_BASE)

    def test_window_end_reports_selected_channel_limit(self):
        origins = usphbm2_channel_origins((0, 1, 4))
        self.assertEqual(usphbm2_window_end(origins), USPHBM2_HIGH_BASE + USPHBM2_CHANNEL_SIZE)

    def test_add_pseudochannels_registers_soc_regions_and_constants(self):
        soc = _FakeSoC()

        origins = add_usphbm2_pseudochannels(
            soc          = soc,
            hbm          = _fake_hbm(),
            channels     = "0,1,4",
            main_channel = 4,
        )

        self.assertEqual(origins, {
            0: 0x4000_0000,
            1: 0x5000_0000,
            4: USPHBM2_HIGH_BASE,
        })
        self.assertEqual(set(soc.bus.slaves), {"hbm0", "hbm1", "hbm4"})
        self.assertEqual(soc.bus.slaves["hbm0"][1].origin, 0x4000_0000)
        self.assertEqual(soc.bus.slaves["hbm4"][1].origin, USPHBM2_HIGH_BASE)
        self.assertEqual(soc.bus.regions["main_ram"].origin, USPHBM2_HIGH_BASE)
        self.assertTrue(soc.bus.regions["main_ram"].linker)
        self.assertEqual(soc.constants["HBM_CHANNELS"], 3)
        self.assertEqual(soc.constants["HBM_MAIN_CHANNEL"], 4)

    def test_add_pseudochannels_rejects_main_channel_outside_mapping(self):
        with self.assertRaisesRegex(ValueError, "main channel"):
            add_usphbm2_pseudochannels(
                soc          = _FakeSoC(),
                hbm          = _fake_hbm(),
                channels     = "0,1",
                main_channel = 4,
            )


if __name__ == "__main__":
    unittest.main()
