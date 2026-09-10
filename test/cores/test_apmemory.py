#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.ram.apmemory import APMemory, APMemoryPHY


def make_pads():
    return Record([
        ("clk", 1), ("cs_n", 1),
        ("dq",  [("o", 16), ("oe", 2), ("i", 16)]),
        ("dqs", [("o", 2),  ("oe", 1), ("i", 2)]),
    ])


class APMemoryModel:
    """Pin-level OB9 model: CA decoding, mode registers, DDR data, DQS and byte masks.

    All times are in ns. Read responses are scheduled from external CLK edges; the model has
    no access to controller state. A sparse byte-addressed array covers both device densities.
    """
    def __init__(self, pads, size, tick=10, latency=5, delays=(10, 20), dq_skew=0):
        self.pads       = pads
        self.size       = size
        self.tick       = tick
        self.latency    = latency
        self.delays     = delays
        self.dq_skew    = dq_skew
        self.respond    = True
        self.accept_x16 = True
        self.memory     = {}
        self.commands   = []
        self.mr         = {0: 0x08, 1: 0x0d, 2: 0x1f if size == 32*1024*1024 else 0x1e,
                           3: 0, 4: 0x40, 8: 0x05}

    @passive
    def run(self):
        p = self.pads
        now = 0
        last_cs, last_clk = 1, 0
        start, end, last_edge = 0, -1000, -1000
        reset_end = None
        edges, address, cmd = 0, 0, None
        events = []
        dq, dqs = 0xffff, 3
        while True:
            cs, clk = (yield p.cs_n), (yield p.clk)
            if not cs and last_cs:
                assert now - end >= 15, "CE# recovery time"
                if reset_end is not None:
                    assert now - reset_end >= 2000, "Global Reset recovery time"
                start, edges, address, cmd = now, 0, 0, None
            if cs and not last_cs:
                assert not clk, "CLK must finish low"
                assert now - start <= 4000, "Maximum CE# low time"
                assert now - last_edge >= 2, "CE# hold time"
                assert edges >= 6, "Minimum CE# low clocks"
                if cmd == 0xff:
                    assert start >= 150000, "Power-up delay"
                    assert edges == 8, "Global Reset requires four clocks"
                    reset_end = now
                self.commands.append((cmd, address, edges))
                end, events, dq, dqs = now, [], 0xffff, 3
            if not cs and clk != last_clk:
                assert now - start >= 2, "CE# setup time"
                last_edge = now
                host_data = (yield p.dq.o)
                if edges < 6:
                    assert (yield p.dq.oe) == 1, "CA uses only the lower byte lane"
                    if edges == 0:
                        assert clk
                        cmd = host_data & 0xff
                        assert cmd in [0xff, 0xc0, 0x40, 0x20, 0xa0]
                    elif edges >= 2:
                        address = (address << 8) | (host_data & 0xff)
                if cmd in [0x20, 0xa0] and edges == 6:
                    assert self.mr[8] & 0x40, "Memory access before x16 enable"
                    assert address & 0x401 == 0, "Even x16 column; CA10 is unused"
                if cmd == 0xc0 and edges == 6:
                    assert (yield p.dq.oe) == 1
                    assert (yield p.dqs.oe) and (yield p.dqs.o) == 0
                    if self.accept_x16:
                        self.mr[address] = host_data & 0xff
                if cmd == 0xa0 and edges >= 14:
                    assert (yield p.dq.oe) == 3
                    assert (yield p.dqs.oe)
                    offset = (address >> 11)*2048 + (address & 0x3ff)*2 + (edges - 14)*2
                    assert offset + 1 < self.size
                    for lane in range(2):
                        if not ((yield p.dqs.o) >> lane) & 1:
                            self.memory[offset + lane] = (host_data >> (8*lane)) & 0xff
                if cmd in [0x20, 0x40] and self.respond:
                    if edges >= 6:
                        assert (yield p.dq.oe) == 0 and (yield p.dqs.oe) == 0
                    for lane in range(2 if cmd == 0x20 else 1):
                        if edges == 4:
                            events.append((now + self.delays[lane], "dqs", lane, 0))
                        beat = edges - (4 + 2*self.latency)
                        if beat >= 0:
                            if cmd == 0x40:
                                pair = {0: 1, 1: 2, 2: 3, 3: 4, 4: 8, 8: 0}
                                value = self.mr[address if beat % 2 == 0 else pair[address]]
                            else:
                                offset = (address >> 11)*2048 + (address & 0x3ff)*2 + beat*2
                                value = self.memory.get(offset + lane, 0)
                            events.append((now + self.delays[lane], "dqs", lane, 1 - beat % 2))
                            events.append((now + self.delays[lane] + self.dq_skew, "dq", lane, value))
                edges += 1
            for event in sorted(events):
                when, kind, lane, value = event
                if when <= now:
                    if kind == "dqs":
                        dqs = (dqs & ~(1 << lane)) | (value << lane)
                    else:
                        dq = (dq & ~(0xff << (8*lane))) | (value << (8*lane))
            events = [event for event in events if event[0] > now]
            yield p.dq.i.eq(dq)
            yield p.dqs.i.eq(dqs)
            last_cs, last_clk = cs, clk
            now += self.tick
            yield


