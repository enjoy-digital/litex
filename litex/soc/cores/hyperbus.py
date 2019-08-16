# This file is Copyright (c) 2019 Antti Lukats <antti.lukats@gmail.com>
# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *
from migen.genlib.misc import timeline
from migen.genlib.io import DifferentialOutput

from litex.soc.interconnect import wishbone

# HyperRAM -----------------------------------------------------------------------------------------

class HyperRAM(Module):
    """HyperRAM

    Provides a very simple/minimal HyperRAM core that should work with all FPGA/HyperRam chips:
    - FPGA vendor agnostic.
    - no setup/chip configuration (use default latency).

    This core favrors portability and ease of use over performance.
    """
    def __init__(self, pads):
        self.pads = pads
        self.bus  = bus = wishbone.Interface()

        # # #

        clk       = Signal()
        clk_phase = Signal(2)
        cs        = Signal()
        ca        = Signal(48)
        sr        = Signal(48)
        dq        = self.add_tristate(pads.dq) if not hasattr(pads.dq, "oe") else pads.dq
        rwds      = self.add_tristate(pads.rwds) if not hasattr(pads.rwds, "oe") else pads.rwds

        # Drive rst_n, cs_n, clk from internal signals ---------------------------------------------
        if hasattr(pads, "rst_n"):
            self.comb += pads.rst_n.eq(1)
        self.comb += pads.cs_n[0].eq(~cs)
        assert len(pads.cs_n) <= 2
        if len(pads.cs_n) == 2:
            self.comb += pads.cs_n[1].eq(1)
        if hasattr(pads, "clk"):
            self.comb += pads.clk.eq(clk)
        else:
            self.specials += DifferentialOutput(clk, pads.clk_p, pads.clk_n)

        # Clock Generation (sys_clk/4) -------------------------------------------------------------
        self.sync += clk_phase.eq(clk_phase + 1)
        cases = {}
        cases[1] = clk.eq(cs) # Set pads clk on 90° (if cs is set)
        cases[3] = clk.eq(0)  # Clear pads clk on 270°
        self.sync += Case(clk_phase, cases)

        # Data Shift Register (for write and read) -------------------------------------------------
        dqi = Signal(8)
        self.sync += dqi.eq(dq.i) # Sample on 90° and 270°
        cases = {}
        cases[0] = sr.eq(Cat(dqi, sr[:-8])) # Shift on 0°
        cases[2] = sr.eq(Cat(dqi, sr[:-8])) # Shift on 180°
        self.sync += Case(clk_phase, cases)
        self.comb += [
            bus.dat_r.eq(sr), # To Wisbone
            dq.o.eq(sr[-8:]), # To HyperRAM
        ]

        # Command generation -----------------------------------------------------------------------
        self.comb += [
            ca[47].eq(~self.bus.we),          # R/W#
            ca[45].eq(1),                     # Burst Type (Linear)
            ca[16:35].eq(self.bus.adr[2:21]), # Row & Upper Column Address
            ca[1:3].eq(self.bus.adr[0:2]),    # Lower Column Address
            ca[0].eq(0),                      # Lower Column Address
        ]

        # Sequencer --------------------------------------------------------------------------------
        dt_seq = [
            # DT,  Action
            (3,    []),
            (12,   [cs.eq(1), dq.oe.eq(1), sr.eq(ca)]),    # Command: 6 clk
            (44,   [dq.oe.eq(0)]),                         # Latency(default): 2*6 clk
            (2,    [dq.oe.eq(self.bus.we),                 # Write/Read data byte: 2 clk
                    sr[:16].eq(0),
                    sr[16:].eq(self.bus.dat_w),
                    rwds.oe.eq(self.bus.we),
                    rwds.o.eq(~bus.sel[0])]),
            (2,    [rwds.o.eq(~bus.sel[1])]),              # Write/Read data byte: 2 clk
            (2,    [rwds.o.eq(~bus.sel[2])]),              # Write/Read data byte: 2 clk
            (2,    [rwds.o.eq(~bus.sel[3])]),              # Write/Read data byte: 2 clk
            (2,    [cs.eq(0), rwds.oe.eq(0), dq.oe.eq(0)]),
            (1,    [bus.ack.eq(1)]),
            (1,    [bus.ack.eq(0)]),
            (0,    []),
        ]
        # Convert delta-time sequencer to time sequencer
        t_seq = []
        t_seq_start = (clk_phase == 1)
        t = 0
        for dt, a in dt_seq:
            t_seq.append((t, a))
            t += dt
        self.sync += timeline(bus.cyc & bus.stb & t_seq_start, t_seq)

    def add_tristate(self, pad):
        t = TSTriple(len(pad))
        self.specials += t.get_tristate(pad)
        return t
