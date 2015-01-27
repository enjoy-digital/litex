
from liteethernet.common import *
from liteethernet.mac.common import *
from liteethernet.mac.preamble import PreambleInserter, PreambleChecker
from liteethernet.mac.crc import CRC32Inserter, CRC32Checker
from liteethernet.mac.last_be import TXLastBE, RXLastBE

class LiteEthernetMACCore(Module, AutoCSR):
	def __init__(self, phy, with_hw_preamble_crc=True, endianness="be"):
		# Preamble / CRC (optional)
		if with_hw_preamble_crc:
			self._hw_preamble_crc = CSRStatus(reset=1)
			# Preamble insert/check
			preamble_inserter = PreambleInserter(phy.dw)
			preamble_checker = PreambleChecker(phy.dw)
			self.submodules += RenameClockDomains(preamble_inserter, "eth_tx")
			self.submodules += RenameClockDomains(preamble_checker, "eth_rx")

			# CRC insert/check
			crc32_inserter = CRC32Inserter(eth_description(phy.dw))
			crc32_checker = CRC32Checker(eth_description(phy.dw))
			self.submodules += RenameClockDomains(crc32_inserter, "eth_tx")
			self.submodules += RenameClockDomains(crc32_checker, "eth_rx")

		# Delimiters
		tx_last_be = TXLastBE(phy.dw)
		rx_last_be = RXLastBE(phy.dw)
		self.submodules += RenameClockDomains(tx_last_be, "eth_tx")
		self.submodules += RenameClockDomains(rx_last_be, "eth_rx")

		# Converters
		reverse = endianness == "be"
		tx_converter = Converter(eth_description(32), eth_description(phy.dw), reverse=reverse)
		rx_converter = Converter(eth_description(phy.dw), eth_description(32), reverse=reverse)
		self.submodules += RenameClockDomains(tx_converter, "eth_tx")
		self.submodules += RenameClockDomains(rx_converter, "eth_rx")

		# Cross Domain Crossing
		tx_cdc = AsyncFIFO(eth_description(32), 4)
		rx_cdc = AsyncFIFO(eth_description(32), 4)
		self.submodules +=  RenameClockDomains(tx_cdc, {"write": "sys", "read": "eth_tx"})
		self.submodules +=  RenameClockDomains(rx_cdc, {"write": "eth_rx", "read": "sys"})

		# Graph
		if with_hw_preamble_crc:
			rx_pipeline = [phy, preamble_checker, crc32_checker, rx_last_be, rx_converter, rx_cdc]
			tx_pipeline = [tx_cdc, tx_converter, tx_last_be, crc32_inserter, preamble_inserter, phy]
		else:
			rx_pipeline = [phy, rx_last_be, rx_converter, rx_cdc]
			tx_pipeline = [tx_cdc, tx_converter, tx_last_be, phy]
		self.submodules.rx_pipeline = Pipeline(*rx_pipeline)
		self.submodules.tx_pipeline = Pipeline(*tx_pipeline)

		self.sink, self.source = self.tx_pipeline.sink, self.rx_pipeline.source
