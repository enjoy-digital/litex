#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.gen import *

from litex.soc.interconnect import wishbone
from litex.soc.cores.dma import WishboneDMAReader, WishboneDMAWriter


# Helpers ------------------------------------------------------------------------------------------

def make_bus(bursting=False):
    return wishbone.Interface(data_width=32, address_width=32, addressing="word", bursting=bursting)


def burst_ctis(length):
    assert length >= 1
    return [wishbone.CTI_BURST_INCREMENTING]*(length - 1) + [wishbone.CTI_BURST_END]


def reverse32(v):
    return int.from_bytes(v.to_bytes(4, byteorder="little"), byteorder="big")


@passive
def wb_read_slave(bus, mem, bus_cycles=None):
    """Passive Wishbone read slave answering with mem[adr] (word-addressed).

    Handles back-to-back beats (stb held high across multiple addresses) by pulsing ack for
    exactly one cycle per beat.
    """
    while True:
        yield bus.ack.eq(0)
        yield
        if (yield bus.cyc) and (yield bus.stb) and not (yield bus.we):
            adr = (yield bus.adr) & (len(mem) - 1)
            if bus_cycles is not None:
                bus_cycles.append((adr, (yield bus.cti), (yield bus.bte)))
            yield bus.dat_r.eq(mem[adr])
            yield bus.ack.eq(1)
            yield


@passive
def wb_write_slave(bus, captures, bus_cycles=None):
    """Passive Wishbone write slave appending (adr, dat) on every accepted write beat."""
    while True:
        yield bus.ack.eq(0)
        yield
        if (yield bus.cyc) and (yield bus.stb) and (yield bus.we):
            adr = (yield bus.adr)
            captures.append((adr, (yield bus.dat_w)))
            if bus_cycles is not None:
                bus_cycles.append((adr, (yield bus.cti), (yield bus.bte)))
            yield bus.ack.eq(1)
            yield


# DMA Reader ---------------------------------------------------------------------------------------

class _ReaderDUT(LiteXModule):
    def __init__(self, bus_bursting=False, dma_bursting=None, endianness="big", with_byteswap=None):
        self.bus = make_bus(bursting=bus_bursting)
        self.dma = WishboneDMAReader(
            bus           = self.bus,
            endianness    = endianness,
            bursting      = dma_bursting,
            with_byteswap = with_byteswap,
        )
        self.dma.add_ctrl()


