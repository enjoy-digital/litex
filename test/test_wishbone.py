#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.interconnect import wishbone

# TestWishbone -------------------------------------------------------------------------------------

class TestWishbone(unittest.TestCase):
    def test_upconverter_16_32(self):
        def generator(dut):
            yield from dut.wb16.write(0x0000, 0x1234)
            yield from dut.wb16.write(0x0001, 0x5678)
            yield from dut.wb16.write(0x0002, 0xdead)
            yield from dut.wb16.write(0x0003, 0xbeef)
            self.assertEqual((yield from dut.wb16.read(0x0000)), 0x1234)
            self.assertEqual((yield from dut.wb16.read(0x0001)), 0x5678)
            self.assertEqual((yield from dut.wb16.read(0x0002)), 0xdead)
            self.assertEqual((yield from dut.wb16.read(0x0003)), 0xbeef)

        class DUT(Module):
            def __init__(self):
                self.wb16 = wishbone.Interface(data_width=16)
                wb32      = wishbone.Interface(data_width=32)
                up_converter = wishbone.UpConverter(self.wb16, wb32)
                self.submodules += up_converter
                wishbone_mem = wishbone.SRAM(32, bus=wb32)
                self.submodules += wishbone_mem

        dut = DUT()
        run_simulation(dut, generator(dut))

    def test_converter_32_64_32(self):
        def generator(dut):
            yield from dut.wb32.write(0x0000, 0x12345678)
            yield from dut.wb32.write(0x0001, 0xdeadbeef)
            self.assertEqual((yield from dut.wb32.read(0x0000)), 0x12345678)
            self.assertEqual((yield from dut.wb32.read(0x0001)), 0xdeadbeef)

        class DUT(Module):
            def __init__(self):
                self.wb32 = wishbone.Interface(data_width=32)
                wb64      = wishbone.Interface(data_width=64)
                wb32      = wishbone.Interface(data_width=32)
                up_converter   = wishbone.UpConverter(self.wb32, wb64)
                down_converter = wishbone.DownConverter(wb64, wb32)
                self.submodules += up_converter, down_converter
                wishbone_mem = wishbone.SRAM(32, bus=wb32)
                self.submodules += wishbone_mem

        dut = DUT()
        run_simulation(dut, generator(dut))
