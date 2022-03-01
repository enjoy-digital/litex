#
# This file is part of LiteHyperBus
#
# Copyright (c) 2019-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 Antti Lukats <antti.lukats@gmail.com>
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.misc import timeline

from litex.build.io import DifferentialOutput

from litex.soc.interconnect import wishbone

# HyperRAM -----------------------------------------------------------------------------------------

class HyperRAM(Module):
    """HyperRAM

    Provides a very simple/minimal HyperRAM core that should work with all FPGA/HyperRam chips:
    - FPGA vendor agnostic.
    - no setup/chip configuration (use default latency).

    This core favors portability and ease of use over performance.
    """
    def __init__(self, pads, latency=6):
        self.pads = pads
        self.bus  = bus = wishbone.Interface()

        # # #

        clk       = Signal()
        clk_phase = Signal(2)
        cs        = Signal()
        ca        = Signal(48)
        ca_active = Signal()
        sr        = Signal(48)
        sr_new    = Signal(48)
        dq        = self.add_tristate(pads.dq)   if not hasattr(pads.dq,   "oe") else pads.dq
        rwds      = self.add_tristate(pads.rwds) if not hasattr(pads.rwds, "oe") else pads.rwds
        dw        = len(pads.dq)                 if not hasattr(pads.dq,   "oe") else len(pads.dq.o)

        assert dw in [8, 16]

        # Drive Control Signals --------------------------------------------------------------------

        # Rst.
        if hasattr(pads, "rst_n"):
            self.comb += pads.rst_n.eq(1)

        # CSn.
        self.comb += pads.cs_n[0].eq(~cs)
        assert len(pads.cs_n) <= 2
        if len(pads.cs_n) == 2:
            self.comb += pads.cs_n[1].eq(1)

        # Clk.
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

        # Data Shift-In Register -------------------------------------------------------------------
        dqi = Signal(dw)
        self.sync += dqi.eq(dq.i) # Sample on 90° and 270°
        self.comb += [
            sr_new.eq(Cat(dqi, sr[:-dw])),
            If(ca_active,
                sr_new.eq(Cat(dqi[:8], sr[:-8])) # Only 8-bit during Command/Address.
            )
        ]
        self.sync += If(clk_phase[0] == 0, sr.eq(sr_new)) # Shift on 0° and 180°

        # Data Shift-Out Register ------------------------------------------------------------------
        self.comb += [
            bus.dat_r.eq(sr_new),
            If(dq.oe,
                dq.o.eq(sr[-dw:]),
                If(ca_active,
                    dq.o.eq(sr[-8:]) # Only 8-bit during Command/Address.
                )
            )
        ]

        # Command generation -----------------------------------------------------------------------
        ashift = {8:1, 16:0}[dw]
        self.comb += [
            ca[47].eq(~bus.we),               # R/W#
            ca[45].eq(1),                     # Burst Type (Linear)
            ca[16:45].eq(bus.adr[3-ashift:]), # Row & Upper Column Address
            ca[ashift:3].eq(bus.adr),         # Lower Column Address
        ]

        # Latency count starts from the middle of the command (thus the -4). In fixed latency mode
        # (default), latency is 2 x Latency count. We have 4 x sys_clk per RAM clock:
        latency_cycles = (latency * 2 * 4) - 4

        # Bus Latch --------------------------------------------------------------------------------
        bus_adr   = Signal(32)
        bus_we    = Signal()
        bus_sel   = Signal(4)
        bus_latch = Signal()
        self.sync += If(bus_latch,
            If(bus.we,
                sr.eq(Cat(Signal(16), bus.dat_w)),
            ),
            bus_we.eq(bus.we),
            bus_sel.eq(bus.sel),
            bus_adr.eq(bus.adr)
        )

        # FSM (Sequencer) --------------------------------------------------------------------------
        cycles = Signal(8)
        first  = Signal()
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            NextValue(first, 1),
            If(bus.cyc & bus.stb,
                If(clk_phase == 0,
                    NextValue(sr, ca),
                    NextState("SEND-COMMAND-ADDRESS")
                )
            )
        )
        fsm.act("SEND-COMMAND-ADDRESS",
            # Set CSn.
            cs.eq(1),
            # Send Command on DQ.
            ca_active.eq(1),
            dq.oe.eq(1),
            # Wait for 6*2 cycles...
            If(cycles == (6*2 - 1),
                NextState("WAIT-LATENCY")
            )
        )
        fsm.act("WAIT-LATENCY",
            # Set CSn.
            cs.eq(1),
            # Wait for Latency cycles...
            If(cycles == (latency_cycles - 1),
                # Latch Bus.
                bus_latch.eq(1),
                # Early Write Ack (to allow bursting).
                bus.ack.eq(bus.we),
                NextState("READ-WRITE-DATA0")
            )
        )
        states = {8:4, 16:2}[dw]
        for n in range(states):
            fsm.act(f"READ-WRITE-DATA{n}",
                # Set CSn.
                cs.eq(1),
                # Send Data on DQ/RWDS (for write).
                If(bus_we,
                    dq.oe.eq(1),
                    rwds.oe.eq(1),
                    *[rwds.o[dw//8-1-i].eq(~bus_sel[4-1-n*dw//8-i]) for i in range(dw//8)],
                ),
                # Wait for 2 cycles (since HyperRAM's Clk = sys_clk/4).
                If(cycles == (2 - 1),
                    # Set next default state (with rollover for bursts).
                    NextState(f"READ-WRITE-DATA{(n + 1)%states}"),
                    # On last state, see if we can continue the burst or if we should end it.
                    If(n == (states - 1),
                        NextValue(first, 0),
                        # Continue burst when a consecutive access is ready.
                        If(bus.stb & bus.cyc & (bus.we == bus_we) & (bus.adr == (bus_adr + 1)),
                            # Latch Bus.
                            bus_latch.eq(1),
                            # Early Write Ack (to allow bursting).
                            bus.ack.eq(bus.we)
                        # Else end the burst.
                        ).Elif(bus_we | ~first,
                            NextState("IDLE")
                        )
                    ),
                    # Read Ack (when dat_r ready).
                    If((n == 0) & ~first,
                        bus.ack.eq(~bus_we),
                    )
                )
            )
        fsm.finalize()
        self.sync += cycles.eq(cycles + 1)
        self.sync += If(fsm.next_state != fsm.state, cycles.eq(0))

    def add_tristate(self, pad):
        t = TSTriple(len(pad))
        self.specials += t.get_tristate(pad)
        return t
