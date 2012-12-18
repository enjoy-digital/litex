from migen.fhdl.structure import *
from migen.fhdl.structure import _Operator, _Slice, _Assign, _ArrayProxy
from migen.fhdl.visit import NodeVisitor, NodeTransformer

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
	for statement in sl:
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

def list_inst_ios(i, ins, outs, inouts):
	if isinstance(i, Fragment):
		return list_inst_ios(i.instances, ins, outs, inouts)
	elif isinstance(i, set):
		if i:
			return set.union(*(list_inst_ios(e, ins, outs, inouts) for e in i))
		else:
			return set()
	else:
		subsets = [list_signals(item.expr) for item in filter(lambda x:
			(ins and isinstance(x, Instance.Input))
			or (outs and isinstance(x, Instance.Output))
			or (inouts and isinstance(x, Instance.InOut)),
			i.items)]
		if subsets:
			return set.union(*subsets)
		else:
			return set()

def list_mem_ios(m, ins, outs):
	if isinstance(m, Fragment):
		return list_mem_ios(m.memories, ins, outs)
	else:
		s = set()
		def add(*sigs):
			for sig in sigs:
				if sig is not None:
					s.add(sig)
		for x in m:
			for p in x.ports:
				if ins:
					add(p.adr, p.we, p.dat_w, p.re)
				if outs:
					add(p.dat_r)
		return s

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
	return If(rst, *resetcode).Else(*sl)

def value_bits_sign(v):
	if isinstance(v, bool):
		return 1, False
	elif isinstance(v, int):
		return bits_for(v), v < 0
	elif isinstance(v, Signal):
		return v.nbits, v.signed
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

class _ArrayLowerer(NodeTransformer):
	def __init__(self):
		self.comb = []
	
	def visit_Assign(self, node):
		if isinstance(node.l, _ArrayProxy):
			k = self.visit(node.l.key)
			cases = {}
			for n, choice in enumerate(node.l.choices):
				assign = self.visit_Assign(_Assign(choice, node.r))
				cases[n] = [assign]
			return Case(k, cases).makedefault()
		else:
			return NodeTransformer.visit_Assign(self, node)
	
	def visit_ArrayProxy(self, node):
		array_muxed = Signal(value_bits_sign(node))
		cases = dict((n, _Assign(array_muxed, self.visit(choice)))
			for n, choice in enumerate(node.choices))
		self.comb.append(Case(self.visit(node.key), cases).makedefault())
		return array_muxed

def lower_arrays(f):
	al = _ArrayLowerer()
	f2 = al.visit(f)
	f2.comb += al.comb
	return f2

def bitreverse(s):
	length, signed = value_bits_sign(s)
	l = [s[i] for i in reversed(range(length))]
	return Cat(*l)
