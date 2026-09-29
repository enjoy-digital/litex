#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import re
import random
import unittest

from migen import *

from litex.gen.fhdl import verilog
from litex.gen.sim  import run_simulation, passive

from litex.build.io import SerDesOutput, SerDesTristate
from litex.build.gowin.common import gowin_special_overrides, gw5a_special_overrides

from litex.soc.cores.ram.opi_psram import *

# OPI PSRAM Model (APS6408L-OBMx datasheet, Rev. 3.7) ----------------------------------------------

MR_DEFAULTS = {
    0: 0b00_0_010_01, # Variable latency, LC 5, half drive.
    1: 0b0_00_01101,  # Vendor ID: AP Memory.
    2: 0b1_00_10_011, # Good die, generation 3, 64Mb.
    3: 0b1_0_0_00000, # RBX supported.
    4: 0b010_0_0_000, # WL 5.
    8: 0b0000_0_1_01, # 32-byte hybrid wrap.
}
MR_READ_PAIRS = {0: (0, 1), 1: (1, 2), 2: (2, 3), 3: (3, 4), 4: (4, 8), 8: (8, 0)}
READ_CODES    = {code: latency for latency, (code, _) in READ_LATENCIES.items()}
WRITE_CODES   = {code: latency for latency, (code, _) in WRITE_LATENCIES.items()}

class _NoSerDes:
    """SerDes specials removed: the model connects to the PHY SerDes words."""
    @staticmethod
    def lower(dr):
        return Module()

SIM_OVERRIDES = {SerDesOutput: _NoSerDes, SerDesTristate: _NoSerDes}