class TestDMAReader(unittest.TestCase):
    def test_reads_sequence(self):
        mem    = [0xdeadbeef, 0xcafebabe, 0x12345678, 0xfeedc0de,
                  0xa5a5a5a5, 0x5a5a5a5a, 0x0f0f0f0f, 0xf0f0f0f0]
        dut     = _ReaderDUT()
        outputs = []

        def driver(dut):
            yield dut.dma.base.eq(0)
            yield dut.dma.length.eq(len(mem)*4)  # bytes
            yield dut.dma.loop.eq(0)
            yield dut.dma.source.ready.eq(1)
            yield dut.dma.enable.eq(1)

            timeout = 0
            while len(outputs) < len(mem):
                if (yield dut.dma.source.valid) and (yield dut.dma.source.ready):
                    outputs.append((yield dut.dma.source.data))
                yield
                timeout += 1
                self.assertLess(timeout, 10_000, "DMA reader stalled")

            # Wait for FSM to reach DONE.
            timeout = 0
            while not (yield dut.dma.done):
                yield
                timeout += 1
                self.assertLess(timeout, 200, "DMA reader never signalled done")

        run_simulation(dut, [driver(dut), wb_read_slave(dut.bus, mem)])
        self.assertEqual(outputs, mem)

    def test_reads_from_nonzero_base(self):
        mem = [i*0x11111111 & 0xffffffff for i in range(16)]
        dut = _ReaderDUT()
        outputs = []

        def driver(dut):
            # Start at word 4, read 4 words.
            yield dut.dma.base.eq(4*4)
            yield dut.dma.length.eq(4*4)
            yield dut.dma.source.ready.eq(1)
            yield dut.dma.enable.eq(1)
            timeout = 0
            while len(outputs) < 4:
                if (yield dut.dma.source.valid) and (yield dut.dma.source.ready):
                    outputs.append((yield dut.dma.source.data))
                yield
                timeout += 1
                self.assertLess(timeout, 10_000)

        run_simulation(dut, [driver(dut), wb_read_slave(dut.bus, mem)])
        self.assertEqual(outputs, mem[4:8])

    def test_reads_burst_when_bus_supports_bursting(self):
        mem        = [0x10000000 + i for i in range(4)]
        dut        = _ReaderDUT(bus_bursting=True)
        outputs    = []
        bus_cycles = []

        def driver(dut):
            yield dut.dma.base.eq(0)
            yield dut.dma.length.eq(len(mem)*4)
            yield dut.dma.source.ready.eq(1)
            yield dut.dma.enable.eq(1)

            timeout = 0
            while len(outputs) < len(mem):
                if (yield dut.dma.source.valid) and (yield dut.dma.source.ready):
                    outputs.append((yield dut.dma.source.data))
                yield
                timeout += 1
                self.assertLess(timeout, 10_000)

        run_simulation(dut, [driver(dut), wb_read_slave(dut.bus, mem, bus_cycles)])
        self.assertEqual(outputs, mem)
        self.assertEqual([cti for _, cti, _ in bus_cycles], burst_ctis(len(mem)))
        self.assertEqual([bte for _, _, bte in bus_cycles], [0]*len(mem))

    def test_reads_classic_when_bursting_forced_off(self):
        mem        = [0x20000000 + i for i in range(4)]
        dut        = _ReaderDUT(bus_bursting=True, dma_bursting=False)
        outputs    = []
        bus_cycles = []

        def driver(dut):
            yield dut.dma.base.eq(0)
            yield dut.dma.length.eq(len(mem)*4)
            yield dut.dma.source.ready.eq(1)
            yield dut.dma.enable.eq(1)

            timeout = 0
            while len(outputs) < len(mem):
                if (yield dut.dma.source.valid) and (yield dut.dma.source.ready):
                    outputs.append((yield dut.dma.source.data))
                yield
                timeout += 1
                self.assertLess(timeout, 10_000)

        run_simulation(dut, [driver(dut), wb_read_slave(dut.bus, mem, bus_cycles)])
        self.assertEqual(outputs, mem)
        self.assertEqual([cti for _, cti, _ in bus_cycles], [wishbone.CTI_BURST_NONE]*len(mem))

    def test_little_endian_reads_byteswapped_word(self):
        mem     = [0xcafef00d]
        dut     = _ReaderDUT(endianness="little")
        outputs = []

        def driver(dut):
            yield dut.dma.base.eq(0)
            yield dut.dma.length.eq(4)
            yield dut.dma.source.ready.eq(1)
            yield dut.dma.enable.eq(1)

            timeout = 0
            while len(outputs) < 1:
                if (yield dut.dma.source.valid) and (yield dut.dma.source.ready):
                    outputs.append((yield dut.dma.source.data))
                yield
                timeout += 1
                self.assertLess(timeout, 10_000)

        run_simulation(dut, [driver(dut), wb_read_slave(dut.bus, mem)])
        self.assertEqual(outputs, [reverse32(mem[0])])

    def test_explicit_no_byteswap_reads_raw_word(self):
        mem     = [0xcafef00d]
        dut     = _ReaderDUT(endianness="little", with_byteswap=False)
        outputs = []

        def driver(dut):
            yield dut.dma.base.eq(0)
            yield dut.dma.length.eq(4)
            yield dut.dma.source.ready.eq(1)
            yield dut.dma.enable.eq(1)

            timeout = 0
            while len(outputs) < 1:
                if (yield dut.dma.source.valid) and (yield dut.dma.source.ready):
                    outputs.append((yield dut.dma.source.data))
                yield
                timeout += 1
                self.assertLess(timeout, 10_000)

        run_simulation(dut, [driver(dut), wb_read_slave(dut.bus, mem)])
        self.assertEqual(outputs, mem)


# DMA Writer ---------------------------------------------------------------------------------------

class _WriterDUT(LiteXModule):
    def __init__(self, bus_bursting=False, dma_bursting=None, endianness="big", with_byteswap=None):
        self.bus = make_bus(bursting=bus_bursting)
        self.dma = WishboneDMAWriter(
            bus           = self.bus,
            endianness    = endianness,
            bursting      = dma_bursting,
            with_byteswap = with_byteswap,
        )
        self.dma.add_ctrl()


