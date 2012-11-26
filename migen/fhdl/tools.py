from copy import copy

from migen.fhdl.structure import *
from migen.fhdl.structure import _Operator, _Slice, _Assign, _ArrayProxy
from migen.fhdl.visit import NodeVisitor

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
	if isinstance(v, Constant):
		return v.bv
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

def _lower_arrays_values(vl):
	r = []
	extra_comb = []
	for v in vl:
		v2, e = _lower_arrays_value(v)
		extra_comb += e
		r.append(v2)
	return r, extra_comb

def _lower_arrays_value(v):
	if isinstance(v, Constant):
		return v, []
	elif isinstance(v, Signal):
		return v, []
	elif isinstance(v, _Operator):
		op2, e = _lower_arrays_values(v.operands)
		return _Operator(v.op, op2), e
	elif isinstance(v, _Slice):
		v2, e = _lower_arrays_value(v.value)
		return _Slice(v2, v.start, v.stop), e
	elif isinstance(v, Cat):
		l2, e = _lower_arrays_values(v.l)
		return Cat(*l2), e
	elif isinstance(v, Replicate):
		v2, e = _lower_arrays_value(v.v)
		return Replicate(v2, v.n), e
	elif isinstance(v, _ArrayProxy):
		choices2, e = _lower_arrays_values(v.choices)
		array_muxed = Signal(value_bv(v))
		cases = [[Constant(n), _Assign(array_muxed, choice)]
			for n, choice in enumerate(choices2)]
		cases[-1][0] = Default()
		e.append(Case(v.key, *cases))
		return array_muxed, e

def _lower_arrays_assign(l, r):
	extra_comb = []
	if isinstance(l, _ArrayProxy):
		k, e = _lower_arrays_value(l.key)
		extra_comb += e
		cases = []
		for n, choice in enumerate(l.choices):
			assign, e = _lower_arrays_assign(choice, r)
			extra_comb += e
			cases.append([Constant(n), assign])
		cases[-1][0] = Default()
		return Case(k, *cases), extra_comb
	else:
		return _Assign(l, r), extra_comb
		
def _lower_arrays_sl(sl):
	rs = []
	extra_comb = []
	for statement in sl:
		if isinstance(statement, _Assign):
			r, e = _lower_arrays_value(statement.r)
			extra_comb += e
			r, e = _lower_arrays_assign(statement.l, r)
			extra_comb += e
			rs.append(r)
		elif isinstance(statement, If):
			cond, e = _lower_arrays_value(statement.cond)
			extra_comb += e
			t, e = _lower_arrays_sl(statement.t)
			extra_comb += e
			f, e = _lower_arrays_sl(statement.f)
			extra_comb += e
			i = If(cond)
			i.t = t
			i.f = f
			rs.append(i)
		elif isinstance(statement, Case):
			test, e = _lower_arrays_value(statement.test)
			extra_comb += e
			c = Case(test)
			for cond, csl in statement.cases:
				stmts, e = _lower_arrays_sl(csl)
				extra_comb += e
				c.cases.append((cond, stmts))
			if statement.default is not None:
				c.default, e = _lower_arrays_sl(statement.default)
				extra_comb += e
			rs.append(c)
		elif statement is not None:
			raise TypeError
	return rs, extra_comb

def lower_arrays(f):
	f = copy(f)
	f.comb, ec1 = _lower_arrays_sl(f.comb)
	f.comb += ec1
	newsync = dict()
	for k, v in f.sync.items():
		newsync[k], ec2 = _lower_arrays_sl(v)
		f.comb += ec2
	f.sync = newsync
	return f
