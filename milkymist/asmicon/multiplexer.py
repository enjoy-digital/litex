from migen.fhdl.structure import *

class CommandRequest:
	def __init__(self, dfi_a, dfi_ba):
		self.a = Signal(BV(dfi_a))
		self.ba = Signal(BV(dfi_ba))
		self.cas_n = Signal(reset=1)
		self.ras_n = Signal(reset=1)
		self.we_n = Signal(reset=1)

class CommandRequestRW(CommandRequest):
	def __init__(self, dfi_a, dfi_ba, tagbits):
		CommandRequest.__init__(self, dfi_a, dfi_ba)
		self.stb = Signal()
		self.ack = Signal()
		self.is_read = Signal()
		self.is_write = Signal()
		self.tag = Signal(BV(tagbits))

class Multiplexer:
	def __init__(self, phy_settings, geom_settings, timing_settings, bank_machines, refresher, dfi, hub):
		pass
	
	def get_fragment(self):
		return Fragment()