class TestDMAWriter(unittest.TestCase):
    def test_writes_sequence(self):
        payload  = [0x11111111, 0x22222222, 0x33333333, 0x44444444, 0xdeadbeef, 0xc0ffee00]
        dut      = _WriterDUT()
        captures = []

        def driver(dut):
            yield dut.dma.base.eq(0)
            yield dut.dma.length.eq(len(payload)*4)
            yield dut.dma.loop.eq(0)
            yield dut.dma.enable.eq(1)
            # Let the FSM leave IDLE (where ready_on_idle=1 would swallow our first beat).
            for _ in range(4):
                yield

            # Feed the payload into the DMA sink.
            for word in payload:
                yield dut.dma.sink.data.eq(word)
                yield dut.dma.sink.valid.eq(1)
                yield
                while not (yield dut.dma.sink.ready):
                    yield
                yield dut.dma.sink.valid.eq(0)
                yield

            timeout = 0
            while not (yield dut.dma.done):
                yield
                timeout += 1
                self.assertLess(timeout, 200, "DMA writer never signalled done")

        run_simulation(dut, [driver(dut), wb_write_slave(dut.bus, captures)])
        self.assertEqual([v for _, v in captures], payload)
        self.assertEqual([a for a, _ in captures], list(range(len(payload))))

    def test_writes_burst_when_bus_supports_bursting(self):
        payload    = [0x10000000 + i for i in range(4)]
        dut        = _WriterDUT(bus_bursting=True)
        captures   = []
        bus_cycles = []

        def driver(dut):
            yield dut.dma.base.eq(0)
            yield dut.dma.length.eq(len(payload)*4)
            yield dut.dma.enable.eq(1)
            for _ in range(4):
                yield

            yield dut.dma.sink.valid.eq(1)
            for word in payload:
                yield dut.dma.sink.data.eq(word)
                yield
                while not (yield dut.dma.sink.ready):
                    yield
            yield dut.dma.sink.valid.eq(0)

            timeout = 0
            while not (yield dut.dma.done):
                yield
                timeout += 1
                self.assertLess(timeout, 200)

        run_simulation(dut, [driver(dut), wb_write_slave(dut.bus, captures, bus_cycles)])
        self.assertEqual([v for _, v in captures], payload)
        self.assertEqual([a for a, _ in captures], list(range(len(payload))))
        self.assertEqual([cti for _, cti, _ in bus_cycles], burst_ctis(len(payload)))
        self.assertEqual([bte for _, _, bte in bus_cycles], [0]*len(payload))

    def test_little_endian_writes_byteswapped_word(self):
        payload  = [0xcafef00d]
        dut      = _WriterDUT(endianness="little")
        captures = []

        def driver(dut):
            yield dut.dma.base.eq(0)
            yield dut.dma.length.eq(4)
            yield dut.dma.enable.eq(1)
            for _ in range(4):
                yield

            yield dut.dma.sink.data.eq(payload[0])
            yield dut.dma.sink.valid.eq(1)
            yield
            while not (yield dut.dma.sink.ready):
                yield
            yield dut.dma.sink.valid.eq(0)

            timeout = 0
            while not (yield dut.dma.done):
                yield
                timeout += 1
                self.assertLess(timeout, 200)

        run_simulation(dut, [driver(dut), wb_write_slave(dut.bus, captures)])
        self.assertEqual([v for _, v in captures], [reverse32(payload[0])])

    def test_explicit_no_byteswap_writes_raw_word(self):
        payload  = [0xcafef00d]
        dut      = _WriterDUT(endianness="little", with_byteswap=False)
        captures = []

        def driver(dut):
            yield dut.dma.base.eq(0)
            yield dut.dma.length.eq(4)
            yield dut.dma.enable.eq(1)
            for _ in range(4):
                yield

            yield dut.dma.sink.data.eq(payload[0])
            yield dut.dma.sink.valid.eq(1)
            yield
            while not (yield dut.dma.sink.ready):
                yield
            yield dut.dma.sink.valid.eq(0)

            timeout = 0
            while not (yield dut.dma.done):
                yield
                timeout += 1
                self.assertLess(timeout, 200)

        run_simulation(dut, [driver(dut), wb_write_slave(dut.bus, captures)])
        self.assertEqual([v for _, v in captures], payload)


if __name__ == "__main__":
    unittest.main()
