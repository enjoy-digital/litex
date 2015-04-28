from migen.genlib.io import DDROutput
from migen.flow.plumbing import Multiplexer, Demultiplexer
from migen.genlib.cdc import PulseSynchronizer

from misoclib.com.liteeth.common import *

from misoclib.com.liteeth.phy.gmii import LiteEthPHYGMIICRG
from misoclib.com.liteeth.phy.mii import LiteEthPHYMIITX, LiteEthPHYMIIRX
from misoclib.com.liteeth.phy.gmii import LiteEthPHYGMIITX, LiteEthPHYGMIIRX

modes = {
    "GMII": 0,
    "MII": 1
}

tx_pads_layout = [("tx_er", 1), ("tx_en", 1), ("tx_data", 8)]
rx_pads_layout = [("rx_er", 1), ("dv", 1), ("rx_data", 8)]


class LiteEthPHYGMIIMIITX(Module):
    def __init__(self, pads, mode):
        self.sink = sink = Sink(eth_phy_description(8))

        # # #

        gmii_tx_pads = Record(tx_pads_layout)
        gmii_tx = LiteEthPHYGMIITX(gmii_tx_pads, pads_register=False)
        self.submodules += gmii_tx

        mii_tx_pads = Record(tx_pads_layout)
        mii_tx = LiteEthPHYMIITX(mii_tx_pads, pads_register=False)
        self.submodules += mii_tx

        demux = Demultiplexer(eth_phy_description(8), 2)
        self.submodules += demux
        self.comb += [
            demux.sel.eq(mode == modes["MII"]),
            Record.connect(sink, demux.sink),
            Record.connect(demux.source0, gmii_tx.sink),
            Record.connect(demux.source1, mii_tx.sink),
        ]

        if hasattr(pads, "tx_er"):
            self.comb += pads.tx_er.eq(0)
        self.sync += [
            If(mode == modes["MII"],
                pads.tx_en.eq(mii_tx_pads.tx_en),
                pads.tx_data.eq(mii_tx_pads.tx_data),
            ).Else(
                pads.tx_en.eq(gmii_tx_pads.tx_en),
                pads.tx_data.eq(gmii_tx_pads.tx_data),
            )
        ]


class LiteEthPHYGMIIMIIRX(Module):
    def __init__(self, pads, mode):
        self.source = source = Source(eth_phy_description(8))

        # # #

        pads_d = Record(rx_pads_layout)
        self.sync += [
            pads_d.dv.eq(pads.dv),
            pads_d.rx_data.eq(pads.rx_data)
        ]

        gmii_rx = LiteEthPHYGMIIRX(pads_d)
        self.submodules += gmii_rx

        mii_rx = LiteEthPHYMIIRX(pads_d)
        self.submodules += mii_rx

        mux = Multiplexer(eth_phy_description(8), 2)
        self.submodules += mux
        self.comb += [
            mux.sel.eq(mode == modes["MII"]),
            Record.connect(gmii_rx.source, mux.sink0),
            Record.connect(mii_rx.source, mux.sink1),
            Record.connect(mux.source, source)
        ]


class LiteEthGMIIMIIModeDetection(Module, AutoCSR):
    def __init__(self, clk_freq):
        self.mode = Signal()
        self._mode = CSRStatus()

        # # #

        mode = Signal()
        update_mode = Signal()
        self.sync += \
            If(update_mode,
                self.mode.eq(mode)
            )
        self.comb += self._mode.status.eq(self.mode)

        # Principle:
        #  sys_clk >= 125MHz
        #  eth_rx <= 125Mhz
        # We generate ticks every 1024 clock cycles in eth_rx domain
        # and measure ticks period in sys_clk domain.

        # Generate a tick every 1024 clock cycles (eth_rx clock domain)
        eth_tick = Signal()
        eth_counter = Signal(10)
        self.sync.eth_rx += eth_counter.eq(eth_counter + 1)
        self.comb += eth_tick.eq(eth_counter == 0)

        # Synchronize tick (sys clock domain)
        sys_tick = Signal()
        eth_ps = PulseSynchronizer("eth_rx", "sys")
        self.comb += [
            eth_ps.i.eq(eth_tick),
            sys_tick.eq(eth_ps.o)
        ]
        self.submodules += eth_ps

        # sys_clk domain counter
        sys_counter = Counter(24)
        self.submodules += sys_counter

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        fsm.act("IDLE",
            sys_counter.reset.eq(1),
            If(sys_tick,
                NextState("COUNT")
            )
        )
        fsm.act("COUNT",
            sys_counter.ce.eq(1),
            If(sys_tick,
                NextState("DETECTION")
            )
        )
        fsm.act("DETECTION",
            update_mode.eq(1),
            # if freq < 125MHz-5% use MII mode
            If(sys_counter.value > int((clk_freq/125000000)*1024*1.05),
                mode.eq(1)
            # if freq >= 125MHz-5% use GMII mode
            ).Else(
                mode.eq(0)
            ),
            NextState("IDLE")
        )


class LiteEthPHYGMIIMII(Module, AutoCSR):
    def __init__(self, clock_pads, pads, clk_freq, with_hw_init_reset=True):
        self.dw = 8
        # Note: we can use GMII CRG since it also handles tx clock pad used for MII
        self.submodules.mode_detection = LiteEthGMIIMIIModeDetection(clk_freq)
        mode = self.mode_detection.mode
        self.submodules.crg = LiteEthPHYGMIICRG(clock_pads, pads, with_hw_init_reset, mode == modes["MII"])
        self.submodules.tx = RenameClockDomains(LiteEthPHYGMIIMIITX(pads, mode), "eth_tx")
        self.submodules.rx = RenameClockDomains(LiteEthPHYGMIIMIIRX(pads, mode), "eth_rx")
        self.sink, self.source = self.tx.sink, self.rx.source
