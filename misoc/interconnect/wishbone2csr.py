from migen import *
from migen.genlib.misc import timeline

from misoc.interconnect import csr_bus, wishbone


class WB2CSR(Module):
    def __init__(self, bus_wishbone=None, bus_csr=None):
        if bus_wishbone is None:
            bus_wishbone = wishbone.Interface()
        self.wishbone = bus_wishbone
        if bus_csr is None:
            bus_csr = csr_bus.Interface()
        self.csr = bus_csr

        ###

        self.sync += [
            self.csr.we.eq(0),
            self.csr.dat_w.eq(self.wishbone.dat_w),
            self.csr.adr.eq(self.wishbone.adr),
            self.wishbone.dat_r.eq(self.csr.dat_r)
        ]
        self.sync += timeline(self.wishbone.cyc & self.wishbone.stb, [
            (1, [self.csr.we.eq(self.wishbone.we)]),
            (2, [self.wishbone.ack.eq(1)]),
            (3, [self.wishbone.ack.eq(0)])
        ])
