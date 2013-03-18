import collections

from migen.fhdl.structure import *
from migen.fhdl.structure import _Operator, _Slice, _Assign, _ArrayProxy
from migen.fhdl.visit import NodeVisitor, NodeTransformer

def bitreverse(s):
	length, signed = value_bits_sign(s)
	l = [s[i] for i in reversed(range(length))]
	return Cat(*l)

def flat_iteration(l):
	for element in l:
		if isinstance(element, collections.Iterable):
			for element2 in flat_iteration(element):
				yield element2
		else:
			yield element

class _SignalLister(NodeVisitor):
	def __init__(self):
		self.output_list = set()
	
	def visit_Signal(self, node):
		self.output_list.add(node)

class _TargetLister(NodeVisitor):
	def __init__(self):
		self.output_list = set()
		self.target_context = False
	
	def visit_Signal(self, node):
		if self.target_context:
			self.output_list.add(node)
	
	def visit_Assign(self, node):
		self.target_context = True
		self.visit(node.l)
		self.target_context = False
	
def list_signals(node):
	lister = _SignalLister()
	lister.visit(node)
	return lister.output_list

def list_targets(node):
	lister = _TargetLister()
	lister.visit(node)
	return lister.output_list

def group_by_targets(sl):
	groups = []
	for statement in flat_iteration(sl):
		targets = list_targets(statement)
		processed = False
		for g in groups:
			if not targets.isdisjoint(g[0]):
				g[0].update(targets)
				g[1].append(statement)
				processed = True
				break
		if not processed:
			groups.append((targets, [statement]))
	return groups

def list_special_ios(f, ins, outs, inouts):
	r = set()
	for special in f.specials:
		r |= special.list_ios(ins, outs, inouts)
	return r

class _ClockDomainLister(NodeVisitor):
	def __init__(self):
		self.clock_domains = set()

	def visit_ClockSignal(self, node):
		self.clock_domains.add(node.cd)

	def visit_ResetSignal(self, node):
		self.clock_domains.add(node.cd)

	def visit_clock_domains(self, node):
		for clockname, statements in node.items():
			self.clock_domains.add(clockname)
			self.visit(statements)

def list_clock_domains_expr(f):
	cdl = _ClockDomainLister()
	cdl.visit(f)
	return cdl.clock_domains

def list_clock_domains(f):
	r = list_clock_domains_expr(f)
	for special in f.specials:
		r |= special.list_clock_domains()
	for cd in f.clock_domains:
		r.add(cd.name)
	return r

def is_variable(node):
	if isinstance(node, Signal):
		return node.variable
	elif isinstance(node, _Slice):
		return is_variable(node.value)
	elif isinstance(node, Cat):
		arevars = list(map(is_variable, node.l))
		r = arevars[0]
		for x in arevars:
			if x != r:
				raise TypeError
		return r
	else:
		raise TypeError

def insert_reset(rst, sl):
	targets = list_targets(sl)
	resetcode = [t.eq(t.reset) for t in sorted(targets, key=lambda x: x.huid)]
	return [If(rst, *resetcode).Else(*sl)]

