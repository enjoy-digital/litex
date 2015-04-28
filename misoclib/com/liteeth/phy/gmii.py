from migen.genlib.io import DDROutput

from misoclib.com.liteeth.common import *


class LiteEthPHYGMIITX(Module):
    def __init__(self, pads, pads_register=True):
        self.sink = sink = Sink(eth_phy_description(8))

        # # #

        if hasattr(pads, "tx_er"):
            self.sync += pads.tx_er.eq(0)
        pads_eq = [
            pads.tx_en.eq(sink.stb),
            pads.tx_data.eq(sink.data)
        ]
        if pads_register:
            self.sync += pads_eq
        else:
            self.comb += pads_eq
        self.comb += sink.ack.eq(1)


class LiteEthPHYGMIIRX(Module):
    def __init__(self, pads):
        self.source = source = Source(eth_phy_description(8))

        # # #

        dv_d = Signal()
        self.sync += dv_d.eq(pads.dv)

        sop = Signal()
        eop = Signal()
        self.comb += [
            sop.eq(pads.dv & ~dv_d),
            eop.eq(~pads.dv & dv_d)
        ]
        self.sync += [
            source.stb.eq(pads.dv),
            source.sop.eq(sop),
            source.data.eq(pads.rx_data)
        ]
        self.comb += source.eop.eq(eop)


class LiteEthPHYGMIICRG(Module, AutoCSR):
    def __init__(self, clock_pads, pads, with_hw_init_reset, mii_mode=0):
        self._reset = CSRStorage()

        # # #

        self.clock_domains.cd_eth_rx = ClockDomain()
        self.clock_domains.cd_eth_tx = ClockDomain()

        # RX : Let the synthesis tool insert the appropriate clock buffer
        self.comb += self.cd_eth_rx.clk.eq(clock_pads.rx)

        # TX : GMII: Drive clock_pads.gtx, clock_pads.tx unused
        #      MII: Use PHY clock_pads.tx as eth_tx_clk, do not drive clock_pads.gtx
        self.specials += DDROutput(1, mii_mode, clock_pads.gtx, ClockSignal("eth_tx"))
        # XXX Xilinx specific, replace BUFGMUX with a generic clock buffer?
        self.specials += Instance("BUFGMUX",
                                  i_I0=self.cd_eth_rx.clk,
                                  i_I1=clock_pads.tx,
                                  i_S=mii_mode,
                                  o_O=self.cd_eth_tx.clk)

        if with_hw_init_reset:
            reset = Signal()
            counter_done = Signal()
            self.submodules.counter = counter = Counter(max=512)
            self.comb += [
                counter_done.eq(counter.value == 256),
                counter.ce.eq(~counter_done),
                reset.eq(~counter_done | self._reset.storage)
            ]
        else:
            reset = self._reset.storage
        self.comb += pads.rst_n.eq(~reset)
        self.specials += [
            AsyncResetSynchronizer(self.cd_eth_tx, reset),
            AsyncResetSynchronizer(self.cd_eth_rx, reset),
        ]


class LiteEthPHYGMII(Module, AutoCSR):
    def __init__(self, clock_pads, pads, with_hw_init_reset=True):
        self.dw = 8
        self.submodules.crg = LiteEthPHYGMIICRG(clock_pads,
                                                pads,
                                                with_hw_init_reset)
        self.submodules.tx = RenameClockDomains(LiteEthPHYGMIITX(pads),
                                                "eth_tx")
        self.submodules.rx = RenameClockDomains(LiteEthPHYGMIIRX(pads),
                                                "eth_rx")
        self.sink, self.source = self.tx.sink, self.rx.source
