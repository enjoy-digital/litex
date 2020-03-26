from migen import *

from litex.soc.interconnect import stream

from litex.soc.cores.spi_xip.core import LiteSPICore


class LiteSPI(Module):
    def __init__(self, phy, endianness="big"):
        self.submodules.core = core = LiteSPICore(endianness)
        self.bus = core.bus

        self.comb += [
            phy.cs_n.eq(core.cs_n),
            phy.source.connect(core.sink),
            core.source.connect(phy.sink),
        ]
