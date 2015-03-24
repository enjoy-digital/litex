from migen.fhdl.std import *
from migen.genlib.record import *
from migen.bank.description import *

from misoclib.mem.sdram.phy import dfii
from misoclib.mem.sdram.core import minicon, lasmicon
from misoclib.mem.sdram.core import lasmixbar

class SDRAMCore(Module, AutoCSR):
	def __init__(self, phy, geom_settings, timing_settings, controller_settings, **kwargs):
		# DFI
		self.submodules.dfii = dfii.DFIInjector(geom_settings.addressbits, geom_settings.bankbits,
				phy.settings.dfi_databits, phy.settings.nphases)
		self.comb += Record.connect(self.dfii.master, phy.dfi)

		# LASMICON
		if isinstance(controller_settings, lasmicon.LASMIconSettings):
			self.submodules.controller = controller = lasmicon.LASMIcon(phy.settings, geom_settings, timing_settings,
				controller_settings, **kwargs)
			self.comb += Record.connect(controller.dfi, self.dfii.slave)

			self.submodules.crossbar = crossbar = lasmixbar.LASMIxbar([controller.lasmic], controller.nrowbits)

		# MINICON
		elif isinstance(controller_settings, minicon.MiniconSettings):
			self.submodules.controller = controller = minicon.Minicon(phy.settings, geom_settings, timing_settings)
			self.comb += Record.connect(controller.dfi, self.dfii.slave)
		else:
			raise ValueError("Unsupported SDRAM controller type")
