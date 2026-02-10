#
# This file is part of LiteX.
#
# Copyright (c) 2025 blurbdust
# SPDX-License-Identifier: BSD-2-Clause

# BPI (Parallel NOR) Flash core for Xilinx 7-Series FPGAs.
# Targets: Micron MT28GU512AAA1EGC (512Mb, x16, BPI).
#
# Reference: openFPGALoader bpiOverJtag_core.v timing.

from migen import *
from migen.fhdl.specials import Tristate

from litex.gen import LiteXModule

from litex.soc.interconnect.csr import *

# BPI Master ------------------------------------------------------------------------------------

class BPIMaster(LiteXModule):
    def __init__(self, pads, sys_clk_freq, wait_cycles=20):
        # CSRs.
        self._addr    = CSRStorage(25, description="Word address A[25:1].")
        self._data_w  = CSRStorage(16, description="Write data DQ[15:0].")
        self._data_r  = CSRStatus(16,  description="Read data DQ[15:0].")
        self._control = CSRStorage(fields=[
            CSRField("start", size=1, offset=0, pulse=True, description="Start operation (auto-clears)."),
            CSRField("rw",    size=1, offset=1, description="0=Read, 1=Write."),
        ])
        self._status = CSRStatus(fields=[
            CSRField("done", size=1, offset=0, description="Operation complete."),
        ])

        # # #

        # Signals.
        addr   = Signal(25)
        data_w = Signal(16)
        rw     = Signal()
        done   = Signal(reset=1)

        dq_o  = Signal(16)
        dq_oe = Signal()
        dq_i  = Signal(16)

        ce_n  = Signal(reset=1)
        oe_n  = Signal(reset=1)
        we_n  = Signal(reset=1)
        adv_n = Signal(reset=1)

        wait_cnt = Signal(max=wait_cycles + 1)

        # Tristate data bus.
        self.specials += Tristate(pads.dq, o=dq_o, oe=dq_oe, i=dq_i)

        # Connect pads.
        self.comb += [
            pads.adr.eq(addr),
            pads.ce_n.eq(ce_n),
            pads.oen.eq(oe_n),
            pads.wen.eq(we_n),
            pads.adv.eq(adv_n),
        ]

        # Connect status CSR.
        self.comb += self._status.fields.done.eq(done)

        # FSM.
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            done.eq(1),
            ce_n.eq(1),
            oe_n.eq(1),
            we_n.eq(1),
            adv_n.eq(1),
            dq_oe.eq(0),
            If(self._control.fields.start,
                NextValue(addr,   self._addr.storage),
                NextValue(data_w, self._data_w.storage),
                NextValue(rw,     self._control.fields.rw),
                NextValue(wait_cnt, 3 - 1),
                NextState("SETUP"),
            ),
        )
        fsm.act("SETUP",
            done.eq(0),
            ce_n.eq(0),
            adv_n.eq(0),
            oe_n.eq(1),
            we_n.eq(1),
            # Drive address on pads.
            # If write: also drive DQ with data.
            If(rw,
                dq_oe.eq(1),
                dq_o.eq(data_w),
            ).Else(
                dq_oe.eq(0),
            ),
            If(wait_cnt == 0,
                NextValue(wait_cnt, wait_cycles - 1),
                NextState("EXEC"),
            ).Else(
                NextValue(wait_cnt, wait_cnt - 1),
            ),
        )
        fsm.act("EXEC",
            done.eq(0),
            ce_n.eq(0),
            adv_n.eq(0),
            If(rw,
                # Write: pulse WE# low, drive data.
                oe_n.eq(1),
                we_n.eq(0),
                dq_oe.eq(1),
                dq_o.eq(data_w),
            ).Else(
                # Read: assert OE#, release data bus.
                oe_n.eq(0),
                we_n.eq(1),
                dq_oe.eq(0),
            ),
            # Sample read data mid-cycle.
            If((~rw) & (wait_cnt == wait_cycles // 2),
                NextValue(self._data_r.status, dq_i),
            ),
            If(wait_cnt == 0,
                NextValue(wait_cnt, 3 - 1),
                NextState("HOLD"),
            ).Else(
                NextValue(wait_cnt, wait_cnt - 1),
            ),
        )
        fsm.act("HOLD",
            done.eq(0),
            ce_n.eq(1),
            oe_n.eq(1),
            we_n.eq(1),
            adv_n.eq(1),
            dq_oe.eq(0),
            If(wait_cnt == 0,
                NextState("DONE"),
            ).Else(
                NextValue(wait_cnt, wait_cnt - 1),
            ),
        )
        fsm.act("DONE",
            done.eq(1),
            ce_n.eq(1),
            oe_n.eq(1),
            we_n.eq(1),
            adv_n.eq(1),
            dq_oe.eq(0),
            # Return to IDLE on next start.
            If(self._control.fields.start,
                NextValue(addr,   self._addr.storage),
                NextValue(data_w, self._data_w.storage),
                NextValue(rw,     self._control.fields.rw),
                NextValue(wait_cnt, 3 - 1),
                NextState("SETUP"),
            ),
        )

# BPI Flash --------------------------------------------------------------------------------------

class BPIFlash(LiteXModule):
    """BPI (Parallel NOR) Flash controller for x16 BPI flash (e.g. Micron MT28GU512AAA)."""
    def __init__(self, pads, sys_clk_freq, wait_cycles=20):
        self.bpi = BPIMaster(pads, sys_clk_freq, wait_cycles)
