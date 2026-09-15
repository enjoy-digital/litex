#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import Record

from litex.build.gowin import GowinPlatform
from litex.soc.integration.soc import SoCCore, SoCRegion, SoCError


class TestGowinAE350(unittest.TestCase):
    def make_soc(self, **kwargs):
        platform = GowinPlatform("GW5AST-LV138FPG676AES", [], devicename="GW5AST-138B")
        return SoCCore(platform, clk_freq=50e6,
            cpu_type            = "gowin_ae350",
            integrated_rom_size = 0x8000,
            with_uart           = False,
            with_timer          = False,
            **kwargs)

    def test_fabric_io_window(self):
        soc = self.make_soc()
        region = soc.bus.io_regions["io0"]
        # MUG1029 Table 3-1: the connected EXTS port covers 0xe8000000..0xefffffff.
        self.assertEqual(region.origin, 0xe800_0000)
        self.assertEqual(region.origin + region.size, 0xf000_0000)
        for origin in [0xe800_0000, 0xefff_f000]:
            soc.bus.add_region(f"fabric_{origin:x}",
                SoCRegion(origin=origin, size=0x1000, cached=False))

    def test_internal_peripherals_and_apb_extension_are_not_fabric_io(self):
        soc = self.make_soc()
        for origin in [0xf000_0000, 0xf800_0000]:
            with self.subTest(origin=origin):
                with self.assertLogs("SoCBusHandler", level="ERROR"), self.assertRaises(SoCError):
                    soc.bus.add_region(f"unreachable_{origin:x}",
                        SoCRegion(origin=origin, size=0x1000, cached=False))

    def test_fixed_reset_address(self):
        soc = self.make_soc(cpu_reset_address=0x8000_0000)
        self.assertEqual(soc.cpu.reset_address, 0x8000_0000)
        self.assertEqual(soc.constants["CONFIG_CPU_RESET_ADDR"], 0x8000_0000)
        for address in [0x0000_0000, 0x8000_0100]:
            with self.subTest(address=address), self.assertRaisesRegex(ValueError, "reset address is fixed"):
                self.make_soc(cpu_reset_address=address)

    def test_64bit_system_bus(self):
        # Fabric ports must support the width converters used by a wider system bus.
        soc = self.make_soc(bus_data_width=64)
        soc.finalize()

    def test_linux_internal_regions(self):
        soc = self.make_soc(cpu_variant="linux")
        for name, origin, size in [
            ("plic",    0xe400_0000, 0x40_0000),
            ("plmt",    0xe600_0000, 0x1000),
            ("opensbi", 0x40f0_0000, 0x8_0000),
        ]:
            with self.subTest(region=name):
                region = soc.bus.regions[name]
                self.assertEqual((region.origin, region.size), (origin, size))
                self.assertTrue(region.linker)
                self.assertNotIn(name, soc.bus.slaves)
        self.assertEqual(soc.constants["CONFIG_CPU_PLIC_NDEV"], 27)
        self.assertEqual(soc.constants["CONFIG_CPU_TIMEBASE_FREQUENCY"], 50_000_000)
        self.assertEqual(soc.constants["CONFIG_CPU_MMU"], "sv32")

    def test_standard_does_not_reserve_linux_regions(self):
        soc = self.make_soc()
        for name in ["plic", "plmt", "opensbi"]:
            self.assertNotIn(name, soc.bus.regions)

    def test_ethernet_buffers_do_not_overlap_csrs(self):
        from liteeth.phy.model import LiteEthPHYModel

        soc = self.make_soc()
        pads = Record([
            ("source_valid", 1), ("source_data", 8),
            ("sink_valid",   1), ("sink_data",   8),
        ])
        soc.ethphy = LiteEthPHYModel(pads)
        soc.add_ethernet(phy=soc.ethphy)
        soc.finalize()

        csr = soc.bus.regions["csr"]
        mac = soc.bus.regions["ethmac"]
        self.assertGreaterEqual(mac.origin, csr.origin + csr.size)
        self.assertLessEqual(mac.origin + mac.size, 0xf000_0000)


if __name__ == "__main__":
    unittest.main()