def value_bits_sign(v):
	if isinstance(v, bool):
		return 1, False
	elif isinstance(v, int):
		return bits_for(v), v < 0
	elif isinstance(v, Signal):
		return v.nbits, v.signed
	elif isinstance(v, (ClockSignal, ResetSignal)):
		return 1, False
	elif isinstance(v, _Operator):
		obs = list(map(value_bits_sign, v.operands))
		if v.op == "+" or v.op == "-":
			if not obs[0][1] and not obs[1][1]:
				# both operands unsigned
				return max(obs[0][0], obs[1][0]) + 1, False
			elif obs[0][1] and obs[1][1]:
				# both operands signed
				return max(obs[0][0], obs[1][0]) + 1, True
			elif not obs[0][1] and obs[1][1]:
				# first operand unsigned (add sign bit), second operand signed
				return max(obs[0][0] + 1, obs[1][0]) + 1, True
			else:
				# first signed, second operand unsigned (add sign bit)
				return max(obs[0][0], obs[1][0] + 1) + 1, True
		elif v.op == "*":
			if not obs[0][1] and not obs[1][1]:
				# both operands unsigned
				return obs[0][0] + obs[1][0]
			elif obs[0][1] and obs[1][1]:
				# both operands signed
				return obs[0][0] + obs[1][0] - 1
			else:
				# one operand signed, the other unsigned (add sign bit)
				return obs[0][0] + obs[1][0] + 1 - 1
		elif v.op == "<<<":
			if obs[1][1]:
				extra = 2**(obs[1][0] - 1) - 1
			else:
				extra = 2**obs[1][0] - 1
			return obs[0][0] + extra, obs[0][1]
		elif v.op == ">>>":
			if obs[1][1]:
				extra = 2**(obs[1][0] - 1)
			else:
				extra = 0
			return obs[0][0] + extra, obs[0][1]
		elif v.op == "&" or v.op == "^" or v.op == "|":
			if not obs[0][1] and not obs[1][1]:
				# both operands unsigned
				return max(obs[0][0], obs[1][0]), False
			elif obs[0][1] and obs[1][1]:
				# both operands signed
				return max(obs[0][0], obs[1][0]), True
			elif not obs[0][1] and obs[1][1]:
				# first operand unsigned (add sign bit), second operand signed
				return max(obs[0][0] + 1, obs[1][0]), True
			else:
				# first signed, second operand unsigned (add sign bit)
				return max(obs[0][0], obs[1][0] + 1), True
		elif v.op == "<" or v.op == "<=" or v.op == "==" or v.op == "!=" \
		  or v.op == ">" or v.op == ">=":
			  return 1, False
		elif v.op == "~":
			return obs[0]
		else:
			raise TypeError
	elif isinstance(v, _Slice):
		return v.stop - v.start, value_bits_sign(v.value)[1]
	elif isinstance(v, Cat):
		return sum(value_bits_sign(sv)[0] for sv in v.l), False
	elif isinstance(v, Replicate):
		return (value_bits_sign(v.v)[0])*v.n, False
	elif isinstance(v, _ArrayProxy):
		bsc = map(value_bits_sign, v.choices)
		return max(bs[0] for bs in bsc), any(bs[1] for bs in bsc)
	else:
		raise TypeError

# Basics are FHDL structure elements that back-ends are not required to support
# but can be expressed in terms of other elements (lowered) before conversion.
class _BasicLowerer(NodeTransformer):
	def __init__(self, clock_domains):
		self.comb = []
		self.target_context = False
		self.extra_stmts = []
		self.clock_domains = clock_domains

	def visit_Assign(self, node):
		old_target_context, old_extra_stmts = self.target_context, self.extra_stmts
		self.extra_stmts = []

		self.target_context = True
		lhs = self.visit(node.l)
		self.target_context = False
		rhs = self.visit(node.r)
		r = _Assign(lhs, rhs)
		if self.extra_stmts:
			r = [r] + self.extra_stmts
		
		self.target_context, self.extra_stmts = old_target_context, old_extra_stmts
		return r
	
	def visit_ArrayProxy(self, node):
		array_muxed = Signal(value_bits_sign(node), variable=True)
		if self.target_context:
			k = self.visit(node.key)
			cases = {}
			for n, choice in enumerate(node.choices):
				cases[n] = [self.visit_Assign(_Assign(choice, array_muxed))]
			self.extra_stmts.append(Case(k, cases).makedefault())
		else:
			cases = dict((n, _Assign(array_muxed, self.visit(choice)))
				for n, choice in enumerate(node.choices))
			self.comb.append(Case(self.visit(node.key), cases).makedefault())
		return array_muxed

	def visit_ClockSignal(self, node):
		return self.clock_domains[node.cd].clk

	def visit_ResetSignal(self, node):
		return self.clock_domains[node.cd].rst

def lower_basics(f):
	bl = _BasicLowerer(f.clock_domains)
	f = bl.visit(f)
	f.comb += bl.comb

	for special in f.specials:
		for obj, attr, direction in special.iter_expressions():
			if direction != SPECIAL_INOUT:
				# inouts are only supported by Migen when connected directly to top-level
				# in this case, they are Signal and never need lowering
				bl.comb = []
				bl.target_context = direction != SPECIAL_INPUT
				bl.extra_stmts = []
				expr = getattr(obj, attr)
				expr = bl.visit(expr)
				setattr(obj, attr, expr)
				f.comb += bl.comb + bl.extra_stmts

	return f

class _ClockDomainRenamer(NodeVisitor):
	def __init__(self, old, new):
		self.old = old
		self.new = new

	def visit_ClockSignal(self, node):
		if node.cd == self.old:
			node.cd = self.new

	def visit_ResetSignal(self, node):
		if node.cd == self.old:
			node.cd = self.new

def rename_clock_domain_expr(f, old, new):
	cdr = _ClockDomainRenamer(old, new)
	cdr.visit(f)

def rename_clock_domain(f, old, new):
	rename_clock_domain_expr(f, old, new)
	f.sync[new] = f.sync[old]
	del f.sync[old]
	for special in f.specials:
		special.rename_clock_domain(old, new)
	try:
		cd = f.clock_domains[old]
	except KeyError:
		pass
	else:
		cd.rename(new)
