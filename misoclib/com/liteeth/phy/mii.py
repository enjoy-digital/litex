from misoclib.com.liteeth.common import *


def converter_description(dw):
    payload_layout = [("data", dw)]
    return EndpointDescription(payload_layout, packetized=True)


class LiteEthPHYMIITX(Module):
    def __init__(self, pads, pads_register=True):
        self.sink = sink = Sink(eth_phy_description(8))

        # # #

        if hasattr(pads, "tx_er"):
            self.sync += pads.tx_er.eq(0)
        converter = Converter(converter_description(8),
                              converter_description(4))
        self.submodules += converter
        self.comb += [
            converter.sink.stb.eq(sink.stb),
            converter.sink.data.eq(sink.data),
            sink.ack.eq(converter.sink.ack),
            converter.source.ack.eq(1)
        ]
        pads_eq = [
            pads.tx_en.eq(converter.source.stb),
            pads.tx_data.eq(converter.source.data)
        ]
        if pads_register:
            self.sync += pads_eq
        else:
            self.comb += pads_eq


class LiteEthPHYMIIRX(Module):
    def __init__(self, pads):
        self.source = source = Source(eth_phy_description(8))

        # # #

        sop = FlipFlop(reset=1)
        self.submodules += sop

        converter = Converter(converter_description(4),
                              converter_description(8))
        converter = InsertReset(converter)
        self.submodules += converter

        self.sync += [
            converter.reset.eq(~pads.dv),
            converter.sink.stb.eq(1),
            converter.sink.data.eq(pads.rx_data)
        ]
        self.comb += [
            sop.reset.eq(~pads.dv),
            sop.ce.eq(pads.dv),
            converter.sink.sop.eq(sop.q),
            converter.sink.eop.eq(~pads.dv)
        ]
        self.comb += Record.connect(converter.source, source)


class LiteEthPHYMIICRG(Module, AutoCSR):
    def __init__(self, clock_pads, pads, with_hw_init_reset):
        self._reset = CSRStorage()

        # # #

        if hasattr(clock_pads, "phy"):
            self.sync.base50 += clock_pads.phy.eq(~clock_pads.phy)

        self.clock_domains.cd_eth_rx = ClockDomain()
        self.clock_domains.cd_eth_tx = ClockDomain()
        self.comb += self.cd_eth_rx.clk.eq(clock_pads.rx)
        self.comb += self.cd_eth_tx.clk.eq(clock_pads.tx)

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


class LiteEthPHYMII(Module, AutoCSR):
    def __init__(self, clock_pads, pads, with_hw_init_reset=True):
        self.dw = 8
        self.submodules.crg = LiteEthPHYMIICRG(clock_pads, pads, with_hw_init_reset)
        self.submodules.tx = RenameClockDomains(LiteEthPHYMIITX(pads), "eth_tx")
        self.submodules.rx = RenameClockDomains(LiteEthPHYMIIRX(pads), "eth_rx")
        self.sink, self.source = self.tx.sink, self.rx.source
