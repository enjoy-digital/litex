#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""HyperRAM controller (AXI4, streaming oriented).

Runs at the HyperRAM clock frequency with a PHY based on DDR IO registers and transfers one full
DDR word (2 x DQ width) per cycle: a x16 HyperRAM at 200MHz gives 800MB/s peak. This differs from
`litex.soc.cores.hyperbus.HyperRAM` (generic fabric oversampling PHY, CK = PHY clock / 4) and
requires a vendor PHY (see `litex.soc.cores.hyperram.phy`).

Architecture:
- AXI4 slave (INCR bursts, data width = 2 x DQ width), AW/AR command queues, bursts split to
  respect tCSM, read/write arbitration, W/R data FIFOs: a command is only issued when its whole
  write data is buffered (or when its whole read data can be stored), so CK never stalls.
- Burst continuation: sequential commands in the same direction continue the HyperRAM burst (CS#
  kept low up to tCSM).
- Core FSM: CA (3 CK) -> fixed 2x latency -> data -> CS high / tRWR.
- PHY interface (`HyperRAMPHYInterface`): per core cycle, CS#/CK enable/DQ/RWDS output words
  (HI = first edge, LO = second edge) and DDR captured DQ/RWDS input words (HI = first in time) in
  a separate capture clock domain. Read words are extracted from the RWDS strobe pattern (both
  word alignments supported) and cross to the core domain through an async FIFO.
- Read calibration (`HyperRAMCalibration`): when the PHY can shift its capture clock phase, a
  pattern is written/read back at startup for each phase and the center of the passing window is
  selected (gateware only, no software needed).
