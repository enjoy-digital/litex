# This file is Copyright (c) 2019 Antti Lukats <antti.lukats@gmail.com>
# This file is Copyright (c) 2016-2019 Florent Kermarrec <florent@enjoy-digital.fr>

# License: BSD

#
#
#

from migen import *
from migen.genlib.misc import timeline

from litex.gen import *

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import *


class HyperMemporyCommon(Module):
    def __init__(self, pads):
        self.pads = pads

class HyperRAM(HyperMemporyCommon):
    def __init__(self, pads):
        """
        HyperRAM simple core for LiteX
        This core should always just work on any FPGA platorm it is fully vendor neutral
        No configuration, no software setup, ready after poweron, fixed latency

        """
        HyperMemporyCommon.__init__(self, pads)

        if hasattr(pads, "rst_n"):
            self.comb += pads.rst_n.eq(1)
        if hasattr(pads, "cs1_n"):
            self.comb += pads.cs1_n.eq(1)

        # Tristate pads
        dq = TSTriple(8)
        self.specials.dq = dq.get_tristate(pads.dq)
        rwds = TSTriple(1)
        self.specials.rwds = rwds.get_tristate(pads.rwds)

        # Wishbone
        self.bus = bus = wishbone.Interface()
        sr = Signal(48)

        dq_oe = Signal(reset=0)
        rwds_oe = Signal(reset=0)
        cs_int = Signal(reset=1)

        self.comb += [
            bus.dat_r.eq(sr),
            dq.oe.eq(dq_oe),
            dq.o.eq(sr[-8:]),
            rwds.oe.eq(rwds_oe),
            pads.cs0_n.eq(cs_int)
        ]

        # we generate complementaty clk out for emulated differential output
        clk_p = Signal(1)
        clk_n = Signal(1)

        self.comb += pads.clk.eq(clk_p)
        # if negative is defined drive complementary clock out
        if hasattr(pads, "clk_n"):
            self.comb += pads.clk_n.eq(clk_n)
        # 1 sys clock delay needed to adjust input timings?
        dqi = Signal(8)
        self.sync += [
                dqi.eq(dq.i)
        ]
        # hyper RAM clock generator and 48 bit byte shifter
        i = Signal(max=4)
        self.sync += [
            If(i == 0,
                sr.eq(Cat(dqi, sr[:-8])),
            ),
            If(i == 1,
                clk_p.eq(~cs_int), # 1
                clk_n.eq(cs_int)   # 0
            ),
            If(i == 2,
                sr.eq(Cat(dqi, sr[:-8]))
            ),
            If(i == 3,
                i.eq(0),
                clk_p.eq(0),      # 1
                clk_n.eq(1)       # 0
            ).Else(
                i.eq(i + 1)
            )
        ]
        # signals to use CA or data to write
        CA = Signal(48)
        # combine bits to create CA bytes
        self.comb += [
            CA[47].eq(~self.bus.we),
            CA[45].eq(1),
            CA[16:35].eq(self.bus.adr[2:21]),
            CA[1:3].eq(self.bus.adr[0:2]),
            CA[0].eq(0),
        ]
        z = Replicate(0, 16)
        seq = [
            (3,        []),
            (12,       [cs_int.eq(0), dq_oe.eq(1), sr.eq(CA)]), # 6 clock edges for command transmit
            (44,       [dq_oe.eq(0)]),                          # 6+6 latency default
            (2,        [dq_oe.eq(self.bus.we), rwds_oe.eq(self.bus.we), rwds.o.eq(~bus.sel[0]), sr.eq(Cat(z, self.bus.dat_w))]), # 4 edges to write data
            (2,        [rwds.o.eq(~bus.sel[1])]), # 4 edges to write data
            (2,        [rwds.o.eq(~bus.sel[2])]), # 4 edges to write data
            (2,        [rwds.o.eq(~bus.sel[3])]), # 4 edges to write data
            (2,        [cs_int.eq(1), rwds_oe.eq(0), dq_oe.eq(0)]),
            (1,        [bus.ack.eq(1)]), # is 1 also OK?
            (1,        [bus.ack.eq(0)]), #
            (0,        []),
        ]

        t, tseq = 0, []
        for dt, a in seq:
            tseq.append((t, a))
            t += dt

        self.sync += timeline(bus.cyc & bus.stb & (i == 1), tseq)

