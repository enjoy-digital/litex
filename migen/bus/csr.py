from migen.fhdl.structure import *
from migen.bus.simple import *
from migen.bus.transactions import *
from migen.sim.generic import PureSimulable
from migen.bank.description import RegisterField

data_width = 8

class Interface(SimpleInterface):
	def __init__(self):
		SimpleInterface.__init__(self, Description(
			(M_TO_S,	"adr",		14),
			(M_TO_S,	"we",		1),
			(M_TO_S,	"dat_w",	data_width),
			(S_TO_M,	"dat_r",	data_width)))

class Interconnect(SimpleInterconnect):
	pass

class Initiator(PureSimulable):
	def __init__(self, generator, bus=None):
		self.generator = generator
		if bus is None:
			bus = Interface()
		self.bus = bus
		self.transaction = None
		self.done = False
		
	def do_simulation(self, s):
		if not self.done:
			if self.transaction is not None:
				if isinstance(self.transaction, TRead):
					self.transaction.data = s.rd(self.bus.dat_r)
				else:
					s.wr(self.bus.we, 0)
			try:
				self.transaction = next(self.generator)
			except StopIteration:
				self.transaction = None
				self.done = True
			if self.transaction is not None:
				s.wr(self.bus.adr, self.transaction.address)
				if isinstance(self.transaction, TWrite):
					s.wr(self.bus.we, 1)
					s.wr(self.bus.dat_w, self.transaction.data)

def _compute_page_bits(nwords):
	npages = (nwords - 1)//512
	if npages > 0:
		return bits_for(npages-1)
	else:
		return 0

class SRAM:
	def __init__(self, mem_or_size, address, bus=None):
		if isinstance(mem_or_size, Memory):
			assert(mem_or_size.width <= data_width)
			self.mem = mem_or_size
		else:
			self.mem = Memory(data_width, mem_or_size//(data_width//8))
		self.address = address
		page_bits = _compute_page_bits(self.mem.depth)
		if page_bits:
			self._page = RegisterField("page", page_bits)
		else:
			self._page = None
		if bus is None:
			bus = Interface()
		self.bus = bus
	
	def get_registers(self):
		if self._page is None:
			return []
		else:
			return [self._page]
	
	def get_fragment(self):
		port = self.mem.get_port(write_capable=True)
		
		sel = Signal()
		sel_r = Signal()
		sync = [sel_r.eq(sel)]
		
		comb = [
			sel.eq(self.bus.adr[9:] == self.address),
			port.we.eq(sel & self.bus.we),
			
			port.dat_w.eq(self.bus.dat_w),
			If(sel_r,
				self.bus.dat_r.eq(port.dat_r)
			)
		]
		
		if self._page is None:
			comb.append(port.adr.eq(self.bus.adr[:len(port.adr)]))
		else:
			pv = self._page.field.r
			comb.append(port.adr.eq(Cat(self.bus.adr[:len(port.adr)-len(pv)], pv)))
		
		return Fragment(comb, sync, memories=[self.mem])
