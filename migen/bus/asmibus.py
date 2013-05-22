from migen.fhdl.std import *
from migen.fhdl.module import FinalizeError
from migen.genlib.misc import optree
from migen.genlib import roundrobin
from migen.bus.transactions import *
from migen.sim.generic import Proxy

(SLOT_EMPTY, SLOT_PENDING, SLOT_PROCESSING) = range(3)

class Slot(Module):
	def __init__(self, aw, time):
		self.state = Signal(2)
		self.we = Signal()
		self.adr = Signal(aw)
		if time:
			self.mature = Signal()
		
		self.allocate = Signal()
		self.allocate_we = Signal()
		self.allocate_adr = Signal(aw)
		self.process = Signal()
		self.call = Signal()
	
		###

		self.sync += [
			If(self.allocate,
				self.state.eq(SLOT_PENDING),
				self.we.eq(self.allocate_we),
				self.adr.eq(self.allocate_adr)
			),
			If(self.process, self.state.eq(SLOT_PROCESSING)),
			If(self.call, self.state.eq(SLOT_EMPTY))
		]
		if time:
			_counter = Signal(max=time+1)
			self.comb += self.mature.eq(self._counter == 0)
			self.sync += [
				If(self.allocate,
					self._counter.eq(self.time)
				).Elif(self._counter != 0,
					self._counter.eq(self._counter - 1)
				)
			]

class Port(Module):
	def __init__(self, hub, base, nslots):
		self.hub = hub
		self.base = base
		self.submodules.slots = [Slot(self.hub.aw, self.hub.time) for i in range(nslots)]
		
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

	def do_finalize(self):
		nslots = len(self.slots)
		if nslots > 1:
			self.tag_issue = Signal(max=nslots)
		self.tag_call = Signal(self.hub.tagbits)

		# allocate
		for s in self.slots:
			self.comb += [
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
		self.comb += choose_slot
		self.comb += self.ack.eq(optree("|", 
			[s.state == SLOT_EMPTY for s in self.slots]))

		# call
		self.comb += [s.call.eq(self.get_call_expression(n))
			for n, s in enumerate(self.slots)]
	
	def get_call_expression(self, slotn=0):
		if not self.finalized:
			raise FinalizeError
		return self.call \
			& (self.tag_call == (self.base + slotn))

class Hub(Module):
	def __init__(self, aw, dw, time=0):
		self.aw = aw
		self.dw = dw
		self.time = time

		self.ports = []
		self._next_base = 0
		self.tagbits = 0
		
		self.call = Signal()
		# tag_call is created by do_finalize()
		self.dat_r = Signal(self.dw)
		self.dat_w = Signal(self.dw)
		self.dat_wm = Signal(self.dw//8)
	
	def get_port(self, nslots=1):
		if self.finalized:
			raise FinalizeError
		new_port = Port(self, self._next_base, nslots)
		self._next_base += nslots
		self.tagbits = bits_for(self._next_base-1)
		self.ports.append(new_port)
		self.submodules += new_port
		return new_port
	
	def do_finalize(self):
		self.tag_call = Signal(self.tagbits)
		for port in self.ports:
			self.comb += [
				port.call.eq(self.call),
				port.tag_call.eq(self.tag_call),
				port.dat_r.eq(self.dat_r)
			]
		self.comb += [
			self.dat_w.eq(optree("|", [port.dat_w for port in self.ports])),
			self.dat_wm.eq(optree("|", [port.dat_wm for port in self.ports]))
		]
	
	def get_slots(self):
		if not self.finalized:
			raise FinalizeError
		return sum([port.slots for port in self.ports], [])

class Tap(Module):
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

class Initiator(Module):
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

class Target(Module):
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

# Port sharing

class SharedPort:
	def __init__(self, base_port):
		if not base_port.finalized:
			raise FinalizeError
		self.finalized = True

		nslots = len(base_port.slots)

		self.hub = base_port.hub
		self.base = base_port.base
		# 1 if that slot is assigned to us
		self.slots = [Signal() for i in range(nslots)]
		
		# request issuance
		self.adr = Signal(self.hub.aw)
		self.we = Signal()
		self.stb = Signal()
		if nslots > 1:
			self.tag_issue = Signal(max=nslots)
		self.ack = Signal()
		
		# request completion
		self.call = Signal()
		self.tag_call = Signal(self.hub.tagbits)
		self.dat_r = Signal(self.hub.dw)
		self.dat_w = Signal(self.hub.dw)
		self.dat_wm = Signal(self.hub.dw//8)

	def get_call_expression(self, slotn=0):
		if not self.finalized:
			raise FinalizeError
		return self.call \
			& (self.tag_call == (self.base + slotn))

class PortSharer(Module):
	def __init__(self, base_port, nshares):
		self.shared_ports = [SharedPort(base_port) for i in range(nshares)]

		###

		# request issuance
		self.submodules.rr = roundrobin.RoundRobin(nshares, roundrobin.SP_CE)
		self.comb += [
			self.rr.request.eq(Cat(*[sp.stb for sp in self.shared_ports])),
			self.rr.ce.eq(base_port.ack)
		]
		self.comb += [
			base_port.adr.eq(Array(sp.adr for sp in self.shared_ports)[self.rr.grant]),
			base_port.we.eq(Array(sp.we for sp in self.shared_ports)[self.rr.grant]),
			base_port.stb.eq(Array(sp.stb for sp in self.shared_ports)[self.rr.grant]),
		]
		if hasattr(base_port, "tag_issue"):
			self.comb += [sp.tag_issue.eq(base_port.tag_issue) for sp in self.shared_ports]
		self.comb += [sp.ack.eq(base_port.ack & (self.rr.grant == n)) for n, sp in enumerate(self.shared_ports)]

		# request completion
		self.comb += [sp.call.eq(base_port.call & Array(sp.slots)[base_port.tag_call-base_port.base])
			for sp in self.shared_ports]
		self.comb += [sp.tag_call.eq(base_port.tag_call) for sp in self.shared_ports]
		self.comb += [sp.dat_r.eq(base_port.dat_r) for sp in self.shared_ports]
		self.comb += [
			base_port.dat_w.eq(optree("|", [sp.dat_w for sp in self.shared_ports])),
			base_port.dat_wm.eq(optree("|", [sp.dat_wm for sp in self.shared_ports])),
		]
		
		# request ownership tracking
		if hasattr(base_port, "tag_issue"):
			for sp in self.shared_ports:
				self.sync += If(sp.stb & sp.ack, Array(sp.slots)[sp.tag_issue].eq(1))
				for n, slot in enumerate(sp.slots):
					self.sync += If(base_port.call & (base_port.tag_call == (base_port.base + n)), slot.eq(0))
		else:
			for sp in self.shared_ports:
				self.sync += [
					If(sp.stb & sp.ack, sp.slots[0].eq(1)),
					If(base_port.call & (base_port.tag_call == base_port.base), sp.slots[0].eq(0))
				]
