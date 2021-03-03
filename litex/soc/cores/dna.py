#
# This file is part of LiteX.
#
# Copyright (c) 2014-2015 Robert Jordens <jordens@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.interconnect.csr import *


# Xilinx DNA (Device Identifier) -------------------------------------------------------------------

class DNA(Module, AutoCSR):
    def __init__(self):
        n = 57
        self._id = CSRStatus(n)

        # # #

        self.do    = do    = Signal()
        self.count = count = Signal(max=2*n + 1)
        self.clk   = clk   = Signal()

        self.comb += clk.eq(count[0])
        self.specials += Instance("DNA_PORT",
                i_DIN   = self._id.status[-1],
                o_DOUT  = do,
                i_CLK   = clk,
                i_READ  = count < 2,
                i_SHIFT = 1
        )

        self.sync += [
            If(count < 2*n,
                count.eq(count + 1),
                If(clk,
                    self._id.status.eq(Cat(do, self._id.status))
                )
            )
        ]

    def add_timing_constraints(self, platform, sys_clk_freq, sys_clk):
        platform.add_period_constraint(self.clk, 2*1e9/sys_clk_freq)
        platform.add_false_path_constraints(self.clk, sys_clk)
