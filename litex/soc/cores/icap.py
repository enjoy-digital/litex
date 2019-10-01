# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *

from migen.genlib.misc import timeline
from migen.genlib.cdc import PulseSynchronizer

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream

# Xilinx 7-series ----------------------------------------------------------------------------------

class ICAP(Module, AutoCSR):
    """ICAP

    Allow sending bitstreams to ICAPE2 of Xilinx 7-Series FPGAs.
    """
    def __init__(self, simulation=False):
        self.data = CSRStorage(32, reset=0xffffffff)
        self.icap_en = CSRStorage(reset=0)
        self.fifofull = CSRStatus()
        self.done = CSRStatus(reset=1)

        # # #

        # Create slow icap clk (sys_clk/4) ---------------------------------------------------------
        self.clock_domains.cd_icap = ClockDomain()
        icap_clk_counter = Signal(4)
        self.sync += icap_clk_counter.eq(icap_clk_counter + 1)
        self.sync += self.cd_icap.clk.eq(icap_clk_counter[1])

        # Helper signals
        _csib = Signal(reset=1)
        _i = Signal(32, reset=0xffffffff)
        acknext = Signal(reset=0)
        syncdata = Signal(32, reset=0xffffffff)

        # FIFO
        fifo = stream.AsyncFIFO([("data", 32)], 8)
        icapfifo = ClockDomainsRenamer({"write": "sys", "read": "icap"})(fifo)

        # Connect to FIFO
        self.comb += [
            icapfifo.sink.valid.eq(self.data.re),
            icapfifo.sink.data.eq(self.data.storage),
            self.fifofull.status.eq(~icapfifo.sink.ready),
            syncdata.eq(icapfifo.source.data),
            icapfifo.source.ready.eq(acknext),
        ]
        self.submodules += icapfifo

        self.sync.icap += [
            If(self.icap_en.storage & icapfifo.source.valid & ~acknext,
                acknext.eq(1),
                self.done.status.eq(0)
            ).Elif(self.icap_en.storage & icapfifo.source.valid & acknext,
                _i.eq(syncdata),
                _csib.eq(0)
            ).Else(
                _i.eq(0xffffffff),
                _csib.eq(1),
                acknext.eq(0),
                self.done.status.eq(1)
            ),
        ]

        self._csib = _csib
        self._i = _i

        # icap instance
        if not simulation:
            self.specials += [
                Instance("ICAPE2",
                    p_ICAP_WIDTH="X32",
                    i_CLK=ClockSignal("icap"),
                    i_CSIB=_csib,
                    i_RDWRB=0,
                    i_I=Cat(*[_i[8*i:8*(i+1)][::-1] for i in range(4)]),
                )
            ]
