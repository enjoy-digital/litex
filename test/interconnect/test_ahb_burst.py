#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import random
import unittest

from migen import *
from migen.sim import passive

from litex.gen import *
from litex.soc.interconnect import ahb, wishbone


class DUT(LiteXModule):
    def __init__(self, width=64):
        self.ahb = ahb.AHBInterface(data_width=width)
        self.wb = wb = wishbone.Interface(data_width=width, address_width=32)
        self.bridge = ahb.AHB2Wishbone(self.ahb, wb, with_bursting=True)
        self.ready = Signal(reset=1)
        self.error = Signal()
        self.cycles = 0
        self.beats = []
        self.errors = []
        self.words = Array(Signal(width) for _ in range(128))
        self.comb += [
            wb.ack.eq(wb.cyc & wb.stb & self.ready & ~self.error),
            wb.err.eq(wb.cyc & wb.stb & self.error),
            wb.dat_r.eq(self.words[wb.adr[:7]]),
        ]
        for lane in range(width//8):
            self.sync += If(wb.ack & wb.we & wb.sel[lane],
                self.words[wb.adr[:7]][8*lane:8*(lane + 1)].eq(wb.dat_w[8*lane:8*(lane + 1)]),
            )

    @passive
    def monitor(self, stalls=False):
        rng = random.Random(42)
        previous = None
        while True:
            if (yield self.ahb.resp):
                self.errors.append((yield self.ahb.readyout))
            wb = self.wb
            active = (yield wb.cyc) and (yield wb.stb)
            beat = tuple((yield from self.read_fields())) if active else None
            if previous is not None:
                assert beat == previous, "Wishbone request changed while stalled"
            if active and (yield wb.ack):
                self.beats.append((self.cycles, beat))
            previous = beat if active and not ((yield wb.ack) or (yield wb.err)) else None
            self.cycles += 1
            if stalls:
                yield self.ready.eq(rng.randrange(4) != 0)
            yield

    def read_fields(self):
        values = []
        for name in ("adr", "we", "sel", "dat_w", "cti", "bte"):
            values.append((yield getattr(self.wb, name)))
        return values


def transfer(dut, phases):
    # Address phases are (address, write-data/None, size, burst, transfer-type). Advance both
    # address and write-data pipelines only on HREADY, including zero-wait-state completions.
    bus = dut.ahb
    pending = None
    index = 0
    result = []
    start = dut.cycles

    def drive(phase):
        address, data, size, burst, trans = phase
        yield bus.addr.eq(address)
        yield bus.write.eq(data is not None)
        yield bus.size.eq(size)
        yield bus.burst.eq(burst)
        yield bus.trans.eq(trans)

    idle = (0, None, 0, 0, 0)
    yield bus.sel.eq(1)
    yield from drive(phases[0])
    while index < len(phases) or pending is not None:
        yield
        assert dut.cycles - start < 5000, "AHB timeout"
        if (yield bus.readyout):
            if pending is not None:
                result.append(((yield bus.rdata), (yield bus.resp)))
            phase = phases[index] if index < len(phases) else idle
            pending = phase if phase[4] & 2 else None
            if pending:
                yield bus.wdata.eq(pending[1] or 0)
            index += 1
            yield from drive(phases[index] if index < len(phases) else idle)
    yield bus.sel.eq(0)
    for _ in range(3):
        yield
    return result


def burst(address, values, size, kind):
    span = (1 << ((kind >> 1) + 1)) * (1 << size)
    phases = []
    for i, value in enumerate(values):
        addr = address + i*(1 << size)
        if kind in (2, 4, 6):
            addr = (address & ~(span - 1)) | (addr & (span - 1))
        phases.append((addr, value, size, kind, 2 if i == 0 else 3))
    return phases


class TestAHB2WishboneBurst(unittest.TestCase):
    def test_bursts(self):
        for width in (32, 64):
            for kind in range(1, 8):
                with self.subTest(width=width, kind=kind):
                    dut = DUT(width)
                    count = 19 if kind == 1 else 1 << ((kind >> 1) + 1)
                    size = log2_int(width//8)
                    values = [0x12345600 + i for i in range(count)]
                    phases = burst(2*(1 << size), values, size, kind)

                    def gen():
                        yield from transfer(dut, phases)
                        reads = [(a, None, s, b, t) for a, _, s, b, t in phases]
                        result = yield from transfer(dut, reads)
                        self.assertEqual(result, [(v, 0) for v in values])
                        writes = [b for _, b in dut.beats[:count]]
                        self.assertEqual([b[4] for b in writes],
                            [2]*count if kind == 1 else [2]*(count - 1) + [7])
                        self.assertTrue(all(b[5] == (0 if kind & 1 else kind >> 1) for b in writes))
                    run_simulation(dut, [gen(), dut.monitor(stalls=True)])

    def test_byte_masks(self):
        for width in (32, 64):
            dut = DUT(width)
            def gen():
                for size in range(log2_int(width//8) + 1):
                    for lane in range(0, width//8, 1 << size):
                        value = ((1 << (8*(1 << size))) - 1) << (8*lane)
                        yield from transfer(dut, [(lane, value, size, 0, 2)])
                        self.assertEqual(dut.beats[-1][1][2], ((1 << (1 << size)) - 1) << lane)
                result = yield from transfer(dut, [(0, None, log2_int(width//8), 0, 2)])
                self.assertEqual(result, [((1 << width) - 1, 0)])
            run_simulation(dut, [gen(), dut.monitor(stalls=True)])

    def test_consecutive_beats(self):
        dut = DUT()
        def gen():
            yield from transfer(dut, burst(0, [1, 2, 3, 4], 3, 2))
            cycles = [cycle for cycle, _ in dut.beats]
            self.assertEqual(cycles, list(range(cycles[0], cycles[0] + 4)))
        run_simulation(dut, [gen(), dut.monitor()])

    def test_busy_and_early_end(self):
        dut = DUT()
        phases = [(0, 1, 3, 1, 2), (8, None, 3, 1, 1), (8, 2, 3, 1, 3),
                  (16, 3, 3, 0, 2), (24, 4, 2, 2, 2)]
        def gen():
            yield from transfer(dut, phases)
            result = yield from transfer(dut, [(i*8, None, 3, 0, 2) for i in range(4)])
            self.assertEqual(result, [(i, 0) for i in range(1, 5)])
            self.assertGreater(dut.beats[2][0] - dut.beats[1][0], 1)
            self.assertEqual(dut.beats[3][1][4], 0) # Subword burst uses classic Wishbone.
        run_simulation(dut, [gen(), dut.monitor()])

    def test_errors(self):
        dut = DUT()
        def gen():
            result = yield from transfer(dut, [(0, None, 4, 0, 2), (0, None, 3, 0, 2)])
            self.assertEqual(result, [(0, 1), (0, 0)])
            self.assertEqual(dut.errors, [0, 1])
            self.assertEqual(len(dut.beats), 1)
            yield dut.error.eq(1)
            result = yield from transfer(dut, [(0, None, 3, 0, 2)])
            self.assertEqual(result[0][1], 1)
            self.assertEqual(dut.errors, [0, 1, 0, 1])
            yield dut.error.eq(0)
            result = yield from transfer(dut, [(0, None, 3, 0, 2)])
            self.assertEqual(result, [(0, 0)])
        run_simulation(dut, [gen(), dut.monitor()])
