#
# This file is part of LiteX.
#
# Copyright (c) 2014-2015 Robert Jordens <jordens@gmail.com>
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.interconnect.csr import *


# Xilinx DNA (Device Identifier) -------------------------------------------------------------------

class DNA(Module, AutoCSR):
    nbits = 57
    def __init__(self):
        self._id = CSRStatus(self.nbits)

        # # #

        # Create slow DNA Clk (sys_clk/16).
        self.clock_domains.cd_dna = ClockDomain()
        dna_clk_count = Signal(4)
        self.sync += dna_clk_count.eq(dna_clk_count + 1)
        self.sync += self.cd_dna.clk.eq(dna_clk_count[3])


        # Shift-Out DNA Identifier.
        count = Signal(8)
        dout  = Signal()
        self.specials += Instance("DNA_PORT",
            i_CLK   = ClockSignal("dna"),
            i_READ  = (count == 0),
            i_SHIFT = 1,
            i_DIN   = 0,
            o_DOUT  = dout,
        )
        self.sync.dna += [
            If(count < (self.nbits + 1),
                count.eq(count + 1),
                self._id.status.eq(Cat(dout, self._id.status))
            )
        ]

    def add_timing_constraints(self, platform, sys_clk_freq, sys_clk):
        platform.add_period_constraint(self.cd_dna.clk, 16*1e9/sys_clk_freq)
        platform.add_false_path_constraints(self.cd_dna.clk, sys_clk)
