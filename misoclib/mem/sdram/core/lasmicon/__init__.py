from migen.fhdl.std import *

from misoclib.mem.sdram.phy import dfi
from misoclib.mem.sdram.core import lasmibus
from misoclib.mem.sdram.core.lasmicon.refresher import *
from misoclib.mem.sdram.core.lasmicon.bankmachine import *
from misoclib.mem.sdram.core.lasmicon.multiplexer import *

class LASMIconSettings:
	def __init__(self, req_queue_size=8,
			read_time=32, write_time=16,
			with_l2=True, l2_size=8192,
			with_bandwidth=False,
			with_memtest=False):
		self.req_queue_size = req_queue_size
		self.read_time = read_time
		self.write_time = write_time
		self.with_l2 = with_l2
		self.l2_size = l2_size
		self.with_bandwidth = with_bandwidth
		self.with_memtest = with_memtest

class LASMIcon(Module):
	def __init__(self, phy_settings, geom_settings, timing_settings, controller_settings, **kwargs):
		if phy_settings.memtype in ["SDR"]:
			burst_length = phy_settings.nphases*1 # command multiplication*SDR
		elif phy_settings.memtype in ["DDR", "LPDDR", "DDR2", "DDR3"]:
			burst_length = phy_settings.nphases*2 # command multiplication*DDR
		address_align = log2_int(burst_length)

		self.dfi = dfi.Interface(geom_settings.addressbits,
			geom_settings.bankbits,
			phy_settings.dfi_databits,
			phy_settings.nphases)
		self.lasmic = lasmibus.Interface(
			aw=geom_settings.rowbits + geom_settings.colbits - address_align,
			dw=phy_settings.dfi_databits*phy_settings.nphases,
			nbanks=2**geom_settings.bankbits,
			req_queue_size=controller_settings.req_queue_size,
			read_latency=phy_settings.read_latency+1,
			write_latency=phy_settings.write_latency+1)
		self.nrowbits = geom_settings.colbits - address_align

		###

		self.submodules.refresher = Refresher(geom_settings.addressbits, geom_settings.bankbits,
			timing_settings.tRP, timing_settings.tREFI, timing_settings.tRFC)
		self.submodules.bank_machines = [BankMachine(geom_settings, timing_settings, controller_settings, address_align, i,
				getattr(self.lasmic, "bank"+str(i)))
			for i in range(2**geom_settings.bankbits)]
		self.submodules.multiplexer = Multiplexer(phy_settings, geom_settings, timing_settings, controller_settings,
			self.bank_machines, self.refresher,
			self.dfi, self.lasmic,
			**kwargs)

	def get_csrs(self):
		return self.multiplexer.get_csrs()
