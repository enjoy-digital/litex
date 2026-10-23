#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import random
import unittest

from migen import *

from litex.gen import *

from litex.soc.interconnect import axi

from litex.soc.cores.hyperram import HyperRAMPHYInterface, HyperRAMCore, HyperRAMController
from litex.soc.cores.hyperram import hyperram_best_phase

# HyperRAM Model -------------------------------------------------------------------------------

class HyperRAMModel:
    """Cycle model of a x16 HyperRAM seen through a DDR PHY (one cycle = one CK period).

    - CA on DQ[7:0], 3 CK cycles, then fixed 2x latency.
    - Memory word (32-bit) per CK cycle: first edge = bits [31:16], second edge = bits [15:0].
    - Read data returned `delay` cycles later on the capture interface, with RWDS high on the first
      half-word; `odd` shifts read data by half a CK period (straddling capture cycles).
    - `stall_every`: drop RWDS strobes for one cycle every N read words (device wait states).
    """
    def __init__(self, phy_if, latency=7, delay=3, odd=False, drop_word=None, phase=None, good_phases=None):
        self.phy_if      = phy_if
        self.phase       = phase       # Capture phase signal (for calibration tests).
        self.good_phases = good_phases # Phases giving correct read data.
        self.latency   = latency
        self.delay     = delay
        self.odd       = odd
        self.drop_word = drop_word
        self.mem       = {}
        self.regs      = {0: 0x0e76, 1: 0x0009, 2: 0x8f2f, 3: 0xffc1}
        self.accesses  = 0

    @passive
    def generator(self):
        p        = self.phy_if
        slots    = {}  # Half-slot index -> (dq, rwds).
        t        = 0
        c        = 0
        ca       = []
        cmd      = None
        addr     = 0
        rd_words = 0
        while True:
            # Outputs (capture interface).
            hi = slots.pop(2*t,     (0, 0))
            lo = slots.pop(2*t + 1, (0, 0))
            yield p.dq_i_hi.eq(hi[0])
            yield p.rwds_i_hi.eq(hi[1])
            yield p.dq_i_lo.eq(lo[0])
            yield p.rwds_i_lo.eq(lo[1])

            cs_n  = (yield p.cs_n)
            ck_en = (yield p.ck_en)
            if cs_n:
                c, ca, cmd = 0, [], None
            elif ck_en:
                dq_hi = (yield p.dq_o_hi)
                dq_lo = (yield p.dq_o_lo)
                if c < 3:
                    ca += [dq_hi & 0xff, dq_lo & 0xff]
                if c == 2:
                    v = 0
                    for b in ca:
                        v = (v << 8) | b
                    cmd = {
                        "read" : (v >> 47) & 1,
                        "reg"  : (v >> 46) & 1,
                    }
                    addr = (((v >> 16) & (2**29 - 1)) << 3) | (v & 0x7)
                    rega = v & (2**40 - 1)
                    rd_words = 0
                    self.accesses += 1
                data_start = 2 + 2*self.latency
                if cmd is not None and cmd["reg"] and not cmd["read"] and c == 3:
                    reg = {0x0000_0000: 0, 0x0000_0001: 1, 0x0100_0000: 2, 0x0100_0001: 3}[rega]
                    self.regs[reg] = ((dq_hi & 0xff) << 8) | (dq_lo & 0xff)
                elif cmd is not None and c >= data_start:
                    if cmd["read"]:
                        if cmd["reg"]:
                            reg  = {0x0000_0000: 0, 0x0000_0001: 1, 0x0100_0000: 2, 0x0100_0001: 3}[rega]
                            v    = self.regs[reg]
                            word = ((v >> 8) << 16) | (v & 0xff)
                        else:
                            word = self.mem.get(addr, 0)
                        rd_words += 1
                        if self.phase is not None and (yield self.phase) not in self.good_phases:
                            word ^= 0x00010001
                        if self.drop_word is None or rd_words != self.drop_word:
                            h = 2*(t + self.delay) + int(self.odd)
                            slots[h + 0] = (word >> 16,     1)
                            slots[h + 1] = (word & 0xffff, 0)
                        addr += 1
                    elif not cmd["reg"]:
                        rwds_hi = (yield p.rwds_o_hi)
                        rwds_lo = (yield p.rwds_o_lo)
                        old  = self.mem.get(addr, 0)
                        new  = (dq_hi << 16) | dq_lo
                        mask = 0
                        for i, m in enumerate([rwds_lo & 1, rwds_lo >> 1, rwds_hi & 1, rwds_hi >> 1]):
                            if not m:
                                mask |= 0xff << (8*i)
                        self.mem[addr] = (old & ~mask) | (new & mask)
                        addr += 1
                c += 1
            t += 1
            yield

