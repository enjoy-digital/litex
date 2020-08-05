# This file is Copyright (c) 2019 William D. Jones <thor0505@comcast.net>
# This file is Copyright (c) 2019 Tim 'mithro' Ansell <me@mith.ro>
# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *
from litex.soc.interconnect import wishbone

kB = 1024

"""
LIFCL Crosslink-NX family-specific Wishbone interface to the Single Port RAM (SPRAM) primitives.
Because it is single port, this module is meant to be used as the CPU's RAM region,
leaving block RAM free for other use.

Example: To get a 32-bit data bus, we must width-cascade 8 4-bit SPRAMs.

"""

class LIFCLSPRAM(Module):
    def __init__(self, width=32, size=64*kB):
        self.bus = wishbone.Interface(width)

        # # #

        assert width in [16, 32, 64]
        if width == 16:
            #assert size in [32*kB, 64*kB, 128*kB]
            depth_cascading = size//(128*kB)
            width_cascading = 8
        if width == 32:
            #assert size in [64*kB, 128*kB]
            depth_cascading = size//(256*kB)
            width_cascading = 16
        if width == 64:
            #assert size in [128*kB]
            depth_cascading = size//(512*kB)
            width_cascading = 32

        for d in range(depth_cascading):
            for w in range(width_cascading):
                datain = Signal(4)
                dataout = Signal(4)
                wren = Signal()
                self.comb += [
                    datain.eq(self.bus.dat_w[4*w:4*(w+1)]),
                    If(self.bus.adr[12:12+log2_int(depth_cascading)+1] == d,
                        wren.eq(self.bus.we & self.bus.stb & self.bus.cyc & self.bus.sel[w//2] ),
                        self.bus.dat_r[4*w:4*(w+1)].eq(dataout)
                    ),
                ]
                self.specials += Instance("SB_SPRAM256KA",
                    p_DATA_WIDTH="X4",
                    i_AD=Cat(self.bus.adr[:12],1,1),
                    i_DI=datain,
                    i_WREN=wren,
                    i_CS=0b000,
                    i_CLK=ClockSignal("sys"),
                    o_DO=dataout
                )

        self.sync += self.bus.ack.eq(self.bus.stb & self.bus.cyc & ~self.bus.ack)
