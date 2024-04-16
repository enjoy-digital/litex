#
# This file is part of LiteX.
#
# Copyright (c) 2019-2024 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 Antti Lukats <antti.lukats@gmail.com>
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *
from litex.gen.genlib.misc import WaitTimer

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream

from litex.build.io import DifferentialOutput

from litex.soc.interconnect import wishbone

# HyperRAM -----------------------------------------------------------------------------------------

class HyperRAM(LiteXModule):
    tCSM = 4e-6
    """HyperRAM

    Provides a very simple/minimal HyperRAM core with a Wishbone Interface that can work with all
    FPGA/HyperRam chips:
    - Vendor agnostic.
    - Fixed/Variable latency.
    - Latency/Registers (re-)configuration.

    Parameters:
        pads (Record)                  : Interface to the HyperRAM connection pads.
        latency (int, optional)        : Initial latency setting, defaults to 6.
        latency_mode (str, optional)   : Specifies the latency mode ('fixed' or 'variable'), defaults to 'variable'.
        sys_clk_freq (float, optional) : System clock frequency in Hz.
        with_csr (bool, optional)      : Enables CSR interface for Latency/Registers configuration, defaults to True.

    Attributes:
        pads (Record)            : Platform pads of HyperRAM.
        bus (wishbone.Interface) : Wishbone Interface.
"""
    def __init__(self, pads, latency=6, latency_mode="variable", sys_clk_freq=None, with_csr=True):
        self.pads = pads
        self.bus  = bus = wishbone.Interface(data_width=32, address_width=32, addressing="word")

        # Config/Reg Interface.
        # ---------------------
        self.conf_rst          = Signal()
        self.conf_latency      = Signal(8, reset=latency)
        self.stat_latency_mode = Signal(reset={"fixed": 0, "variable": 1}[latency_mode])
        self.reg_write         = Signal()
        self.reg_read          = Signal()
        self.reg_addr          = Signal(2)
        self.reg_write_done    = Signal()
        self.reg_read_done     = Signal()
        self.reg_write_data    = Signal(16)
        self.reg_read_data     = Signal(16)
        if with_csr:
            self.add_csr(default_latency=latency)

        # # #

        # Parameters.
        # -----------
        assert latency_mode in ["fixed", "variable"]

        # Internal Signals.
        # -----------------
        clk       = Signal()
        clk_phase = Signal(2)
        cs        = Signal()
        ca        = Signal(48)
        ca_active = Signal()
        sr        = Signal(48)
        sr_next   = Signal(48)
        dq        = self.add_tristate(pads.dq)   if not hasattr(pads.dq,   "oe") else pads.dq
        rwds      = self.add_tristate(pads.rwds) if not hasattr(pads.rwds, "oe") else pads.rwds
        dw        = len(pads.dq)                 if not hasattr(pads.dq,   "oe") else len(pads.dq.o)

        assert dw in [8, 16]

        # Drive Control Signals --------------------------------------------------------------------

        # Rst.
        if hasattr(pads, "rst_n"):
            self.comb += pads.rst_n.eq(1 & ~self.conf_rst)

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

        # Burst Timer ------------------------------------------------------------------------------
        sys_clk_freq = 10e6 if sys_clk_freq is None else sys_clk_freq
        burst_timer  = WaitTimer(sys_clk_freq*self.tCSM)
        self.burst_timer = burst_timer

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
            sr_next.eq(Cat(dqi, sr[:-dw])),
            If(ca_active,
                sr_next.eq(Cat(dqi[:8], sr[:-8])) # Only 8-bit during Command/Address.
            )
        ]
        self.sync += If(clk_phase[0] == 0, sr.eq(sr_next)) # Shift on 0° and 180°

        # Data Shift-Out Register ------------------------------------------------------------------
        self.comb += [
            bus.dat_r.eq(sr_next),
            If(dq.oe,
                dq.o.eq(sr[-dw:]),
                If(ca_active,
                    dq.o.eq(sr[-8:]) # Only 8-bit during Command/Address.
                )
            )
        ]

        # Register Access/Buffer -------------------------------------------------------------------
        reg_write_req = Signal()
        reg_read_req  = Signal()
        self.reg_buf = reg_buf = stream.SyncFIFO(
            layout = [("write", 1), ("read", 1), ("addr", 4), ("data", 16)],
            depth  = 4,
        )
        reg_ep = reg_buf.source
        self.comb += [
            reg_buf.sink.valid.eq(self.reg_write | self.reg_read),
            reg_buf.sink.write.eq(self.reg_write),
            reg_buf.sink.read.eq(self.reg_read),
            reg_buf.sink.addr.eq(self.reg_addr),
            reg_buf.sink.data.eq(self.reg_write_data),
            reg_write_req.eq(reg_ep.valid & reg_ep.write),
            reg_read_req.eq( reg_ep.valid & reg_ep.read),
        ]
        self.sync += If(reg_buf.sink.valid,
            self.reg_write_done.eq(0),
            self.reg_read_done.eq(0),
        )

        # Command generation -----------------------------------------------------------------------
        ashift = {8:1, 16:0}[dw]
        self.comb += [
            # Register Command Generation.
            If(reg_write_req | reg_read_req,
                ca[47].eq(reg_ep.read), # R/W#
                ca[46].eq(1),           # Register Space.
                ca[45].eq(1),           # Burst Type (Linear)
                Case(reg_ep.addr, {
                    0 : ca[0:40].eq(0x00_00_00_00_00), # Identification Register 0 (Read Only).
                    1 : ca[0:40].eq(0x00_00_00_00_01), # Identification Register 1 (Read Only).
                    2 : ca[0:40].eq(0x00_01_00_00_00), # Configuration Register 0.
                    3 : ca[0:40].eq(0x00_01_00_00_01), # Configuration Register 1.
                }),
            # Wishbone Command Generation.
            ).Else(
                ca[47].eq(~bus.we),                # R/W#
                ca[46].eq(0),                      # Memory Space.
                ca[45].eq(1),                      # Burst Type (Linear)
                ca[16:45].eq(bus.adr[3-ashift:]),  # Row & Upper Column Address
                ca[ashift:3].eq(bus.adr),          # Lower Column Address
            )
        ]

        # Bus Latch --------------------------------------------------------------------------------
        bus_adr   = Signal(32)
        bus_we    = Signal()
        bus_sel   = Signal(4)
        bus_latch = Signal()
        self.sync += If(bus_latch,
            If(bus.we, sr.eq(Cat(Signal(16), bus.dat_w))),
            bus_we.eq(bus.we),
            bus_sel.eq(bus.sel),
            bus_adr.eq(bus.adr)
        )

        # FSM (Sequencer) --------------------------------------------------------------------------
        cycles  = Signal(8)
        first   = Signal()
        refresh = Signal()
        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            NextValue(first, 1),
            If(clk_phase == 0,
                If((bus.cyc & bus.stb) | reg_write_req | reg_read_req,
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
                If(reg_write_req,
                    NextValue(sr, Cat(Signal(40), self.reg_write_data[8:])),
                    NextState("REG-WRITE-0")
                ).Else(
                    # Sample RWDS to know if 1X/2X Latency should be used (Refresh).
                    NextValue(refresh, rwds.i | (latency_mode in ["fixed"])),
                    NextState("WAIT-LATENCY")
                )
            )
        )
        fsm.act("REG-WRITE-0",
            # Set CSn.
            cs.eq(1),
            # Send Reg on DQ.
            ca_active.eq(1),
            dq.oe.eq(1),
            # Wait for 2 cycles...
            If(cycles == (2 - 1),
                NextValue(sr, Cat(Signal(40), self.reg_write_data[:8])),
                NextState("REG-WRITE-1")
            )
        )
        fsm.act("REG-WRITE-1",
            # Set CSn.
            cs.eq(1),
            # Send Reg on DQ.
            ca_active.eq(1),
            dq.oe.eq(1),
            # Wait for 2 cycles...
            If(cycles == (2 - 1),
                reg_ep.ready.eq(1),
                NextValue(self.reg_write_done, 1),
                NextState("IDLE")
            )
        )
        fsm.act("WAIT-LATENCY",
            # Set CSn.
            cs.eq(1),
            # Wait for 1X or 2X Latency cycles... (-4 since count start in the middle of the command).
            If(((cycles == 2*(self.conf_latency * 4) - 4 - 1) &  refresh) | # 2X Latency (No DRAM refresh required).
               ((cycles == 1*(self.conf_latency * 4) - 4 - 1) & ~refresh) , # 1X Latency (   DRAM refresh required).
                # Latch Bus.
                bus_latch.eq(1),
                # Early Write Ack (to allow bursting).
                If(~reg_read_req,
                    bus.ack.eq(bus.we),
                ),
                NextState("READ-WRITE-DATA0")
            )
        )
        states = {8:4, 16:2}[dw]
        for n in range(states):
            fsm.act(f"READ-WRITE-DATA{n}",
                # Enable Burst Timer.
                burst_timer.wait.eq(1),
                # Set CSn.
                cs.eq(1),
                ca_active.eq(reg_read_req),
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
                        If(~reg_read_req & bus.stb & bus.cyc & (bus.we == bus_we) & (bus.adr == (bus_adr + 1)) & (~burst_timer.done),
                            # Latch Bus.
                            bus_latch.eq(1),
                            # Early Write Ack (to allow bursting).
                            bus.ack.eq(bus.we)
                        # Else end the burst.
                        ).Elif(bus_we | (~first) | burst_timer.done,
                            NextState("IDLE")
                        )
                    ),
                    # Read Ack (when dat_r ready).
                    If((n == 0) & ~first,
                        If(reg_read_req,
                            reg_ep.ready.eq(1),
                            NextValue(self.reg_read_done, 1),
                            NextValue(self.reg_read_data, bus.dat_r),
                            NextState("IDLE"),
                        ).Else(
                            bus.ack.eq(~bus_we),
                        )
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

    def add_csr(self, default_latency=6):
        # Config/Status Interface.
        # ------------------------
        self.config = CSRStorage(fields=[
            CSRField("rst",     offset=0, size=1, pulse=True, description="HyperRAM Rst."),
            CSRField("latency", offset=8, size=8,             description="HyperRAM Latency (X1).", reset=default_latency),
        ])
        self.comb += [
            self.conf_rst.eq(    self.config.fields.rst),
            self.conf_latency.eq(self.config.fields.latency),
        ]
        self.status = CSRStatus(fields=[
            CSRField("latency_mode", offset=0, size=1, values=[
                ("``0b0``", "Fixed Latency."),
                ("``0b1``", "Variable Latency."),
            ])
        ])
        self.comb += self.status.fields.latency_mode.eq(self.stat_latency_mode)

        # Reg Interface.
        # --------------
        self.reg_control = CSRStorage(fields=[
            CSRField("write", offset=0, size=1, pulse=True, description="Issue Register Write."),
            CSRField("read",  offset=1, size=1, pulse=True, description="Issue Register Read."),
            CSRField("addr",  offset=8, size=4, values=[
                ("``0b00``", "Identification Register 0 (Read Only)."),
                ("``0b01``", "Identification Register 1 (Read Only)."),
                ("``0b10``", "Configuration Register 0."),
                ("``0b11``", "Configuration Register 1."),
            ]),
        ])
        self.reg_status = CSRStatus(fields=[
            CSRField("write_done", offset=0, size=1, description="Register Write Done."),
            CSRField("read_done",  offset=1, size=1, description="Register Read Done."),
        ])
        self.reg_wdata = CSRStorage(16, description="Register Write Data.")
        self.reg_rdata = CSRStatus( 16, description="Register Read Data.")

        self.comb += [
            # Control.
            self.reg_write.eq(self.reg_control.fields.write),
            self.reg_read.eq( self.reg_control.fields.read),
            self.reg_addr.eq( self.reg_control.fields.addr),

            # Status.
            self.reg_status.fields.write_done.eq(self.reg_write_done),
            self.reg_status.fields.read_done.eq( self.reg_read_done),

            # Data.
            self.reg_write_data.eq(self.reg_wdata.storage),
            self.reg_rdata.status.eq(self.reg_read_data),
        ]
