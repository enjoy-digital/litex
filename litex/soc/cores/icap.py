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

    Allow sending commands to ICAPE2 of Xilinx 7-Series FPGAs, the bistream can for example be
    reloaded from SPI Flash by writing 0x00000000 at address @0x4.
    """
    def __init__(self, simulation=False):
        self.addr = CSRStorage(5)
        self.data = CSRStorage(32)
        self.send = CSR()
        self.done = CSRStatus(reset=1)

        # # #

        # Create slow icap clk (sys_clk/16) ---------------------------------------------------------
        self.clock_domains.cd_icap = ClockDomain()
        icap_clk_counter = Signal(4)
        self.sync += icap_clk_counter.eq(icap_clk_counter + 1)
        self.sync += self.cd_icap.clk.eq(icap_clk_counter[3])

        # Resychronize send pulse to icap domain ---------------------------------------------------
        ps_send = PulseSynchronizer("sys", "icap")
        self.submodules += ps_send
        self.comb += [ps_send.i.eq(self.send.re)]

        # Generate icap bitstream write sequenceenerate icap bitstream write sequence
        _csib = Signal(reset=1)
        _i = Signal(32)
        _addr = self.addr.storage << 13
        _data = self.data.storage
        self.sync.icap += [
            _i.eq(0xffffffff), # dummy
            timeline(ps_send.o, [
                (1,  [_csib.eq(1), self.done.status.eq(0)]),
                (2,  [_csib.eq(0), _i.eq(0x20000000)]),         # noop
                (3,  [_csib.eq(0), _i.eq(0xaa995566)]),         # sync word
                (4,  [_csib.eq(0), _i.eq(0x20000000)]),         # noop
                (5,  [_csib.eq(0), _i.eq(0x20000000)]),         # noop
                (6,  [_csib.eq(0), _i.eq(0x30000001 | _addr)]), # write command
                (7,  [_csib.eq(0), _i.eq(_data)]),              # write value
                (8,  [_csib.eq(0), _i.eq(0x20000000)]),         # noop
                (9,  [_csib.eq(0), _i.eq(0x20000000)]),         # noop
                (10, [_csib.eq(0), _i.eq(0x30008001)]),         # write to cmd register
                (11, [_csib.eq(0), _i.eq(0x0000000d)]),         # desync command
                (12, [_csib.eq(0), _i.eq(0x20000000)]),         # noop
                (13, [_csib.eq(0), _i.eq(0x20000000)]),         # noop
                (14, [_csib.eq(1), self.done.status.eq(1)]),
            ])
        ]

        self._csib = _csib
        self._i    = _i

        # ICAP instance
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


class ICAPBitstream(Module, AutoCSR):
    """ICAP

    Allow sending bitstreams to ICAPE2 of Xilinx 7-Series FPGAs.
    """
    def __init__(self, fifo_depth=8, simulation=False):
        self.sink_data  = CSRStorage(32)
        self.sink_ready = CSRStatus()
        self.start      = CSR()
        self.done       = CSRStatus()

        # # #

        _run  = Signal()
        _csib = Signal(reset=1)
        _i    = Signal(32, reset=0xffffffff)

        # Create slow icap clk (sys_clk/4) ---------------------------------------------------------
        self.clock_domains.cd_icap = ClockDomain()
        icap_clk_counter = Signal(4)
        self.sync += icap_clk_counter.eq(icap_clk_counter + 1)
        self.sync += self.cd_icap.clk.eq(icap_clk_counter[1])

        # FIFO
        fifo = stream.AsyncFIFO([("data", 32)], fifo_depth)
        fifo = ClockDomainsRenamer({"write": "sys", "read": "icap"})(fifo)
        self.submodules += fifo
        self.comb += [
            fifo.sink.valid.eq(self.sink_data.re),
            fifo.sink.data.eq(self.sink_data.storage),
            self.sink_ready.status.eq(fifo.sink.ready),
        ]

        # Generate ICAP commands
        self.sync.icap += [
            If(self.start.re,
                _run.eq(1),
            ).Elif(~fifo.source.valid,
                _run.eq(0)
            )
        ]
        self.comb += [
            self.done.status.eq(~_run),
            If(_run,
                _i.eq(fifo.source.data),
                _csib.eq(0),
                fifo.source.ready.eq(1)
            )
        ]

        self._csib = _csib
        self._i    = _i

        # ICAP instance
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
