#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.specials import Tristate

from litex.gen import *

from litex.soc.cores.hyperbus import HyperRAM

# Gowin HyperRAM/PSRAM ----------------------------------------------------------------------------

class GowinHyperRAM(LiteXModule):
    """HyperRAM/PSRAM wrapper for Gowin raw tristate pads."""
    def __init__(self, pads, sys_clk_freq=100e6, chip=0, data_width=8, **kwargs):
        assert hasattr(pads, "clk")
        assert hasattr(pads, "clk_n")
        assert hasattr(pads, "cs_n")
        assert hasattr(pads, "rst_n")
        assert hasattr(pads, "dq")
        assert hasattr(pads, "rwds")
        assert data_width in [8, 16]

        # Split IOs expected by the generic HyperRAM core.
        class _Pads:
            pass
        split_pads = _Pads()
        split_pads.clk    = Signal()
        split_pads.rst_n  = pads.rst_n[chip]
        split_pads.cs_n   = pads.cs_n[chip]
        split_pads.dq_o   = Signal(data_width)
        split_pads.dq_oe  = Signal()
        split_pads.dq_i   = Signal(data_width)
        split_pads.rwds_o = Signal(data_width//8)
        split_pads.rwds_oe = Signal()
        split_pads.rwds_i = Signal(data_width//8)

        # Raw differential clock.
        self.comb += [
            pads.clk[chip].eq(split_pads.clk),
            pads.clk_n[chip].eq(~split_pads.clk),
        ]

        # Raw tristate data and RWDS.
        self.specials += [
            Tristate(
                pads.dq[data_width*chip:data_width*(chip+1)],
                o  = split_pads.dq_o,
                oe = split_pads.dq_oe,
                i  = split_pads.dq_i,
            ),
            Tristate(
                pads.rwds[chip],
                o  = split_pads.rwds_o,
                oe = split_pads.rwds_oe,
                i  = split_pads.rwds_i,
            ),
        ]

        self.hyperram = HyperRAM(split_pads, sys_clk_freq=sys_clk_freq, **kwargs)
        self.bus = self.hyperram.bus
