# This file is Copyright (c) 2019 William D. Jones <thor0505@comcast.net>
# This file is Copyright (c) 2019 Tim 'mithro' Ansell <me@mith.ro>
# License: BSD


from migen import *
from litex.soc.interconnect import wishbone

"""
ICE40 UltraPlus family-specific Wishbone interface to the Single Port RAM
(SPRAM) primitives. Because SPRAM is much more coarse grained than Block
RAM resources, this RAM is only minimally configurable at present (64kB or
128kB). Because it is single port, this module is meant to be used as the
CPU's RAM region, leaving block RAM free for other use.
"""

class Up5kSPRAM(Module):
    def __init__(self, width=32, size=64*1024):

        # Right now, LiteX only supports 32-bit CPUs. To get a 32-bit data bus,
        # we must width-cascade 2 16-bit SPRAMs. We've already used 2 out of 4
        # SPRAMs for this, so the only other valid config is using all 4 SPRAMs
        # by depth-cascading.
        if width != 32:
            raise ValueError("Width of Up5kSPRAM must be 32 bits")
        if size != 64*1024 and size != 128*1024:
            raise ValueError("Size of Up5kSPRAM must be 64kB or 128kB.")

        self.bus = wishbone.Interface(width)

        bytesels = []
        for i in range(0, 2):
            datain = Signal(16)
            dataout = Signal(16)
            maskwren = Signal(4)
            wren = Signal(1)

            # 64k vs 128k-specific routing signals.
            datain0 = Signal(16)
            dataout0 = Signal(16)
            maskwren0 = Signal(4)

            if size == 128 * 1024:
                datain1 = Signal(16)
                dataout1 = Signal(16)
                maskwren1 = Signal(4)

            # Generic routing common to all depths.
            for j in range(16):
                self.comb += [self.bus.dat_r[16*i + j].eq(dataout[j])]

            self.comb += [
                datain.eq(self.bus.dat_w[16*i:16*i+16]),
                # MASKWREN is nibble-based, interestingly enough.
                maskwren.eq(
                    Cat(
                        Replicate(self.bus.sel[2*i], 2),
                        Replicate(self.bus.sel[2*i + 1], 2),
                    )
                ),
                wren.eq(self.bus.we & self.bus.stb & self.bus.cyc)
            ]

            # Signals which must be routed differently based on depth.
            # 64kB
            if size == 64*1024:
                self.comb += [
                    datain0.eq(datain),
                    dataout.eq(dataout0),
                    maskwren0.eq(maskwren)
                ]
            # 128kB
            else:
                self.comb += [
                    If(self.bus.adr[14],
                        datain1.eq(datain),
                        dataout.eq(dataout1),
                        maskwren1.eq(maskwren)
                    ).Else(
                        datain0.eq(datain),
                        dataout.eq(dataout0),
                        maskwren0.eq(maskwren)
                    )
                ]

            self.specials.spram = Instance("SB_SPRAM256KA",
                i_ADDRESS=self.bus.adr[0:14], i_DATAIN=datain0,
                i_MASKWREN=maskwren0,
                i_WREN=wren,
                i_CHIPSELECT=C(1,1),
                i_CLOCK=ClockSignal("sys"),
                i_STANDBY=C(0,1),
                i_SLEEP=C(0,1),
                i_POWEROFF=C(1,1),
                o_DATAOUT=dataout0
            )

            # We need to depth cascade if using 128kB.
            if size == 128*1024:
                self.specials.spram = Instance("SB_SPRAM256KA",
                    i_ADDRESS=self.bus.adr[0:14], i_DATAIN=datain1,
                    i_MASKWREN=maskwren1,
                    i_WREN=wren,
                    i_CHIPSELECT=C(1,1),
                    i_CLOCK=ClockSignal("sys"),
                    i_STANDBY=C(0,1),
                    i_SLEEP=C(0,1),
                    i_POWEROFF=C(1,1),
                    o_DATAOUT=dataout1
                )

        self.sync += [
            self.bus.ack.eq(0),
            If(self.bus.stb & self.bus.cyc & ~self.bus.ack,
                self.bus.ack.eq(1)
            )
        ]
