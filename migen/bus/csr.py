from migen.fhdl.structure import *
from migen.fhdl.specials import Memory
from migen.fhdl.module import Module
from migen.bus.transactions import *
from migen.bank.description import CSRStorage
from migen.genlib.record import *
from migen.genlib.misc import chooser

data_width = 8

class Interface(Record):
	def __init__(self):
		Record.__init__(self, [
			("adr",		14,			DIR_M_TO_S),
			("we",		1,			DIR_M_TO_S),
			("dat_w",	data_width,	DIR_M_TO_S),
			("dat_r",	data_width,	DIR_S_TO_M)])

class Interconnect(Module):
	def __init__(self, master, slaves):
		self.comb += master.connect(*slaves)

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

class SRAM(Module):
	def __init__(self, mem_or_size, address, read_only=None, bus=None):
		if isinstance(mem_or_size, Memory):
			mem = mem_or_size
		else:
			mem = Memory(data_width, mem_or_size//(data_width//8))
		if mem.width > data_width:
			csrw_per_memw = (self.mem.width + data_width - 1)//data_width
			word_bits = bits_for(csrw_per_memw-1)
		else:
			csrw_per_memw = 1
			word_bits = 0
		page_bits = _compute_page_bits(mem.depth + word_bits)
		if page_bits:
			self._page = CSRStorage(page_bits, name=self.mem.name_override + "_page")
		else:
			self._page = None
		if read_only is None:
			if hasattr(mem, "bus_read_only"):
				read_only = mem.bus_read_only
			else:
				read_only = False
		if bus is None:
			bus = Interface()
		self.bus = bus
	
		###

		self.specials += mem
		port = mem.get_port(write_capable=not read_only,
			we_granularity=data_width if not read_only and word_bits else 0)
		
		sel = Signal()
		sel_r = Signal()
		self.sync += sel_r.eq(sel)
		self.comb += sel.eq(self.bus.adr[9:] == address)

		if word_bits:
			word_index = Signal(word_bits)
			word_expanded = Signal(csrw_per_memw*data_width)
			sync.append(word_index.eq(self.bus.adr[:word_bits]))
			self.comb += [
				word_expanded.eq(port.dat_r),
				If(sel_r,
					chooser(word_expanded, word_index, self.bus.dat_r, n=csrw_per_memw, reverse=True)
				)
			]
			if not read_only:
				self.comb += [
					If(sel & self.bus.we, port.we.eq((1 << word_bits) >> self.bus.adr[:self.word_bits])),
					port.dat_w.eq(Replicate(self.bus.dat_w, csrw_per_memw))
				]
		else:
			self.comb += If(sel_r, self.bus.dat_r.eq(port.dat_r))
			if not read_only:
				self.comb += [
					port.we.eq(sel & self.bus.we),
					port.dat_w.eq(self.bus.dat_w)
				]
		
		if self._page is None:
			self.comb += port.adr.eq(self.bus.adr[word_bits:len(port.adr)])
		else:
			pv = self._page.storage
			self.comb += port.adr.eq(Cat(self.bus.adr[word_bits:len(port.adr)-len(pv)], pv))

	def get_csrs(self):
		if self._page is None:
			return []
		else:
			return [self._page]