def access(bus, address, value=None, sel=0xf, error=False, hold_cyc=False):
    yield bus.adr.eq(address//4)
    yield bus.dat_w.eq(value or 0)
    yield bus.sel.eq(sel)
    yield bus.we.eq(value is not None)
    yield bus.cyc.eq(1)
    yield bus.stb.eq(1)
    yield
    for _ in range(1000):
        if (yield bus.ack) or (yield bus.err):
            assert bool((yield bus.err)) == error
            result = (yield bus.dat_r)
            break
        yield
    else:
        raise AssertionError("Wishbone access did not complete")
    yield bus.stb.eq(0)
    yield bus.cyc.eq(hold_cyc)
    yield
    return result


class TestAPMemory(unittest.TestCase):
    def wait_ready(self, cores):
        for _ in range(20000):
            states = []
            for core in cores:
                states.append((yield core.ready) or (yield core.init_error))
            if all(states):
                return
            yield
        self.fail("PSRAM initialization did not complete")

    def test_four_devices(self):
        dut = Module()
        sizes = [32*1024*1024]*3 + [64*1024*1024]
        pads = [make_pads() for _ in sizes]
        cores = [APMemory(p, 100e6, size=s) for p, s in zip(pads, sizes)]
        models = [APMemoryModel(p, s, latency=5 + i) for i, (p, s) in enumerate(zip(pads, sizes))]
        dut.submodules += cores

        def bench():
            yield from self.wait_ready(cores)
            for i, (core, model, size) in enumerate(zip(cores, models, sizes)):
                self.assertEqual((yield core.ready), 1)
                self.assertEqual((yield core.id) & 0x7ff, (7 if i < 3 else 6)*256 + 0x0d)
                self.assertEqual([cmd for cmd, _, _ in model.commands[:4]], [0xff, 0xc0, 0x40, 0x40])
                # Distinguish all lanes, both sides of a row, the high address bit and the last word.
                offsets = [0, 4, 0x7fc, 0x800, size//2, size - 4]
                for n, offset in enumerate(offsets):
                    yield from access(core.bus, offset, 0x12345678 ^ (i << 24) ^ n, hold_cyc=True)
                for n, offset in enumerate(offsets):
                    self.assertEqual((yield from access(core.bus, offset, hold_cyc=True)),
                        0x12345678 ^ (i << 24) ^ n)
                # CA10 must not alias columns or steal the highest row address bit.
                self.assertIn((0xa0, ((size//2)//2048) << 11, 16), model.commands)
                for mask in range(16):
                    old = yield from access(core.bus, 0)
                    new = 0xfedcba98 ^ mask
                    yield from access(core.bus, 0, new, sel=mask)
                    expected = sum(((new if mask & (1 << b) else old) & (0xff << (8*b))) for b in range(4))
                    self.assertEqual((yield from access(core.bus, 0)), expected)

            # Four requests in flight at once, with different data at the same local address.
            for i, core in enumerate(cores):
                yield core.bus.adr.eq(16)
                yield core.bus.dat_w.eq(0xaabbcc00 + i)
                yield core.bus.we.eq(1)
                yield core.bus.sel.eq(15)
                yield core.bus.cyc.eq(1)
                yield core.bus.stb.eq(1)
            yield
            pending = set(range(4))
            for _ in range(1000):
                for i in list(pending):
                    if (yield cores[i].bus.ack):
                        yield cores[i].bus.cyc.eq(0)
                        yield cores[i].bus.stb.eq(0)
                        pending.remove(i)
                if not pending:
                    break
                yield
            self.assertFalse(pending)
            yield
            for i, core in enumerate(cores):
                self.assertEqual((yield from access(core.bus, 64)), 0xaabbcc00 + i)

            # A missing response terminates with ERR and CE# high, then a later access can succeed.
            models[0].respond = False
            yield from access(cores[0].bus, 0, error=True)
            self.assertEqual((yield cores[0].timeout), 1)
            self.assertEqual((yield pads[0].cs_n), 1)
            models[0].respond = True
            self.assertEqual((yield from access(cores[0].bus, 64)), 0xaabbcc00)

            # Abandon a request, then present another before the old transaction finishes.
            bus = cores[0].bus
            yield bus.adr.eq(0)
            yield bus.cyc.eq(1)
            yield bus.stb.eq(1)
            for _ in range(20):
                yield
            yield bus.cyc.eq(0)
            yield
            self.assertEqual((yield from access(bus, 64)), 0xaabbcc00)

        run_simulation(dut, [bench()] + [m.run() for m in models])

    def test_initialization_errors(self):
        dut = Module()
        pads = [make_pads() for _ in range(3)]
        cores = [APMemory(p, 100e6) for p in pads]
        models = [APMemoryModel(p, 32*1024*1024) for p in pads]
        models[0].respond = False
        models[1].accept_x16 = False
        models[2].mr[2] = 0x1e # Wrong density.
        dut.submodules += cores

        def bench():
            yield from self.wait_ready(cores)
            for core in cores:
                self.assertEqual((yield core.ready), 0)
                self.assertEqual((yield core.init_error), 1)
                yield from access(core.bus, 0, error=True)
            self.assertEqual((yield cores[0].timeout), 1)

        run_simulation(dut, [bench()] + [m.run() for m in models])

    def test_read_timing(self):
        # Test the PHY separately with 2ns resolution, response delays crossing sys edges,
        # lane skew, and late DQ. Both clock limits must support the full variable-latency range.
        for sys_freq in [50e6, 100e6]:
            for skew, delay in [(s, d) for s in [-8, 8] for d in [2, 6, 10, 14, 18]]:
                with self.subTest(sys_freq=sys_freq, dq_skew=skew, delay=delay):
                    pads = make_pads()
                    phy = APMemoryPHY(pads, sys_freq)
                    model = APMemoryModel(pads, 32*1024*1024, tick=2,
                        delays=(delay + 8, delay + 18), dq_skew=skew)
                    model.mr[8] = 0x40
                    model.memory = {0: 0x12, 1: 0x34, 2: 0x56, 3: 0x78}

                    def bench():
                        for latency in range(5, 11):
                            model.latency = latency
                            yield phy.cmd.eq(0x20)
                            yield phy.start.eq(1)
                            yield
                            yield phy.start.eq(0)
                            for _ in range(500):
                                if (yield phy.done):
                                    break
                                yield
                            else:
                                self.fail("Read did not finish")
                            self.assertEqual((yield phy.error), 0)
                            self.assertEqual((yield phy.dat_r), 0x78563412)
                            yield

                    run_simulation(phy, {"sys": bench(), "model": model.run()},
                        clocks={"sys": int(1e9/sys_freq), "model": 2})

    def test_parameters(self):
        for freq in [0, 49e6, 101e6]:
            with self.assertRaises(ValueError):
                APMemory(make_pads(), freq)
        with self.assertRaises(ValueError):
            APMemory(make_pads(), 100e6, size=16*1024*1024)
