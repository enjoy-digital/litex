# This file is Copyright (c) 2019 William D. Jones <thor0505@comcast.net>
# This file is Copyright (c) 2019 Tim 'mithro' Ansell <me@mith.ro>
# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *
from litex.soc.interconnect import wishbone

kB = 1024

"""
RAM comprised of 2KByte 1Kx18 bit wide BRAMS

"""

class LIFCLSPRAM(Module):
    def __init__(self, width=32, size=64*kB):
        self.bus = wishbone.Interface(width)

        # # #

        assert width in [16, 32, 64]
        if width == 16:
            #assert size in [32*kB, 64*kB, 128*kB]
            depth_cascading = size//(2*kB)
            width_cascading = 1
        if width == 32:
            #assert size in [64*kB, 128*kB]
            depth_cascading = size//(4*kB)
            width_cascading = 2
        if width == 64:
            #assert size in [128*kB]
            depth_cascading = size//(8*kB)
            width_cascading = 4

        for d in range(depth_cascading):
            for w in range(width_cascading):
                datain = Signal(16)
                dataout = Signal(16)
                wren = Signal()
                self.comb += [
                    datain.eq(self.bus.dat_w[16*w:16*(w+1)]),
                    If(self.bus.adr[10:10+log2_int(depth_cascading)+1] == d,
                        wren.eq(self.bus.we & self.bus.stb & self.bus.cyc & self.bus.sel[w//2] ),
                        self.bus.dat_r[16*w:16*(w+1)].eq(dataout)
                    ),
                ]
                self.specials += Instance("SP16K",
                    i_AD=Cat(self.bus.adr[:10], 1, 1, 1, 1),
                    i_DI=datain,
                    i_WE=wren,
                    i_CS=0b000,
                    i_CLK=ClockSignal("sys"),
                    o_DO=dataout
                )

        self.sync += self.bus.ack.eq(self.bus.stb & self.bus.cyc & ~self.bus.ack)
