from migen.fhdl.std import *
from migen.bus import dfi, lasmibus

from milkymist.lasmicon.refresher import *
from milkymist.lasmicon.bankmachine import *
from milkymist.lasmicon.multiplexer import *

class PhySettings:
	def __init__(self, dfi_d, nphases, rdphase, wrphase):
		self.dfi_d = dfi_d
		self.nphases = nphases
		self.rdphase = rdphase
		self.wrphase = wrphase

class GeomSettings:
	def __init__(self, bank_a, row_a, col_a):
		self.bank_a = bank_a
		self.row_a = row_a
		self.col_a = col_a
		self.mux_a = max(row_a, col_a)

class TimingSettings:
	def __init__(self, tRP, tRCD, tWR, tWTR, tREFI, tRFC, CL, read_latency, write_latency, read_time, write_time):
		self.tRP = tRP
		self.tRCD = tRCD
		self.tWR = tWR
		self.tWTR = tWTR
		self.tREFI = tREFI
		self.tRFC = tRFC
		
		self.CL = CL
		self.read_latency = read_latency
		self.write_latency = write_latency
		
		self.read_time = read_time
		self.write_time = write_time

class LASMIcon(Module):
	def __init__(self, phy_settings, geom_settings, timing_settings):
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
			read_latency=timing_settings.read_latency,
			write_latency=timing_settings.write_latency)
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
