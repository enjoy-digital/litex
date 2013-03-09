from migen.fhdl.structure import *
from migen.genlib.misc import optree
from migen.bus.transactions import *
from migen.sim.generic import Proxy, PureSimulable

(SLOT_EMPTY, SLOT_PENDING, SLOT_PROCESSING) = range(3)

class Slot:
	def __init__(self, aw, time):
		self.state = Signal(2)
		self.we = Signal()
		self.adr = Signal(aw)
		self.time = time
		if self.time:
			self._counter = Signal(max=time+1)
			self.mature = Signal()
		
		self.allocate = Signal()
		self.allocate_we = Signal()
		self.allocate_adr = Signal(aw)
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
		self.adr = Signal(self.hub.aw)
		self.we = Signal()
		self.stb = Signal()
		# tag_issue is created by finalize()
		self.ack = Signal()
		
		# request completion
		self.call = Signal()
		# tag_call is created by finalize()
		self.dat_r = Signal(self.hub.dw)
		self.dat_w = Signal(self.hub.dw)
		self.dat_wm = Signal(self.hub.dw//8)
	
	def finalize(self, tagbits, base):
		if self.finalized:
			raise FinalizeError
		self.finalized = True
		self.tagbits = tagbits
		self.base = base
		nslots = len(self.slots)
		if nslots > 1:
			self.tag_issue = Signal(max=nslots)
		self.tag_call = Signal(tagbits)
	
	def get_call_expression(self, slotn=0):
		if not self.finalized:
			raise FinalizeError
		return self.call \
			& (self.tag_call == (self.base + slotn))
		
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
		needs_tags = len(self.slots) > 1
		for n, s in reversed(list(enumerate(self.slots))):
			choose_slot = If(s.state == SLOT_EMPTY,
				s.allocate.eq(self.stb),
				self.tag_issue.eq(n) if needs_tags else None
			).Else(choose_slot)
		comb.append(choose_slot)
		comb.append(self.ack.eq(optree("|", 
			[s.state == SLOT_EMPTY for s in self.slots])))
		
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
		self.dat_r = Signal(self.dw)
		self.dat_w = Signal(self.dw)
		self.dat_wm = Signal(self.dw//8)
	
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
		self.tag_call = Signal(tagbits)
	
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

class Tap(PureSimulable):
	def __init__(self, hub, handler=print):
		self.hub = hub
		self.handler = handler
		self.tag_to_transaction = dict()
		self.transaction = None
	
	def do_simulation(self, s):
		hub = Proxy(s, self.hub)
		
		# Pull any data announced in the previous cycle.
		if isinstance(self.transaction, TWrite):
			self.transaction.data = hub.dat_w
			self.transaction.sel = ~hub.dat_wm
			self.handler(self.transaction)
			self.transaction = None
		if isinstance(self.transaction, TRead):
			self.transaction.data = hub.dat_r
			self.handler(self.transaction)
			self.transaction = None
		
		# Tag issue. Transaction objects are created here
		# and placed into the tag_to_transaction dictionary.
		for tag, slot in enumerate(self.hub.get_slots()):
			if s.rd(slot.allocate):
				adr = s.rd(slot.allocate_adr)
				we = s.rd(slot.allocate_we)
				if we:
					transaction = TWrite(adr)
				else:
					transaction = TRead(adr)
				transaction.latency = s.cycle_counter
				self.tag_to_transaction[tag] = transaction
		
		# Tag call.
		if hub.call:
			transaction = self.tag_to_transaction[hub.tag_call]
			transaction.latency = s.cycle_counter - transaction.latency + 1
			self.transaction = transaction

class Initiator(PureSimulable):
	def __init__(self, generator, port):
		self.generator = generator
		self.port = port
		self.done = False
		self._exe = None
	
	def _execute(self, s, generator, port):
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
					s.wr(port.dat_wm, ~transaction.sel)
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
				self._exe = self._execute(s, self.generator, self.port)
			try:
				next(self._exe)
			except StopIteration:
				self.done = True

class TargetModel:
	def __init__(self):
		self.last_slot = 0
	
	def read(self, address):
		return 0
	
	def write(self, address, data, mask):
		pass
	
	# Round-robin scheduling.
	def select_slot(self, pending_slots):
		if not pending_slots:
			return -1
		self.last_slot += 1
		if self.last_slot > max(pending_slots):
			self.last_slot = 0
		while self.last_slot not in pending_slots:
			self.last_slot += 1
		return self.last_slot

class Target(PureSimulable):
	def __init__(self, model, hub):
		self.model = model
		self.hub = hub
		self._calling_tag = -1
		self._write_request_d = -1
		self._write_request = -1
		self._read_request = -1
	
	def do_simulation(self, s):
		slots = self.hub.get_slots()
		
		# Data I/O
		if self._write_request >= 0:
			self.model.write(self._write_request,
				s.rd(self.hub.dat_w), s.rd(self.hub.dat_wm))
		if self._read_request >= 0:
			s.wr(self.hub.dat_r, self.model.read(self._read_request))
			
		# Request pipeline
		self._read_request = -1
		self._write_request = self._write_request_d
		self._write_request_d = -1
		
		# Examine pending slots and possibly choose one.
		# Note that we do not use the SLOT_PROCESSING state here.
		# Selected slots are immediately called.
		pending_slots = set()
		for tag, slot in enumerate(slots):
			if tag != self._calling_tag and s.rd(slot.state) == SLOT_PENDING:
				pending_slots.add(tag)
		slot_to_call = self.model.select_slot(pending_slots)
		
		# Call slot.
		if slot_to_call >= 0:
			slot = slots[slot_to_call]
			s.wr(self.hub.call, 1)
			s.wr(self.hub.tag_call, slot_to_call)
			self._calling_tag = slot_to_call
			if s.rd(slot.we):
				self._write_request_d = s.rd(slot.adr)
			else:
				self._read_request = s.rd(slot.adr)
		else:
			s.wr(self.hub.call, 0)
			self._calling_tag = -1
