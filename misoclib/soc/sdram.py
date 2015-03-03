from migen.fhdl.std import *
from migen.bus import wishbone, csr
from migen.genlib.record import *

from misoclib.mem.sdram.core import SDRAMCore
from misoclib.mem.sdram.frontend import memtest, wishbone2lasmi
from misoclib.soc import SoC, mem_decoder

class SDRAMSoC(SoC):
	csr_map = {
		"sdram":				8,
		"wishbone2lasmi":		9,
		"memtest_w":			10,
		"memtest_r":			11
	}
	csr_map.update(SoC.csr_map)

	def __init__(self, platform, clk_freq,
			ramcon_type="lasmicon",
			with_l2=True, l2_size=8192,
			with_bandwidth=False,	# specific to LASMICON,
			with_memtest=False,     # ignored for MINICON
			**kwargs):
		SoC.__init__(self, platform, clk_freq, **kwargs)
		self.ramcon_type = ramcon_type

		self.with_l2 = with_l2
		self.l2_size = l2_size

		self.with_memtest = with_memtest
		self.with_bandwidth = with_bandwidth or with_memtest

		self._sdram_phy_registered = False

	def register_sdram_phy(self, phy, sdram_geom, sdram_timing):
		if self._sdram_phy_registered:
			raise FinalizeError
		self._sdram_phy_registered = True

		# Core
		self.submodules.sdram = SDRAMCore(phy, self.ramcon_type, sdram_geom, sdram_timing)

		# LASMICON frontend
		if self.ramcon_type == "lasmicon":
			if self.with_bandwidth:
				self.sdram.controller.multiplexer.add_bandwidth()

			if self.with_memtest:
				self.submodules.memtest_w = memtest.MemtestWriter(self.sdram.crossbar.get_master())
				self.submodules.memtest_r = memtest.MemtestReader(self.sdram.crossbar.get_master())

			if self.with_l2:
				self.submodules.wishbone2lasmi = wishbone2lasmi.WB2LASMI(self.l2_size//4, self.sdram.crossbar.get_master())
				lasmic = self.sdram.controller.lasmic
				sdram_size = 2**lasmic.aw*lasmic.dw*lasmic.nbanks//8
				self.register_mem("sdram", self.mem_map["sdram"], self.wishbone2lasmi.wishbone, sdram_size)

		# MINICON frontend
		elif self.ramcon_type == "minicon":
			sdram_width = flen(self.sdram.controller.bus.dat_r)
			sdram_size = 2**(sdram_geom.bank_a+sdram_geom.row_a+sdram_geom.col_a)*sdram_width//8

			if sdram_width == 32:
				self.register_mem("sdram", self.mem_map["sdram"], self.sdram.controller.bus, sdram_size)
			elif sdram_width < 32:
				self.submodules.downconverter = downconverter = wishbone.DownConverter(32, sdram_width)
				self.comb += Record.connect(downconverter.wishbone_o, self.sdram.controller.bus)
				self.register_mem("sdram", self.mem_map["sdram"], downconverter.wishbone_i, sdram_size)
			else:
				raise NotImplementedError("Unsupported SDRAM width of {} > 32".format(sdram_width))

	def do_finalize(self):
		if not self._sdram_phy_registered:
			raise FinalizeError("Need to call SDRAMSoC.register_sdram_phy()")
		SoC.do_finalize(self)
