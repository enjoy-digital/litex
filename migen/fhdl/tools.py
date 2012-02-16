from migen.fhdl.structure import *
from migen.fhdl.structure import _Operator, _Slice, _Assign, _StatementList

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
