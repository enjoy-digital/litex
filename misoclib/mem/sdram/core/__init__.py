from migen.fhdl.std import *
from migen.genlib.record import *
from migen.bank.description import *

from misoclib.mem.sdram.phy import dfii
from misoclib.mem.sdram.core import minicon, lasmicon
from misoclib.mem.sdram.core.lasmicon.crossbar import Crossbar

class SDRAMCore(Module, AutoCSR):
	def __init__(self, phy, ramcon_type, sdram_geom, sdram_timing, **kwargs):
		# DFI
		self.submodules.dfii = dfii.DFIInjector(sdram_geom.mux_a, sdram_geom.bank_a,
				phy.settings.dfi_d, phy.settings.nphases)
		self.comb += Record.connect(self.dfii.master, phy.dfi)

		# LASMICON
		if ramcon_type == "lasmicon":
			self.submodules.controller = controller = lasmicon.LASMIcon(phy.settings, sdram_geom, sdram_timing, **kwargs)
			self.comb += Record.connect(controller.dfi, self.dfii.slave)

			self.submodules.crossbar = crossbar = Crossbar([controller.lasmic], controller.nrowbits)

		# MINICON
		elif ramcon_type == "minicon":
			self.submodules.controller = controller = minicon.Minicon(phy.settings, sdram_geom, sdram_timing)
			self.comb += Record.connect(controller.dfi, self.dfii.slave)
		else:
			raise ValueError("Unsupported SDRAM controller type: {}".format(self.ramcon_type))
