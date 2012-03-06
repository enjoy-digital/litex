import math
import inspect
import re

from migen.fhdl import tracer

def bits_for(n):
	if isinstance(n, Constant):
		return n.bv.width
	else:
		if n == 0:
			return 1
		else:
			return int(math.ceil(math.log(n+1, 2)))

class BV:
	def __init__(self, width=1, signed=False):
		self.width = width
		self.signed = signed
	
	def __repr__(self):
		r = str(self.width) + "'"
		if self.signed:
			r += "s"
		r += "d"
		return r
	
	def __eq__(self, other):
		return self.width == other.width and self.signed == other.signed

class Value:
	def __invert__(self):
		return _Operator("~", [self])

	def __add__(self, other):
		return _Operator("+", [self, other])
	def __radd__(self, other):
		return _Operator("+", [other, self])
	def __sub__(self, other):
		return _Operator("-", [self, other])
	def __rsub__(self, other):
		return _Operator("-", [other, self])
	def __mul__(self, other):
		return _Operator("*", [self, other])
	def __rmul__(self, other):
		return _Operator("*", [other, self])
	def __lshift__(self, other):
		return _Operator("<<", [self, other])
	def __rlshift__(self, other):
		return _Operator("<<", [other, self])
	def __rshift__(self, other):
		return _Operator(">>", [self, other])
	def __rrshift__(self, other):
		return _Operator(">>", [other, self])
	def __and__(self, other):
		return _Operator("&", [self, other])
	def __rand__(self, other):
		return _Operator("&", [other, self])
	def __xor__(self, other):
		return _Operator("^", [self, other])
	def __rxor__(self, other):
		return _Operator("^", [other, self])
	def __or__(self, other):
		return _Operator("|", [self, other])
	def __ror__(self, other):
		return _Operator("|", [other, self])
	
	def __lt__(self, other):
		return _Operator("<", [self, other])
	def __le__(self, other):
		return _Operator("<=", [self, other])
	def __eq__(self, other):
		return _Operator("==", [self, other])
	def __ne__(self, other):
		return _Operator("!=", [self, other])
	def __gt__(self, other):
		return _Operator(">", [self, other])
	def __ge__(self, other):
		return _Operator(">=", [self, other])
	
	
	def __getitem__(self, key):
		if isinstance(key, int):
			return _Slice(self, key, key+1)
		elif isinstance(key, slice):
			start = key.start or 0
			stop = key.stop or self.bv.width
			if stop > self.bv.width:
				stop = self.bv.width
			if key.step != None:
				raise KeyError
			return _Slice(self, start, stop)
		else:
			raise KeyError
	
	def eq(self, r):
		return _Assign(self, r)

class _Operator(Value):
	def __init__(self, op, operands):
		self.op = op
		self.operands = list(map(_cst, operands))

class _Slice(Value):
	def __init__(self, value, start, stop):
		self.value = value
		self.start = start
		self.stop = stop

class Cat(Value):
	def __init__(self, *args):
		self.l = list(map(_cst, args))

class Replicate(Value):
	def __init__(self, v, n):
		self.v = _cst(v)
		self.n = n

class Constant(Value):
	def __init__(self, n, bv=None):
		self.bv = bv or BV(bits_for(n))
		self.n = n
	
	def __repr__(self):
		return str(self.bv) + str(self.n)
	
	def __eq__(self, other):
		return self.bv == other.bv and self.n == other.n

def binc(x, signed=False):
	return Constant(int(x, 2), BV(len(x), signed))

def _cst(x):
	if isinstance(x, int):
		return Constant(x)
	else:
		return x

class Signal(Value):
	def __init__(self, bv=BV(), name=None, variable=False, reset=0, name_override=None):
		assert(isinstance(bv, BV))
		self.bv = bv
		self.variable = variable
		self.reset = Constant(reset, bv)
		self.name_override = name_override
		self.backtrace = tracer.trace_back(name)

	def __hash__(self):
		return id(self)
	
	def __repr__(self):
		return "<Signal " + (self.backtrace[-1][1] or "anonymous") + ">"

# statements

class _Assign:
	def __init__(self, l, r):
		self.l = l
		self.r = _cst(r)

class _StatementList:
	def __init__(self, l=None):
		if l is None: l = []
		self.l = l

class If:
	def __init__(self, cond, *t):
		self.cond = cond
		self.t = _StatementList(t)
		self.f = _StatementList()
	
	def Else(self, *f):
		_insert_else(self, _StatementList(f))
		return self
	
	def Elif(self, cond, *t):
		_insert_else(self, _StatementList([If(cond, *t)]))
		return self

def _insert_else(obj, clause):
	o = obj
	while o.f.l:
		assert(len(o.f.l) == 1)
		assert(isinstance(o.f.l[0], If))
		o = o.f.l[0]
	o.f = clause

def _sl(x):
	if isinstance(x, list):
		return _StatementList(x)
	else:
		return x

class Default:
	pass

class Case:
	def __init__(self, test, *cases):
		self.test = test
		self.cases = [(c[0], _StatementList(c[1:])) for c in cases if not isinstance(c[0], Default)]
		self.default = None
		for c in cases:
			if isinstance(c[0], Default):
				if self.default is not None:
					raise ValueError
				self.default = _StatementList(c[1:])
		if self.default is None:
			self.default = _StatementList()

#

class Instance:
	def __init__(self, of, outs=[], ins=[], inouts=[], parameters=[], clkport="", rstport="", name=""):
		self.of = of
		if name:
			self.name_override = name
		else:
			self.name_override = of
		def process_io(x):
			if isinstance(x[1], Signal):
				return x # override
			elif isinstance(x[1], BV):
				return (x[0], Signal(x[1], x[0]))
			else:
				raise TypeError
		self.outs = dict(map(process_io, outs))
		self.ins = dict(map(process_io, ins))
		self.inouts = dict(map(process_io, inouts))
		self.parameters = parameters
		self.clkport = clkport
		self.rstport = rstport

	def __hash__(self):
		return id(self)

(READ_FIRST, WRITE_FIRST, NO_CHANGE) = range(3)

class MemoryPort:
	def __init__(self, adr, dat_r, we=None, dat_w=None,
	  async_read=False, re=None, we_granularity=0, mode=WRITE_FIRST):
		self.adr = adr
		self.dat_r = dat_r
		self.we = we
		self.dat_w = dat_w
		self.async_read = async_read
		self.re = re
		self.we_granularity = we_granularity
		self.mode = mode

class Memory:
	def __init__(self, width, depth, *ports, init=None):
		self.width = width
		self.depth = depth
		self.ports = ports
		self.init = init

class Fragment:
	def __init__(self, comb=None, sync=None, instances=None, memories=None, pads=set(), sim=None):
		if comb is None: comb = []
		if sync is None: sync = []
		if instances is None: instances = []
		if memories is None: memories = []
		if sim is None: sim = []
		self.comb = _sl(comb)
		self.sync = _sl(sync)
		self.instances = instances
		self.memories = memories
		self.pads = pads
		self.sim = sim
	
	def __add__(self, other):
		return Fragment(self.comb.l + other.comb.l,
			self.sync.l + other.sync.l,
			self.instances + other.instances,
			self.memories + other.memories,
			self.pads | other.pads,
			self.sim + other.sim)

	def call_sim(self, simulator):
		for s in self.sim:
			s(simulator)
