#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""
Octal DDR (OPI, x8) PSRAM core (Xccela protocol, ex: AP Memory APS6408L-OBMx).

Written from the AP Memory APS6408L-OBMx DDR OPI Xccela PSRAM datasheet, Rev. 3.7:
https://www.apmemory.com/en/product/iotram/OPIHPI

- PHY: memory CLK at the core clock rate (one CLK per cycle: 2 bytes), 4:1 SerDes on CE#/CLK/DQ/DQS
  (``sys2x`` DDR fast clock, generic SerDesOutput/SerDesTristate specials), DQS based read capture.
- Core: initialization (Global Reset, latency codes, read path calibration, ID), linear bursts with
  variable read latency (DQS), byte write masks (DM), bursts split at row boundaries and to bound
  the CE# low time (tCEM), tCPH/tRC.
- Native port (command/write data/read data streams) and Wishbone frontend.
"""

import math

from migen import *

from litex.gen import *

from litex.build.io import SerDesOutput, SerDesTristate

from litex.soc.interconnect.csr import *
from litex.soc.interconnect     import stream
from litex.soc.interconnect     import wishbone

# Constants ----------------------------------------------------------------------------------------

CMD_READ         = 0x20 # Linear burst read.
CMD_WRITE        = 0xa0 # Linear burst write.
CMD_MR_READ      = 0x40
CMD_MR_WRITE     = 0xc0
CMD_GLOBAL_RESET = 0xff

# Latency: (MR code, max CLK frequency).
READ_LATENCIES = { # MR0[4:2].
    3: (0b000,  66e6),
    4: (0b001, 109e6),
    5: (0b010, 133e6),
    6: (0b011, 166e6),
    7: (0b100, 200e6),
}
WRITE_LATENCIES = { # MR4[7:5].
    3: (0b000,  66e6),
    4: (0b100, 104e6),
    5: (0b010, 133e6),
    6: (0b110, 166e6),
    7: (0b001, 200e6),
}

DRIVE_STRENGTHS = { # MR0[1:0].
    "full"   : 0b00,
    "half"   : 0b01,
    "quarter": 0b10,
    "eighth" : 0b11,
}

def get_latency(latencies, clk_freq):
    """Lowest latency supported at clk_freq."""
    for latency, (_, fmax) in sorted(latencies.items()):
        if clk_freq <= fmax:
            return latency
    raise ValueError(f"Unsupported OPI PSRAM clock frequency {clk_freq/1e6:.2f}MHz.")

# Layouts ------------------------------------------------------------------------------------------

def opi_psram_cmd_layout(address_width=32, length_width=16):
    return [
        ("we",   1),             # 1: Write, 0: Read.
        ("addr", address_width), # Byte address (even).
        ("len",  length_width),  # Length (16-bit words, > 0).
    ]

def opi_psram_wdata_layout():
    return [
        ("data", 16), # [7:0]: Byte at addr, [15:8]: Byte at addr + 1.
        ("we",    2), # Byte write enables.
    ]

def opi_psram_rdata_layout():
    return [("data", 16)]

# OPI PSRAM PHY ------------------------------------------------------------------------------------

class OPIPSRAMPHY(LiteXModule):
    """
    OPI PSRAM PHY: CLK at the core clock rate, 4:1 SerDes (``cd_fast``: 2x core clock, DDR).

    Each core cycle: CE# (``cs_n``), one CLK (``clk_en``, 90° shifted: edges centered on the data),
    two DQ bytes (``dq_o``: [7:0] rising edge, [15:8] falling edge) and DQS/DM (``dqs_o``).

    Reads: DQ/DQS sampled 4 times per cycle (2 samples per byte); each DQS rising edge (with
    ``rx_en``, masked DQS samples read as low) captures a 16-bit word (``rx_valid``/``rx_data``),
    ``rx_sample`` selects the sample used in each byte after the DQS edge (0: first, 1: second).

    Pads: ``cs_n`` (or ``ce_n``), ``clk``, ``dq`` (8-bit), ``dqs`` (or ``rwds``), optional
    ``rst_n``.
    """
    def __init__(self, pads, cd_fast="sys2x", rx_sample=1):
        assert rx_sample in [0, 1]
        # TX.
        self.cs_n     = Signal(reset=1)
        self.clk_en   = Signal()
        self.dq_o     = Signal(16)
        self.dq_oe    = Signal()
        self.dqs_o    = Signal(2)
        self.dqs_oe   = Signal()

        # RX.
        self.rx_en    = Signal()
        self.rx_valid = Signal()
        self.rx_data  = Signal(16)

        # SerDes words (i[0]/o[0] first) and output enables.
        self.cs_n_word   = Signal(4, reset=0b1111)
        self.clk_word    = Signal(4)
        self.dq_words    = [Signal(4) for _ in range(8)]
        self.dq_oe_word  = Signal()
        self.dqs_word    = Signal(4)
        self.dqs_oe_word = Signal()
        self.dq_i_words  = [Signal(4) for _ in range(8)]
        self.dqs_i_word  = Signal(4)

        # # #

        # TX ---------------------------------------------------------------------------------------
        # Registered, CLK centered on the data: CLK rises after the 1st sample, falls after the 3rd.
        self.sync += [
            self.cs_n_word.eq(Replicate(self.cs_n, 4)),
            self.clk_word.eq(Cat(0, self.clk_en, self.clk_en, 0)),
            self.dqs_word.eq(Cat(self.dqs_o[0], self.dqs_o[0], self.dqs_o[1], self.dqs_o[1])),
        ]
        self.sync += [self.dq_words[n].eq(Cat(
            self.dq_o[0 + n], self.dq_o[0 + n],
            self.dq_o[8 + n], self.dq_o[8 + n],
        )) for n in range(8)]
        self.sync += [
            self.dq_oe_word.eq(self.dq_oe),
            self.dqs_oe_word.eq(self.dqs_oe),
        ]

        # RX ---------------------------------------------------------------------------------------
        # DQS/DQ samples of the last 3 cycles (12 samples, oldest first): DQS rising edges are
        # detected in the middle cycle, each edge captures 2 bytes (up to 4 samples later).
        dq_i = [Cat(*[self.dq_i_words[n][k] for n in range(8)]) for k in range(4)]
        dqs  = [Signal(4) for _ in range(3)]
        dq   = [[Signal(8) for _ in range(4)] for _ in range(3)]
        self.comb += dqs[2].eq(self.dqs_i_word & Replicate(self.rx_en, 4))
        self.comb += [dq[2][k].eq(dq_i[k]) for k in range(4)]
        self.sync += [
            dqs[0].eq(dqs[1]),
            dqs[1].eq(dqs[2]),
        ]
        self.sync += [dq[0][k].eq(dq[1][k]) for k in range(4)]
        self.sync += [dq[1][k].eq(dq[2][k]) for k in range(4)]
        dqs_window = Cat(*dqs)
        dq_window  = dq[0] + dq[1] + dq[2]
        # One DQS rising edge at most per cycle (DQS period: 4 samples).
        self.sync += self.rx_valid.eq(0)
        for k in range(4, 8):
            self.sync += If(~dqs_window[k - 1] & dqs_window[k],
                self.rx_valid.eq(1),
                self.rx_data.eq(Cat(dq_window[k + rx_sample], dq_window[k + 2 + rx_sample])),
            )

        # IOs --------------------------------------------------------------------------------------
        pads_cs_n = pads.cs_n if hasattr(pads, "cs_n") else pads.ce_n
        pads_dqs  = pads.dqs  if hasattr(pads, "dqs")  else pads.rwds
        if hasattr(pads, "rst_n"):
            self.comb += pads.rst_n.eq(1)
        # SerDes reset with the core clock domain reset (word alignment after a clock restart).
        clk      = ClockSignal()
        clk_fast = ClockSignal(cd_fast)
        rst      = ResetSignal()
        self.specials += [
            SerDesOutput(i=self.cs_n_word, o=pads_cs_n, clk=clk, clk_fast=clk_fast, rst=rst),
            SerDesOutput(i=self.clk_word,  o=pads.clk,  clk=clk, clk_fast=clk_fast, rst=rst),
            SerDesTristate(pads_dqs,
                o        = self.dqs_word,
                oe       = self.dqs_oe_word,
                i        = self.dqs_i_word,
                clk      = clk,
                clk_fast = clk_fast,
                rst      = rst,
            ),
        ]
        for n in range(8):
            self.specials += SerDesTristate(pads.dq[n],
                o        = self.dq_words[n],
                oe       = self.dq_oe_word,
                i        = self.dq_i_words[n],
                clk      = clk,
                clk_fast = clk_fast,
                rst      = rst,
            )

# OPI PSRAM Core -----------------------------------------------------------------------------------

class OPIPSRAMCore(LiteXModule):
    """
    OPI PSRAM controller (core clock domain, ``clk_freq``: memory CLK frequency).

    Native port:
    - ``cmd``   : Accesses (``we``, even byte ``addr``, ``len`` in 16-bit words).
    - ``wdata`` : Write data (``len`` words per write access), must be valid during the write burst
                  (underruns are masked and reported).
    - ``rdata`` : Read data (``len`` words per read access), no back-pressure.

    Initialization: Global Reset, read/write latency codes (MR0/MR4), read path calibration (latest
    DQS window start reading back a pattern written at address 0), ID (MR0 check, MR1/MR2).
    Accesses are split at ``page_size`` boundaries (no row crossing) and to bound CE# low time to
    ``tcem``.
    """
    def __init__(self, phy, clk_freq, size=8*1024*1024, page_size=1024,
        read_latency   = None,
        write_latency  = None,
        drive_strength = "half",
        tcem           = 4e-6,
        rx_offset_max  = 8):
        if read_latency is None:
            read_latency = get_latency(READ_LATENCIES, clk_freq)
        if write_latency is None:
            write_latency = get_latency(WRITE_LATENCIES, clk_freq)
        assert read_latency   in READ_LATENCIES
        assert write_latency  in WRITE_LATENCIES
        assert drive_strength in DRIVE_STRENGTHS
        assert size      % page_size == 0
        assert page_size % 2 == 0
        self.read_latency  = read_latency
        self.write_latency = write_latency
        self.mr0 = mr0 = (READ_LATENCIES[read_latency][0] << 2) | DRIVE_STRENGTHS[drive_strength]
        self.mr4 = mr4 = (WRITE_LATENCIES[write_latency][0] << 5)

        # Timings (cycles).
        tpu  = math.ceil(150e-6*clk_freq)
        trst = math.ceil(2e-6*clk_freq)
        tcph = max(math.ceil(20e-9*clk_freq), 1)
        trc  = math.ceil(60e-9*clk_freq)
        # Max words per CE# low: worst case read (setup, command/address, 2x latency, read path).
        overhead  = 1 + 3 + 2*read_latency + rx_offset_max + 8 + 1
        max_words = min(math.floor(tcem*clk_freq) - overhead, page_size//2)
        if max_words < 8:
            raise ValueError(f"OPI PSRAM: tCEM too short at {clk_freq/1e6:.2f}MHz.")
        self.max_words = max_words

        address_width = log2_int(size)
        length_width  = 16
        self.cmd   = cmd   = stream.Endpoint(opi_psram_cmd_layout(address_width, length_width))
        self.wdata = wdata = stream.Endpoint(opi_psram_wdata_layout())
        self.rdata = rdata = stream.Endpoint(opi_psram_rdata_layout())

        # Status.
        self.ready      = Signal()
        self.init_error = Signal() # Calibration failed or MR0 mismatch.
        self.timeout    = Signal() # Read data timeout (sticky).
        self.underrun   = Signal() # Write data underrun (sticky).
        self.vendor_id  = Signal(5)
        self.density    = Signal(3)
        self.rx_offset  = Signal(max=rx_offset_max + 1)

        # # #

        # Transaction Engine -----------------------------------------------------------------------
        # One CE# low transaction: setup, command/address (3 cycles), latency/data, hold, tCPH.
        KIND_RESET, KIND_MR_WRITE, KIND_MR_READ, KIND_WRITE, KIND_READ = range(5)
        e_start   = Signal()
        e_kind    = Signal(3)
        e_addr    = Signal(32)
        e_len     = Signal(length_width)
        e_mr_data = Signal(8)
        e_done    = Signal()
        e_wdata   = Record(opi_psram_wdata_layout())
        e_wready  = Signal()
        e_wvalid  = Signal()
        e_rvalid  = Signal()

        kind  = Signal(3)
        inst  = Signal(8)
        addr  = Signal(32)
        count = Signal(length_width)
        cycle = Signal(8)
        idle  = Signal(max=2*read_latency + rx_offset_max + 32 + 1)
        since = Signal(max=trc + 1) # Cycles since CE# low (tRC).
        timer = Signal(max=max(tcph, trc) + 1)

        engine_setup = Signal()
        e_timeout    = Signal()
        e_underrun   = Signal()
        timeout_clr  = Signal()
        rx_start     = Signal(max=2 + read_latency + rx_offset_max + 1)
        self.comb += rx_start.eq(2 + read_latency + self.rx_offset)

        self.sync += If(engine_setup,
            since.eq(0),
        ).Elif(since != trc,
            since.eq(since + 1),
        )

        self.engine = engine = FSM(reset_state="IDLE")
        engine.act("IDLE",
            If(e_start,
                NextValue(kind,  e_kind),
                NextValue(addr,  e_addr),
                NextValue(count, e_len),
                NextState("TRC"),
            )
        )
        self.comb += Case(kind, {
            KIND_RESET    : inst.eq(CMD_GLOBAL_RESET),
            KIND_MR_WRITE : inst.eq(CMD_MR_WRITE),
            KIND_MR_READ  : inst.eq(CMD_MR_READ),
            KIND_WRITE    : inst.eq(CMD_WRITE),
            KIND_READ     : inst.eq(CMD_READ),
        })
        engine.act("TRC",
            If(since == trc,
                NextState("SETUP"),
            )
        )
        engine.act("SETUP",
            phy.cs_n.eq(0),
            engine_setup.eq(1),
            NextValue(cycle, 0),
            NextState("CMD"),
        )
        engine.act("CMD",
            phy.cs_n.eq(0),
            phy.clk_en.eq(1),
            phy.dq_oe.eq(1),
            Case(cycle, {
                0: phy.dq_o.eq(Cat(inst, inst)),
                1: phy.dq_o.eq(Cat(addr[24:32], addr[16:24])),
                2: phy.dq_o.eq(Cat(addr[8:16],  addr[0:8])),
            }),
            NextValue(cycle, cycle + 1),
            If(cycle == 2,
                NextValue(idle, 0),
                Case(kind, {
                    KIND_RESET    : NextState("RESET-CLK"),
                    KIND_MR_WRITE : NextState("MR-WRITE"),
                    KIND_MR_READ  : NextState("READ"),
                    KIND_WRITE    : NextState("WRITE-LATENCY"),
                    KIND_READ     : NextState("READ"),
                })
            )
        )
        engine.act("RESET-CLK", # Global Reset: 4 clocked CE# lows.
            phy.cs_n.eq(0),
            phy.clk_en.eq(1),
            phy.dq_oe.eq(1),
            phy.dq_o.eq(0xffff),
            NextValue(cycle, cycle + 1),
            If(cycle == 6,
                NextState("HOLD"),
            )
        )
        engine.act("MR-WRITE", # Mode Register Write: latency 1.
            phy.cs_n.eq(0),
            phy.clk_en.eq(1),
            phy.dq_oe.eq(1),
            phy.dq_o.eq(Cat(e_mr_data, e_mr_data)),
            NextState("HOLD"),
        )
        engine.act("WRITE-LATENCY",
            phy.cs_n.eq(0),
            phy.clk_en.eq(1),
            phy.dq_oe.eq(1),
            phy.dqs_oe.eq(1),
            phy.dqs_o.eq(0b11),
            NextValue(cycle, cycle + 1),
            If(cycle == (2 + write_latency - 1),
                NextState("WRITE-DATA"),
            )
        )
        engine.act("WRITE-DATA",
            phy.cs_n.eq(0),
            phy.clk_en.eq(1),
            phy.dq_oe.eq(1),
            phy.dqs_oe.eq(1),
            phy.dq_o.eq(e_wdata.data),
            phy.dqs_o.eq(~Mux(e_wvalid, e_wdata.we, 0)),
            e_wready.eq(1),
            e_underrun.eq(~e_wvalid),
            NextValue(count, count - 1),
            If(count == 1,
                NextState("HOLD"),
            )
        )
        engine.act("READ",
            phy.cs_n.eq(0),
            phy.clk_en.eq(1),
            phy.rx_en.eq(cycle >= rx_start),
            If(cycle != (2**len(cycle) - 1),
                NextValue(cycle, cycle + 1),
            ),
            NextValue(idle, idle + 1),
            If(phy.rx_valid,
                e_rvalid.eq(1),
                NextValue(idle, 0),
                NextValue(count, count - 1),
                If(count == 1,
                    NextState("HOLD"),
                )
            ).Elif(idle == (2*read_latency + rx_offset_max + 32),
                e_timeout.eq(1),
                NextState("HOLD"),
            )
        )
        self.sync += [
            If(e_timeout,
                self.timeout.eq(1),
            ).Elif(timeout_clr,
                self.timeout.eq(0),
            ),
            If(e_underrun,
                self.underrun.eq(1),
            ),
        ]
        engine.act("HOLD",
            phy.cs_n.eq(0),
            NextValue(timer, 0),
            NextState("TCPH"),
        )
        engine.act("TCPH",
            NextValue(timer, timer + 1),
            If(timer == (tcph - 1),
                e_done.eq(1),
                NextState("IDLE"),
            )
        )

        # Initialization ---------------------------------------------------------------------------
        CAL_WORDS = 8
        CAL_TRIES = 4
        def cal_pattern(n):
            return Cat(Constant((0x5a + 2*n) & 0xff, 8), Constant((0xa5 + 2*n + 1) & 0xff, 8))
        cal_word    = Signal(max=CAL_WORDS + 1)
        cal_try     = Signal(max=CAL_TRIES + 1)
        cal_ok      = Signal()
        cal_offset  = Signal(max=rx_offset_max + 2)
        cal_first   = Signal(max=rx_offset_max + 1)
        cal_last    = Signal(max=rx_offset_max + 1)
        cal_found   = Signal()
        cal_ended   = Signal()
        cal_expect  = Signal(16)
        self.comb += Case(cal_word, {n: cal_expect.eq(cal_pattern(n)) for n in range(CAL_WORDS)})
        rword       = Signal(16)
        self.comb += rword.eq(phy.rx_data)

        wait = Signal(max=max(tpu, trst) + 1)

        # Accesses.
        acc_we    = Signal()
        acc_addr  = Signal(address_width)
        acc_len   = Signal(length_width)
        chunk     = Signal(length_width)
        page_left = Signal(length_width)
        page_len  = Signal(length_width)
        self.comb += [
            page_left.eq((page_size//2) - acc_addr[1:log2_int(page_size)]),
            page_len.eq(Mux(acc_len < page_left, acc_len, page_left)),
            chunk.eq(Mux(page_len < max_words, page_len, max_words)),
        ]

        self.fsm = fsm = FSM(reset_state="POWERUP")
        fsm.act("POWERUP",
            NextValue(wait, wait + 1),
            If(wait == (tpu - 1),
                NextState("RESET"),
            )
        )
        fsm.act("RESET",
            e_start.eq(1),
            e_kind.eq(KIND_RESET),
            If(e_done,
                NextValue(wait, 0),
                NextState("RESET-WAIT"),
            )
        )
        fsm.act("RESET-WAIT",
            NextValue(wait, wait + 1),
            If(wait == (trst - 1),
                NextState("MR0"),
            )
        )
        fsm.act("MR0",
            e_start.eq(1),
            e_kind.eq(KIND_MR_WRITE),
            e_addr.eq(0),
            e_mr_data.eq(mr0),
            If(e_done,
                NextState("MR4"),
            )
        )
        fsm.act("MR4",
            e_start.eq(1),
            e_kind.eq(KIND_MR_WRITE),
            e_addr.eq(4),
            e_mr_data.eq(mr4),
            If(e_done,
                NextValue(cal_word, 0),
                NextState("CAL-WRITE"),
            )
        )
        fsm.act("CAL-WRITE",
            e_start.eq(1),
            e_kind.eq(KIND_WRITE),
            e_addr.eq(0),
            e_len.eq(CAL_WORDS),
            e_wvalid.eq(1),
            e_wdata.data.eq(cal_expect),
            e_wdata.we.eq(0b11),
            If(e_wready,
                NextValue(cal_word, cal_word + 1),
            ),
            If(e_done,
                NextValue(cal_offset, 0),
                NextValue(cal_found,  0),
                NextValue(cal_ended,  0),
                NextValue(cal_try,    0),
                NextValue(cal_ok,     1),
                NextState("CAL-READ"),
            )
        )
        fsm.act("CAL-READ",
            e_start.eq(1),
            e_kind.eq(KIND_READ),
            e_addr.eq(0),
            e_len.eq(CAL_WORDS),
            If(engine.ongoing("IDLE"),
                NextValue(self.rx_offset, cal_offset),
                NextValue(cal_word, 0),
            ),
            If(e_rvalid,
                NextValue(cal_word, cal_word + 1),
                If(rword != cal_expect,
                    NextValue(cal_ok, 0),
                )
            ),
            If(e_done,
                If(self.timeout | (cal_word != CAL_WORDS),
                    NextValue(cal_ok, 0),
                ),
                timeout_clr.eq(1),
                NextValue(cal_try, cal_try + 1),
                If(cal_try == (CAL_TRIES - 1),
                    NextState("CAL-NEXT"),
                )
            )
        )
        fsm.act("CAL-NEXT",
            NextValue(cal_try, 0),
            NextValue(cal_ok,  1),
            NextValue(cal_offset, cal_offset + 1),
            # Keep the first passing run of offsets.
            If(cal_ok & ~cal_ended,
                If(~cal_found,
                    NextValue(cal_found, 1),
                    NextValue(cal_first, cal_offset),
                ),
                NextValue(cal_last, cal_offset),
            ).Elif(cal_found,
                NextValue(cal_ended, 1),
            ),
            If(cal_offset == rx_offset_max,
                NextState("CAL-SELECT"),
            ).Else(
                NextState("CAL-READ"),
            )
        )
        fsm.act("CAL-SELECT",
            # Latest passing window start minus one cycle: within the DQS preamble.
            If(cal_found,
                NextValue(self.rx_offset, Mux(cal_last > cal_first, cal_last - 1, cal_last)),
                NextState("ID-MR0"),
            ).Else(
                NextValue(self.init_error, 1),
                NextState("ERROR"),
            )
        )
        fsm.act("ID-MR0", # MR0 check / MR1 (vendor ID).
            e_start.eq(1),
            e_kind.eq(KIND_MR_READ),
            e_addr.eq(0),
            e_len.eq(1),
            If(e_rvalid,
                NextValue(self.vendor_id, rword[8:13]),
                If(rword[0:8] != mr0,
                    NextValue(self.init_error, 1),
                )
            ),
            If(e_done,
                NextState("ID-MR2"),
            )
        )
        fsm.act("ID-MR2", # MR2 (density).
            e_start.eq(1),
            e_kind.eq(KIND_MR_READ),
            e_addr.eq(2),
            e_len.eq(1),
            If(e_rvalid,
                NextValue(self.density, rword[0:3]),
            ),
            If(e_done,
                If(self.init_error | self.timeout,
                    NextValue(self.init_error, 1),
                    NextState("ERROR"),
                ).Else(
                    NextState("READY"),
                )
            )
        )
        fsm.act("ERROR")

        # Accesses ---------------------------------------------------------------------------------
        fsm.act("READY",
            self.ready.eq(1),
            cmd.ready.eq(1),
            If(cmd.valid,
                NextValue(acc_we,   cmd.we),
                NextValue(acc_addr, cmd.addr),
                NextValue(acc_len,  cmd.len),
                NextState("ACCESS"),
            )
        )
        fsm.act("ACCESS",
            self.ready.eq(1),
            e_start.eq(1),
            e_kind.eq(Mux(acc_we, KIND_WRITE, KIND_READ)),
            e_addr.eq(acc_addr),
            If(engine.ongoing("IDLE"),
                NextValue(acc_len, acc_len - chunk),
                NextValue(acc_addr, acc_addr + 2*chunk),
            ),
            e_len.eq(chunk),
            e_wvalid.eq(wdata.valid),
            e_wdata.data.eq(wdata.data),
            e_wdata.we.eq(wdata.we),
            wdata.ready.eq(e_wready),
            rdata.valid.eq(e_rvalid),
            rdata.data.eq(rword),
            If(e_done,
                If(acc_len == 0,
                    NextState("READY"),
                )
            )
        )

# OPI PSRAM Wishbone Frontend ----------------------------------------------------------------------

class OPIPSRAMWishbone(LiteXModule):
    """Wishbone slave: each access is one burst of ``data_width``/16 words (``sel``: byte write
    enables), at byte address ``adr`` x ``data_width``/8. Accesses are acknowledged without effect
    (read data: 0) after an initialization error."""
    def __init__(self, core, data_width=32):
        assert data_width in [16, 32, 64, 128]
        nwords = data_width//16
        self.bus = bus = wishbone.Interface(
            data_width    = data_width,
            address_width = 32,
            addressing    = "word",
        )

        # # #

        index = Signal(max=max(nwords, 2))
        dat_r = Signal(data_width)
        self.comb += bus.dat_r.eq(dat_r)

        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(bus.cyc & bus.stb & core.init_error,
                NextValue(dat_r, 0),
                NextState("ACK"),
            ).Elif(bus.cyc & bus.stb,
                core.cmd.valid.eq(1),
                core.cmd.we.eq(bus.we),
                core.cmd.addr.eq(bus.adr << log2_int(data_width//8)),
                core.cmd.len.eq(nwords),
                If(core.cmd.ready,
                    NextValue(index, 0),
                    If(bus.we,
                        NextState("WRITE"),
                    ).Else(
                        NextState("READ"),
                    )
                )
            )
        )
        fsm.act("WRITE",
            core.wdata.valid.eq(1),
            core.wdata.data.eq(Array(bus.dat_w[16*n:16*(n + 1)] for n in range(nwords))[index]),
            core.wdata.we.eq(Array(bus.sel[2*n:2*(n + 1)] for n in range(nwords))[index]),
            If(core.wdata.ready,
                NextValue(index, index + 1),
                If(index == (nwords - 1),
                    NextState("ACK"),
                )
            )
        )
        fsm.act("READ",
            If(core.rdata.valid,
                NextValue(index, index + 1),
                Case(index, {
                    n: NextValue(dat_r[16*n:16*(n + 1)], core.rdata.data) for n in range(nwords)
                }),
                If(index == (nwords - 1),
                    NextState("ACK"),
                )
            )
        )
        fsm.act("ACK",
            bus.ack.eq(1),
            NextState("IDLE"),
        )

# OPI PSRAM ----------------------------------------------------------------------------------------

class OPIPSRAM(LiteXModule):
    """
    OPI PSRAM with Wishbone interface (PHY, core and Wishbone frontend, optional status CSR).

    Runs in ``sys`` (memory CLK frequency ``clk_freq``) and ``cd_fast`` (2x, SerDes); use a
    ClockDomainsRenamer and a Wishbone ClockDomainCrossing for a separate memory clock domain.
    """
    def __init__(self, pads, clk_freq, size=8*1024*1024, data_width=32, cd_fast="sys2x",
        rx_sample = 1,
        with_csr  = True,
        **kwargs):
        self.phy      = phy  = OPIPSRAMPHY(pads, cd_fast=cd_fast, rx_sample=rx_sample)
        self.core     = core = OPIPSRAMCore(phy, clk_freq, size=size, **kwargs)
        self.wishbone = OPIPSRAMWishbone(core, data_width=data_width)
        self.bus      = self.wishbone.bus

        # # #

        if with_csr:
            self.add_csr()

    def add_csr(self):
        core = self.core
        self.status = CSRStatus(fields=[
            CSRField("ready",      size=1, offset= 0, description="Initialization completed."),
            CSRField("init_error", size=1, offset= 1, description="Initialization failed."),
            CSRField("timeout",    size=1, offset= 2, description="A read timed out (sticky)."),
            CSRField("underrun",   size=1, offset= 3, description="Write data underrun (sticky)."),
            CSRField("rx_offset",  size=4, offset= 8, description="Calibrated read window offset."),
            CSRField("vendor_id",  size=5, offset=16, description="MR1 Vendor ID."),
            CSRField("density",    size=3, offset=24, description="MR2 Density."),
        ])
        self.comb += [
            self.status.fields.ready.eq(core.ready),
            self.status.fields.init_error.eq(core.init_error),
            self.status.fields.timeout.eq(core.timeout),
            self.status.fields.underrun.eq(core.underrun),
            self.status.fields.rx_offset.eq(core.rx_offset),
            self.status.fields.vendor_id.eq(core.vendor_id),
            self.status.fields.density.eq(core.density),
        ]
