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

    def test_sram_burst(self):
        def generator(dut):
            yield from dut.wb.write(0x0000, 0x01234567, cti=0b010)
            yield from dut.wb.write(0x0001, 0x89abcdef, cti=0b010)
            yield from dut.wb.write(0x0002, 0xdeadbeef, cti=0b010)
            yield from dut.wb.write(0x0003, 0xc0ffee00, cti=0b111)
            self.assertEqual((yield from dut.wb.read(0x0000, cti=0b010)), 0x01234567)
            self.assertEqual((yield from dut.wb.read(0x0001, cti=0b010)), 0x89abcdef)
            self.assertEqual((yield from dut.wb.read(0x0002, cti=0b010)), 0xdeadbeef)
            self.assertEqual((yield from dut.wb.read(0x0003, cti=0b111)), 0xc0ffee00)

        class DUT(Module):
            def __init__(self):
                self.wb = wishbone.Interface(bursting=True)
                wishbone_mem = wishbone.SRAM(32, bus=self.wb)
                self.submodules += wishbone_mem

        dut = DUT()
        run_simulation(dut, generator(dut))

    def test_sram_burst_wrap(self):
        def generator(dut):
            bte = 0b01
            yield from dut.wb.write(0x0001, 0x01234567, cti=0b010, bte=bte)
            yield from dut.wb.write(0x0002, 0x89abcdef, cti=0b010, bte=bte)
            yield from dut.wb.write(0x0003, 0xdeadbeef, cti=0b010, bte=bte)
            yield from dut.wb.write(0x0000, 0xc0ffee00, cti=0b111, bte=bte)
            self.assertEqual((yield from dut.wb.read(0x0001, cti=0b010, bte=bte)), 0x01234567)
            self.assertEqual((yield from dut.wb.read(0x0002, cti=0b010, bte=bte)), 0x89abcdef)
            self.assertEqual((yield from dut.wb.read(0x0003, cti=0b010, bte=bte)), 0xdeadbeef)
            self.assertEqual((yield from dut.wb.read(0x0000, cti=0b111, bte=bte)), 0xc0ffee00)

        class DUT(Module):
            def __init__(self):
                self.wb = wishbone.Interface(bursting=True)
                wishbone_mem = wishbone.SRAM(32, bus=self.wb)
                self.submodules += wishbone_mem

        dut = DUT()
        run_simulation(dut, generator(dut))

    def test_sram_burst_constant(self):
        def generator(dut):
            yield from dut.wb.write(0x0001, 0x01234567, cti=0b001)
            yield from dut.wb.write(0x0002, 0x89abcdef, cti=0b001)
            yield from dut.wb.write(0x0003, 0xdeadbeef, cti=0b001)
            yield from dut.wb.write(0x0000, 0xc0ffee00, cti=0b111)
            self.assertEqual((yield from dut.wb.read(0x0001, cti=0b001)), 0x01234567)
            self.assertEqual((yield from dut.wb.read(0x0002, cti=0b001)), 0x89abcdef)
            self.assertEqual((yield from dut.wb.read(0x0003, cti=0b001)), 0xdeadbeef)
            self.assertEqual((yield from dut.wb.read(0x0000, cti=0b111)), 0xc0ffee00)

        class DUT(Module):
            def __init__(self):
                self.wb = wishbone.Interface(bursting=True)
                wishbone_mem = wishbone.SRAM(32, bus=self.wb)
                self.submodules += wishbone_mem

        dut = DUT()
        run_simulation(dut, generator(dut))