"""

import math

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen import *

from litex.soc.interconnect import axi, stream, wishbone
from litex.soc.interconnect.csr import *

from litex.soc.cores.hyperram.common import *
from litex.soc.cores.hyperram.calibration import HyperRAMCalibration

# Read Capture -------------------------------------------------------------------------------------

class _HyperRAMReadCapture(LiteXModule):
    """Extract read words from DDR captured DQ/RWDS (runs in the capture clock domain).

    During a read, the device drives RWDS high with the first half-word and low with the second
    one. Depending on the capture clock phase, a word is either fully captured in one cycle
    (HI=first, LO=second) or straddles two cycles (LO of cycle n = first, HI of cycle n+1 =
    second): both alignments are supported.
    """
    def __init__(self, phy_if):
        dw = phy_if.dq_width
        self.enable = Signal()
        self.source = source = stream.Endpoint([("data", 2*dw)])

        # # #

        rwds_hi = phy_if.rwds_i_hi[0]
        rwds_lo = phy_if.rwds_i_lo[0]

        # Register inputs.
        dq_hi   = Signal(dw)
        dq_lo   = Signal(dw)
        s_hi    = Signal()
        s_lo    = Signal()
        en      = Signal()
        self.sync += [
            dq_hi.eq(phy_if.dq_i_hi),
            dq_lo.eq(phy_if.dq_i_lo),
            s_hi.eq(rwds_hi),
            s_lo.eq(rwds_lo),
            en.eq(self.enable),
        ]

        # Odd alignment: first half in LO, second half in next HI.
        pending      = Signal()
        pending_data = Signal(dw)
        self.sync += [
            source.valid.eq(0),
            pending.eq(0),
            If(en,
                If(s_hi & ~s_lo,
                    # Even alignment.
                    source.valid.eq(1),
                    source.data.eq(Cat(dq_lo, dq_hi)),
                ).Elif(pending & ~s_hi,
                    source.valid.eq(1),
                    source.data.eq(Cat(dq_hi, pending_data)),
                ),
                If(s_lo & ~s_hi,
                    pending.eq(1),
                    pending_data.eq(dq_lo),
                ),
            ),
        ]

# AXI Burst Splitter -------------------------------------------------------------------------------

class _HyperRAMBurstSplitter(LiteXModule):
    """Split AXI AW/AR INCR bursts in HyperRAM commands of at most `max_words` words."""
    def __init__(self, ax, max_words, word_bytes, id_width):
        self.source = source = stream.Endpoint([
            ("addr", 32), ("len", 9), ("id", id_width)])

        # # #

        addr   = Signal(32)
        left   = Signal(9) # Remaining words (1-256).
        txn_id = Signal(id_width)
        busy   = Signal()
        n      = Signal(9)

        self.comb += [
            n.eq(Mux(left > max_words, max_words, left)),
            source.valid.eq(busy),
            source.addr.eq(addr),
            source.len.eq(n),
            source.id.eq(txn_id),
            source.last.eq(left == n),
            ax.ready.eq(~busy),
        ]
        self.sync += [
            If(ax.valid & ax.ready,
                busy.eq(1),
                addr.eq(ax.addr),
                left.eq(ax.len + 1),
                txn_id.eq(ax.id),
            ),
            If(source.valid & source.ready,
                addr.eq(addr + n*word_bytes),
                left.eq(left - n),
                If(left == n, busy.eq(0)),
            ),
        ]

# HyperRAM Core ------------------------------------------------------------------------------------

class HyperRAMCore(LiteXModule):
    """HyperRAM controller core (AXI4 slave).

    Parameters:
    - phy_if       : HyperRAMPHYInterface.
    - clk_freq     : Core (= HyperRAM CK) frequency.
    - latency      : HyperRAM initial latency (CK cycles, fixed 2x latency used).
    - axi_id_width : AXI ID width.
    - fifo_depth   : W/R data FIFOs depth (words), must be >= max burst words.
    - cmd_depth    : AW/AR command FIFOs depth (lets masters queue bursts/write data ahead).
    - max_words    : Max words per HyperRAM burst (default: from tCSM, at most 256).
    - size         : HyperRAM size in bytes (AXI addresses are masked to it, ex to ignore the SoC
                     region base).
    - with_continuation : Continue the HyperRAM burst with the next AXI command when sequential and
                     in the same direction (CS# kept low up to tCSM, saving CA/latency/tRWR).
    - arbitration_words : Words after which a continued burst is ended when the other direction
                     is waiting (read/write fairness for concurrent streams, ex framebuffers).
    - with_reset   : Pulse RST# and wait tVCS at startup.
    """
    def __init__(self, phy_if, clk_freq, latency=7, axi_id_width=4, fifo_depth=512, max_words=None,
        size=None, cmd_depth=8, with_continuation=True, arbitration_words=256, with_reset=True,
        with_csr=True):
        dw         = phy_if.dq_width
        word_width = 2*dw
        word_bytes = word_width//8
        if max_words is None:
            # Largest power of two burst keeping CS# low time (CA + latency + data) below tCSM.
            tcsm_words = int(HYPERRAM_TCSM*clk_freq) - 3 - 2*latency - 8
            max_words  = 256
            while max_words > tcsm_words and max_words > 1:
                max_words //= 2
        if max_words < 1 or max_words > 256:
            raise ValueError("HyperRAM clock too low for tCSM.")
        if fifo_depth < max_words:
            raise ValueError("HyperRAM fifo_depth must be >= max_words.")
        # Max words per CS# low period (CA + latency + data below tCSM).
        cs_words_max = max(max_words, int(HYPERRAM_TCSM*clk_freq) - 3 - 2*latency - 8)
        # CS# high time between accesses: tRWR, and at least the read capture window close delay
        # (+2: CS# hold cycles added by the PHY after the last CK cycle).
        trwr_cycles = max(4, math.ceil(HYPERRAM_TRWR*clk_freq)) + 2

        self.bus = bus = axi.AXIInterface(
            data_width    = word_width,
            address_width = 32,
            id_width      = axi_id_width,
        )
        self.max_words = max_words

        # Config/Status.
        self.latency       = Signal(4, reset=latency)
        self.ready         = Signal()
        self.read_timeouts = Signal(32)

        # Register Interface (0: ID0, 1: ID1, 2: CR0, 3: CR1).
        self.reg = reg = wishbone.Interface(data_width=16, address_width=4, addressing="word")

        # # #

        # Startup: RST# pulse + tVCS.
        # ---------------------------
        if with_reset:
            startup_cycles = int((HYPERRAM_TVCS + 2e-6)*clk_freq)
            startup = Signal(max=startup_cycles + 1, reset=startup_cycles)
            self.sync += If(startup != 0, startup.eq(startup - 1))
            self.comb += [
                phy_if.rst_n.eq(startup < (startup_cycles - int(1e-6*clk_freq))),
                self.ready.eq(startup == 0),
            ]
        else:
            self.comb += self.ready.eq(1)

        # Command FIFOs/Splitters.
        # ------------------------
        # Note: buffered (synchronous read) FIFOs, async read memories are not reliably implemented
        # on all FPGAs (observed on Efinix Titanium with depth > 2).
        self.aw_fifo = aw_fifo = stream.SyncFIFO(bus.aw.description, cmd_depth, buffered=True)
        self.ar_fifo = ar_fifo = stream.SyncFIFO(bus.ar.description, cmd_depth, buffered=True)
        self.comb += [
            bus.aw.connect(aw_fifo.sink),
            bus.ar.connect(ar_fifo.sink),
        ]
        split_kwargs = dict(max_words=max_words, word_bytes=word_bytes, id_width=axi_id_width)
        self.aw_split = aw_split = _HyperRAMBurstSplitter(aw_fifo.source, **split_kwargs)
        self.ar_split = ar_split = _HyperRAMBurstSplitter(ar_fifo.source, **split_kwargs)

        # Write data FIFO.
        # ----------------
        w_layout = [("data", word_width), ("strb", word_bytes)]
        self.w_fifo = w_fifo = stream.SyncFIFO(w_layout, fifo_depth, buffered=True)
        self.comb += [
            w_fifo.sink.valid.eq(bus.w.valid),
            bus.w.ready.eq(w_fifo.sink.ready),
            w_fifo.sink.data.eq(bus.w.data),
            w_fifo.sink.strb.eq(bus.w.strb),
        ]

        # B responses.
        # ------------
        self.b_fifo = b_fifo = stream.SyncFIFO([("id", axi_id_width)], 8)
        self.comb += [
            bus.b.valid.eq(b_fifo.source.valid),
            bus.b.id.eq(b_fifo.source.id),
            bus.b.resp.eq(axi.RESP_OKAY),
            b_fifo.source.ready.eq(bus.b.ready),
        ]

        # Read data: capture (cd_cap) -> async FIFO -> R FIFO.
        # ----------------------------------------------------
        self.capture = capture = ClockDomainsRenamer(phy_if.cd_cap)(_HyperRAMReadCapture(phy_if))
        cap_en = Signal()
        self.specials += MultiReg(cap_en, capture.enable, odomain=phy_if.cd_cap, n=2)
        if phy_if.cd_cap == "sys":
            cap_source = capture.source
        else:
            self.cap_cdc = cap_cdc = stream.ClockDomainCrossing([("data", word_width)],
                cd_from = phy_if.cd_cap,
                cd_to   = "sys",
                depth   = 16,
            )
            self.comb += capture.source.connect(cap_cdc.sink)
            cap_source = cap_cdc.source

        r_layout = [("data", word_width), ("resp", 2)]
        self.r_fifo = r_fifo = stream.SyncFIFO(r_layout, fifo_depth, buffered=True)
        rd_cmd = stream.SyncFIFO([("len", 9), ("id", axi_id_width)], 4)
        self.rd_cmd = rd_cmd

        # Words routed to the register interface or R FIFO; timeouts inject error beats.
        rd_reg        = Signal()          # Current read is a register read.
        rd_expected   = Signal(11)        # Words still expected for the current read.
        rd_add        = Signal(9)         # Words added to the current read (continuation).
        rd_inject     = Signal()
        self.comb += [
            r_fifo.sink.valid.eq(~rd_reg & (((cap_source.valid & (rd_expected != 0)) | rd_inject))),
            r_fifo.sink.data.eq(cap_source.data),
            r_fifo.sink.resp.eq(Mux(rd_inject, axi.RESP_SLVERR, axi.RESP_OKAY)),
            cap_source.ready.eq(1),
        ]

        # R channel: beats from R FIFO, id/last from read commands.
        r_count = Signal(9)
        r_last  = Signal()
        self.comb += r_last.eq(r_count == (rd_cmd.source.len - 1))
        self.comb += [
            bus.r.valid.eq(r_fifo.source.valid & rd_cmd.source.valid),
            bus.r.data.eq(r_fifo.source.data),
            bus.r.resp.eq(r_fifo.source.resp),
            bus.r.id.eq(rd_cmd.source.id),
            bus.r.last.eq(r_last & rd_cmd.source.last),
            r_fifo.source.ready.eq(bus.r.ready & rd_cmd.source.valid),
            rd_cmd.source.ready.eq(bus.r.valid & bus.r.ready & r_last),
        ]
        self.sync += If(bus.r.valid & bus.r.ready,
            r_count.eq(r_count + 1),
            If(r_last, r_count.eq(0)),
        )

        # R FIFO space reservation (words reserved for issued reads, released when sent on R).
        r_reserved = Signal(max=fifo_depth + 257)
        r_reserve  = Signal(9)
        self.sync += r_reserved.eq(r_reserved + r_reserve - (bus.r.valid & bus.r.ready))

        # Write data level (words available in W FIFO).
        w_level = Signal(max=fifo_depth + 2)
        self.comb += w_level.eq(w_fifo.level)

        # Command Arbitration.
        # --------------------
        cmd_we     = Signal()
        cmd_reg    = Signal()
        cmd_addr   = Signal(32)
        cmd_len    = Signal(9)
        cmd_id     = Signal(axi_id_width)
        cmd_last   = Signal()
        last_write = Signal()

        w_ok = aw_split.source.valid & (w_level >= aw_split.source.len) & b_fifo.sink.ready
        r_ok = (
            ar_split.source.valid &
            ((r_reserved + ar_split.source.len) <= fifo_depth) &
            rd_cmd.sink.ready
        )
        sel_w = Signal()
        self.comb += sel_w.eq(Mux(w_ok & r_ok, ~last_write, w_ok))

        # Burst continuation: next command sequential, same direction, fits in tCSM.
        cs_words = Signal(max=cs_words_max + 257)
        next_w   = Signal()
        next_r   = Signal()
        if with_continuation:
            # Fairness: yield to the other direction after arbitration_words when it is waiting.
            yield_w = r_ok & (cs_words >= arbitration_words)
            yield_r = w_ok & (cs_words >= arbitration_words)
            self.comb += [
                next_w.eq(
                    ~yield_w &
                    aw_split.source.valid &
                    (aw_split.source.addr == (cmd_addr + cmd_len*word_bytes)) &
                    (w_level >= (aw_split.source.len + 1)) &   # +1: current word still in FIFO.
                    (b_fifo.level < (b_fifo.depth - 1)) &
                    ((cs_words + aw_split.source.len) <= cs_words_max)
                ),
                next_r.eq(
                    ~yield_r &
                    ar_split.source.valid &
                    (ar_split.source.addr == (cmd_addr + cmd_len*word_bytes)) &
                    ((r_reserved + ar_split.source.len) <= fifo_depth) &
                    rd_cmd.sink.ready &
                    ((cs_words + ar_split.source.len) <= cs_words_max)
                ),
            ]

        # CA generation.
        # --------------
        ca      = Signal(48)
        waddr   = Signal(32)
        addr_mask = (2**32 - 1) if size is None else (size - 1)
        self.comb += waddr.eq((cmd_addr & addr_mask)[log2_int(word_bytes):])
        self.comb += If(cmd_reg,
            ca[47].eq(~cmd_we),
            ca[46].eq(1),
            ca[45].eq(1),
            Case(reg.adr[:2], {
                0 : ca[0:40].eq(0x00_00_00_00_00),
                1 : ca[0:40].eq(0x00_00_00_00_01),
                2 : ca[0:40].eq(0x00_01_00_00_00),
                3 : ca[0:40].eq(0x00_01_00_00_01),
            }),
        ).Else(
            ca[47].eq(~cmd_we),
            ca[46].eq(0),
            ca[45].eq(1),             # Linear burst.
            ca[16:45].eq(waddr[3:]),  # Row & upper column address.
            ca[0:3].eq(waddr[0:3]),   # Lower column address.
        )
        ca_bytes = [ca[48 - 8*(i + 1):48 - 8*i] for i in range(6)]

        # FSM.
        # ----
        count     = Signal(10)
        data_wait = Signal(5)
        # CK cycles from end of CA to first data (fixed 2x latency).
        self.comb += data_wait.eq(2*self.latency - 1)

        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(self.ready,
                If(reg.stb & reg.cyc,
                    NextValue(cmd_reg, 1),
                    NextValue(cmd_we,  reg.we),
                    NextValue(cmd_len, 1),
                    NextState("CA0"),
                ).Elif(w_ok | r_ok,
                    NextValue(cs_words, Mux(sel_w, aw_split.source.len, ar_split.source.len)),
                    NextValue(cmd_reg,    0),
                    NextValue(cmd_we,     sel_w),
                    NextValue(last_write, sel_w),
                    If(sel_w,
                        aw_split.source.ready.eq(1),
                        NextValue(cmd_addr, aw_split.source.addr),
                        NextValue(cmd_len,  aw_split.source.len),
                        NextValue(cmd_id,   aw_split.source.id),
                        NextValue(cmd_last, aw_split.source.last),
                    ).Else(
                        ar_split.source.ready.eq(1),
                        rd_cmd.sink.valid.eq(1),
                        rd_cmd.sink.len.eq(ar_split.source.len),
                        rd_cmd.sink.id.eq(ar_split.source.id),
                        rd_cmd.sink.last.eq(ar_split.source.last),
                        r_reserve.eq(ar_split.source.len),
                        NextValue(cmd_addr, ar_split.source.addr),
                        NextValue(cmd_len,  ar_split.source.len),
                    ),
                    NextState("CA0"),
                )
            )
        )
        for i in range(3):
            fsm.act(f"CA{i}",
                phy_if.cs_n.eq(0),
                phy_if.ck_en.eq(1),
                phy_if.dq_oe.eq(1),
                phy_if.dq_o_hi.eq(ca_bytes[2*i + 0]),
                phy_if.dq_o_lo.eq(ca_bytes[2*i + 1]),
                NextValue(count, 0),
                If(cmd_reg & cmd_we,
                    NextState("REG-WRITE")
                ).Else(
                    NextState("LATENCY")
                ) if i == 2 else NextState(f"CA{i+1}")
            )
        fsm.act("LATENCY",
            phy_if.cs_n.eq(0),
            phy_if.ck_en.eq(1),
            # Open read capture window ahead of the first data (RWDS is low during latency).
            cap_en.eq(~cmd_we & (count + 6 >= data_wait)),
            NextValue(count, count + 1),
            If(count == (data_wait - 1),
                NextValue(count, 0),
                If(cmd_we,
                    NextState("WRITE")
                ).Else(
                    NextValue(rd_reg, cmd_reg),
                    rd_add.eq(cmd_len),
                    NextState("READ")
                )
            )
        )
        fsm.act("REG-WRITE",
            phy_if.cs_n.eq(0),
            phy_if.ck_en.eq(1),
            phy_if.dq_oe.eq(1),
            phy_if.dq_o_hi.eq(reg.dat_w[8:16]),
            phy_if.dq_o_lo.eq(reg.dat_w[0:8]),
            reg.ack.eq(1),
            NextState("END"),
        )
        fsm.act("WRITE",
            phy_if.cs_n.eq(0),
            phy_if.ck_en.eq(1),
            phy_if.dq_oe.eq(1),
            phy_if.rwds_oe.eq(1),
            phy_if.dq_o_hi.eq(w_fifo.source.data[dw:]),
            phy_if.dq_o_lo.eq(w_fifo.source.data[:dw]),
            phy_if.rwds_o_hi.eq(~w_fifo.source.strb[dw//8:]),
            phy_if.rwds_o_lo.eq(~w_fifo.source.strb[:dw//8]),
            w_fifo.source.ready.eq(1),
            NextValue(count, count + 1),
            If(count == (cmd_len - 1),
                If(cmd_last,
                    b_fifo.sink.valid.eq(1),
                    b_fifo.sink.id.eq(cmd_id),
                ),
                NextValue(count, 0),
                If(next_w,
                    aw_split.source.ready.eq(1),
                    NextValue(cmd_addr, aw_split.source.addr),
                    NextValue(cmd_len,  aw_split.source.len),
                    NextValue(cmd_id,   aw_split.source.id),
                    NextValue(cmd_last, aw_split.source.last),
                    NextValue(cs_words, cs_words + aw_split.source.len),
                ).Else(
                    NextState("END"),
                )
            )
        )
        fsm.act("READ",
            phy_if.cs_n.eq(0),
            phy_if.ck_en.eq(1),
            cap_en.eq(1),
            NextValue(count, count + 1),
            If(count == (cmd_len - 1),
                NextValue(count, 0),
                If(next_r & ~cmd_reg,
                    ar_split.source.ready.eq(1),
                    rd_cmd.sink.valid.eq(1),
                    rd_cmd.sink.len.eq(ar_split.source.len),
                    rd_cmd.sink.id.eq(ar_split.source.id),
                    rd_cmd.sink.last.eq(ar_split.source.last),
                    r_reserve.eq(ar_split.source.len),
                    rd_add.eq(ar_split.source.len),
                    NextValue(cmd_addr, ar_split.source.addr),
                    NextValue(cmd_len,  ar_split.source.len),
                    NextValue(cs_words, cs_words + ar_split.source.len),
                ).Else(
                    NextState("READ-WAIT"),
                )
            )
        )
        # Wait for the read words to cross the capture path (CS# high, no CK).
        read_timeout = 64
        fsm.act("READ-WAIT",
            cap_en.eq(1),
            NextValue(count, count + 1),
            If(rd_expected == 0,
                NextValue(count, 0),
                NextState("END"),
            ).Elif(count == (read_timeout - 1),
                NextValue(self.read_timeouts, self.read_timeouts + 1),
                NextValue(count, 0),
                NextState("READ-FLUSH"),
            )
        )
        # Timeout: complete the read with error beats so the AXI master never hangs.
        fsm.act("READ-FLUSH",
            If(rd_expected == 0,
                NextState("END"),
            ).Elif(rd_reg,
                reg.ack.eq(1),
                rd_inject.eq(1), # Consumes the missing register word (not sent to the R FIFO).
            ).Else(
                rd_inject.eq(~cap_source.valid),
            )
        )
        fsm.act("END",
            NextValue(count, count + 1),
            If(count >= (trwr_cycles - 1),
                NextValue(count, 0),
                NextState("IDLE"),
            )
        )

        # Read words accounting.
        rd_dec = Signal()
        self.comb += rd_dec.eq((cap_source.valid | rd_inject) & (rd_expected != 0))
        self.sync += [
            rd_expected.eq(rd_expected - rd_dec + rd_add),
            If(rd_dec,
                If(rd_reg & cap_source.valid,
                    # Register data: MSB on first edge, LSB on second edge (DQ[7:0]).
                    reg.dat_r.eq(Cat(cap_source.data[0:8], cap_source.data[dw:dw+8])),
                ),
            ),
        ]
        self.comb += If(fsm.ongoing("READ-WAIT") & rd_reg & (rd_expected == 0), reg.ack.eq(1))

        # CSRs.
        # -----
        if with_csr:
            self.add_csr()

    def add_csr(self):
        # Config/Status Interface.
        # ------------------------
        self.config = CSRStorage(fields=[
            CSRField("latency", offset=0, size=4, reset=self.latency.reset.value,
                description="HyperRAM Latency (X1, fixed 2x latency is used)."),
        ])
        self.status = CSRStatus(fields=[
            CSRField("ready",     offset=0, size=1, description="HyperRAM startup done."),
            CSRField("max_words", offset=8, size=9, reset=self.max_words,
                description="Max words per HyperRAM command."),
        ])
        self.timeouts = CSRStatus(32, description="Read timeouts (missing read words).")
        self.comb += [
            self.latency.eq(self.config.fields.latency),
            self.status.fields.ready.eq(self.ready),
            self.timeouts.status.eq(self.read_timeouts),
        ]

        # Reg Interface.
        # --------------
        self.reg_control = CSRStorage(fields=[
            CSRField("write", offset=0, size=1, pulse=True, description="Issue Register Write."),
            CSRField("read",  offset=1, size=1, pulse=True, description="Issue Register Read."),
            CSRField("addr",  offset=8, size=2, description="Register access address.", values=[
                ("``0b00``", "Identification Register 0 (Read Only)."),
                ("``0b01``", "Identification Register 1 (Read Only)."),
                ("``0b10``", "Configuration Register 0."),
                ("``0b11``", "Configuration Register 1."),
            ]),
        ])
        self.reg_status = CSRStatus(fields=[
            CSRField("done", offset=0, size=1, description="Register Access Done."),
        ])
        self.reg_wdata = CSRStorage(16, description="Register Write Data.")
        self.reg_rdata = CSRStatus( 16, description="Register Read Data.")

        self.reg_fsm = reg_fsm = FSM(reset_state="IDLE")
        reg_fsm.act("IDLE",
            self.reg_status.fields.done.eq(1),
            If(self.reg_control.fields.write,
                NextState("WRITE")
            ).Elif(self.reg_control.fields.read,
                NextState("READ")
            )
        )
        reg_fsm.act("WRITE",
            self.reg.cyc.eq(1),
            self.reg.stb.eq(1),
            self.reg.we.eq(1),
            self.reg.adr.eq(self.reg_control.fields.addr),
            self.reg.dat_w.eq(self.reg_wdata.storage),
            If(self.reg.ack,
                NextState("IDLE")
            )
        )
        reg_fsm.act("READ",
            self.reg.cyc.eq(1),
            self.reg.stb.eq(1),
            self.reg.we.eq(0),
            self.reg.adr.eq(self.reg_control.fields.addr),
            If(self.reg.ack,
                NextValue(self.reg_rdata.status, self.reg.dat_r),
                NextState("IDLE")
            )
        )

# HyperRAM Controller ------------------------------------------------------------------------------

class HyperRAMController(LiteXModule):
    """HyperRAM controller (PHY + core, optional read capture calibration).

    With a PHY providing a capture phase control, the read capture phase is calibrated at startup
    (and on `calibrate` CSR writes); the AXI bus is held off until calibration is done.
    """
    def __init__(self, phy, clk_freq, with_calibration=True, with_csr=True, **kwargs):
        self.phy  = phy
        self.core = core = HyperRAMCore(phy.phy_if, clk_freq=clk_freq, with_csr=with_csr, **kwargs)
        self.bus  = bus  = axi.AXIInterface(
            data_width    = core.bus.data_width,
            address_width = 32,
            id_width      = len(core.bus.aw.id),
        )

        # # #

        if not (with_calibration and getattr(phy, "phase_steps", 0)):
            self.comb += bus.connect(core.bus)
            return

        cal_bus = axi.AXIInterface(
            data_width    = core.bus.data_width,
            address_width = 32,
            id_width      = len(core.bus.aw.id),
        )
        self.cal = cal = HyperRAMCalibration(cal_bus, phy)

        # Start calibration once the core is ready (and on CSR request).
        cal_req   = Signal(reset=1)
        cal_start = Signal()
        self.comb += cal_start.eq(cal_req & core.ready & cal.fsm.ongoing("IDLE"))
        self.sync += If(cal_start, cal_req.eq(0))
        self.comb += cal.start.eq(cal_start)
        busy = Signal(reset=1)
        self.sync += [
            If(cal_start,
                busy.eq(1),
            ).Elif(cal.done,
                busy.eq(0),
            )
        ]
        self.comb += If(busy,
            cal_bus.connect(core.bus),
        ).Else(
            bus.connect(core.bus),
        )

        if with_csr:
            self.calibration = CSRStatus(fields=[
                CSRField("done",   offset=0,  size=1, description="Calibration done."),
                CSRField("error",  offset=1,  size=1, description="Calibration failed."),
                CSRField("phase",  offset=8,  size=8, description="Selected capture phase."),
                CSRField("passes", offset=16, size=8, description="Passing phases (1 bit/phase)."),
            ])
            self.calibrate = CSR()
            self.comb += [
                self.calibration.fields.done.eq(~busy & cal.done),
                self.calibration.fields.error.eq(cal.error),
                self.calibration.fields.phase.eq(cal.phase),
                self.calibration.fields.passes.eq(cal.passes),
            ]
            self.sync += If(self.calibrate.re, cal_req.eq(1))