class OPIPSRAMModel:
    """
    Slot level (4 slots per cycle) OPI PSRAM model: command/address latching on CLK edges, latencies
    (MR0/MR4, variable read latency with refresh pushout), DQS preamble/strobe, DM, MR accesses,
    Global Reset, page wrap. Read data/DQS reach the PHY ``delay`` slots after the CLK edge.
    Protocol/timing violations are collected in ``errors``.
    """
    def __init__(self, phy, clk_freq, size=8*1024*1024, page_size=1024, delay=4, pushout=0.0,
        uncertain=False, tcem=4e-6, seed=0, dead=False):
        self.phy       = phy
        self.size      = size
        self.page_size = page_size
        self.delay     = delay
        self.pushout   = pushout
        self.uncertain = uncertain
        self.dead      = dead
        self.rng       = random.Random(seed)
        self.mem       = {}
        self.mr        = dict(MR_DEFAULTS)
        self.errors    = []
        self.commands  = []
        self.slot_ns   = 1e9/clk_freq/4
        self.tcem      = tcem
        self.reset_done = None # Slot of the Global Reset.

    def error(self, msg):
        if len(self.errors) < 16:
            self.errors.append(f"{self.t}: {msg}")

    def read_byte(self, addr):
        return self.mem.get(addr % self.size, 0)

    @passive
    def generator(self):
        phy = self.phy
        self.t = 0
        # Host side timeline state.
        clk_prev  = 0
        cs_prev   = 1
        cs_low_t  = None
        cs_high_t = 0
        # Device output: slot -> (dq, dqs) (None: high impedance).
        out = {}
        # Transaction state.
        tr = None
        while True:
            cs_word  = (yield phy.cs_n_word)
            clk_word = (yield phy.clk_word)
            dq_words = []
            for w in phy.dq_words:
                dq_words.append((yield w))
            dq_oe    = (yield phy.dq_oe_word)
            dqs_word = (yield phy.dqs_word)
            dqs_oe   = (yield phy.dqs_oe_word)
            for k in range(4):
                cs  = (cs_word  >> k) & 1
                clk = (clk_word >> k) & 1
                dq  = sum(((dq_words[n] >> k) & 1) << n for n in range(8))
                dqs = (dqs_word >> k) & 1
                # CE# transitions / timings.
                if cs_prev and not cs:
                    if (self.t - cs_high_t)*self.slot_ns < 20:
                        self.error("tCPH violation.")
                    if self.t*self.slot_ns < 150e3:
                        self.error("Access before tPU.")
                    if self.reset_done is not None:
                        if (self.t - self.reset_done)*self.slot_ns < 2e3:
                            self.error("Access during tRST.")
                    cs_low_t = self.t
                    tr = {"edges": 0, "rises": 0, "bytes": [], "out_k": None}
                if not cs_prev and cs:
                    if (self.t - cs_low_t)*self.slot_ns > self.tcem*1e9:
                        self.error("tCEM violation.")
                    cs_high_t = self.t
                    self.end(tr)
                    tr  = None
                    out = {s: v for s, v in out.items() if s < self.t + 2} # tHZ.
                if tr is not None and cs and clk:
                    self.error("CLK with CE# high.")
                # Bus contention (device drives DQ/DQS).
                dev = out.get(self.t)
                if dev is not None and dev[0] is not None and dq_oe:
                    self.error("DQ contention.")
                if dev is not None and dev[1] is not None and dqs_oe:
                    self.error("DQS contention.")
                # CLK edges.
                if tr is not None and not cs and clk != clk_prev:
                    rise = clk == 1
                    self.edge(tr, rise, dq if dq_oe else None, dqs if dqs_oe else None, out)
                clk_prev = clk
                cs_prev  = cs
                self.t  += 1
            # Device outputs to the PHY (delayed).
            dq_i  = [0]*8
            dqs_i = 0
            for k in range(4):
                v = None if self.dead else out.get(self.t - 4 - self.delay + k)
                if v is None:
                    rdq, rdqs = self.rng.randrange(256), self.rng.randrange(2)
                else:
                    rdq  = self.rng.randrange(256) if v[0] is None else v[0]
                    rdqs = self.rng.randrange(2)   if v[1] is None else v[1]
                    if self.uncertain and len(v) > 2 and v[2]:
                        rdq = self.rng.randrange(256)
                for n in range(8):
                    dq_i[n] |= ((rdq >> n) & 1) << k
                dqs_i |= rdqs << k
            for n in range(8):
                yield phy.dq_i_words[n].eq(dq_i[n])
            yield phy.dqs_i_word.eq(dqs_i)
            yield

    def edge(self, tr, rise, dq, dqs, out):
        e = tr["edges"]
        tr["edges"] += 1
        if rise:
            tr["rises"] += 1
        k = (e // 2) # Clock index (0: instruction).
        if e == 0:
            tr["cmd"] = dq
            return
        if e in [2, 3, 4, 5]:
            tr["bytes"].append(dq)
            if e == 5:
                self.address(tr, out)
            return
        if e < 6:
            return
        cmd = tr.get("cmd")
        if cmd in [0x80, 0xa0] and k >= 2 + tr["wl"]:
            # Write data (DM on DQS/DM).
            if dq is None or dqs is None:
                self.error("Write data/DM not driven.")
                return
            addr = tr["addr"]
            if tr.get("wrapped"):
                self.error("Write crossing a page.")
            if dqs == 0:
                self.mem[addr % self.size] = dq
            tr["addr"] = addr + 1
            if (addr % self.page_size) == (self.page_size - 1):
                # Wraps within the page (no RBX write).
                tr["addr"]    = addr - self.page_size + 1
                tr["wrapped"] = True
        if cmd == 0xc0 and e == 6:
            ma = tr["ma"]
            if ma not in [0, 4, 8]:
                self.error(f"MR{ma} write.")
            else:
                self.mr[ma] = dq
                tr["mr_written"] = True
        if cmd in [0x00, 0x20, 0x40] and rise and k >= tr["out_k"]:
            # Read data: one word per rising edge, DQS high then low.
            slot = self.t + self.delay_out
            if cmd == 0x40:
                a, b = MR_READ_PAIRS.get(tr["ma"], (0, 0))
                d0, d1 = self.mr[a], self.mr[b]
            else:
                addr = tr["addr"]
                d0, d1 = self.read_byte(addr), self.read_byte(addr + 1)
                addr += 2
                if (addr % self.page_size) == 0:
                    addr -= self.page_size # Linear burst: wraps within the page (no RBX).
                tr["addr"] = addr
            out[slot + 0] = (d0, 1, True)
            out[slot + 1] = (d0, 1, False)
            out[slot + 2] = (d1, 0, True)
            out[slot + 3] = (d1, 0, False)
        if cmd in [0x00, 0x20, 0x40] and rise and k == 3:
            # DQS preamble (driven low) until the data.
            for s in range(self.t + self.delay_out, self.t + self.delay_out + 4*(tr["out_k"] - 3)):
                out.setdefault(s, (None, 0))

    delay_out = 1 # CLK edge -> output (slots, tDQSCK).

    def address(self, tr, out):
        cmd = tr["cmd"]
        a3, a2, a1, a0 = tr["bytes"]
        addr = (a3 << 24) | (a2 << 16) | (a1 << 8) | a0
        self.commands.append((cmd, addr))
        lc = READ_CODES[(self.mr[0] >> 2) & 0b111]
        wl = WRITE_CODES[(self.mr[4] >> 5) & 0b111]
        tr["wl"] = wl
        tr["ma"] = a0
        if cmd == 0xff:
            self.mr = dict(MR_DEFAULTS)
            self.reset_done = self.t
            return
        if self.reset_done is None:
            self.error("Command before Global Reset.")
        if cmd in [0x00, 0x80, 0x20, 0xa0]:
            if addr & 1:
                self.error("Odd address.")
            if addr >= self.size:
                self.error("Address out of range.")
            tr["addr"] = addr
        if cmd in [0x00, 0x20]:
            pushout = (self.rng.random() < self.pushout)
            tr["out_k"] = 2 + lc*(2 if pushout else 1)
        elif cmd == 0x40:
            tr["out_k"] = 2 + lc
        elif cmd not in [0x80, 0xa0, 0xc0]:
            self.error(f"Unknown command 0x{cmd:02x}.")

    def end(self, tr):
        if tr is None:
            return
        if tr.get("cmd") == 0xc0 and not tr.get("mr_written"):
            self.error("MR write without data.")
        if tr.get("cmd") == 0xff and tr["rises"] < 4:
            self.error("Global Reset: less than 4 clocks.")

# Helpers ------------------------------------------------------------------------------------------

PADS_LAYOUT = [("cs_n", 1), ("clk", 1), ("dq", 8), ("dqs", 1)]

class _DUT(LiteXModule):
    def __init__(self, clk_freq, data_width=None, rx_sample=1, **kwargs):
        self.pads = Record(PADS_LAYOUT)
        self.phy  = OPIPSRAMPHY(self.pads, rx_sample=rx_sample)
        self.core = OPIPSRAMCore(self.phy, clk_freq, **kwargs)
        if data_width is not None:
            self.wb = OPIPSRAMWishbone(self.core, data_width=data_width)

def run(dut, model, generators, timeout=200000):
    def watchdog():
        for _ in range(timeout):
            yield
        raise TimeoutError("Simulation timeout.")
    run_simulation(dut, generators + [model.generator(), passive(watchdog)()],
        special_overrides=SIM_OVERRIDES)

def wait_ready(dut, test):
    while not (yield dut.core.ready):
        test.assertFalse((yield dut.core.init_error), "Initialization error.")
        yield

def native_write(core, addr, words, wes=None):
    yield core.cmd.valid.eq(1)
    yield core.cmd.we.eq(1)
    yield core.cmd.addr.eq(addr)
    yield core.cmd.len.eq(len(words))
    yield
    while not (yield core.cmd.ready):
        yield
    yield core.cmd.valid.eq(0)
    n = 0
    yield core.wdata.valid.eq(1)
    while n < len(words):
        yield core.wdata.data.eq(words[n])
        yield core.wdata.we.eq(0b11 if wes is None else wes[n])
        yield
        if (yield core.wdata.ready):
            n += 1
    yield core.wdata.valid.eq(0)

def native_read(core, addr, length):
    yield core.cmd.valid.eq(1)
    yield core.cmd.we.eq(0)
    yield core.cmd.addr.eq(addr)
    yield core.cmd.len.eq(length)
    yield
    while not (yield core.cmd.ready):
        yield
    yield core.cmd.valid.eq(0)
    words = []
    while len(words) < length:
        if (yield core.rdata.valid):
            words.append((yield core.rdata.data))
        yield
    return words

# Tests --------------------------------------------------------------------------------------------

CLK_FREQ = 33e6
CAL_AREA = 0x100 # Calibration pattern written at 0 during initialization.

class TestOPIPSRAM(unittest.TestCase):
    def check_model(self, model):
        self.assertEqual(model.errors, [])

    def test_latencies(self):
        cases = [(33e6, 3, 3), (67.1e6, 4, 4), (100e6, 4, 4), (133e6, 5, 5), (200e6, 7, 7)]
        for clk_freq, lc, wl in cases:
            with self.subTest(clk_freq=clk_freq):
                self.assertEqual(get_latency(READ_LATENCIES,  clk_freq), lc)
                self.assertEqual(get_latency(WRITE_LATENCIES, clk_freq), wl)
        with self.assertRaises(ValueError):
            get_latency(READ_LATENCIES, 250e6)

    def test_init(self):
        for delay in [0, 3, 6, 9, 13]:
            with self.subTest(delay=delay):
                dut   = _DUT(CLK_FREQ)
                model = OPIPSRAMModel(dut.phy, CLK_FREQ, delay=delay, seed=delay)
                def gen():
                    yield from wait_ready(dut, self)
                    self.assertEqual((yield dut.core.vendor_id), 0b01101)
                    self.assertEqual((yield dut.core.density),   0b011)
                    self.assertFalse((yield dut.core.timeout))
                run(dut, model, [gen()])
                self.check_model(model)
                # Global Reset first, then latency codes.
                self.assertEqual(model.commands[0][0], 0xff)
                self.assertEqual(model.mr[0], dut.core.mr0)
                self.assertEqual(model.mr[4], dut.core.mr4)

    def _test_bursts(self, clk_freq, delay, pushout=0.0, uncertain=False, n=12, seed=0):
        rng   = random.Random(seed)
        dut   = _DUT(clk_freq)
        model = OPIPSRAMModel(dut.phy, clk_freq, delay=delay, pushout=pushout, uncertain=uncertain,
            seed=seed)
        ref   = {}
        def gen():
            yield from wait_ready(dut, self)
            for i in range(n):
                length = rng.choice([1, 2, 7, 64, 300, 600])
                addr   = rng.randrange(CAL_AREA, 64*1024, 2)
                if i % 2 == 0 or not ref:
                    words = [rng.randrange(2**16) for _ in range(length)]
                    wes   = [rng.choice([0b11, 0b11, 0b01, 0b10, 0b00]) for _ in range(length)]
                    yield from native_write(dut.core, addr, words, wes)
                    for j, (w, we) in enumerate(zip(words, wes)):
                        for b in range(2):
                            if (we >> b) & 1:
                                ref[addr + 2*j + b] = (w >> 8*b) & 0xff
                else:
                    words = yield from native_read(dut.core, addr, length)
                    # Model memory initialized to 0.
                    for j in range(length):
                        for b in range(2):
                            a = addr + 2*j + b
                            self.assertEqual((words[j] >> 8*b) & 0xff, ref.get(a, 0), hex(a))
            self.assertFalse((yield dut.core.timeout))
            self.assertFalse((yield dut.core.underrun))
        run(dut, model, [gen()], timeout=400000)
        self.check_model(model)

    def test_bursts(self):
        for delay in [0, 5, 10]:
            with self.subTest(delay=delay):
                self._test_bursts(CLK_FREQ, delay=delay, seed=delay)

    def test_bursts_refresh_pushout(self):
        self._test_bursts(CLK_FREQ, delay=4, pushout=0.3, seed=1)

    def test_bursts_uncertain_samples(self):
        # First sample of each byte unreliable: second sample (rx_sample=1) used.
        self._test_bursts(CLK_FREQ, delay=7, uncertain=True, seed=2)

    def test_bursts_67mhz(self):
        self._test_bursts(67.1e6, delay=6, pushout=0.2, n=8, seed=3)

    def test_wishbone(self):
        for data_width in [32, 64]:
            with self.subTest(data_width=data_width):
                rng   = random.Random(data_width)
                dut   = _DUT(CLK_FREQ, data_width=data_width)
                model = OPIPSRAMModel(dut.phy, CLK_FREQ, delay=5, pushout=0.2, seed=data_width)
                bus   = dut.wb.bus
                nbytes = data_width//8
                def gen():
                    yield from wait_ready(dut, self)
                    ref = {}
                    for i in range(24):
                        adr = CAL_AREA//nbytes + rng.randrange(256)
                        if i % 3 != 2:
                            dat = rng.randrange(2**data_width)
                            sel = rng.choice([2**nbytes - 1, rng.randrange(2**nbytes)])
                            yield from bus.write(adr, dat, sel=sel)
                            for b in range(nbytes):
                                if (sel >> b) & 1:
                                    ref[adr*nbytes + b] = (dat >> 8*b) & 0xff
                        else:
                            dat = yield from bus.read(adr)
                            for b in range(nbytes):
                                self.assertEqual((dat >> 8*b) & 0xff, ref.get(adr*nbytes + b, 0))
                run(dut, model, [gen()])
                self.check_model(model)

    def test_init_error(self):
        # No read data from the device: initialization error, Wishbone accesses still acknowledged.
        dut   = _DUT(CLK_FREQ, data_width=32)
        model = OPIPSRAMModel(dut.phy, CLK_FREQ, dead=True)
        def gen():
            while not (yield dut.core.init_error):
                yield
            self.assertFalse((yield dut.core.ready))
            yield from dut.wb.bus.write(0x100, 0x12345678)
            self.assertEqual((yield from dut.wb.bus.read(0x100)), 0)
        run(dut, model, [gen()])

    def test_underrun(self):
        dut   = _DUT(CLK_FREQ)
        model = OPIPSRAMModel(dut.phy, CLK_FREQ, delay=3)
        def gen():
            yield from wait_ready(dut, self)
            yield dut.core.cmd.valid.eq(1)
            yield dut.core.cmd.we.eq(1)
            yield dut.core.cmd.addr.eq(0x100)
            yield dut.core.cmd.len.eq(4)
            yield
            yield dut.core.cmd.valid.eq(0)
            for _ in range(64):
                yield
            self.assertTrue((yield dut.core.underrun))
        run(dut, model, [gen()])

# Conversion ---------------------------------------------------------------------------------------

class TestOPIPSRAMConversion(unittest.TestCase):
    def test_gw5a(self):
        pads = Record(PADS_LAYOUT)
        top  = OPIPSRAM(pads, 67.1e6, data_width=64)
        top.clock_domains.cd_sys   = ClockDomain()
        top.clock_domains.cd_sys2x = ClockDomain(reset_less=True)
        v = str(verilog.convert(top,
            ios               = {*pads.flatten(), top.cd_sys.clk, top.cd_sys.rst, top.cd_sys2x.clk},
            special_overrides = {**gowin_special_overrides, **gw5a_special_overrides},
        ))
        # CE#, CLK, DQS and DQ serializers, DQS and DQ deserializers/IOBUFs.
        self.assertEqual(len(re.findall(r"\nOSER4 ", v)), 11)
        self.assertEqual(len(re.findall(r"\nIDES4 ", v)),  9)
        self.assertEqual(len(re.findall(r"\nIOBUF ", v)),  9)

    def test_generic_needs_lowering(self):
        pads = Record(PADS_LAYOUT)
        top  = OPIPSRAM(pads, 67.1e6)
        top.clock_domains.cd_sys   = ClockDomain()
        top.clock_domains.cd_sys2x = ClockDomain(reset_less=True)
        with self.assertRaises(NotImplementedError):
            ios = {*pads.flatten(), top.cd_sys.clk, top.cd_sys.rst, top.cd_sys2x.clk}
            verilog.convert(top, ios=ios)
