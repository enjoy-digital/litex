from migen.fhdl.structure import *
from migen.fhdl.specials import Memory
from migen.genlib import roundrobin
from migen.genlib.misc import optree
from migen.bus.simple import *
from migen.bus.transactions import *
from migen.sim.generic import Proxy, PureSimulable

_desc = Description(
	(M_TO_S,	"adr",		30),
	(M_TO_S,	"dat_w",	32),
	(S_TO_M,	"dat_r",	32),
	(M_TO_S,	"sel",		4),
	(M_TO_S,	"cyc",		1),
	(M_TO_S,	"stb",		1),
	(S_TO_M,	"ack",		1),
	(M_TO_S,	"we",		1),
	(M_TO_S,	"cti",		3),
	(M_TO_S,	"bte",		2),
	(S_TO_M,	"err",		1)
)

class Interface(SimpleInterface):
	def __init__(self):
		SimpleInterface.__init__(self, _desc)

class InterconnectPointToPoint(SimpleInterconnect):
	def __init__(self, master, slave):
		SimpleInterconnect.__init__(self, master, [slave])

class Arbiter:
	def __init__(self, masters, target):
		self.masters = masters
		self.target = target
		self.rr = roundrobin.RoundRobin(len(self.masters))

	def get_fragment(self):
		comb = []
		
		# mux master->slave signals
		for name in _desc.get_names(M_TO_S):
			choices = Array(getattr(m, name) for m in self.masters)
			comb.append(getattr(self.target, name).eq(choices[self.rr.grant]))
		
		# connect slave->master signals
		for name in _desc.get_names(S_TO_M):
			source = getattr(self.target, name)
			for i, m in enumerate(self.masters):
				dest = getattr(m, name)
				if name == "ack" or name == "err":
					comb.append(dest.eq(source & (self.rr.grant == i)))
				else:
					comb.append(dest.eq(source))
		
		# connect bus requests to round-robin selector
		reqs = [m.cyc for m in self.masters]
		comb.append(self.rr.request.eq(Cat(*reqs)))
		
		return Fragment(comb) + self.rr.get_fragment()

class Decoder:
	# slaves is a list of pairs:
	# 0) function that takes the address signal and returns a FHDL expression
	#    that evaluates to 1 when the slave is selected and 0 otherwise.
	# 1) wishbone.Slave reference.
	# register adds flip-flops after the address comparators. Improves timing,
	# but breaks Wishbone combinatorial feedback.
	def __init__(self, master, slaves, register=False):
		self.master = master
		self.slaves = slaves
		self.register = register

	def get_fragment(self):
		comb = []
		sync = []
		
		ns = len(self.slaves)
		slave_sel = Signal(ns)
		slave_sel_r = Signal(ns)
		
		# decode slave addresses
		comb += [slave_sel[i].eq(fun(self.master.adr))
			for i, (fun, bus) in enumerate(self.slaves)]
		if self.register:
			sync.append(slave_sel_r.eq(slave_sel))
		else:
			comb.append(slave_sel_r.eq(slave_sel))
		
		# connect master->slaves signals except cyc
		m2s_names = _desc.get_names(M_TO_S, "cyc")
		comb += [getattr(slave[1], name).eq(getattr(self.master, name))
			for name in m2s_names for slave in self.slaves]
		
		# combine cyc with slave selection signals
		comb += [slave[1].cyc.eq(self.master.cyc & slave_sel[i])
			for i, slave in enumerate(self.slaves)]
		
		# generate master ack (resp. err) by ORing all slave acks (resp. errs)
		comb += [
			self.master.ack.eq(optree("|", [slave[1].ack for slave in self.slaves])),
			self.master.err.eq(optree("|", [slave[1].err for slave in self.slaves]))
		]
		
		# mux (1-hot) slave data return
		masked = [Replicate(slave_sel_r[i], len(self.master.dat_r)) & self.slaves[i][1].dat_r for i in range(len(self.slaves))]
		comb.append(self.master.dat_r.eq(optree("|", masked)))
		
		return Fragment(comb, sync)

class InterconnectShared:
	def __init__(self, masters, slaves, register=False):
		self._shared = Interface()
		self._arbiter = Arbiter(masters, self._shared)
		self._decoder = Decoder(self._shared, slaves, register)
	
	def get_fragment(self):
		return self._arbiter.get_fragment() + self._decoder.get_fragment()

class Tap(PureSimulable):
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

class Initiator(PureSimulable):
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

class Target(PureSimulable):
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

class SRAM:
	def __init__(self, mem_or_size, bus=None):
		if isinstance(mem_or_size, Memory):
			assert(mem_or_size.width <= 32)
			self.mem = mem_or_size
		else:
			self.mem = Memory(32, mem_or_size//4)
		if bus is None:
			bus = Interface()
		self.bus = bus
	
	def get_fragment(self):
		# memory
		port = self.mem.get_port(write_capable=True, we_granularity=8)
		# generate write enable signal
		comb = [port.we[i].eq(self.bus.cyc & self.bus.stb & self.bus.we & self.bus.sel[i])
			for i in range(4)]
		# address and data
		comb += [
			port.adr.eq(self.bus.adr[:len(port.adr)]),
			port.dat_w.eq(self.bus.dat_w),
			self.bus.dat_r.eq(port.dat_r)
		]
		# generate ack
		sync = [
			self.bus.ack.eq(0),
			If(self.bus.cyc & self.bus.stb & ~self.bus.ack,
				self.bus.ack.eq(1)
			)
		]
		return Fragment(comb, sync, specials={self.mem})
