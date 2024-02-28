#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.gen import *

from litex.soc.interconnect import wishbone

from litex.soc.integration.soc_core import SoCRegion

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

        class DUT(LiteXModule):
            def __init__(self):
                self.wb16 = wishbone.Interface(data_width=16, address_width=32, addressing="word")
                wb32      = wishbone.Interface(data_width=32, address_width=32, addressing="word")
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

        class DUT(LiteXModule):
            def __init__(self):
                self.wb32 = wishbone.Interface(data_width=32, address_width=32, addressing="word")
                wb64      = wishbone.Interface(data_width=64, address_width=32, addressing="word")
                wb32      = wishbone.Interface(data_width=32, address_width=32, addressing="word")
                up_converter   = wishbone.UpConverter(self.wb32, wb64)
                down_converter = wishbone.DownConverter(wb64, wb32)
                self.submodules += up_converter, down_converter
                wishbone_mem = wishbone.SRAM(32, bus=wb32)
                self.submodules += wishbone_mem

        dut = DUT()
        run_simulation(dut, generator(dut))

    def test_sram_burst(self):
        def generator(dut):
            yield from dut.wb.write(0x0000, 0x01234567, cti=wishbone.CTI_BURST_INCREMENTING)
            yield from dut.wb.write(0x0001, 0x89abcdef, cti=wishbone.CTI_BURST_INCREMENTING)
            yield from dut.wb.write(0x0002, 0xdeadbeef, cti=wishbone.CTI_BURST_INCREMENTING)
            yield from dut.wb.write(0x0003, 0xc0ffee00, cti=wishbone.CTI_BURST_END)
            self.assertEqual((yield from dut.wb.read(0x0000, cti=wishbone.CTI_BURST_INCREMENTING)), 0x01234567)
            self.assertEqual((yield from dut.wb.read(0x0001, cti=wishbone.CTI_BURST_INCREMENTING)), 0x89abcdef)
            self.assertEqual((yield from dut.wb.read(0x0002, cti=wishbone.CTI_BURST_INCREMENTING)), 0xdeadbeef)
            self.assertEqual((yield from dut.wb.read(0x0003, cti=wishbone.CTI_BURST_END)), 0xc0ffee00)

        class DUT(LiteXModule):
            def __init__(self):
                self.wb = wishbone.Interface(data_width=32, address_width=32, addressing="word", bursting=True)
                wishbone_mem = wishbone.SRAM(32, bus=self.wb)
                self.submodules += wishbone_mem

        dut = DUT()
        run_simulation(dut, generator(dut))

    def test_sram_burst_wrap(self):
        def generator(dut):
            bte = 0b01
            yield from dut.wb.write(0x0001, 0x01234567, cti=wishbone.CTI_BURST_INCREMENTING, bte=bte)
            yield from dut.wb.write(0x0002, 0x89abcdef, cti=wishbone.CTI_BURST_INCREMENTING, bte=bte)
            yield from dut.wb.write(0x0003, 0xdeadbeef, cti=wishbone.CTI_BURST_INCREMENTING, bte=bte)
            yield from dut.wb.write(0x0000, 0xc0ffee00, cti=wishbone.CTI_BURST_END, bte=bte)
            self.assertEqual((yield from dut.wb.read(0x0001, cti=wishbone.CTI_BURST_INCREMENTING, bte=bte)), 0x01234567)
            self.assertEqual((yield from dut.wb.read(0x0002, cti=wishbone.CTI_BURST_INCREMENTING, bte=bte)), 0x89abcdef)
            self.assertEqual((yield from dut.wb.read(0x0003, cti=wishbone.CTI_BURST_INCREMENTING, bte=bte)), 0xdeadbeef)
            self.assertEqual((yield from dut.wb.read(0x0000, cti=wishbone.CTI_BURST_END, bte=bte)), 0xc0ffee00)

        class DUT(LiteXModule):
            def __init__(self):
                self.wb = wishbone.Interface(data_width=32, address_width=32, addressing="word", bursting=True)
                wishbone_mem = wishbone.SRAM(32, bus=self.wb)
                self.submodules += wishbone_mem

        dut = DUT()
        run_simulation(dut, generator(dut))

    def test_sram_burst_constant(self):
        def generator(dut):
            yield from dut.wb.write(0x0001, 0x01234567, cti=wishbone.CTI_BURST_CONSTANT)
            yield from dut.wb.write(0x0002, 0x89abcdef, cti=wishbone.CTI_BURST_CONSTANT)
            yield from dut.wb.write(0x0003, 0xdeadbeef, cti=wishbone.CTI_BURST_CONSTANT)
            yield from dut.wb.write(0x0000, 0xc0ffee00, cti=wishbone.CTI_BURST_END)
            self.assertEqual((yield from dut.wb.read(0x0001, cti=wishbone.CTI_BURST_CONSTANT)), 0x01234567)
            self.assertEqual((yield from dut.wb.read(0x0002, cti=wishbone.CTI_BURST_CONSTANT)), 0x89abcdef)
            self.assertEqual((yield from dut.wb.read(0x0003, cti=wishbone.CTI_BURST_CONSTANT)), 0xdeadbeef)
            self.assertEqual((yield from dut.wb.read(0x0000, cti=wishbone.CTI_BURST_END)), 0xc0ffee00)

        class DUT(LiteXModule):
            def __init__(self):
                self.wb = wishbone.Interface(data_width=32, address_width=32, addressing="word", bursting=True)
                wishbone_mem = wishbone.SRAM(32, bus=self.wb)
                self.submodules += wishbone_mem

        dut = DUT()
        run_simulation(dut, generator(dut))

    def test_origin_remap_byte(self):
        def generator(dut):
            yield from dut.master.write(0x0000_0000, 0)
            yield from dut.master.write(0x0000_0004, 0)
            yield from dut.master.write(0x0000_0008, 0)
            yield from dut.master.write(0x0000_000c, 0)
            yield from dut.master.write(0x1000_0000, 0)
            yield from dut.master.write(0x1000_0004, 0)
            yield from dut.master.write(0x1000_0008, 0)
            yield from dut.master.write(0x1000_000c, 0)

        def checker(dut):
            yield dut.slave.ack.eq(1)
            while (yield dut.slave.stb) == 0:
                yield
            self.assertEqual((yield dut.slave.adr), 0x0001_0000)
            yield
            self.assertEqual((yield dut.slave.adr), 0x0001_0004)
            yield
            self.assertEqual((yield dut.slave.adr), 0x0001_0008)
            yield
            self.assertEqual((yield dut.slave.adr), 0x0001_000c)
            yield
            self.assertEqual((yield dut.slave.adr), 0x0001_0000)
            yield
            self.assertEqual((yield dut.slave.adr), 0x0001_0004)
            yield
            self.assertEqual((yield dut.slave.adr), 0x0001_0008)
            yield
            self.assertEqual((yield dut.slave.adr), 0x0001_000c)

        class DUT(LiteXModule):
            def __init__(self):
                self.master    = wishbone.Interface(data_width=32, address_width=32, addressing="byte")
                self.slave     = wishbone.Interface(data_width=32, address_width=32, addressing="byte")
                self.remapper  = wishbone.Remapper(self.master, self.slave,
                    origin = 0x0001_0000,
                    size   = 0x1000_0000,
                )
        dut = DUT()
        run_simulation(dut, [generator(dut), checker(dut)])


    def origin_remap_test(self, addressing="byte"):
        adr_div = {
            "byte": 1,
            "word": 4,
        }[addressing]
        def generator(dut):
            yield from dut.master.write(0x0000_0000//adr_div, 0)
            yield from dut.master.write(0x0000_0004//adr_div, 0)
            yield from dut.master.write(0x0000_0008//adr_div, 0)
            yield from dut.master.write(0x0000_000c//adr_div, 0)
            yield from dut.master.write(0x1000_0000//adr_div, 0)
            yield from dut.master.write(0x1000_0004//adr_div, 0)
            yield from dut.master.write(0x1000_0008//adr_div, 0)
            yield from dut.master.write(0x1000_000c//adr_div, 0)

        def checker(dut):
            yield dut.slave.ack.eq(1)
            while (yield dut.slave.stb) == 0:
                yield
            self.assertEqual((yield dut.slave.adr), 0x0001_0000//adr_div)
            yield
            self.assertEqual((yield dut.slave.adr), 0x0001_0004//adr_div)
            yield
            self.assertEqual((yield dut.slave.adr), 0x0001_0008//adr_div)
            yield
            self.assertEqual((yield dut.slave.adr), 0x0001_000c//adr_div)
            yield
            self.assertEqual((yield dut.slave.adr), 0x0001_0000//adr_div)
            yield
            self.assertEqual((yield dut.slave.adr), 0x0001_0004//adr_div)
            yield
            self.assertEqual((yield dut.slave.adr), 0x0001_0008//adr_div)
            yield
            self.assertEqual((yield dut.slave.adr), 0x0001_000c//adr_div)

        class DUT(LiteXModule):
            def __init__(self):
                self.master    = wishbone.Interface(data_width=32, address_width=32, addressing=addressing)
                self.slave     = wishbone.Interface(data_width=32, address_width=32, addressing=addressing)
                self.remapper  = wishbone.Remapper(self.master, self.slave,
                    origin = 0x0001_0000,
                    size   = 0x1000_0000,
                )
        dut = DUT()
        run_simulation(dut, [generator(dut), checker(dut)])

    def test_origin_remap_byte(self):
        self.origin_remap_test(addressing="byte")

    def test_origin_remap_word(self):
        self.origin_remap_test(addressing="word")

    def region_remap_test(self, addressing="byte"):
        adr_div = {
            "byte": 1,
            "word": 4,
        }[addressing]
        def generator(dut):
            yield from dut.master.write(0x0000_0000//adr_div, 0)
            yield from dut.master.write(0x0001_0004//adr_div, 0)
            yield from dut.master.write(0x0002_0008//adr_div, 0)
            yield from dut.master.write(0x0003_000c//adr_div, 0)

        def checker(dut):
            yield dut.slave.ack.eq(1)
            while (yield dut.slave.stb) == 0:
                yield
            self.assertEqual((yield dut.slave.adr), 0x0000_0000//adr_div)
            yield
            self.assertEqual((yield dut.slave.adr), 0x1000_0004//adr_div)
            yield
            self.assertEqual((yield dut.slave.adr), 0x2000_0008//adr_div)
            yield
            self.assertEqual((yield dut.slave.adr), 0x3000_000c//adr_div)
            yield

        class DUT(LiteXModule):
            def __init__(self):
                self.master    = wishbone.Interface(data_width=32, address_width=32, addressing=addressing)
                self.slave     = wishbone.Interface(data_width=32, address_width=32, addressing=addressing)
                self.remapper  = wishbone.Remapper(self.master, self.slave,
                    src_regions = [
                        SoCRegion(origin=0x0000_0000, size=0x1000),
                        SoCRegion(origin=0x0001_0000, size=0x1000),
                        SoCRegion(origin=0x0002_0000, size=0x1000),
                        SoCRegion(origin=0x0003_0000, size=0x1000),
                    ],
                    dst_regions = [
                        SoCRegion(origin=0x0000_0000, size=0x1000),
                        SoCRegion(origin=0x1000_0000, size=0x1000),
                        SoCRegion(origin=0x2000_0000, size=0x1000),
                        SoCRegion(origin=0x3000_0000, size=0x1000),
                    ]
                )
        dut = DUT()
        run_simulation(dut, [generator(dut), checker(dut)])

    def test_region_remap_byte(self):
        self.region_remap_test(addressing="byte")

    def test_region_remap_word(self):
        self.region_remap_test(addressing="word")

    def origin_region_remap_test(self, addressing="byte"):
        adr_div = {
            "byte": 1,
            "word": 4,
        }[addressing]
        def generator(dut):
            yield from dut.master.write(0x6000_0000//adr_div, 0)
            yield from dut.master.write(0x6001_0000//adr_div, 0)
            yield from dut.master.write(0x6001_0040//adr_div, 0)

        def checker(dut):
            yield dut.slave.ack.eq(1)
            while (yield dut.slave.stb) == 0:
                yield
            self.assertEqual((yield dut.slave.adr), 0xf000_0000//adr_div)
            yield
            self.assertEqual((yield dut.slave.adr), 0x8100_0000//adr_div)
            yield
            self.assertEqual((yield dut.slave.adr), 0x2000_0000//adr_div)
            yield
            for i in range(128):
                yield

        class DUT(LiteXModule):
            def __init__(self):
                self.master    = wishbone.Interface(data_width=32, address_width=32, addressing=addressing)
                self.slave     = wishbone.Interface(data_width=32, address_width=32, addressing=addressing)
                self.remapper  = wishbone.Remapper(self.master, self.slave,
                    origin = 0x0000_0000,
                    size   = 0x2000_0000,
                    src_regions = [
                        SoCRegion(origin=0x0000_0000, size=65536),
                        SoCRegion(origin=0x0001_0000, size=64),
                        SoCRegion(origin=0x0001_0040, size=8),
                    ],
                    dst_regions = [
                        SoCRegion(origin=0xf000_0000, size=65536),
                        SoCRegion(origin=0x8100_0000,  size=64),
                        SoCRegion(origin=0x2000_0000,  size=8),
                    ]
                )
        dut = DUT()
        run_simulation(dut, [generator(dut), checker(dut)])

    def test_origin_region_remap_byte(self):
        self.origin_region_remap_test(addressing="byte")

    def test_origin_region_remap_word(self):
        self.origin_region_remap_test(addressing="word")
