# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *
from migen.genlib.misc import timeline

from litex.soc.interconnect import csr_bus, wishbone


class WB2CSR(Module):
    def __init__(self, bus_wishbone=None, bus_csr=None):
        self.csr = bus_csr
        if self.csr is None:
            # If no CSR bus provided, create it with default parameters.
            self.csr = csr_bus.Interface()
        self.wishbone = bus_wishbone
        if self.wishbone is None:
            # If no Wishbone bus provided, create it with default parameters.
            self.wishbone = wishbone.Interface()

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
