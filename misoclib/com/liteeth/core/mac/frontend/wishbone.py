from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.core.mac.frontend import sram

from migen.bus import wishbone
from migen.fhdl.simplify import FullMemoryWE


class LiteEthMACWishboneInterface(Module, AutoCSR):
    def __init__(self, dw, nrxslots=2, ntxslots=2):
        self.sink = Sink(eth_phy_description(dw))
        self.source = Source(eth_phy_description(dw))
        self.bus = wishbone.Interface()

        # # #

        # storage in SRAM
        sram_depth = buffer_depth//(dw//8)
        self.submodules.sram = sram.LiteEthMACSRAM(dw, sram_depth, nrxslots, ntxslots)
        self.comb += [
            Record.connect(self.sink, self.sram.sink),
            Record.connect(self.sram.source, self.source)
        ]

        # Wishbone interface
        wb_rx_sram_ifs = [wishbone.SRAM(self.sram.writer.mems[n], read_only=True)
            for n in range(nrxslots)]
        # TODO: FullMemoryWE should move to Mibuild
        wb_tx_sram_ifs = [FullMemoryWE()(wishbone.SRAM(self.sram.reader.mems[n], read_only=False))
            for n in range(ntxslots)]
        wb_sram_ifs = wb_rx_sram_ifs + wb_tx_sram_ifs

        wb_slaves = []
        decoderoffset = log2_int(sram_depth)
        decoderbits = log2_int(len(wb_sram_ifs))
        for n, wb_sram_if in enumerate(wb_sram_ifs):
            def slave_filter(a, v=n):
                return a[decoderoffset:decoderoffset+decoderbits] == v
            wb_slaves.append((slave_filter, wb_sram_if.bus))
            self.submodules += wb_sram_if
        wb_con = wishbone.Decoder(self.bus, wb_slaves, register=True)
        self.submodules += wb_con
