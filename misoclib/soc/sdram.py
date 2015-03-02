from migen.fhdl.std import *
from migen.bus import wishbone, csr

from misoclib.mem.sdram.bus import dfi, lasmibus
from misoclib.mem.sdram import minicon, lasmicon
from misoclib.mem.sdram import dfii
from misoclib.mem.sdram.frontend import memtest, wishbone2lasmi
from misoclib.soc import SoC, mem_decoder

class SDRAMSoC(SoC):
	csr_map = {
		"dfii":					7,
		"lasmicon":				8,
		"wishbone2lasmi":		9,
		"memtest_w":			10,
		"memtest_r":			11
	}
	csr_map.update(SoC.csr_map)

	def __init__(self, platform, clk_freq,
			ramcon_type="lasmicon",
			with_l2=True, l2_size=8192,
			with_memtest=False,
			**kwargs):
		SoC.__init__(self, platform, clk_freq, **kwargs)
		self.ramcon_type = ramcon_type

		self.with_l2 = with_l2
		self.l2_size = l2_size

		self.with_memtest = with_memtest

		self._sdram_phy_registered = False

	def register_sdram_phy(self, phy_dfi, phy_settings, sdram_geom, sdram_timing):
		if self._sdram_phy_registered:
			raise FinalizeError
		self._sdram_phy_registered = True

		# DFI
		self.submodules.dfii = dfii.DFIInjector(sdram_geom.mux_a, sdram_geom.bank_a,
			phy_settings.dfi_d, phy_settings.nphases)
		self.submodules.dficon0 = dfi.Interconnect(self.dfii.master, phy_dfi)

		# LASMICON
		if self.ramcon_type == "lasmicon":
			self.submodules.lasmicon = lasmicon.LASMIcon(phy_settings, sdram_geom, sdram_timing)
			self.submodules.dficon1 = dfi.Interconnect(self.lasmicon.dfi, self.dfii.slave)

			self.submodules.lasmixbar = lasmibus.Crossbar([self.lasmicon.lasmic], self.lasmicon.nrowbits)

			if self.with_memtest:
				self.submodules.memtest_w = memtest.MemtestWriter(self.lasmixbar.get_master())
				self.submodules.memtest_r = memtest.MemtestReader(self.lasmixbar.get_master())

			if self.with_l2:
				self.submodules.wishbone2lasmi = wishbone2lasmi.WB2LASMI(self.l2_size//4, self.lasmixbar.get_master())
				sdram_size = 2**self.lasmicon.lasmic.aw*self.lasmicon.lasmic.dw*self.lasmicon.lasmic.nbanks//8
				self.register_mem("sdram", self.mem_map["sdram"], self.wishbone2lasmi.wishbone, sdram_size)

		# MINICON
		elif self.ramcon_type == "minicon":
			if self.with_l2:
				raise ValueError("MINICON does not implement L2 cache (Use LASMICON or disable L2 cache (with_l2=False))")

			self.submodules.minicon = sdramcon = minicon.Minicon(phy_settings, sdram_geom, sdram_timing)
			self.submodules.dficon1 = dfi.Interconnect(sdramcon.dfi, self.dfii.slave)
			sdram_width = flen(sdramcon.bus.dat_r)

			sdram_size = 2**(sdram_geom.bank_a+sdram_geom.row_a+sdram_geom.col_a)*sdram_width//8

			if sdram_width == 32:
				self.register_mem("sdram", self.mem_map["sdram"], sdramcon.bus, sdram_size)
			elif sdram_width < 32:
				self.submodules.dc = wishbone.DownConverter(32, sdram_width)
				self.submodules.intercon = wishbone.InterconnectPointToPoint(self.dc.wishbone_o, sdramcon.bus)
				self.register_mem("sdram", self.mem_map["sdram"], self.dc.wishbone_i, sdram_size)
			else:
				raise NotImplementedError("Unsupported SDRAM width of {} > 32".format(sdram_width))
		else:
			raise ValueError("Unsupported SDRAM controller type: {}".format(self.ramcon_type))

	def do_finalize(self):
		if not self._sdram_phy_registered:
			raise FinalizeError("Need to call SDRAMSoC.register_sdram_phy()")
		SoC.do_finalize(self)
