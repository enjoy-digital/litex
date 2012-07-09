from copy import copy

from migen.fhdl.structure import *
from migen.fhdl.structure import _Operator, _Slice, _Assign, _StatementList, _ArrayProxy

def list_signals(node):
	if node is None:
		return set()
	elif isinstance(node, Constant):
		return set()
	elif isinstance(node, Signal):
		return {node}
	elif isinstance(node, _Operator):
		l = list(map(list_signals, node.operands))
		return set().union(*l)
	elif isinstance(node, _Slice):
		return list_signals(node.value)
	elif isinstance(node, Cat):
		l = list(map(list_signals, node.l))
		return set().union(*l)
	elif isinstance(node, Replicate):
		return list_signals(node.v)
	elif isinstance(node, _Assign):
		return list_signals(node.l) | list_signals(node.r)
	elif isinstance(node, _StatementList):
		l = list(map(list_signals, node.l))
		return set().union(*l)
	elif isinstance(node, If):
		return list_signals(node.cond) | list_signals(node.t) | list_signals(node.f)
	elif isinstance(node, Case):
		l = list(map(lambda x: list_signals(x[1]), node.cases))
		return list_signals(node.test).union(*l).union(list_signals(node.default))
	elif isinstance(node, Fragment):
		return list_signals(node.comb) | list_signals(node.sync)
	else:
		raise TypeError

def list_targets(node):
	if node is None:
		return set()
	elif isinstance(node, Signal):
		return {node}
	elif isinstance(node, _Slice):
		return list_targets(node.value)
	elif isinstance(node, Cat):
		l = list(map(list_targets, node.l))
		return set().union(*l)
	elif isinstance(node, _Assign):
		return list_targets(node.l)
	elif isinstance(node, _StatementList):
		l = list(map(list_targets, node.l))
		return set().union(*l)
	elif isinstance(node, If):
		return list_targets(node.t) | list_targets(node.f)
	elif isinstance(node, Case):
		l = list(map(lambda x: list_targets(x[1]), node.cases))
		return list_targets(node.default).union(*l)
	elif isinstance(node, Fragment):
		return list_targets(node.comb) | list_targets(node.sync)
	else:
		raise TypeError

def group_by_targets(sl):
	groups = []
	for statement in sl.l:
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
	else:
		l = []
		for x in i:
			if ins:
				l += x.ins.values()
			if outs:
				l += x.outs.values()
			if inouts:
				l += x.inouts.values()
		return set(l)

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
	resetcode = [t.eq(t.reset) for t in targets]
	return If(rst, *resetcode).Else(*sl.l)

def _lower_arrays_values(vl):
	r = []
	extra_comb = []
	for v in vl:
		v2, e = _lower_arrays_value(v)
		extra_comb += e
		r.append(v2)
	return r, extra_comb
	
def _lower_arrays_value(v):
	if isinstance(v, _Operator):
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
	elif isinstance(v, Constant):
		return v, []
	elif isinstance(v, Signal):
		return v, []
	elif isinstance(v, _ArrayProxy):
		choices2, e = _lower_arrays_values(v.choices)
		array_muxed = Signal(BV(32)) # TODO: use the correct BV
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
	result = _StatementList()
	rs = result.l
	extra_comb = []
	for statement in sl.l:
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
	return result, extra_comb

def lower_arrays(f):
	f = copy(f)
	f.comb, ec1 = _lower_arrays_sl(f.comb)
	f.sync, ec2 = _lower_arrays_sl(f.sync)
	f.comb.l += ec1 + ec2
	return f
