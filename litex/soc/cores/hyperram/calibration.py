#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""HyperRAM read capture calibration (gateware)."""

from migen import *

from litex.gen import *

from litex.soc.interconnect import axi

# Read Calibration ---------------------------------------------------------------------------------

def hyperram_best_phase(passes, nphases):
    """Center of the largest (circular) window of passing phases, None if none passes."""
    if passes == 0:
        return None
    if passes == (2**nphases - 1):
        return 0
    best_len, best_start = 0, 0
    for start in range(nphases):
        # Window starts on a passing phase preceded by a failing one.
        if not (passes >> start) & 1 or (passes >> ((start - 1) % nphases)) & 1:
            continue
        length = 0
        while (passes >> ((start + length) % nphases)) & 1:
            length += 1
        if length > best_len:
            best_len, best_start = length, start
    return (best_start + (best_len - 1)//2) % nphases

class HyperRAMCalibration(LiteXModule):
    """Read capture phase calibration (gateware).

    Writes a pattern at `address` and, for each capture phase, reads it back `rounds` times as one
    long burst (`words`) and as single-word reads (`single_words`); a phase passes when all reads
    match. Marginal phases (capture near RWDS/DQ transitions, twice per CK period) can pass short
    reads but fail long ones, so long bursts are used. Selects the center of the largest window of
    passing phases. Memory at `address` is overwritten.
    """
    def __init__(self, bus, phy, address=0x0, words=128, single_words=16, rounds=4,
        settle_cycles=256):
        nphases     = phy.phase_steps
        dw          = len(bus.w.data)
        self.start  = Signal()
        self.done   = Signal()
        self.error  = Signal()
        self.passes = Signal(nphases)
        self.phase  = Signal(max=nphases)

        # # #

        patterns = [
            0x00000000, 0xffffffff, 0xaaaa5555, 0x5555aaaa, 0x0001fffe, 0xfffe0001, 0x12345678,
            0x9abcdef0, 0x0f0f0f0f, 0xf0f0f0f0, 0x00ff00ff, 0xff00ff00, 0x13579bdf, 0x2468ace0,
            0x5a5aa5a5, 0xa5a55a5a,
        ]
        def pattern(i):
            return Cat(*[Constant(patterns[(i + j) % len(patterns)], 32) for j in range(dw//32)])

        count    = Signal(max=max(words, settle_cycles) + 1)
        index    = Signal(max=nphases + 1)
        ok       = Signal()
        single   = Signal()                 # Single-word reads (else burst read).
        rd_index = Signal(max=single_words) # Word of the single-word read.
        rnd      = Signal(max=rounds)
        expect   = Signal(dw)
        sel      = Signal(max=words)
        self.comb += sel.eq(Mux(single, rd_index, count))
        # 16 base patterns, made unique per word with the word index.
        base = Signal(dw)
        self.comb += Case(sel[:4], {i: base.eq(pattern(i)) for i in range(16)})
        self.comb += expect.eq(base ^ sel)

        best = Signal(max=nphases)
        self.comb += Case(self.passes, {
            m: best.eq(hyperram_best_phase(m, nphases) or 0) for m in range(2**nphases)})

        self.comb += [
            bus.aw.addr.eq(address),
            bus.aw.len.eq(words - 1),
            bus.aw.size.eq(log2_int(dw//8)),
            bus.aw.burst.eq(axi.BURST_INCR),
            bus.ar.addr.eq(address + Mux(single, rd_index*(dw//8), 0)),
            bus.ar.len.eq(Mux(single, 0, words - 1)),
            bus.ar.size.eq(log2_int(dw//8)),
            bus.ar.burst.eq(axi.BURST_INCR),
            bus.w.data.eq(expect),
            bus.w.strb.eq(2**(dw//8) - 1),
            bus.w.last.eq(count == (words - 1)),
        ]

        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(self.start,
                NextValue(self.done,   0),
                NextValue(self.error,  0),
                NextValue(self.passes, 0),
                NextValue(index, 0),
                NextValue(count, 0),
                NextState("WRITE-AW"),
            )
        )
        fsm.act("WRITE-AW",
            bus.aw.valid.eq(1),
            If(bus.aw.ready, NextState("WRITE-W"))
        )
        fsm.act("WRITE-W",
            bus.w.valid.eq(1),
            If(bus.w.ready,
                NextValue(count, count + 1),
                If(bus.w.last,
                    NextValue(count, 0),
                    NextState("WRITE-B"),
                )
            )
        )
        fsm.act("WRITE-B",
            bus.b.ready.eq(1),
            If(bus.b.valid, NextState("PHASE-LOAD"))
        )
        fsm.act("PHASE-LOAD",
            phy.phase.eq(index),
            phy.phase_load.eq(1),
            NextValue(count, 0),
            NextState("PHASE-SETTLE"),
        )
        fsm.act("PHASE-SETTLE",
            NextValue(count, count + 1),
            If(count == (settle_cycles - 1),
                NextValue(count, 0),
                NextValue(ok, 1),
                NextValue(single, 0),
                NextValue(rd_index, 0),
                NextValue(rnd, 0),
                NextState("READ-AR"),
            )
        )
        fsm.act("READ-AR",
            bus.ar.valid.eq(1),
            If(bus.ar.ready, NextState("READ-R"))
        )
        fsm.act("READ-R",
            bus.r.ready.eq(1),
            If(bus.r.valid,
                NextValue(count, count + 1),
                If((bus.r.data != expect) | (bus.r.resp != axi.RESP_OKAY),
                    NextValue(ok, 0),
                ),
                If(bus.r.last,
                    NextValue(count, 0),
                    NextState("READ-NEXT"),
                )
            )
        )
        fsm.act("READ-NEXT",
            If(~single,
                NextValue(single, 1),
                NextValue(rd_index, 0),
                NextState("READ-AR"),
            ).Elif(rd_index != (single_words - 1),
                NextValue(rd_index, rd_index + 1),
                NextState("READ-AR"),
            ).Elif(rnd != (rounds - 1),
                NextValue(rnd, rnd + 1),
                NextValue(single, 0),
                NextState("READ-AR"),
            ).Else(
                NextState("READ-DONE"),
            )
        )
        fsm.act("READ-DONE",
            NextValue(self.passes, self.passes | (ok << index)),
            NextValue(index, index + 1),
            If(index == (nphases - 1),
                NextState("SELECT"),
            ).Else(
                NextState("PHASE-LOAD"),
            )
        )
        fsm.act("SELECT",
            NextValue(self.phase, best),
            NextValue(self.error, self.passes == 0),
            phy.phase.eq(best),
            phy.phase_load.eq(1),
            NextValue(count, 0),
            NextState("SELECT-SETTLE"),
        )
        fsm.act("SELECT-SETTLE",
            NextValue(count, count + 1),
            If(count == (settle_cycles - 1),
                NextValue(self.done, 1),
                NextState("IDLE"),
            )
        )
