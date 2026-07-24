#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from litex.soc.interconnect import axi, wishbone
from litex.tools.litex_periph_gen import LiteXSoCGenerator, get_common_ios, get_uart_ios


def make_soc(bus_standard):
    return LiteXSoCGenerator(
        name                 = "unit_soc",
        cpu_type             = "None",
        bus_standard         = bus_standard,
        uart_name            = "serial",
        integrated_rom_size  = 0,
        integrated_sram_size = 0,
        with_ctrl            = False,
        with_timer           = False,
        with_uart            = False,
    )


class TestLiteXPeriphGen(unittest.TestCase):
    def test_common_ios_expose_clock_and_reset(self):
        ios = get_common_ios()

        self.assertEqual(ios[0][0], "clk")
        self.assertEqual(ios[1][0], "rst")

    def test_uart_ios_expose_tx_and_rx(self):
        uart = get_uart_ios()[0]

        self.assertEqual(uart[0], "uart")
        self.assertEqual(uart[2].name, "tx")
        self.assertEqual(uart[3].name, "rx")

    def test_generator_adds_wishbone_mmap_interfaces(self):
        soc = make_soc("wishbone")

        self.assertEqual(soc.platform.name, "unit_soc")
        self.assertIsInstance(soc.bus.masters["mmap_s"], wishbone.Interface)
        self.assertIsInstance(soc.bus.slaves["mmap_m"],  wishbone.Interface)
        self.assertEqual(soc.bus.regions["mmap_m"].origin, 0x20000000)
        self.assertEqual(soc.bus.regions["mmap_m"].size,   0x10000000)

    def test_generator_adds_axi_lite_mmap_interfaces(self):
        soc = make_soc("axi-lite")

        self.assertIsInstance(soc.bus.masters["mmap_s"], axi.AXILiteInterface)
        self.assertIsInstance(soc.bus.slaves["mmap_m"],  axi.AXILiteInterface)
        self.assertEqual(soc.bus.regions["mmap_m"].origin, 0x20000000)
        self.assertEqual(soc.bus.regions["mmap_m"].size,   0x10000000)


if __name__ == "__main__":
    unittest.main()
