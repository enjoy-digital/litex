# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *
from migen.genlib.misc import timeline

from litex.soc.interconnect import csr_bus, wishbone


class WB2CSR(Module):
    def __init__(self, bus_wishbone=None, bus_csr=None):
        if bus_wishbone is None:
            bus_wishbone = wishbone.Interface()
        self.wishbone = bus_wishbone
        if bus_csr is None:
            bus_csr = csr_bus.Interface()
        self.csr = bus_csr

        # # #

        self.comb += [
            self.csr.dat_w.eq(self.wishbone.dat_w),
            self.wishbone.dat_r.eq(self.csr.dat_r)
        ]

        fsm = FSM(reset_state="WRITE-READ")
        self.submodules += fsm
        fsm.act("WRITE-READ",
            If(self.wishbone.cyc & self.wishbone.stb,
                self.csr.adr.eq(self.wishbone.adr),
                self.csr.we.eq(self.wishbone.we),
                NextState("ACK")
            )
        )
        fsm.act("ACK",
            self.wishbone.ack.eq(1),
            NextState("WRITE-READ")
        )
