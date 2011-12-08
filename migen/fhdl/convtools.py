from .structure import *

class Namespace:
	def __init__(self):
		self.counts = {}
		self.sigs = {}
	
	def GetName(self, sig):
		try:
			n = self.sigs[sig]
			if n:
				return sig.name + "_" + str(n)
			else:
				return sig.name
		except KeyError:
			try:
				n = self.counts[sig.name]
			except KeyError:
				n = 0
			self.sigs[sig] = n
			self.counts[sig.name] = n + 1
			if n:
				return sig.name + "_" + str(n)
			else:
				return sig.name

def ListSignals(node):
	if isinstance(node, Constant):
		return set()
	elif isinstance(node, Signal):
		return {node}
	elif isinstance(node, Operator):
		l = list(map(ListSignals, node.operands))
		return set().union(*l)
	elif isinstance(node, Slice):
		return ListSignals(node.value)
	elif isinstance(node, Cat):
		l = list(map(ListSignals, node.l))
		return set().union(*l)
	elif isinstance(node, Assign):
		return ListSignals(node.l) | ListSignals(node.r)
	elif isinstance(node, StatementList):
		l = list(map(ListSignals, node.l))
		return set().union(*l)
	elif isinstance(node, If):
		return ListSignals(node.cond) | ListSignals(node.t) | ListSignals(node.f)
	elif isinstance(node, Case):
		l = list(map(lambda x: ListSignals(x[1]), node.cases))
		return ListSignals(node.test).union(*l).union(ListSignals(node.default))
	elif isinstance(node, Fragment):
		return ListSignals(node.comb) | ListSignals(node.sync)
	else:
		raise TypeError

def ListTargets(node):
	if isinstance(node, Signal):
		return {node}
	elif isinstance(node, Slice):
		return ListTargets(node.value)
	elif isinstance(node, Cat):
		l = list(map(ListTargets, node.l))
		return set().union(*l)
	elif isinstance(node, Assign):
		return ListTargets(node.l)
	elif isinstance(node, StatementList):
		l = list(map(ListTargets, node.l))
		return set().union(*l)
	elif isinstance(node, If):
		return ListTargets(node.t) | ListTargets(node.f)
	elif isinstance(node, Case):
		l = list(map(lambda x: ListTargets(x[1]), node.cases))
		return ListTargets(node.default).union(*l)
	elif isinstance(node, Fragment):
		return ListTargets(node.comb) | ListTargets(node.sync)
	else:
		raise TypeError

def ListInstOuts(i):
	if isinstance(i, Fragment):
		return ListInstOuts(i.instances)
	else:
		l = []
		for x in i:
			l += list(map(lambda x: x[1], list(x.outs.items())))
		return set(l)

def IsVariable(node):
	if isinstance(node, Signal):
		return node.variable
	elif isinstance(node, Slice):
		return IsVariable(node.value)
	elif isinstance(node, Cat):
		arevars = list(map(IsVariable, node.l))
		r = arevars[0]
		for x in arevars:
			if x != r:
				raise TypeError
		return r
	else:
		raise TypeError

def InsertReset(rst, sl):
	targets = ListTargets(sl)
	resetcode = []
	for t in targets:
		if not t.variable:
			resetcode.append(Assign(t, t.reset))
	return If(rst, resetcode, sl)