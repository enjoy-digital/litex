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

# Helpers ------------------------------------------------------------------------------------------

def burst_ctis(length, beat_cti=wishbone.CTI_BURST_INCREMENTING):
    assert length >= 1
    return [beat_cti] * (length - 1) + [wishbone.CTI_BURST_END]


def wishbone_write_burst(bus, addrs, values, beat_cti=wishbone.CTI_BURST_INCREMENTING, bte=0, sel=None):
    assert len(addrs) == len(values)
    ctis = burst_ctis(len(addrs), beat_cti)
    if sel is None:
        sel = (1 << len(bus.sel)) - 1

    yield bus.we.eq(1)
    yield bus.sel.eq(sel)
    yield bus.cyc.eq(1)
    yield bus.stb.eq(1)
    yield bus.bte.eq(bte)
    yield bus.adr.eq(addrs[0])
    yield bus.dat_w.eq(values[0])
    yield bus.cti.eq(ctis[0])
    while not (yield bus.ack):
        yield

    for adr, value, cti in zip(addrs[1:], values[1:], ctis[1:]):
        yield bus.adr.eq(adr)
        yield bus.dat_w.eq(value)
        yield bus.cti.eq(cti)
        yield
        while not (yield bus.ack):
            yield

    yield bus.cyc.eq(0)
    yield bus.stb.eq(0)
    yield bus.we.eq(0)
    yield bus.cti.eq(wishbone.CTI_BURST_NONE)
    yield bus.bte.eq(0)
    yield


def wishbone_read_burst(bus, addrs, beat_cti=wishbone.CTI_BURST_INCREMENTING, bte=0, sel=None):
    assert len(addrs) >= 1
    ctis = burst_ctis(len(addrs), beat_cti)
    if sel is None:
        sel = (1 << len(bus.sel)) - 1

    values = []

    yield bus.we.eq(0)
    yield bus.sel.eq(sel)
    yield bus.cyc.eq(1)
    yield bus.stb.eq(1)
    yield bus.bte.eq(bte)
    yield bus.adr.eq(addrs[0])
    yield bus.cti.eq(ctis[0])
    while not (yield bus.ack):
        yield
    values.append((yield bus.dat_r))

    for adr, cti in zip(addrs[1:], ctis[1:]):
        yield bus.adr.eq(adr)
        yield bus.cti.eq(cti)
        yield
        while not (yield bus.ack):
            yield
        values.append((yield bus.dat_r))

    yield bus.cyc.eq(0)
    yield bus.stb.eq(0)
    yield bus.cti.eq(wishbone.CTI_BURST_NONE)
    yield bus.bte.eq(0)
    yield
    return values

# TestWishbone -------------------------------------------------------------------------------------

class TestWishbone(unittest.TestCase):
    def test_interface_like_preserves_bursting(self):
        original = wishbone.Interface(data_width=32, address_width=32, addressing="word", bursting=True)
        clone    = wishbone.Interface.like(original)
        self.assertTrue(clone.bursting)

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

    def test_sram_burst_continuous(self):
        values = [0x01234567, 0x89abcdef, 0xdeadbeef, 0xc0ffee00]

        def generator(dut):
            addrs = list(range(len(values)))
            yield from wishbone_write_burst(dut.wb, addrs, values)
            self.assertEqual((yield from wishbone_read_burst(dut.wb, addrs)), values)

        class DUT(LiteXModule):
            def __init__(self):
                self.wb = wishbone.Interface(data_width=32, address_width=32, addressing="word", bursting=True)
                wishbone_mem = wishbone.SRAM(32, bus=self.wb)
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

    def test_sram_burst_wrap_continuous(self):
        burst_cases = [
            (0b01, 1,  4),
            (0b10, 5,  8),
            (0b11, 13, 16),
        ]

        def generator(dut):
            for case_index, (bte, start, length) in enumerate(burst_cases):
                addrs  = [start] + [0] * (length - 2) + [((start + length - 1) % length)]
                values = [(0x100 * (case_index + 1)) + i for i in range(length)]
                yield from wishbone_write_burst(dut.wb, addrs, values, bte=bte)

                wrapped_addrs = list(range(start, length)) + list(range(start))
                for adr, expected in zip(wrapped_addrs, values):
                    self.assertEqual((yield from dut.wb.read(adr)), expected)
                yield

        class DUT(LiteXModule):
            def __init__(self):
                self.wb = wishbone.Interface(data_width=32, address_width=32, addressing="word", bursting=True)
                wishbone_mem = wishbone.SRAM(256, bus=self.wb)
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

    def test_upconverter_burst_continuous(self):
        values = [0x11111111, 0x22222222, 0x33333333, 0x44444444]

        def generator(dut):
            addrs = list(range(len(values)))
            yield from wishbone_write_burst(dut.wb32, addrs, values)
            self.assertEqual((yield from wishbone_read_burst(dut.wb32, addrs)), values)

        class DUT(LiteXModule):
            def __init__(self):
                self.wb32 = wishbone.Interface(data_width=32, address_width=32, addressing="word", bursting=True)
                self.wb64 = wishbone.Interface(data_width=64, address_width=32, addressing="word", bursting=True)
                self.submodules += wishbone.UpConverter(self.wb32, self.wb64)
                wishbone_mem = wishbone.SRAM(128, bus=self.wb64)
                self.submodules += wishbone_mem

        dut = DUT()
        run_simulation(dut, generator(dut))

    def test_downconverter_burst_continuous(self):
        values = [
            0x2222222211111111,
            0x4444444433333333,
            0x6666666655555555,
        ]

        def generator(dut):
            addrs = list(range(len(values)))
            yield from wishbone_write_burst(dut.wb64, addrs, values)
            self.assertEqual((yield from wishbone_read_burst(dut.wb64, addrs)), values)

        class DUT(LiteXModule):
            def __init__(self):
                self.wb64 = wishbone.Interface(data_width=64, address_width=32, addressing="word", bursting=True)
                self.wb32 = wishbone.Interface(data_width=32, address_width=32, addressing="word", bursting=True)
                self.submodules += wishbone.DownConverter(self.wb64, self.wb32)
                wishbone_mem = wishbone.SRAM(128, bus=self.wb32)
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
