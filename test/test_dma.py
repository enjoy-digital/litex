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

def make_bus():
    return wishbone.Interface(data_width=32, address_width=32, addressing="word")


@passive
def wb_read_slave(bus, mem):
    """Passive Wishbone read slave answering with mem[adr] (word-addressed).

    Handles back-to-back beats (stb held high across multiple addresses) by pulsing ack for
    exactly one cycle per beat.
    """
    while True:
        yield bus.ack.eq(0)
        yield
        if (yield bus.cyc) and (yield bus.stb) and not (yield bus.we):
            adr = (yield bus.adr) & (len(mem) - 1)
            yield bus.dat_r.eq(mem[adr])
            yield bus.ack.eq(1)
            yield


@passive
def wb_write_slave(bus, captures):
    """Passive Wishbone write slave appending (adr, dat) on every accepted write beat."""
    while True:
        yield bus.ack.eq(0)
        yield
        if (yield bus.cyc) and (yield bus.stb) and (yield bus.we):
            captures.append(((yield bus.adr), (yield bus.dat_w)))
            yield bus.ack.eq(1)
            yield


# DMA Reader ---------------------------------------------------------------------------------------

class _ReaderDUT(LiteXModule):
    def __init__(self):
        self.bus = make_bus()
        # endianness="big" leaves bus.dat_r unmodified so the stream data matches mem[] directly.
        self.dma = WishboneDMAReader(bus=self.bus, endianness="big")
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


# DMA Writer ---------------------------------------------------------------------------------------

class _WriterDUT(LiteXModule):
    def __init__(self):
        self.bus = make_bus()
        self.dma = WishboneDMAWriter(bus=self.bus, endianness="big")
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


if __name__ == "__main__":
    unittest.main()