# AXI helpers --------------------------------------------------------------------------------------

def axi_write(bus, addr, data, strb=None, id=0):
    yield bus.aw.valid.eq(1)
    yield bus.aw.addr.eq(addr)
    yield bus.aw.len.eq(len(data) - 1)
    yield bus.aw.size.eq(2)
    yield bus.aw.burst.eq(axi.BURST_INCR)
    yield bus.aw.id.eq(id)
    yield
    while not (yield bus.aw.ready):
        yield
    yield bus.aw.valid.eq(0)
    for i, d in enumerate(data):
        yield bus.w.valid.eq(1)
        yield bus.w.data.eq(d)
        yield bus.w.strb.eq(0xf if strb is None else strb[i])
        yield bus.w.last.eq(i == len(data) - 1)
        yield
        while not (yield bus.w.ready):
            yield
    yield bus.w.valid.eq(0)
    yield bus.b.ready.eq(1)
    yield
    while not (yield bus.b.valid):
        yield
    bid = (yield bus.b.id)
    yield bus.b.ready.eq(0)
    return bid

def axi_read(bus, addr, n, id=0):
    yield bus.ar.valid.eq(1)
    yield bus.ar.addr.eq(addr)
    yield bus.ar.len.eq(n - 1)
    yield bus.ar.size.eq(2)
    yield bus.ar.burst.eq(axi.BURST_INCR)
    yield bus.ar.id.eq(id)
    yield
    while not (yield bus.ar.ready):
        yield
    yield bus.ar.valid.eq(0)
    yield bus.r.ready.eq(1)
    data, resps, last = [], [], 0
    while not last:
        yield
        if (yield bus.r.valid):
            data.append((yield bus.r.data))
            resps.append((yield bus.r.resp))
            last = (yield bus.r.last)
            assert (yield bus.r.id) == id
    yield bus.r.ready.eq(0)
    return data, resps

# Tests --------------------------------------------------------------------------------------------

class DUT(LiteXModule):
    def __init__(self, clk_freq=100e6, **kwargs):
        self.phy_if = HyperRAMPHYInterface(dq_width=16, cd_cap="sys")
        self.core   = HyperRAMCore(self.phy_if, clk_freq=clk_freq, with_reset=False, **kwargs)

