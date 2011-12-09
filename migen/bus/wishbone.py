from migen.fhdl import structure as f
from migen.corelogic import roundrobin, multimux
from .simple import Simple, GetSigName
from functools import partial

_desc = [
	(True,	"adr",	32),
	(True,	"dat",	32),
	(False,	"dat",	32),
	(True,	"sel",	4),
	(True,	"cyc",	1),
	(True,	"stb",	1),
	(False,	"ack",	1),
	(True,	"we",	1),
	(True,	"cti",	3),
	(True,	"bte",	2),
	(False,	"err",	1)
]

class Master(Simple):
	def __init__(self, name=""):
		Simple.__init__(self, _desc, False, name)

class Slave(Simple):
	def __init__(self, name=""):
		Simple.__init__(self, _desc, True, name)

class Arbiter:
	def __init__(self, masters, target):
		self.masters = masters
		self.target = target
		self.rr = roundrobin.Inst(len(self.masters))

	def GetFragment(self):
		comb = []
		
		# mux master->slave signals
		m2s_names = [GetSigName(x, False) for x in _desc if x[0]]
		m2s_masters = [[getattr(m, name) for name in m2s_names] for m in self.masters]
		m2s_target = [getattr(self.target, name) for name in m2s_names]
		comb += multimux.MultiMux(self.rr.grant, m2s_masters, m2s_target)
		
		# connect slave->master signals
		s2m_names = [GetSigName(x, False) for x in _desc if not x[0]]
		for name in s2m_names:
			source = getattr(self.target, name)
			for m in self.masters:
				dest = getattr(m, name)
				comb.append(f.Assign(dest, source))
		
		# connect bus requests to round-robin selector
		reqs = [m.cyc_o for m in self.masters]
		comb.append(f.Assign(self.rr.request, f.Cat(*reqs)))
		
		return f.Fragment(comb) + self.rr.GetFragment()


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
		maxbits = max([f.BitsFor(addr) for addr in addresses])
		def mkconst(x):
			if isinstance(x, int):
				return f.Constant(x, f.BV(maxbits))
			else:
				return x
		self.addresses = list(map(mkconst, addresses))
		
		ns = len(self.slaves)
		d = partial(f.Declare, self)
		d("_slave_sel", f.BV(ns))
		d("_slave_sel_r", f.BV(ns))

	def GetFragment(self):
		comb = []
		sync = []
		
		# decode slave addresses
		i = 0
		hi = self.master.adr_o.bv.width - self.offset
		for addr in self.addresses:
			comb.append(f.Assign(self._slave_sel[i],
				self.master.adr_o[hi-addr.bv.width:hi] == addr))
			i += 1
		if self.register:
			sync.append(f.Assign(self._slave_sel_r, self._slave_sel))
		else:
			comb.append(f.Assign(self._slave_sel_r, self._slave_sel))
		
		# connect master->slaves signals except cyc
		m2s_names = [(GetSigName(x, False), GetSigName(x, True))
			for x in _desc if x[0] and x[1] != "cyc"]
		comb += [f.Assign(getattr(slave[1], name[1]), getattr(self.master, name[0]))
			for name in m2s_names for slave in self.slaves]
		
		# combine cyc with slave selection signals
		i = 0
		for slave in self.slaves:
			comb.append(f.Assign(slave[1].cyc_i, self.master.cyc_o & self._slave_sel_r[i]))
			i += 1
		
		# generate master ack (resp. err) by ORing all slave acks (resp. errs)
		ackv = f.Constant(0)
		errv = f.Constant(0)
		for slave in self.slaves:
			ackv = ackv | slave[1].ack_o
			errv = errv | slave[1].err_o
		comb.append(f.Assign(self.master.ack_i, ackv))
		comb.append(f.Assign(self.master.err_i, errv))
		
		# mux (1-hot) slave data return
		i = 0
		datav = f.Constant(0, self.master.dat_i.bv)
		for slave in self.slaves:
			datav = datav | (f.Replicate(self._slave_sel_r[i], self.master.dat_i.bv.width) & slave[1].dat_o)
			i += 1
		comb.append(f.Assign(self.master.dat_i, datav))
		
		return f.Fragment(comb, sync)

class InterconnectShared:
	def __init__(self, masters, slaves, offset=0, register=False):
		self._shared = Master("shr")
		self._arbiter = Arbiter(masters, self._shared)
		self._decoder = Decoder(self._shared, slaves, offset, register)
		self.addresses = self._decoder.addresses
	
	def GetFragment(self):
		return self._arbiter.GetFragment() + self._decoder.GetFragment()
