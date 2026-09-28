#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""
Gowin GW5A clocking for the USB 2.0 soft PHY (usb2_phy.phy.USB2PHY).

Generates the SerDes clock domains from a 960 MHz clock (same PLL as the 60 MHz UTMI clock): the
960 MHz clock is gated (DHCE) and divided by 8 (CLKDIV, 120 MHz); the SerDes reset sequence stops
the high-speed clock while CLKDIV/IOLOGIC are reset (for the SerDes alignment).
"""

from migen import *

from litex.gen import *

# GW5A SerDes Reset --------------------------------------------------------------------------------

class GW5ASerDesReset(LiteXModule):
    """
    SerDes reset sequence ("sys" domain): high-speed clock stopped (``stop``) with CLKDIV and IOLOGIC
    in reset, CLKDIV and IOLOGIC released while the clock is stopped, then high-speed clock started:
    CLKDIV and the SerDes (OSER/IDES) start in lockstep (deterministic word alignment).
    """
    def __init__(self, cycles=16):
        self.stop          = Signal(reset=1)
        self.reset         = Signal(reset=1)
        self.clkdiv_resetn = Signal()
        self.ready         = Signal()

        # # #

        timer = Signal(max=cycles)
        done  = Signal()
        self.comb += done.eq(timer == (cycles - 1))
        self.sync += If(done, timer.eq(0)).Else(timer.eq(timer + 1))

        self.fsm = fsm = FSM(reset_state="RESET")
        fsm.act("RESET",
            If(done, NextState("RELEASE"))
        )
        fsm.act("RELEASE",
            # Resets released, clock still stopped.
            self.clkdiv_resetn.eq(1),
            self.reset.eq(0),
            If(done, NextState("CLOCK_START"))
        )
        fsm.act("CLOCK_START",
            self.clkdiv_resetn.eq(1),
            self.reset.eq(0),
            self.stop.eq(0),
            If(done, NextState("READY"))
        )
        fsm.act("READY",
            self.clkdiv_resetn.eq(1),
            self.reset.eq(0),
            self.stop.eq(0),
            self.ready.eq(1),
        )

# GW5A USB 2.0 PHY CRG -----------------------------------------------------------------------------

class GW5AUSB2PHYCRG(LiteXModule):
    """
    Creates the ``cd_hs`` (120 MHz) and ``cd_hs_fast`` (960 MHz, gated) clock domains of USB2PHY from
    ``cd_960`` (960 MHz), the reset sequence runs in ``cd_utmi`` (60 MHz, its reset restarts it).
    ``serdes_rst`` is the SerDes (IOLOGIC) reset.
    """
    def __init__(self, cd_utmi="usb", cd_960="usb_960", cd_hs="usb_hs", cd_hs_fast="usb_hs_fast"):
        self.serdes_rst = Signal()

        # # #

        self.cd_hs      = ClockDomain(cd_hs)
        self.cd_hs_fast = ClockDomain(cd_hs_fast, reset_less=True)

        self.serdes_reset = serdes_reset = ClockDomainsRenamer(cd_utmi)(GW5ASerDesReset())
        self.specials += [
            Instance("DHCE", name="usb2_phy_dhce",
                i_CLKIN  = ClockSignal(cd_960),
                i_CEN    = serdes_reset.stop,
                o_CLKOUT = ClockSignal(cd_hs_fast),
            ),
            Instance("CLKDIV", name="usb2_phy_clkdiv",
                p_DIV_MODE = "8",
                i_HCLKIN   = ClockSignal(cd_hs_fast),
                i_RESETN   = serdes_reset.clkdiv_resetn,
                i_CALIB    = 0,
                o_CLKOUT   = ClockSignal(cd_hs),
            ),
        ]
        # cd_hs reset: synchronized release of the SerDes reset (reset-less synchronizer).
        rst_meta = Signal(reset_less=True, reset=1)
        rst_sync = Signal(reset_less=True, reset=1)
        sync_hs  = getattr(self.sync, cd_hs)
        sync_hs += [rst_meta.eq(~serdes_reset.ready), rst_sync.eq(rst_meta)]
        self.comb += [
            self.cd_hs.rst.eq(rst_sync),
            self.serdes_rst.eq(serdes_reset.reset),
        ]

    def add_timing_constraints(self, platform, cd_utmi, cd_960):
        """SerDes clock period and false paths between the UTMI (60 MHz), 960 MHz and SerDes (120 MHz)
        clocks (crossings: SerDes reset sequence, asynchronous FIFOs). The UTMI/960 MHz PLL clocks
        must be declared (ex: GW5APLL.add_generated_clock_constraints)."""
        platform.add_period_constraint(self.cd_hs.clk, 1e9/120e6)
        platform.add_false_path_constraints(cd_utmi.clk, cd_960.clk, self.cd_hs.clk)
