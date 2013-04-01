from migen.fhdl.structure import *
from migen.fhdl.specials import Memory
from migen.fhdl.module import Module
from migen.genlib import roundrobin
from migen.genlib.record import *
from migen.genlib.misc import optree
from migen.bus.transactions import *
from migen.sim.generic import Proxy

_layout = [
	("adr",		30,		DIR_M_TO_S),
	("dat_w",	32, 	DIR_M_TO_S),
	("dat_r",	32, 	DIR_S_TO_M),
	("sel",		4,		DIR_M_TO_S),
	("cyc",		1,		DIR_M_TO_S),
	("stb",		1,		DIR_M_TO_S),
	("ack",		1,		DIR_S_TO_M),
	("we",		1,		DIR_M_TO_S),
	("cti",		3,		DIR_M_TO_S),
	("bte",		2,		DIR_M_TO_S),
	("err",		1,		DIR_S_TO_M)
]

class Interface(Record):
	def __init__(self):
		Record.__init__(self, _layout)

class InterconnectPointToPoint(Module):
	def __init__(self, master, slave):
		self.comb += master.connect(slave)

class Arbiter(Module):
	def __init__(self, masters, target):
		self.submodules.rr = roundrobin.RoundRobin(len(masters))
		
		# mux master->slave signals
		for name, size, direction in _layout:
			if direction == DIR_M_TO_S:
				choices = Array(getattr(m, name) for m in masters)
				self.comb += getattr(target, name).eq(choices[self.rr.grant])
		
		# connect slave->master signals
		for name, size, direction in _layout:
			if direction == DIR_S_TO_M:
				source = getattr(target, name)
				for i, m in enumerate(masters):
					dest = getattr(m, name)
					if name == "ack" or name == "err":
						self.comb += dest.eq(source & (self.rr.grant == i))
					else:
						self.comb += dest.eq(source)
		
		# connect bus requests to round-robin selector
		reqs = [m.cyc for m in masters]
		self.comb += self.rr.request.eq(Cat(*reqs))

class Decoder(Module):
	# slaves is a list of pairs:
	# 0) function that takes the address signal and returns a FHDL expression
	#    that evaluates to 1 when the slave is selected and 0 otherwise.
	# 1) wishbone.Slave reference.
	# register adds flip-flops after the address comparators. Improves timing,
	# but breaks Wishbone combinatorial feedback.
	def __init__(self, master, slaves, register=False):
		ns = len(slaves)
		slave_sel = Signal(ns)
		slave_sel_r = Signal(ns)
		
		# decode slave addresses
		self.comb += [slave_sel[i].eq(fun(master.adr))
			for i, (fun, bus) in enumerate(slaves)]
		if register:
			self.sync += slave_sel_r.eq(slave_sel)
		else:
			self.comb += slave_sel_r.eq(slave_sel)
		
		# connect master->slaves signals except cyc
		for slave in slaves:
			for name, size, direction in _layout:
				if direction == DIR_M_TO_S and name != "cyc":
					self.comb += getattr(slave[1], name).eq(getattr(master, name))
		
		# combine cyc with slave selection signals
		self.comb += [slave[1].cyc.eq(master.cyc & slave_sel[i])
			for i, slave in enumerate(slaves)]
		
		# generate master ack (resp. err) by ORing all slave acks (resp. errs)
		self.comb += [
			master.ack.eq(optree("|", [slave[1].ack for slave in slaves])),
			master.err.eq(optree("|", [slave[1].err for slave in slaves]))
		]
		
		# mux (1-hot) slave data return
		masked = [Replicate(slave_sel_r[i], len(master.dat_r)) & slaves[i][1].dat_r for i in range(ns)]
		self.comb += master.dat_r.eq(optree("|", masked))

class InterconnectShared(Module):
	def __init__(self, masters, slaves, register=False):
		shared = Interface()
		self.submodules += Arbiter(masters, shared)
		self.submodules += Decoder(shared, slaves, register)

class Tap(Module):
	def __init__(self, bus, handler=print):
		self.bus = bus
		self.handler = handler
	
	def do_simulation(self, s):
		if s.rd(self.bus.ack):
			assert(s.rd(self.bus.cyc) and s.rd(self.bus.stb))
			if s.rd(self.bus.we):
				transaction = TWrite(s.rd(self.bus.adr),
					s.rd(self.bus.dat_w),
					s.rd(self.bus.sel))
			else:
				transaction = TRead(s.rd(self.bus.adr),
					s.rd(self.bus.dat_r))
			self.handler(transaction)

class Initiator(Module):
	def __init__(self, generator, bus=None):
		self.generator = generator
		if bus is None:
			bus = Interface()
		self.bus = bus
		self.transaction_start = 0
		self.transaction = None
		self.done = False
	
	def do_simulation(self, s):
		if not self.done:
			if self.transaction is None or s.rd(self.bus.ack):
				if self.transaction is not None:
					self.transaction.latency = s.cycle_counter - self.transaction_start - 1
					if isinstance(self.transaction, TRead):
						self.transaction.data = s.rd(self.bus.dat_r)
				try:
					self.transaction = next(self.generator)
				except StopIteration:
					self.done = True
					self.transaction = None
				if self.transaction is not None:
					self.transaction_start = s.cycle_counter
					s.wr(self.bus.cyc, 1)
					s.wr(self.bus.stb, 1)
					s.wr(self.bus.adr, self.transaction.address)
					if isinstance(self.transaction, TWrite):
						s.wr(self.bus.we, 1)
						s.wr(self.bus.sel, self.transaction.sel)
						s.wr(self.bus.dat_w, self.transaction.data)
					else:
						s.wr(self.bus.we, 0)
				else:
					s.wr(self.bus.cyc, 0)
					s.wr(self.bus.stb, 0)

class TargetModel:
	def read(self, address):
		return 0
	
	def write(self, address, data, sel):
		pass
	
	def can_ack(self, bus):
		return True

class Target(Module):
	def __init__(self, model, bus=None):
		if bus is None:
			bus = Interface()
		self.bus = bus
		self.model = model
	
	def do_simulation(self, s):
		bus = Proxy(s, self.bus)
		if not bus.ack:
			if self.model.can_ack(bus) and bus.cyc and bus.stb:
				if bus.we:
					self.model.write(bus.adr, bus.dat_w, bus.sel)
				else:
					bus.dat_r = self.model.read(bus.adr)
				bus.ack = 1
		else:
			bus.ack = 0

class SRAM(Module):
	def __init__(self, mem_or_size, bus=None):
		if isinstance(mem_or_size, Memory):
			assert(mem_or_size.width <= 32)
			mem = mem_or_size
		else:
			mem = Memory(32, mem_or_size//4)
		if bus is None:
			bus = Interface()
		self.bus = bus
	
		###
	
		# memory
		self.specials += mem
		port = mem.get_port(write_capable=True, we_granularity=8)
		# generate write enable signal
		self.comb += [port.we[i].eq(self.bus.cyc & self.bus.stb & self.bus.we & self.bus.sel[i])
			for i in range(4)]
		# address and data
		self.comb += [
			port.adr.eq(self.bus.adr[:len(port.adr)]),
			port.dat_w.eq(self.bus.dat_w),
			self.bus.dat_r.eq(port.dat_r)
		]
		# generate ack
		self.sync += [
			self.bus.ack.eq(0),
			If(self.bus.cyc & self.bus.stb & ~self.bus.ack,	self.bus.ack.eq(1))
		]
