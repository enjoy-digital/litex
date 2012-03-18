from migen.fhdl.structure import *
from migen.bus import dfi, asmibus

from milkymist.asmicon.refresher import *
from milkymist.asmicon.bankmachine import *
from milkymist.asmicon.multiplexer import *

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
	def __init__(self, tRP, tRCD, tREFI, tRFC, slot_time):
		self.tRP = tRP
		self.tRCD = tRCD
		self.tREFI = tREFI
		self.tRFC = tRFC
		self.slot_time = slot_time

class ASMIcon:
	def __init__(self, phy_settings, geom_settings, timing_settings):
		self.phy_settings = phy_settings
		self.geom_settings = geom_settings
		self.timing_settings = timing_settings
		self.finalized = False
		
		self.dfi = dfi.Interface(self.geom_settings.mux_a,
			self.geom_settings.bank_a,
			self.phy_settings.dfi_d,
			self.phy_settings.nphases)
		burst_length = self.phy_settings.nphases*2
		self.address_align = log2_int(burst_length)
		aw = self.geom_settings.bank_a + self.geom_settings.row_a + self.geom_settings.col_a - self.address_align
		dw = self.phy_settings.dfi_d*self.phy_settings.nphases
		self.hub = asmibus.Hub(aw, dw, self.timing_settings.slot_time)
	
	def finalize(self):
		if self.finalized:
			raise FinalizeError
		self.finalized = True
		self.hub.finalize()
		slots = self.hub.get_slots()
		self.refresher = Refresher(self.geom_settings.mux_a, self.geom_settings.bank_a,
			self.timing_settings.tRP, self.timing_settings.tREFI, self.timing_settings.tRFC)
		self.bank_machines = [BankMachine(self.geom_settings, self.timing_settings, self.address_align, i, slots) for i in range(2**self.geom_settings.bank_a)]
		self.multiplexer = Multiplexer(self.phy_settings, self.geom_settings, self.timing_settings,
			self.bank_machines, self.refresher,
			self.dfi, self.hub)
	
	def get_fragment(self):
		if not self.finalized:
			raise FinalizeError
		return self.hub.get_fragment() + \
			self.refresher.get_fragment() + \
			sum([bm.get_fragment() for bm in self.bank_machines], Fragment()) + \
			self.multiplexer.get_fragment()
