from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.core.mac.core import gap, preamble, crc, padding, last_be
from misoclib.com.liteeth.phy.sim import LiteEthPHYSim
from misoclib.com.liteeth.phy.mii import LiteEthPHYMII


class LiteEthMACCore(Module, AutoCSR):
    def __init__(self, phy, dw, endianness="big",
            with_preamble_crc=True,
            with_padding=True):
        if dw < phy.dw:
            raise ValueError("Core data width({}) must be larger than PHY data width({})".format(dw, phy.dw))

        rx_pipeline = [phy]
        tx_pipeline = [phy]

        # Interpacket gap
        tx_gap_inserter = gap.LiteEthMACGap(phy.dw)
        rx_gap_checker = gap.LiteEthMACGap(phy.dw, ack_on_gap=True)
        self.submodules += RenameClockDomains(tx_gap_inserter, "eth_tx")
        self.submodules += RenameClockDomains(rx_gap_checker, "eth_rx")

        tx_pipeline += [tx_gap_inserter]
        rx_pipeline += [rx_gap_checker]

        # Preamble / CRC
        if isinstance(phy, LiteEthPHYSim):
            # In simulation, avoid CRC/Preamble to enable direct connection
            # to the Ethernet tap.
            self._preamble_crc = CSRStatus(reset=1)
        elif with_preamble_crc:
            self._preamble_crc = CSRStatus(reset=1)
            # Preamble insert/check
            preamble_inserter = preamble.LiteEthMACPreambleInserter(phy.dw)
            preamble_checker = preamble.LiteEthMACPreambleChecker(phy.dw)
            self.submodules += RenameClockDomains(preamble_inserter, "eth_tx")
            self.submodules += RenameClockDomains(preamble_checker, "eth_rx")

            # CRC insert/check
            crc32_inserter = crc.LiteEthMACCRC32Inserter(eth_phy_description(phy.dw))
            crc32_checker = crc.LiteEthMACCRC32Checker(eth_phy_description(phy.dw))
            self.submodules += RenameClockDomains(crc32_inserter, "eth_tx")
            self.submodules += RenameClockDomains(crc32_checker, "eth_rx")

            tx_pipeline += [preamble_inserter, crc32_inserter]
            rx_pipeline += [preamble_checker, crc32_checker]

        # Padding
        if with_padding:
            padding_inserter = padding.LiteEthMACPaddingInserter(phy.dw, 60)
            padding_checker = padding.LiteEthMACPaddingChecker(phy.dw, 60)
            self.submodules += RenameClockDomains(padding_inserter, "eth_tx")
            self.submodules += RenameClockDomains(padding_checker, "eth_rx")

            tx_pipeline += [padding_inserter]
            rx_pipeline += [padding_checker]

        # Delimiters
        if dw != 8:
            tx_last_be = last_be.LiteEthMACTXLastBE(phy.dw)
            rx_last_be = last_be.LiteEthMACRXLastBE(phy.dw)
            self.submodules += RenameClockDomains(tx_last_be, "eth_tx")
            self.submodules += RenameClockDomains(rx_last_be, "eth_rx")

            tx_pipeline += [tx_last_be]
            rx_pipeline += [rx_last_be]

        # Converters
        if dw != phy.dw:
            reverse = endianness == "big"
            tx_converter = Converter(eth_phy_description(dw),
                                     eth_phy_description(phy.dw),
                                     reverse=reverse)
            rx_converter = Converter(eth_phy_description(phy.dw),
                                     eth_phy_description(dw),
                                     reverse=reverse)
            self.submodules += RenameClockDomains(tx_converter, "eth_tx")
            self.submodules += RenameClockDomains(rx_converter, "eth_rx")

            tx_pipeline += [tx_converter]
            rx_pipeline += [rx_converter]

        # Cross Domain Crossing
        if isinstance(phy, LiteEthPHYMII):
            fifo_depth = 8
        else:
            fifo_depth = 64
        tx_cdc = AsyncFIFO(eth_phy_description(dw), fifo_depth)
        rx_cdc = AsyncFIFO(eth_phy_description(dw), fifo_depth)
        self.submodules += RenameClockDomains(tx_cdc, {"write": "sys", "read": "eth_tx"})
        self.submodules += RenameClockDomains(rx_cdc, {"write": "eth_rx", "read": "sys"})

        tx_pipeline += [tx_cdc]
        rx_pipeline += [rx_cdc]

        # Graph
        self.submodules.tx_pipeline = Pipeline(*reversed(tx_pipeline))
        self.submodules.rx_pipeline = Pipeline(*rx_pipeline)

        self.sink, self.source = self.tx_pipeline.sink, self.rx_pipeline.source
