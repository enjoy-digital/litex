from migen.fhdl.structure import *
from migen.corelogic import roundrobin
from migen.corelogic.misc import optree
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
		super().__init__(_desc)

class InterconnectPointToPoint(SimpleInterconnect):
	def __init__(self, master, slave):
		super().__init__(master, [slave])

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
					comb.append(dest.eq(source & (self.rr.grant == Constant(i, self.rr.grant.bv))))
				else:
					comb.append(dest.eq(source))
		
		# connect bus requests to round-robin selector
		reqs = [m.cyc for m in self.masters]
		comb.append(self.rr.request.eq(Cat(*reqs)))
		
		return Fragment(comb) + self.rr.get_fragment()

class Decoder:
	# slaves is a list of pairs:
	# 0) structure.Constant defining address (always decoded on the upper bits)
	#    Slaves can have differing numbers of address bits, but addresses 
	#    must not conflict.
	# 1) wishbone.Slave reference
	# Addresses are decoded from bit 31-offset and downwards.
	# register adds flip-flops after the address comparators. Improves timing,
	# but breaks Wishbone combinatorial feedback.
	def __init__(self, master, slaves, offset=0, register=False):
		self.master = master
		self.slaves = slaves
		self.offset = offset
		self.register = register
		
		addresses = [slave[0] for slave in self.slaves]
		maxbits = max([bits_for(addr) for addr in addresses])
		def mkconst(x):
			if isinstance(x, int):
				return Constant(x, BV(maxbits))
			else:
				return x
		self.addresses = list(map(mkconst, addresses))

	def get_fragment(self):
		comb = []
		sync = []
		
		ns = len(self.slaves)
		slave_sel = Signal(BV(ns))
		slave_sel_r = Signal(BV(ns))
		
		# decode slave addresses
		hi = len(self.master.adr) - self.offset
		comb += [slave_sel[i].eq(self.master.adr[hi-len(addr):hi] == addr)
			for i, addr in enumerate(self.addresses)]
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
	def __init__(self, masters, slaves, offset=0, register=False):
		self._shared = Interface()
		self._arbiter = Arbiter(masters, self._shared)
		self._decoder = Decoder(self._shared, slaves, offset, register)
		self.addresses = self._decoder.addresses
	
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
	def __init__(self, generator, bus=Interface()):
		self.generator = generator
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
	def __init__(self, model, bus=Interface()):
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
