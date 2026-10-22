#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import random

from migen import *
from migen.sim import passive

from litex.gen import *

from litex.soc.interconnect.axi import *
from litex.soc.interconnect.axi.axi_full import axi_interleaved_id_width

# Helpers ------------------------------------------------------------------------------------------

DATA_WIDTH = 64
BEAT_BYTES = DATA_WIDTH//8

def init_word(word):
    return (word*0x9e3779b97f4a7c15 + 0x1234) & (2**DATA_WIDTH - 1)

class AXIMemory:
    """Behavioural AXI4 memory slave (word addressed, INCR bursts of full beats).

    - latency: cycles from AR to the first R beat of a burst.
    - reorder: serves the oldest ready burst of a random ID (in order per ID, as AXI requires);
      otherwise in AR order.
    - ready_rate: probability of AR/AW/W ready on a cycle (random back-pressure).
    - write_order: "aw_first" (W taken only for an accepted AW), "w_first" (AW taken only once its
      WVALID is seen, as some hard controllers do) or "aw_after_w" (AW taken after its whole burst).
    """
    def __init__(self, bus, latency=8, reorder=False, ready_rate=1.0, write_order="aw_first", seed=0):
        self.bus         = bus
        self.latency     = latency
        self.reorder     = reorder
        self.ready_rate  = ready_rate
        self.write_order = write_order
        self.prng        = random.Random(seed)
        self.mem         = {}
        self.r_beats     = 0

    def read(self, word):
        return self.mem.get(word, init_word(word))

    def _ready(self):
        return int(self.prng.random() < self.ready_rate)

    @passive
    def reads(self):
        bus, cycle, pending, current = self.bus, 0, [], None
        while True:
            if (yield bus.ar.valid) and (yield bus.ar.ready):
                pending.append(dict(
                    id    = (yield bus.ar.id),
                    word  = (yield bus.ar.addr)//BEAT_BYTES,
                    beats = (yield bus.ar.len) + 1,
                    ready = cycle + self.latency,
                    beat  = 0))
            if (yield bus.r.valid) and (yield bus.r.ready):
                self.r_beats += 1
                current["beat"] += 1
                if current["beat"] == current["beats"]:
                    pending.remove(current)
                    current = None
            if current is None:
                heads = {}
                for p in pending:
                    heads.setdefault(p["id"], p)
                ready = [p for p in heads.values() if p["ready"] <= cycle]
                if ready:
                    current = self.prng.choice(ready) if self.reorder else min(ready, key=pending.index)
            if current is not None:
                yield bus.r.valid.eq(1)
                yield bus.r.id.eq(current["id"])
                yield bus.r.data.eq(self.read(current["word"] + current["beat"]))
                yield bus.r.last.eq(current["beat"] == current["beats"] - 1)
                yield bus.r.resp.eq(0)
            else:
                yield bus.r.valid.eq(0)
            yield bus.ar.ready.eq(self._ready())
            cycle += 1
            yield

    @passive
    def writes(self):
        bus, aws, bursts, burst, b_queue, paired = self.bus, [], [], [], [], 0
        while True:
            if (yield bus.aw.valid) and (yield bus.aw.ready):
                aws.append(((yield bus.aw.id), (yield bus.aw.addr)//BEAT_BYTES))
            if (yield bus.w.valid) and (yield bus.w.ready):
                burst.append((yield bus.w.data))
                if (yield bus.w.last):
                    bursts.append(burst)
                    burst = []
            if (yield bus.b.valid) and (yield bus.b.ready):
                b_queue.pop(0)
            while paired < min(len(aws), len(bursts)):
                aw_id, word = aws[paired]
                for k, data in enumerate(bursts[paired]):
                    self.mem[word + k] = data
                b_queue.append(aw_id)
                paired += 1
            yield bus.b.valid.eq(len(b_queue) > 0)
            yield bus.b.id.eq(b_queue[0] if b_queue else 0)
            yield bus.b.resp.eq(0)
            unpaired_w = (len(bursts) > len(aws)) or len(burst) > 0
            if self.write_order == "aw_first":
                yield bus.aw.ready.eq(self._ready())
                yield bus.w.ready.eq((len(aws) > len(bursts)) & self._ready())
            elif self.write_order == "w_first":
                yield bus.aw.ready.eq(((yield bus.w.valid) | unpaired_w) & self._ready())
                yield bus.w.ready.eq(self._ready())
            else: # "aw_after_w"
                yield bus.aw.ready.eq((len(bursts) > len(aws)) & self._ready())
                yield bus.w.ready.eq(self._ready())
            yield

def read_master(m, bursts, outstanding, results, key, seed=0, r_ready_rate=1.0):
    """Issues `bursts` [(id, word, beats)] with up to `outstanding` in flight, checks every beat
    (data and ID, in order per ID) and records the completion cycle in results[key]."""
    prng, issued, inflight, done, cycle = random.Random(seed), 0, {}, 0, 0
    while done < len(bursts):
        if (yield m.ar.valid) and (yield m.ar.ready):
            i, word, beats = bursts[issued]
            inflight.setdefault(i, []).append([word, beats, 0])
            issued += 1
        if (yield m.r.valid) and (yield m.r.ready):
            i     = (yield m.r.id)
            burst = inflight[i][0]
            assert (yield m.r.data) == init_word(burst[0] + burst[2]), (key, i, burst)
            burst[2] += 1
            assert (yield m.r.last) == (burst[2] == burst[1]), (key, i, burst)
            if burst[2] == burst[1]:
                inflight[i].pop(0)
                done += 1
        n_inflight = sum(len(v) for v in inflight.values())
        if issued < len(bursts) and n_inflight < outstanding:
            i, word, beats = bursts[issued]
            yield m.ar.valid.eq(1)
            yield m.ar.id.eq(i)
            yield m.ar.addr.eq(word*BEAT_BYTES)
            yield m.ar.len.eq(beats - 1)
            yield m.ar.size.eq(log2_int(BEAT_BYTES))
            yield m.ar.burst.eq(0b01)
        else:
            yield m.ar.valid.eq(0)
        yield m.r.ready.eq(int(prng.random() < r_ready_rate))
        cycle += 1
        assert cycle < 50000, f"{key}: stalled, {done} of {len(bursts)} bursts"
        yield
    results[key] = cycle

def write_master(m, bursts, results, key, w_wait=None):
    """Writes `bursts` [(id, word, [data...])]: all AWs first, then the W beats (after
    `w_wait()` turns true, if given); records the cycle all B responses are back."""
    def aw():
        for i, word, data in bursts:
            yield m.aw.valid.eq(1)
            yield m.aw.id.eq(i)
            yield m.aw.addr.eq(word*BEAT_BYTES)
            yield m.aw.len.eq(len(data) - 1)
            yield m.aw.size.eq(log2_int(BEAT_BYTES))
            yield m.aw.burst.eq(0b01)
            yield
            while not (yield m.aw.ready):
                yield
        yield m.aw.valid.eq(0)
    def w():
        if w_wait is not None:
            while not w_wait():
                yield
        for i, word, data in bursts:
            for k, d in enumerate(data):
                yield m.w.valid.eq(1)
                yield m.w.data.eq(d)
                yield m.w.strb.eq(2**(DATA_WIDTH//8) - 1)
                yield m.w.last.eq(k == len(data) - 1)
                yield
                while not (yield m.w.ready):
                    yield
        yield m.w.valid.eq(0)
    def b():
        ids, cycle = [i for i, _, _ in bursts], 0
        yield m.b.ready.eq(1)
        while ids:
            if (yield m.b.valid):
                assert (yield m.b.id) == ids.pop(0), key
            cycle += 1
            assert cycle < 10000, f"{key}: stalled, {len(ids)} responses missing"
            yield
        results[key] = cycle
    return [aw(), w(), b()]

def axi(id_width, **kwargs):
    return AXIInterface(data_width=DATA_WIDTH, address_width=32, id_width=id_width, **kwargs)

def read_bursts(base, n, beats, n_ids):
    return [(k % n_ids, base + k*beats, beats) for k in range(n)]

def write_bursts(base, n, beats, seed):
    prng = random.Random(seed)
    return [(k % 2, base + k*beats, [prng.getrandbits(DATA_WIDTH) for _ in range(beats)]) for k in range(n)]

# Test AXIArbiter ----------------------------------------------------------------------------------

class TestAXIArbiter(unittest.TestCase):
    def shared_port(self, n_readers=3, interleave=True, latency=20, reorder=False, ready_rate=1.0,
        r_ready_rate=1.0, r_buffer=0, outstanding=4, n_bursts=12, beats=8, seed=0):
        readers = [axi(2) for _ in range(n_readers)]
        writer  = axi(2)
        masters = readers + [writer]
        target  = axi(axi_interleaved_id_width(masters) if interleave else 2)
        dut = Module()
        if interleave:
            dut.submodules.arbiter = AXIArbiter(masters, target, interleave=True, r_buffer=r_buffer)
        else:
            dut.submodules.arbiter = AXIArbiter(masters, target)
        memory  = AXIMemory(target, latency=latency, reorder=reorder, ready_rate=ready_rate, seed=seed)
        results = {}
        wbursts = write_bursts(0x10000, 4, beats, seed)
        gens = [memory.reads(), memory.writes()]
        for n, m in enumerate(readers):
            gens.append(read_master(m, read_bursts(0x1000*n, n_bursts, beats, n_ids=2), outstanding,
                results, f"reader{n}", seed=seed + n, r_ready_rate=r_ready_rate))
        gens += write_master(writer, wbursts, results, "writer")
        run_simulation(dut, gens)
        for i, word, data in wbursts:
            for k, d in enumerate(data):
                self.assertEqual(memory.read(word + k), d)
        return max(results[f"reader{n}"] for n in range(n_readers))

    def test_default_mode_shares_one_port(self):
        self.shared_port(interleave=False)

    def test_interleave_shares_one_port(self):
        self.shared_port(interleave=True)

    def test_interleave_reordering_target(self):
        self.shared_port(interleave=True, latency=40, reorder=True, seed=1)

    def test_interleave_backpressure(self):
        self.shared_port(interleave=True, reorder=True, ready_rate=0.6, r_ready_rate=0.7, seed=2)

    def test_interleave_read_buffers(self):
        self.shared_port(interleave=True, reorder=True, r_ready_rate=0.5, r_buffer=4*8, seed=3)

    def test_interleave_beats_the_default_mode(self):
        interleaved = self.shared_port(interleave=True,  latency=40, n_bursts=16)
        locked      = self.shared_port(interleave=False, latency=40, n_bursts=16)
        # 3 readers x 16 bursts x 8 beats: interleaved reads keep the port busy (~400 cycles), the
        # default mode waits out the latency at each switch between masters.
        self.assertLess(interleaved, 0.75*locked)

    def test_interleave_write_data_waiting_on_another_master(self):
        # Master a's AW comes first, but its W data only once master b's writes are done: with W
        # in AW order at the target, the bursts are buffered per master before their AW is issued.
        a, b    = axi(2), axi(2)
        target  = axi(axi_interleaved_id_width([a, b]))
        dut     = Module()
        dut.submodules.arbiter = AXIArbiter([a, b], target, interleave=True)
        memory  = AXIMemory(target, latency=4)
        results = {}
        a_bursts = write_bursts(0x000, 2, 8, seed=4)
        b_bursts = write_bursts(0x100, 2, 8, seed=5)
        gens  = [memory.reads(), memory.writes()]
        gens += write_master(a, a_bursts, results, "a", w_wait=lambda: "b" in results)
        b_gens = write_master(b, b_bursts, results, "b")
        def delayed(gen, cycles):
            for _ in range(cycles):
                yield
            yield from gen
        gens += [delayed(b_gens[0], 2)] + b_gens[1:]
        run_simulation(dut, gens)
        self.assertIn("a", results)
        self.assertIn("b", results)
        for i, word, data in a_bursts + b_bursts:
            for k, d in enumerate(data):
                self.assertEqual(memory.read(word + k), d)

    def test_interleave_every_target_write_order(self):
        for write_order in ["aw_first", "w_first", "aw_after_w"]:
            with self.subTest(write_order=write_order):
                a, b    = axi(2), axi(2)
                target  = axi(axi_interleaved_id_width([a, b]))
                dut     = Module()
                dut.submodules.arbiter = AXIArbiter([a, b], target, interleave=True)
                memory  = AXIMemory(target, latency=4, write_order=write_order, ready_rate=0.8, seed=6)
                results = {}
                a_bursts = write_bursts(0x000, 5, 8, seed=7)
                b_bursts = write_bursts(0x100, 5, 8, seed=8)
                gens  = [memory.reads(), memory.writes()]
                gens += write_master(a, a_bursts, results, "a")
                gens += write_master(b, b_bursts, results, "b")
                run_simulation(dut, gens)
                for i, word, data in a_bursts + b_bursts:
                    for k, d in enumerate(data):
                        self.assertEqual(memory.read(word + k), d)

    def test_interleave_read_and_write_only_masters(self):
        r0, r1  = axi(2, mode="r"), axi(2, mode="r")
        w0      = axi(2, mode="w")
        masters = [r0, r1, w0]
        target  = axi(axi_interleaved_id_width(masters))
        dut     = Module()
        dut.submodules.arbiter = AXIArbiter(masters, target, interleave=True)
        memory  = AXIMemory(target, latency=10, reorder=True, seed=9)
        results = {}
        wbursts = write_bursts(0x10000, 3, 8, seed=10)
        gens  = [memory.reads(), memory.writes()]
        gens += [read_master(r0, read_bursts(0x000, 6, 8, 2), 4, results, "r0"),
                 read_master(r1, read_bursts(0x800, 6, 8, 2), 4, results, "r1")]
        gens += write_master(w0, wbursts, results, "w0")
        run_simulation(dut, gens)
        self.assertEqual(set(results), {"r0", "r1", "w0"})
        for i, word, data in wbursts:
            for k, d in enumerate(data):
                self.assertEqual(memory.read(word + k), d)

    def test_interleave_rejects_narrow_target_id(self):
        masters = [axi(2) for _ in range(3)]
        with self.assertRaises(ValueError):
            AXIArbiter(masters, axi(3), interleave=True)

    def test_interleaved_id_width(self):
        self.assertEqual(axi_interleaved_id_width([axi(2), axi(4)]), 5)
        self.assertEqual(axi_interleaved_id_width([axi(1) for _ in range(5)]), 4)

# Test AXIInterconnectShared -----------------------------------------------------------------------

class TestAXIInterconnectSharedInterleave(unittest.TestCase):
    def test_two_masters_two_slaves(self):
        masters = [axi(2) for _ in range(2)]
        id_width = axi_interleaved_id_width(masters)
        slaves  = [axi(id_width) for _ in range(2)]
        dut = Module()
        dut.submodules.interconnect = AXIInterconnectShared(masters, [
            (lambda a: a[16] == 0, slaves[0]),
            (lambda a: a[16] == 1, slaves[1]),
        ], interleave=True)
        memories = [AXIMemory(s, latency=6 + 4*n, seed=n) for n, s in enumerate(slaves)]
        results  = {}
        gens = []
        for mem in memories:
            gens += [mem.reads(), mem.writes()]
        # Word addresses: slave 1 from byte address 0x10000 (word 0x2000).
        gens += [read_master(masters[0], read_bursts(0x0000, 6, 8, 2), 4, results, "m0"),
                 read_master(masters[1], read_bursts(0x2000, 6, 8, 2), 4, results, "m1")]
        run_simulation(dut, gens)
        self.assertEqual(set(results), {"m0", "m1"})

    def test_rejects_narrow_slaves(self):
        masters = [axi(2) for _ in range(2)]
        with self.assertRaises(ValueError):
            AXIInterconnectShared(masters, [(lambda a: 1, axi(2))], interleave=True)
