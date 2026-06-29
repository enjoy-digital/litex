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

    def test_wishbone_cdc_cancelled_cycle_discards_late_response(self):
        class DelayedWishboneSlave(LiteXModule):
            def __init__(self, bus, delay=8):
                ack     = Signal()
                active  = Signal()
                pending = Signal()
                counter = Signal(max=delay)

                self.comb += [
                    bus.ack.eq(ack),
                    bus.dat_r.eq(0x1000 + bus.adr),
                ]
                self.sync += [
                    ack.eq(0),
                    If(~(bus.cyc & bus.stb),
                        active.eq(0),
                        pending.eq(0),
                        counter.eq(0),
                    ).Elif(~active & ~pending,
                        pending.eq(1),
                        counter.eq(0),
                    ).Elif(pending,
                        If(counter == (delay - 1),
                            ack.eq(1),
                            active.eq(1),
                            pending.eq(0),
                        ).Else(
                            counter.eq(counter + 1)
                        )
                    )
                ]

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
                self.delayed = ClockDomainsRenamer("periph")(DelayedWishboneSlave(self.slave))
                self.errors  = 0

        def generator(dut):
            yield dut.master.adr.eq(0)
            yield dut.master.we.eq(0)
            yield dut.master.cyc.eq(1)
            yield dut.master.stb.eq(1)
            for _ in range(2):
                yield

            yield dut.master.cyc.eq(0)
            yield dut.master.stb.eq(0)
            for _ in range(30):
                if (yield dut.master.ack) or (yield dut.master.err):
                    dut.errors += 1
                yield

            data = (yield from dut.master.read(1))
            if data != 0x1001:
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

    def test_axi_lite_cdc_response_backpressure(self):
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
                    init = [0x7000 + i for i in range(64)]))
                self.errors = 0

        def generator(dut):
            yield dut.master.aw.valid.eq(1)
            yield dut.master.aw.addr.eq(0)
            yield
            while not (yield dut.master.aw.ready):
                yield
            yield dut.master.aw.valid.eq(0)

            yield dut.master.w.valid.eq(1)
            yield dut.master.w.data.eq(0x8000)
            yield dut.master.w.strb.eq(0xf)
            yield
            while not (yield dut.master.w.ready):
                yield
            yield dut.master.w.valid.eq(0)

            for _ in range(32):
                if (yield dut.master.b.valid):
                    break
                yield
            for _ in range(8):
                if not (yield dut.master.b.valid):
                    dut.errors += 1
                if (yield dut.master.b.resp) != axi.RESP_OKAY:
                    dut.errors += 1
                yield
            yield dut.master.b.ready.eq(1)
            yield
            yield dut.master.b.ready.eq(0)

            yield dut.master.ar.valid.eq(1)
            yield dut.master.ar.addr.eq(0)
            yield
            while not (yield dut.master.ar.ready):
                yield
            yield dut.master.ar.valid.eq(0)

            for _ in range(32):
                if (yield dut.master.r.valid):
                    break
                yield
            for _ in range(8):
                if not (yield dut.master.r.valid):
                    dut.errors += 1
                if (yield dut.master.r.resp) != axi.RESP_OKAY:
                    dut.errors += 1
                if (yield dut.master.r.data) != 0x8000:
                    dut.errors += 1
                yield
            yield dut.master.r.ready.eq(1)
            yield
            yield dut.master.r.ready.eq(0)

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

    def test_axi_cdc_response_backpressure(self):
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
                    init = [0x9000 + i for i in range(64)]))
                self.errors = 0

        def generator(dut):
            yield dut.master.aw.valid.eq(1)
            yield dut.master.aw.addr.eq(0)
            yield dut.master.aw.len.eq(0)
            yield dut.master.aw.size.eq(2)
            yield dut.master.aw.burst.eq(axi.BURST_INCR)
            yield
            while not (yield dut.master.aw.ready):
                yield
            yield dut.master.aw.valid.eq(0)

            yield dut.master.w.valid.eq(1)
            yield dut.master.w.data.eq(0xa000)
            yield dut.master.w.strb.eq(0xf)
            yield dut.master.w.last.eq(1)
            yield
            while not (yield dut.master.w.ready):
                yield
            yield dut.master.w.valid.eq(0)
            yield dut.master.w.last.eq(0)

            for _ in range(32):
                if (yield dut.master.b.valid):
                    break
                yield
            for _ in range(8):
                if not (yield dut.master.b.valid):
                    dut.errors += 1
                if (yield dut.master.b.resp) != axi.RESP_OKAY:
                    dut.errors += 1
                yield
            yield dut.master.b.ready.eq(1)
            yield
            yield dut.master.b.ready.eq(0)

            yield dut.master.ar.valid.eq(1)
            yield dut.master.ar.addr.eq(0)
            yield dut.master.ar.len.eq(0)
            yield dut.master.ar.size.eq(2)
            yield dut.master.ar.burst.eq(axi.BURST_INCR)
            yield
            while not (yield dut.master.ar.ready):
                yield
            yield dut.master.ar.valid.eq(0)

            for _ in range(32):
                if (yield dut.master.r.valid):
                    break
                yield
            for _ in range(8):
                if not (yield dut.master.r.valid):
                    dut.errors += 1
                if (yield dut.master.r.resp) != axi.RESP_OKAY:
                    dut.errors += 1
                if (yield dut.master.r.data) != 0xa000:
                    dut.errors += 1
                if (yield dut.master.r.last) != 1:
                    dut.errors += 1
                yield
            yield dut.master.r.ready.eq(1)
            yield
            yield dut.master.r.ready.eq(0)

        dut = DUT()
        run_simulation(dut, {"sys": [generator(dut)]}, self.clocks)
        self.assertEqual(dut.errors, 0)


if __name__ == "__main__":
    unittest.main()