class TestHyperRAMController(unittest.TestCase):
    def run_dut(self, dut, model, gen, timeout=200000):
        @passive
        def watchdog():
            for _ in range(timeout):
                yield
            raise TimeoutError
        run_simulation(dut, [gen(), model.generator(), watchdog()])

    def check_write_read(self, odd=False, delay=3, bursts=[(0x0, 1), (0x100, 4), (0x1000, 16), (0x2000, 64)]):
        dut   = DUT()
        model = HyperRAMModel(dut.phy_if, delay=delay, odd=odd)
        random.seed(0)
        errors = []
        def gen():
            for addr, n in bursts:
                data = [random.getrandbits(32) for _ in range(n)]
                yield from axi_write(dut.core.bus, addr, data)
                rdata, resps = yield from axi_read(dut.core.bus, addr, n)
                if rdata != data or any(resps):
                    errors.append((addr, n, [hex(d) for d in data[:4]], [hex(d) for d in rdata[:4]], resps[:4]))
        self.run_dut(dut, model, gen)
        self.assertEqual(errors, [])

    def test_write_read_even(self):
        self.check_write_read(odd=False)

    def test_write_read_odd(self):
        self.check_write_read(odd=True)

    def test_write_read_delays(self):
        for delay in [1, 2, 5]:
            self.check_write_read(delay=delay, bursts=[(0x40, 8)])

    def test_split_bursts(self):
        # max_words=16: a 64 beats AXI burst is split in 4 HyperRAM commands, merged back in a single
        # HyperRAM access with continuation.
        for with_continuation, accesses in [(False, 8), (True, 2)]:
            with self.subTest(with_continuation=with_continuation):
                dut   = DUT(max_words=16, with_continuation=with_continuation)
                model = HyperRAMModel(dut.phy_if)
                data  = list(range(1, 65))
                res   = {}
                def gen():
                    yield from axi_write(dut.core.bus, 0x400, data)
                    res["rd"], _ = yield from axi_read(dut.core.bus, 0x400, 64)
                self.run_dut(dut, model, gen)
                self.assertEqual(res["rd"], data)
                self.assertEqual(model.accesses, accesses)

    def test_continuation_sequential_bursts(self):
        # Sequential AXI bursts issued back to back are merged; non-sequential ones are not.
        dut   = DUT()
        model = HyperRAMModel(dut.phy_if)
        random.seed(1)
        data  = [random.getrandbits(32) for _ in range(64)]
        res   = {}
        def writer():
            for i in range(4):
                yield from axi_write(dut.core.bus, 0x1000 + 64*i, data[16*i:16*(i+1)])
            yield from axi_write(dut.core.bus, 0x8000, data[:16])
            rd = []
            for i in range(4):
                d, _ = yield from axi_read(dut.core.bus, 0x1000 + 64*i, 16)
                rd += d
            res["rd"] = rd
            d, _ = yield from axi_read(dut.core.bus, 0x8000, 16)
            res["rd2"] = d
        self.run_dut(dut, model, writer)
        self.assertEqual(res["rd"], data)
        self.assertEqual(res["rd2"], data[:16])

    def test_strobes(self):
        dut   = DUT()
        model = HyperRAMModel(dut.phy_if)
        res   = {}
        def gen():
            yield from axi_write(dut.core.bus, 0x0, [0x11223344, 0x55667788])
            yield from axi_write(dut.core.bus, 0x0, [0xaabbccdd, 0xeeff0011], strb=[0b0001, 0b1000])
            res["rd"], _ = yield from axi_read(dut.core.bus, 0x0, 2)
        self.run_dut(dut, model, gen)
        self.assertEqual(res["rd"], [0x112233dd, 0xee667788])

    def test_registers(self):
        dut   = DUT(with_csr=False)
        model = HyperRAMModel(dut.phy_if)
        res   = {}
        def reg_access(we, addr, wdata=0):
            reg = dut.core.reg
            yield reg.cyc.eq(1)
            yield reg.stb.eq(1)
            yield reg.we.eq(we)
            yield reg.adr.eq(addr)
            yield reg.dat_w.eq(wdata)
            yield
            while not (yield reg.ack):
                yield
            yield reg.cyc.eq(0)
            yield reg.stb.eq(0)
            yield
            return (yield reg.dat_r)
        def gen():
            res["id0"] = yield from reg_access(0, 0)
            yield from reg_access(1, 2, 0x8fe7)
            res["cr0"] = yield from reg_access(0, 2)
        self.run_dut(dut, model, gen)
        self.assertEqual(res["id0"], 0x0e76)
        self.assertEqual(res["cr0"], 0x8fe7)
        self.assertEqual(model.regs[2], 0x8fe7)

    def test_read_timeout(self):
        # A missing read word must complete the burst with SLVERR (no hang).
        dut   = DUT()
        model = HyperRAMModel(dut.phy_if, drop_word=3)
        res   = {}
        def gen():
            yield from axi_write(dut.core.bus, 0x0, list(range(8)))
            res["rd"], res["resp"] = yield from axi_read(dut.core.bus, 0x0, 8)
            res["rd2"], _ = yield from axi_read(dut.core.bus, 0x10, 4)
        self.run_dut(dut, model, gen)
        self.assertEqual(len(res["rd"]), 8)
        self.assertEqual(res["resp"].count(axi.RESP_SLVERR), 1)

    def test_write_burst_cycles(self):
        # Back-to-back write bursts: CA + latency + data + tRWR per burst (no extra stall).
        dut   = DUT()
        model = HyperRAMModel(dut.phy_if)
        res   = {"cycles": 0}
        @passive
        def counter():
            while True:
                res["cycles"] += 1
                yield
        def gen():
            for i in range(4):
                yield from axi_write(dut.core.bus, 0x100*i, list(range(16)))
        run_simulation(dut, [gen(), model.generator(), counter()])
        self.assertLess(res["cycles"], 4*80)

    def test_concurrent_fairness(self):
        # Concurrent write and read streams (ex framebuffer write + scanout) both progress.
        dut   = DUT(arbitration_words=32)
        model = HyperRAMModel(dut.phy_if)
        bus   = dut.core.bus
        res   = {"w": 0, "r": 0}
        @passive
        def writer():
            i = 0
            while True:
                yield from axi_write(bus, 0x10000 + 64*(i % 64), list(range(16)))
                res["w"] += 1
                i += 1
        @passive
        def reader():
            i = 0
            while True:
                yield from axi_read(bus, 64*(i % 64), 16)
                res["r"] += 1
                i += 1
        def main():
            for _ in range(20000):
                yield
        run_simulation(dut, [main(), writer(), reader(), model.generator()])
        self.assertGreater(res["w"], 20)
        self.assertGreater(res["r"], 20)
        self.assertLess(max(res["w"], res["r"])/min(res["w"], res["r"]), 4)

    def test_best_phase(self):
        self.assertEqual(hyperram_best_phase(0b00000000, 8), None)
        self.assertEqual(hyperram_best_phase(0b11111111, 8), 0)
        self.assertEqual(hyperram_best_phase(0b00011100, 8), 3)
        self.assertEqual(hyperram_best_phase(0b10000011, 8), 0)
        self.assertEqual(hyperram_best_phase(0b11000111, 8), 0)

    def test_calibration(self):
        class PHY(LiteXModule):
            def __init__(self):
                self.phy_if      = HyperRAMPHYInterface(dq_width=16, cd_cap="sys")
                self.phase_steps = 8
                self.phase       = Signal(3)
                self.phase_load  = Signal()
                self.cur_phase   = Signal(3)
                self.sync += If(self.phase_load, self.cur_phase.eq(self.phase))
        class CalDUT(LiteXModule):
            def __init__(self):
                self.phy = PHY()
                self.hr  = HyperRAMController(self.phy, clk_freq=100e6, with_reset=False)
        dut   = CalDUT()
        model = HyperRAMModel(dut.phy.phy_if, phase=dut.phy.cur_phase, good_phases=[5, 6, 7, 0])
        res   = {}
        def gen():
            while not (yield dut.hr.cal.done):
                yield
            res["passes"] = (yield dut.hr.cal.passes)
            res["phase"]  = (yield dut.phy.cur_phase)
            yield from axi_write(dut.hr.bus, 0x80, [0x1234, 0x5678])
            res["rd"], _ = yield from axi_read(dut.hr.bus, 0x80, 2)
        self.run_dut(dut, model, gen)
        self.assertEqual(res["passes"], 0b11100001)
        self.assertEqual(res["phase"], 6)
        self.assertEqual(res["rd"], [0x1234, 0x5678])

    def test_max_words(self):
        self.assertEqual(HyperRAMCore(HyperRAMPHYInterface(), clk_freq=200e6, with_csr=False).max_words, 256)
        self.assertEqual(HyperRAMCore(HyperRAMPHYInterface(), clk_freq=50e6,  with_csr=False).max_words, 128)

if __name__ == "__main__":
    unittest.main()
