# This file is Copyright (c) 2014 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen.fhdl.std import *

from migen.bus import wishbone
from migen.actorlib.fifo import AsyncFIFO
from migen.actorlib.structuring import Converter, Pipeline
from migen.bank.eventmanager import SharedIRQ
from migen.bank.description import *
from migen.fhdl.simplify import *

from misoclib.ethmac.common import *
from misoclib.ethmac.preamble import PreambleInserter, PreambleChecker
from migen.actorlib.crc import CRC32Inserter, CRC32Checker
from misoclib.ethmac.last_be import TXLastBE, RXLastBE
from misoclib.ethmac.sram import SRAMWriter, SRAMReader

class EthMAC(Module, AutoCSR):
	def __init__(self, phy, interface="wishbone", with_hw_preamble_crc=True, endianness="be"):
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

		if interface == "wishbone":
			nrxslots = 2
			ntxslots = 2

			self.bus = wishbone.Interface()

			# SRAM Memories
			sram_depth = buffer_depth//(32//8)
			self.submodules.sram_writer = SRAMWriter(sram_depth, nrxslots)
			self.submodules.sram_reader = SRAMReader(sram_depth, ntxslots)
			self.submodules.ev = SharedIRQ(self.sram_writer.ev, self.sram_reader.ev)

			# Connect to pipelines
			self.comb += [
				self.rx_pipeline.source.connect(self.sram_writer.sink),
				self.sram_reader.source.connect(self.tx_pipeline.sink)
			]

			# Interface
			wb_rx_sram_ifs = [wishbone.SRAM(self.sram_writer.mems[n], read_only=True)
				for n in range(nrxslots)]
			# TODO: FullMemoryWE should move to Mibuild
			wb_tx_sram_ifs = [FullMemoryWE(wishbone.SRAM(self.sram_reader.mems[n], read_only=False))
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

		elif interface == "lasmi":
			raise NotImplementedError

		elif interface == "expose":
			# expose pipelines endpoints
			self.sink = tx_pipeline.sink
			self.source = rx_pipeline.source

		else:
			raise ValueError("EthMAC only supports Wishbone, LASMI or expose interfaces")
