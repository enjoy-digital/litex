import inspect
import re
import builtins
from collections import defaultdict

from migen.fhdl import tracer

def log2_int(n, need_pow2=True):
	l = 1
	r = 0
	while l < n:
		l *= 2
		r += 1
	if need_pow2 and l != n:
		raise ValueError("Not a power of 2")
	return r

def bits_for(n, require_sign_bit=False):
	if n > 0:
		r = log2_int(n + 1, False)
	else:
		require_sign_bit = True
		r = log2_int(-n, False)
	if require_sign_bit:
		r += 1
	return r

class HUID:
	__next_uid = 0
	def __init__(self):
		self.huid = HUID.__next_uid
		HUID.__next_uid += 1
	
	def __hash__(self):
		return self.huid

class Value(HUID):
	def __invert__(self):
		return _Operator("~", [self])
	def __neg__(self):
		return _Operator("-", [self])

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
		return _Operator("<<<", [self, other])
	def __rlshift__(self, other):
		return _Operator("<<<", [other, self])
	def __rshift__(self, other):
		return _Operator(">>>", [self, other])
	def __rrshift__(self, other):
		return _Operator(">>>", [other, self])
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
			stop = key.stop or len(self)
			if stop > len(self):
				stop = len(self)
			if key.step != None:
				raise KeyError
			return _Slice(self, start, stop)
		else:
			raise KeyError
	
	def eq(self, r):
		return _Assign(self, r)
	
	def __hash__(self):
		return HUID.__hash__(self)

class _Operator(Value):
	def __init__(self, op, operands):
		Value.__init__(self)
		self.op = op
		self.operands = operands

class _Slice(Value):
	def __init__(self, value, start, stop):
		Value.__init__(self)
		self.value = value
		self.start = start
		self.stop = stop

class Cat(Value):
	def __init__(self, *args):
		Value.__init__(self)
		self.l = args

class Replicate(Value):
	def __init__(self, v, n):
		Value.__init__(self)
		self.v = v
		self.n = n

class Signal(Value):
	def __init__(self, bits_sign=None, name=None, variable=False, reset=0, name_override=None, min=None, max=None):
		Value.__init__(self)
		
		# determine number of bits and signedness
		if bits_sign is None:
			if min is None:
				min = 0
			if max is None:
				max = 2
			max -= 1 # make both bounds inclusive
			assert(min < max)
			self.signed = min < 0 or max < 0
			self.nbits = builtins.max(bits_for(min, self.signed), bits_for(max, self.signed))
		else:
			assert(min is None and max is None)
			if isinstance(bits_sign, tuple):
				self.nbits, self.signed = bits_sign
			else:
				self.nbits, self.signed = bits_sign, False
		assert(isinstance(self.nbits, int))
		
		self.variable = variable
		self.reset = reset
		self.name_override = name_override
		self.backtrace = tracer.trace_back(name)

	def __len__(self): # TODO: remove (use tools.value_bits_sign instead)
		return self.nbits

	def __repr__(self):
		return "<Signal " + (self.backtrace[-1][0] or "anonymous") + " at " + hex(id(self)) + ">"

# statements

class _Assign:
	def __init__(self, l, r):
		self.l = l
		self.r = r

class If:
	def __init__(self, cond, *t):
		self.cond = cond
		self.t = list(t)
		self.f = []
	
	def Else(self, *f):
		_insert_else(self, list(f))
		return self
	
	def Elif(self, cond, *t):
		_insert_else(self, [If(cond, *t)])
		return self

def _insert_else(obj, clause):
	o = obj
	while o.f:
		assert(len(o.f) == 1)
		assert(isinstance(o.f[0], If))
		o = o.f[0]
	o.f = clause

class Case:
	def __init__(self, test, cases):
		self.test = test
		self.cases = cases
	
	def makedefault(self, key=None):
		if key is None:
			for choice in self.cases.keys():
				if key is None or choice > key:
					key = choice
		self.cases["default"] = self.cases[key]
		del self.cases[key]
		return self

# arrays

class _ArrayProxy(Value):
	def __init__(self, choices, key):
		self.choices = choices
		self.key = key
	
	def __getattr__(self, attr):
		return _ArrayProxy([getattr(choice, attr) for choice in self.choices],
			self.key)
	
	def __getitem__(self, key):
		return _ArrayProxy([choice.__getitem__(key) for choice in self.choices],
			self.key)

class Array(list):
	def __getitem__(self, key):
		if isinstance(key, Value):
			return _ArrayProxy(self, key)
		else:
			return list.__getitem__(self, key)

class Fragment:
	def __init__(self, comb=None, sync=None, specials=None, sim=None):
		if comb is None: comb = []
		if sync is None: sync = dict()
		if specials is None: specials = set()
		if sim is None: sim = []
		
		if isinstance(sync, list):
			sync = {"sys": sync}
		
		self.comb = comb
		self.sync = sync
		self.specials = set(specials)
		self.sim = sim
	
	def __add__(self, other):
		newsync = defaultdict(list)
		for k, v in self.sync.items():
			newsync[k] = v[:]
		for k, v in other.sync.items():
			newsync[k].extend(v)
		return Fragment(self.comb + other.comb, newsync,
			self.specials | other.specials,
			self.sim + other.sim)
	
	def rename_clock_domain(self, old, new):
		self.sync["new"] = self.sync["old"]
		del self.sync["old"]
		for special in self.specials:
			special.rename_clock_domain(old, new)
	
	def call_sim(self, simulator):
		for s in self.sim:
			if simulator.cycle_counter >= 0 or (hasattr(s, "initialize") and s.initialize):
				s(simulator)

class ClockDomain:
	def __init__(self, n1, n2=None):
		self.name = n1
		if n2 is None:
			n_clk = n1 + "_clk"
			n_rst = n1 + "_rst"
		else:
			n_clk = n1
			n_rst = n2
		self.clk = Signal(name_override=n_clk)
		self.rst = Signal(name_override=n_rst)
