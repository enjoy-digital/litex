from migen.fhdl.structure import *
from migen.corelogic.misc import optree
from migen.bus.transactions import *

class FinalizeError(Exception):
	pass

(SLOT_EMPTY, SLOT_PENDING, SLOT_PROCESSING) = range(3)

class Slot:
	def __init__(self, aw, time):
		self.state = Signal(BV(2))
		self.we = Signal()
		self.adr = Signal(BV(aw))
		self.time = time
		if self.time:
			self._counter = Signal(BV(bits_for(time)))
			self.mature = Signal()
		
		self.allocate = Signal()
		self.allocate_we = Signal()
		self.allocate_adr = Signal(BV(aw))
		self.process = Signal()
		self.call = Signal()
	
	def get_fragment(self):
		comb = []
		sync = [
			If(self.allocate,
				self.state.eq(SLOT_PENDING),
				self.we.eq(self.allocate_we),
				self.adr.eq(self.allocate_adr)
			),
			If(self.process, self.state.eq(SLOT_PROCESSING)),
			If(self.call, self.state.eq(SLOT_EMPTY))
		]
		if self.time:
			comb += [
				self.mature.eq(self._counter == 0)
			]
			sync += [
				If(self.allocate,
					self._counter.eq(self.time)
				).Elif(self._counter != 0,
					self._counter.eq(self._counter - 1)
				)
			]
		return Fragment(comb, sync)

class Port:
	def __init__(self, hub, nslots):
		self.hub = hub
		self.slots = [Slot(self.hub.aw, self.hub.time) for i in range(nslots)]
		self.finalized = False
		
		# request issuance
		self.adr = Signal(BV(self.hub.aw))
		self.we = Signal()
		self.stb = Signal()
		# tag_issue is created by finalize()
		self.ack = Signal()
		
		# request completion
		self.call = Signal()
		# tag_call is created by finalize()
		self.dat_r = Signal(BV(self.hub.dw))
		self.dat_w = Signal(BV(self.hub.dw))
		self.dat_wm = Signal(BV(self.hub.dw//8))
	
	def finalize(self, tagbits, base):
		if self.finalized:
			raise FinalizeError
		self.finalized = True
		self.tagbits = tagbits
		self.base = base
		nslots = len(self.slots)
		if nslots > 1:
			self.tag_issue = Signal(BV(bits_for(nslots-1)))
		self.tag_call = Signal(BV(tagbits))
	
	def get_call_expression(self, slotn=0):
		if not self.finalized:
			raise FinalizeError
		return self.call \
			& (self.tag_call == Constant(self.base + slotn, BV(self.tagbits)))
		
	def get_fragment(self):
		if not self.finalized:
			raise FinalizeError
		
		slots_fragment = sum([s.get_fragment() for s in self.slots], Fragment())
		
		comb = []
		sync = []
		
		# allocate
		for s in self.slots:
			comb += [
				s.allocate_we.eq(self.we),
				s.allocate_adr.eq(self.adr)
			]
		choose_slot = None
		for s in reversed(self.slots):
			choose_slot = If(s.state == SLOT_EMPTY,
				self.ack.eq(1),
				s.allocate.eq(self.stb)
			).Else(choose_slot)
		comb.append(choose_slot)
		
		# call
		comb += [s.call.eq(self.get_call_expression(n))
			for n, s in enumerate(self.slots)]
		
		return slots_fragment + Fragment(comb, sync)

class Hub:
	def __init__(self, aw, dw, time=0):
		self.aw = aw
		self.dw = dw
		self.time = time
		self.ports = []
		self.finalized = False
		
		self.call = Signal()
		# tag_call is created by finalize()
		self.dat_r = Signal(BV(self.dw))
		self.dat_w = Signal(BV(self.dw))
		self.dat_wm = Signal(BV(self.dw//8))
	
	def get_port(self, nslots=1):
		if self.finalized:
			raise FinalizeError
		new_port = Port(self, nslots)
		self.ports.append(new_port)
		return new_port
	
	def finalize(self):
		if self.finalized:
			raise FinalizeError
		self.finalized = True
		nslots = sum([len(port.slots) for port in self.ports])
		tagbits = bits_for(nslots-1)
		base = 0
		for port in self.ports:
			port.finalize(tagbits, base)
			base += len(port.slots)
		self.tag_call = Signal(BV(tagbits))
	
	def get_slots(self):
		if not self.finalized:
			raise FinalizeError
		return sum([port.slots for port in self.ports], [])
	
	def get_fragment(self):
		if not self.finalized:
			raise FinalizeError
		ports = sum([port.get_fragment() for port in self.ports], Fragment())
		comb = []
		for port in self.ports:
			comb += [
				port.call.eq(self.call),
				port.tag_call.eq(self.tag_call),
				port.dat_r.eq(self.dat_r)
			]
		comb += [
			self.dat_w.eq(optree("|", [port.dat_w for port in self.ports])),
			self.dat_wm.eq(optree("|", [port.dat_wm for port in self.ports]))
		]
		return ports + Fragment(comb)

class Initiator:
	def __init__(self, port, generator):
		self.port = port
		self.generator = generator
		self.done = False
		self._exe = None
	
	def _execute(self, s, port, generator):
		while True:
			transaction = next(generator)
			transaction_start = s.cycle_counter
			if transaction is None:
				yield
			else:
				# tag phase
				s.wr(port.adr, transaction.address)
				if isinstance(transaction, TWrite):
					s.wr(port.we, 1)
				else:
					s.wr(port.we, 0)
				s.wr(port.stb, 1)
				yield
				while not s.rd(port.ack):
					yield
				if hasattr(port, "tag_issue"):
					tag = s.rd(port.tag_issue)
				else:
					tag = 0
				tag += port.base
				s.wr(port.stb, 0)
				
				# data phase
				while not (s.rd(port.call) and (s.rd(port.tag_call) == tag)):
					yield
				if isinstance(transaction, TWrite):
					s.wr(port.dat_w, transaction.data)
					s.wr(port.dat_wm, transaction.sel)
					yield
					s.wr(port.dat_w, 0)
					s.wr(port.dat_wm, 0)
				else:
					yield
					transaction.data = s.rd(port.dat_r)
				transaction.latency = s.cycle_counter - transaction_start - 1
	
	def do_simulation(self, s):
		if not self.done:
			if self._exe is None:
				self._exe = self._execute(s, self.port, self.generator)
			try:
				next(self._exe)
			except StopIteration:
				self.done = True
	
	def get_fragment(self):
		return Fragment(sim=[self.do_simulation])
