import math

def BitsFor(n):
	if n == 0:
		return 1
	else:
		return int(math.ceil(math.log(n+1, 2)))

class BV:
	def __init__(self, width=1, signed=False):
		self.width = width
		self.signed = signed
	
	def __str__(self):
		r = str(self.width) + "'"
		if self.signed:
			r += "s"
		r += "d"
		return r

class Value:
	def __init__(self, bv):
		self.bv = bv
	
	def __add__(self, other):
		return Operator("+", [self, other])
	def __radd__(self, other):
		return Operator("+", [other, self])
	def __sub__(self, other):
		return Operator("-", [self, other])
	def __rsub__(self, other):
		return Operator("-", [other, self])
	def __mul__(self, other):
		return Operator("*", [self, other])
	def __rmul__(self, other):
		return Operator("*", [other, self])
	def __lshift__(self, other):
		return Operator("<<", [self, other])
	def __rlshift__(self, other):
		return Operator("<<", [other, self])
	def __rshift__(self, other):
		return Operator(">>", [self, other])
	def __rrshift__(self, other):
		return Operator(">>", [other, self])
	def __and__(self, other):
		return Operator("&", [self, other])
	def __rand__(self, other):
		return Operator("&", [other, self])
	def __xor__(self, other):
		return Operator("^", [self, other])
	def __rxor__(self, other):
		return Operator("^", [other, self])
	def __or__(self, other):
		return Operator("|", [self, other])
	def __ror__(self, other):
		return Operator("|", [other, self])
	
	def __lt__(self, other):
		return Operator("<", [self, other])
	def __le__(self, other):
		return Operator("<=", [self, other])
	def __eq__(self, other):
		return Operator("==", [self, other])
	def __ne__(self, other):
		return Operator("!=", [self, other])
	def __gt__(self, other):
		return Operator(">", [self, other])
	def __ge__(self, other):
		return Operator(">=", [self, other])
	
	
	def __getitem__(self, key):
		if isinstance(key, int):
			return Slice(self, key, key+1)
		elif isinstance(key, slice):
			start = key.start or 0
			stop = key.stop or self.bv.width
			if key.step != None:
				raise KeyError
			return Slice(self, start, stop)
		else:
			raise KeyError

class Operator(Value):
	def __init__(self, op, operands):
		self.op = op
		self.operands = list(map(_cst, operands))
	
	def __str__(self):
		arity = len(self.operands)
		if arity == 1:
			r = self.op + str(self.operands[0])
		elif arity == 2:
			r = str(self.operands[0]) + " " + self.op + " " + str(self.operands[1])
		else:
			r = self.op + "(" + ", ".join(map(str, self.operands)) + ")"
		return "(" + r + ")"

class Slice(Value):
	def __init__(self, value, start, stop):
		self.value = value
		self.start = start
		self.stop = stop
	
	def __str__(self):
		if self.start + 1 == self.stop:
			sr = "[" + str(self.start) + "]"
		else:
			sr = "[" + str(self.start) + ":" + str(self.stop) + "]"
		return str(self.value) + sr

class Cat(Value):
	def __init__(self, *args):
		self.l = list(map(_cst, args))
	
	def __str__(self):
		return "{" + ", ".join(map(str, self.l)) + "}"

class Constant(Value):
	def __init__(self, n, bv=None):
		if bv == None:
			Value.__init__(self, BV(BitsFor(n)))
		else:
			Value.__init__(self, bv)
		self.n = n
	
	def __str__(self):
		if self.n >= 0:
			return str(self.bv) + str(self.n)
		else:
			return "-" + str(self.bv) + str(-self.n)

def _cst(x):
	if isinstance(x, int):
		return Constant(x)
	else:
		return x

class Signal(Value):
	def __init__(self, bv=BV(), name="anonymous", variable=False, reset=0):
		Value.__init__(self, bv)
		self.bv = bv
		self.variable = variable
		self.name = name
		self.reset = Constant(reset, bv)

	def __str__(self):
		return self.name
	
	def __hash__(self):
		return id(self)

def Declare(parent, name, bv=BV(), variable=False, reset=0):
	setattr(parent, name, Signal(bv, parent.__class__.__name__+"_"+name, variable, reset))

# statements

class Assign:
	def __init__(self, l, r):
		self.l = l
		self.r = _cst(r)
	
	def __str__(self):
		return str(self.l) + " = " + str(self.r)

class StatementList:
	def __init__(self, l=[]):
		self.l = l
	
	def __str__(self):
		return "\n".join(map(str, self.l))

def _sl(x):
	if isinstance(x, list):
		return StatementList(x)
	else:
		return x

def _indent(s):
	if s:
		return "\t" + s.replace("\n", "\n\t")
	else:
		return ""
		
class If:
	def __init__(self, cond, t, f=StatementList()):
		self.cond = cond
		self.t = _sl(t)
		self.f = _sl(f)
	
	def __str__(self):
		r = "if " + str(self.cond) + ":\n" + _indent(str(self.t))
		if self.f.l:
			r += "\nelse:\n" + _indent(str(self.f))
		return r

class Case:
	def __init__(self, test, cases=[], default=StatementList()):
		self.test = test
		self.cases = [(c[0], _sl(c[1])) for c in cases]
		self.default = _sl(default)

#

class Fragment:
	def __init__(self, comb=StatementList(), sync=StatementList()):
		self.comb = _sl(comb)
		self.sync = _sl(sync)
	
	def __str__(self):
		return "Comb:\n" + _indent(str(self.comb)) + "\nSync:\n" + _indent(str(self.sync))
	
	def __add__(self, other):
		return Fragment(self.comb.l + other.comb.l, self.sync.l + other.sync.l)