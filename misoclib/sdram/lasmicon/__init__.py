from migen.fhdl.std import *
from migen.bus import dfi, lasmibus

from misoclib.sdram.lasmicon.refresher import *
from misoclib.sdram.lasmicon.bankmachine import *
from misoclib.sdram.lasmicon.multiplexer import *

class LASMIcon(Module):
	def __init__(self, phy_settings, geom_settings, timing_settings):
		if phy_settings.memtype in ["SDR"]:
			burst_length = phy_settings.nphases*1 # command multiplication*SDR
		elif phy_settings.memtype in ["DDR", "LPDDR", "DDR2", "DDR3"]:
			burst_length = phy_settings.nphases*2 # command multiplication*DDR
		address_align = log2_int(burst_length)

		self.dfi = dfi.Interface(geom_settings.mux_a,
			geom_settings.bank_a,
			phy_settings.dfi_d,
			phy_settings.nphases)
		self.lasmic = lasmibus.Interface(
			aw=geom_settings.row_a + geom_settings.col_a - address_align,
			dw=phy_settings.dfi_d*phy_settings.nphases,
			nbanks=2**geom_settings.bank_a,
			req_queue_size=timing_settings.req_queue_size,
			read_latency=phy_settings.read_latency+1,
			write_latency=phy_settings.write_latency+1)
		self.nrowbits = geom_settings.col_a - address_align

		###

		self.submodules.refresher = Refresher(geom_settings.mux_a, geom_settings.bank_a,
			timing_settings.tRP, timing_settings.tREFI, timing_settings.tRFC)
		self.submodules.bank_machines = [BankMachine(geom_settings, timing_settings, address_align, i,
				getattr(self.lasmic, "bank"+str(i)))
			for i in range(2**geom_settings.bank_a)]
		self.submodules.multiplexer = Multiplexer(phy_settings, geom_settings, timing_settings,
			self.bank_machines, self.refresher,
			self.dfi, self.lasmic)

	def get_csrs(self):
		return self.multiplexer.get_csrs()
