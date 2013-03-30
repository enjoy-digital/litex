from migen.fhdl.structure import *
from migen.fhdl.specials import Memory
from migen.fhdl.module import Module
from migen.bus.simple import *
from migen.bus.transactions import *
from migen.bank.description import CSRStorage
from migen.genlib.misc import chooser

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

class Initiator(Module):
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
	def __init__(self, mem_or_size, address, read_only=None, bus=None):
		if isinstance(mem_or_size, Memory):
			self.mem = mem_or_size
		else:
			self.mem = Memory(data_width, mem_or_size//(data_width//8))
		self.address = address
		if self.mem.width > data_width:
			self.csrw_per_memw = (self.mem.width + data_width - 1)//data_width
			self.word_bits = bits_for(self.csrw_per_memw-1)
		else:
			self.csrw_per_memw = 1
			self.word_bits = 0
		page_bits = _compute_page_bits(self.mem.depth + self.word_bits)
		if page_bits:
			self._page = CSRStorage(page_bits, name=self.mem.name_override + "_page")
		else:
			self._page = None
		if read_only is None:
			if hasattr(self.mem, "bus_read_only"):
				read_only = self.mem.bus_read_only
			else:
				read_only = False
		self.read_only = read_only
		if bus is None:
			bus = Interface()
		self.bus = bus
	
	def get_csrs(self):
		if self._page is None:
			return []
		else:
			return [self._page]
	
	def get_fragment(self):
		port = self.mem.get_port(write_capable=not self.read_only,
			we_granularity=data_width if not self.read_only and self.word_bits else 0)
		
		sel = Signal()
		sel_r = Signal()
		sync = [sel_r.eq(sel)]
		comb = [sel.eq(self.bus.adr[9:] == self.address)]

		if self.word_bits:
			word_index = Signal(self.word_bits)
			word_expanded = Signal(self.csrw_per_memw*data_width)
			sync.append(word_index.eq(self.bus.adr[:self.word_bits]))
			comb += [
				word_expanded.eq(port.dat_r),
				If(sel_r,
					chooser(word_expanded, word_index, self.bus.dat_r, n=self.csrw_per_memw, reverse=True)
				)
			]
			if not self.read_only:
				comb += [
					If(sel & self.bus.we, port.we.eq((1 << self.word_bits) >> self.bus.adr[:self.word_bits])),
					port.dat_w.eq(Replicate(self.bus.dat_w, self.csrw_per_memw))
				]
		else:
			comb += [
				If(sel_r,
					self.bus.dat_r.eq(port.dat_r)
				)
			]
			if not self.read_only:
				comb += [
					port.we.eq(sel & self.bus.we),
					port.dat_w.eq(self.bus.dat_w)
				]
		
		if self._page is None:
			comb.append(port.adr.eq(self.bus.adr[self.word_bits:len(port.adr)]))
		else:
			pv = self._page.storage
			comb.append(port.adr.eq(Cat(self.bus.adr[self.word_bits:len(port.adr)-len(pv)], pv)))
		
		return Fragment(comb, sync, specials={self.mem})
