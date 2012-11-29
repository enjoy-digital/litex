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

def value_bv(v):
	if isinstance(v, bool):
		return BV(1, False)
	elif isinstance(v, int):
		return BV(bits_for(v), v < 0)
	elif isinstance(v, Signal):
		return v.bv
	elif isinstance(v, _Operator):
		obv = list(map(value_bv, v.operands))
		if v.op == "+" or v.op == "-":
			return BV(max(obv[0].width, obv[1].width) + 1,
				obv[0].signed and obv[1].signed)
		elif v.op == "*":
			signed = obv[0].signed and obv[1].signed
			if signed:
				return BV(obv[0].width + obv[1].width - 1, signed)
			else:
				return BV(obv[0].width + obv[1].width, signed)
		elif v.op == "<<" or v.op == ">>":
			return obv[0].bv
		elif v.op == "&" or v.op == "^" or v.op == "|":
			return BV(max(obv[0].width, obv[1].width),
				obv[0].signed and obv[1].signed)
		elif v.op == "<" or v.op == "<=" or v.op == "==" or v.op == "!=" \
		  or v.op == ">" or v.op == ">=":
			  return BV(1)
		else:
			raise TypeError
	elif isinstance(v, _Slice):
		return BV(v.stop - v.start, value_bv(v.value).signed)
	elif isinstance(v, Cat):
		return BV(sum(value_bv(sv).width for sv in v.l))
	elif isinstance(v, Replicate):
		return BV(value_bv(v.v).width*v.n)
	elif isinstance(v, _ArrayProxy):
		bvc = map(value_bv, v.choices)
		return BV(max(bv.width for bv in bvc), any(bv.signed for bv in bvc))
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
			return super().visit_Assign(node)
	
	def visit_ArrayProxy(self, node):
		array_muxed = Signal(value_bv(node))
		cases = dict((n, _Assign(array_muxed, self.visit(choice)))
			for n, choice in enumerate(node.choices))
		self.comb.append(Case(self.visit(node.key), cases).makedefault())
		return array_muxed

def lower_arrays(f):
	al = _ArrayLowerer()
	f2 = al.visit(f)
	f2.comb += al.comb
	return f2
