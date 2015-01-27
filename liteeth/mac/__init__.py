from liteethernet.common import *
from liteethernet.mac import LiteEthernetMAC

class LiteEthernetMAC(Module, AutoCSR):
	def __init__(self, phy, frontend="wishbone", with_hw_preamble_crc=True, endianness="be"):
		self.submodules.core = LiteEthernetMAC(phy, with_hw_preamble, endianness)

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
