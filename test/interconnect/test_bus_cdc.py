#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.gen import *

from litex.soc.interconnect import axi, wishbone


# Helpers ------------------------------------------------------------------------------------------

def axil_write(bus, addr, data, strb=0xf):
    yield bus.aw.valid.eq(1)
    yield bus.aw.addr.eq(addr)
    yield
    while not (yield bus.aw.ready):
        yield
    yield bus.aw.valid.eq(0)

    yield bus.w.valid.eq(1)
    yield bus.w.data.eq(data)
    yield bus.w.strb.eq(strb)
    yield
    while not (yield bus.w.ready):
        yield
    yield bus.w.valid.eq(0)

    yield bus.b.ready.eq(1)
    while not (yield bus.b.valid):
        yield
    resp = (yield bus.b.resp)
    yield bus.b.ready.eq(0)
    yield
    return resp


def axil_read(bus, addr):
    yield bus.ar.valid.eq(1)
    yield bus.ar.addr.eq(addr)
    yield
    while not (yield bus.ar.ready):
        yield
    yield bus.ar.valid.eq(0)

    yield bus.r.ready.eq(1)
    while not (yield bus.r.valid):
        yield
    data = (yield bus.r.data)
    resp = (yield bus.r.resp)
    yield bus.r.ready.eq(0)
    yield
    return data, resp


def axi_write_single(bus, addr, data, strb=0xf):
    yield bus.aw.valid.eq(1)
    yield bus.aw.addr.eq(addr)
    yield bus.aw.len.eq(0)
    yield bus.aw.size.eq(2)
    yield bus.aw.burst.eq(axi.BURST_INCR)
    yield
    while not (yield bus.aw.ready):
        yield
    yield bus.aw.valid.eq(0)

    yield bus.w.valid.eq(1)
    yield bus.w.data.eq(data)
    yield bus.w.strb.eq(strb)
    yield bus.w.last.eq(1)
    yield
    while not (yield bus.w.ready):
        yield
    yield bus.w.valid.eq(0)
    yield bus.w.last.eq(0)

    yield bus.b.ready.eq(1)
    while not (yield bus.b.valid):
        yield
    resp = (yield bus.b.resp)
    yield bus.b.ready.eq(0)
    yield
    return resp


def axi_read_single(bus, addr):
    yield bus.ar.valid.eq(1)
    yield bus.ar.addr.eq(addr)
    yield bus.ar.len.eq(0)
    yield bus.ar.size.eq(2)
    yield bus.ar.burst.eq(axi.BURST_INCR)
    yield
    while not (yield bus.ar.ready):
        yield
    yield bus.ar.valid.eq(0)

    yield bus.r.ready.eq(1)
    while not (yield bus.r.valid):
        yield
    data = (yield bus.r.data)
    resp = (yield bus.r.resp)
    last = (yield bus.r.last)
    yield bus.r.ready.eq(0)
    yield
    return data, resp, last


# Tests --------------------------------------------------------------------------------------------

class TestBusClockDomainCrossing(unittest.TestCase):
    clocks = {
        "sys"    : 10,
        "periph" : 7,
    }

    def test_wishbone_cdc_sram_read_write(self):
        class DUT(LiteXModule):
            def __init__(self):
                self.clock_domains.cd_periph = ClockDomain("periph")
                self.master = wishbone.Interface(data_width=32, address_width=32, addressing="word")
                self.slave  = wishbone.Interface(data_width=32, address_width=32, addressing="word")
                self.cdc    = wishbone.ClockDomainCrossing(
                    master  = self.master,
                    slave   = self.slave,
                    cd_from = "sys",
                    cd_to   = "periph",
                )
                self.sram   = ClockDomainsRenamer("periph")(wishbone.SRAM(256,
                    bus  = self.slave,
                    init = [0x1000 + i for i in range(64)]))
                self.errors = 0

        def generator(dut):
            for addr in range(8):
                data = (yield from dut.master.read(addr))
                if data != 0x1000 + addr:
                    dut.errors += 1

            for addr in range(8):
                yield from dut.master.write(addr, 0x2000 + addr)

            for addr in range(8):
                data = (yield from dut.master.read(addr))
                if data != 0x2000 + addr:
                    dut.errors += 1

        dut = DUT()
        run_simulation(dut, {"sys": [generator(dut)]}, self.clocks)
        self.assertEqual(dut.errors, 0)

    def test_axi_lite_cdc_sram_read_write(self):
        class DUT(LiteXModule):
            def __init__(self):
                self.clock_domains.cd_periph = ClockDomain("periph")
                self.master = axi.AXILiteInterface(data_width=32, address_width=32)
                self.slave  = axi.AXILiteInterface(data_width=32, address_width=32)
                self.cdc    = axi.AXILiteClockDomainCrossing(
                    master  = self.master,
                    slave   = self.slave,
                    cd_from = "sys",
                    cd_to   = "periph",
                )
                self.sram   = ClockDomainsRenamer("periph")(axi.AXILiteSRAM(256,
                    bus  = self.slave,
                    init = [0x3000 + i for i in range(64)]))
                self.errors = 0

        def generator(dut):
            for addr in range(8):
                data, resp = (yield from axil_read(dut.master, 4*addr))
                if resp != axi.RESP_OKAY or data != 0x3000 + addr:
                    dut.errors += 1

            for addr in range(8):
                resp = (yield from axil_write(dut.master, 4*addr, 0x4000 + addr))
                if resp != axi.RESP_OKAY:
                    dut.errors += 1

            for addr in range(8):
                data, resp = (yield from axil_read(dut.master, 4*addr))
                if resp != axi.RESP_OKAY or data != 0x4000 + addr:
                    dut.errors += 1

        dut = DUT()
        run_simulation(dut, {"sys": [generator(dut)]}, self.clocks)
        self.assertEqual(dut.errors, 0)

    def test_axi_cdc_sram_read_write(self):
        class DUT(LiteXModule):
            def __init__(self):
                self.clock_domains.cd_periph = ClockDomain("periph")
                self.master = axi.AXIInterface(data_width=32, address_width=32)
                self.slave  = axi.AXIInterface(data_width=32, address_width=32)
                self.cdc    = axi.AXIClockDomainCrossing(
                    master  = self.master,
                    slave   = self.slave,
                    cd_from = "sys",
                    cd_to   = "periph",
                )
                self.sram   = ClockDomainsRenamer("periph")(axi.AXISRAM(256,
                    bus  = self.slave,
                    init = [0x5000 + i for i in range(64)]))
                self.errors = 0

        def generator(dut):
            for addr in range(8):
                data, resp, last = (yield from axi_read_single(dut.master, 4*addr))
                if resp != axi.RESP_OKAY or data != 0x5000 + addr or last != 1:
                    dut.errors += 1

            for addr in range(8):
                resp = (yield from axi_write_single(dut.master, 4*addr, 0x6000 + addr))
                if resp != axi.RESP_OKAY:
                    dut.errors += 1

            for addr in range(8):
                data, resp, last = (yield from axi_read_single(dut.master, 4*addr))
                if resp != axi.RESP_OKAY or data != 0x6000 + addr or last != 1:
                    dut.errors += 1

        dut = DUT()
        run_simulation(dut, {"sys": [generator(dut)]}, self.clocks)
        self.assertEqual(dut.errors, 0)


if __name__ == "__main__":
    unittest.main()
