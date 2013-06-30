import inspect
import re
import builtins
from collections import defaultdict

from migen.fhdl import tracer

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
		from migen.fhdl.size import flen

		if isinstance(key, int):
			if key < 0:
				key += flen(self)
			return _Slice(self, key, key+1)
		elif isinstance(key, slice):
			start, stop, step = key.indices(flen(self))
			if step != 1:
				return Cat(*(self[i] for i in range(start, stop, step)))
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
		from migen.fhdl.size import bits_for

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
		
		self.variable = variable # deprecated
		self.reset = reset
		self.name_override = name_override
		self.backtrace = tracer.trace_back(name)

	def __repr__(self):
		return "<Signal " + (self.backtrace[-1][0] or "anonymous") + " at " + hex(id(self)) + ">"

class ClockSignal(Value):
	def __init__(self, cd="sys"):
		Value.__init__(self)
		self.cd = cd
	
class ResetSignal(Value):
	def __init__(self, cd="sys"):
		Value.__init__(self)
		self.cd = cd

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

class ClockDomain:
	def __init__(self, name=None, reset_less=False):
		self.name = tracer.get_obj_var_name(name)
		if self.name is None:
			raise ValueError("Cannot extract clock domain name from code, need to specify.")
		if len(self.name) > 3 and self.name[:3] == "cd_":
			self.name = self.name[3:]
		self.clk = Signal(name_override=self.name + "_clk")
		if reset_less:
			self.rst = None
		else:
			self.rst = Signal(name_override=self.name + "_rst")

	def rename(self, new_name):
		self.name = new_name
		self.clk.name_override = new_name + "_clk"
		if self.rst is not None:
			self.rst.name_override = new_name + "_rst"

class _ClockDomainList(list):
	def __getitem__(self, key):
		if isinstance(key, str):
			for cd in self:
				if cd.name == key:
					return cd
			raise KeyError(key)
		else:
			return list.__getitem__(self, key)

(SPECIAL_INPUT, SPECIAL_OUTPUT, SPECIAL_INOUT) = range(3)

class Fragment:
	def __init__(self, comb=None, sync=None, specials=None, clock_domains=None, sim=None):
		if comb is None: comb = []
		if sync is None: sync = dict()
		if specials is None: specials = set()
		if clock_domains is None: clock_domains = _ClockDomainList()
		if sim is None: sim = []
		
		if isinstance(sync, list):
			sync = {"sys": sync}
		
		self.comb = comb
		self.sync = sync
		self.specials = set(specials)
		self.clock_domains = _ClockDomainList(clock_domains)
		self.sim = sim
	
	def __add__(self, other):
		newsync = defaultdict(list)
		for k, v in self.sync.items():
			newsync[k] = v[:]
		for k, v in other.sync.items():
			newsync[k].extend(v)
		return Fragment(self.comb + other.comb, newsync,
			self.specials | other.specials,
			self.clock_domains + other.clock_domains,
			self.sim + other.sim)

