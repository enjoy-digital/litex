#
# This file is part of LiteX.
#
# Copyright (c) 2020 David Corrigan <davidcorrigan714@gmail.com>
# Copyright (c) 2019 William D. Jones <thor0505@comcast.net>
# Copyright (c) 2019 Tim 'mithro' Ansell <me@mith.ro>
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from litex.soc.interconnect import wishbone

kB = 1024

"""
NX family-specific Wishbone interface to the LRAM primitive.

Each LRAM is 64kBytes arranged in 32 bit wide words.

Note that this memory is dual port, but we only use a single port in this
instantiation.
"""

class NXLRAM(Module):
    def __init__(self, width=32, size=128*kB):
        self.bus = wishbone.Interface(width)
        assert width in [32, 64]

        # TODO: allow larger sizes to support Crosslink/NX-17 & Certus
        if width == 32:
            assert size in [64*kB, 128*kB]
            depth_cascading = size//(64*kB)
            width_cascading = 1
        if width == 64:
            assert size in [128*kB]
            depth_cascading = size//(128*kB)
            width_cascading = 2

        for d in range(depth_cascading):
            for w in range(width_cascading):
                datain = Signal(32)
                dataout = Signal(32)
                cs = Signal()
                wren = Signal()
                self.comb += [
                    cs.eq(self.bus.adr[14:14+log2_int(depth_cascading)+1] == d),
                    wren.eq(self.bus.we & self.bus.stb & self.bus.cyc),
                    datain.eq(self.bus.dat_w[32*w:32*(w+1)]),
                    If(cs,
                        self.bus.dat_r[32*w:32*(w+1)].eq(dataout)
                    ),
                ]
                self.specials += Instance("SP512K",
                    p_ECC_BYTE_SEL = "BYTE_EN",
                    i_DI       = datain,
                    i_AD       = self.bus.adr[:14],
                    i_CLK      = ClockSignal(),
                    i_CE       = 0b1,
                    i_WE       = wren,
                    i_CS       = cs,
                    i_RSTOUT   = 0b0,
                    i_CEOUT    = 0b0,
                    i_BYTEEN_N = ~self.bus.sel[4*w:4*(w+1)],
                    o_DO       = dataout
                )

        self.sync += self.bus.ack.eq(self.bus.stb & self.bus.cyc & ~self.bus.ack)
