from liteeth.common import *
from liteeth.mac.common import *
from liteeth.mac.core import preamble, crc, last_be

class LiteEthMACCore(Module, AutoCSR):
	def __init__(self, phy, dw, endianness="be", with_hw_preamble_crc=True):
		if dw < phy.dw:
			raise ValueError("Core data width({}) must be larger than PHY data width({})".format(dw, phy.dw))
		# Preamble / CRC (optional)
		if with_hw_preamble_crc:
			self._hw_preamble_crc = CSRStatus(reset=1)
			# Preamble insert/check
			preamble_inserter = preamble.LiteEthMACPreambleInserter(phy.dw)
			preamble_checker = preamble.LiteEthMACPreambleChecker(phy.dw)
			self.submodules += RenameClockDomains(preamble_inserter, "eth_tx")
			self.submodules += RenameClockDomains(preamble_checker, "eth_rx")

			# CRC insert/check
			crc32_inserter = crc.LiteEthMACCRC32Inserter(eth_description(phy.dw))
			crc32_checker = crc.LiteEthMACCRC32Checker(eth_description(phy.dw))
			self.submodules += RenameClockDomains(crc32_inserter, "eth_tx")
			self.submodules += RenameClockDomains(crc32_checker, "eth_rx")

		# Delimiters
		tx_last_be = last_be.LiteEthMACTXLastBE(phy.dw)
		rx_last_be = last_be.LiteEthMACRXLastBE(phy.dw)
		self.submodules += RenameClockDomains(tx_last_be, "eth_tx")
		self.submodules += RenameClockDomains(rx_last_be, "eth_rx")

		# Converters
		reverse = endianness == "be"
		tx_converter = Converter(eth_mac_description(dw), eth_mac_description(phy.dw), reverse=reverse)
		rx_converter = Converter(eth_mac_description(phy.dw), eth_mac_description(dw), reverse=reverse)
		self.submodules += RenameClockDomains(tx_converter, "eth_tx")
		self.submodules += RenameClockDomains(rx_converter, "eth_rx")

		# Cross Domain Crossing
		tx_cdc = AsyncFIFO(eth_mac_description(dw), 4)
		rx_cdc = AsyncFIFO(eth_mac_description(dw), 4)
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
