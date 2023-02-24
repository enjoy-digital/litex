#
# This file is part of LiteX.
#
# Copyright (c) 2014-2015 Robert Jordens <jordens@gmail.com>
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import math

from migen import *

from litex.gen import *

from litex.soc.interconnect.csr import *

# Xilinx DNA (Device Identifier) -------------------------------------------------------------------

class XilinxDNA(Module, AutoCSR):
    def __init__(self, nbits=57, primitive="DNA_PORT", clk_divider=2):
        self.nbits       = nbits
        self.clk_divider = clk_divider
        self._id = CSRStatus(nbits)

        # # #

        # Parameters check.
        assert nbits      <= 256
        assert clk_divider > 1
        assert math.log2(clk_divider).is_integer()

        # Create slow DNA Clk.
        self.clock_domains.cd_dna = ClockDomain()
        dna_clk_count = Signal(int(math.log2(clk_divider)))
        self.sync += dna_clk_count.eq(dna_clk_count + 1)
        self.sync += self.cd_dna.clk.eq(dna_clk_count[-1])


        # Shift-Out DNA Identifier.
        count = Signal(8)
        dout  = Signal()
        self.specials += Instance(primitive,
            i_CLK   = ClockSignal("dna"),
            i_READ  = (count == 0),
            i_SHIFT = 1,
            i_DIN   = 0,
            o_DOUT  = dout,
        )
        self.sync.dna += [
            If(count < (nbits + 1),
                count.eq(count + 1),
                self._id.status.eq(Cat(dout, self._id.status))
            )
        ]

    def add_timing_constraints(self, platform, sys_clk_freq, sys_clk):
        platform.add_period_constraint(self.cd_dna.clk, self.clk_divider*1e9/sys_clk_freq)
        platform.add_false_path_constraints(self.cd_dna.clk, sys_clk)

# Xilinx 7-Series DNA ------------------------------------------------------------------------------

class S7DNA(XilinxDNA):
    def __init__(self, *args, **kwargs):
        XilinxDNA.__init__(self, nbits=57, primitive="DNA_PORT", *args, **kwargs)

class DNA(XilinxDNA): pass # Compat.

# Xilinx Ultrascale DNA ----------------------------------------------------------------------------

class USDNA(XilinxDNA):
    def __init__(self, *args, **kwargs):
        XilinxDNA.__init__(self, nbits=96, primitive="DNA_PORTE2", *args, **kwargs)
