import networkx as nx

from migen.flow.actor import *
from migen.flow.ala import *
from migen.flow.plumbing import *
from migen.flow.network import *

def _get_bin_sigs(a, b):
	assert id(a.dfg) == id(b.dfg)
	return (a.endp.token_signal(), b.endp.token_signal())

def _simple_binary(a, b, actor_class):
	(signal_self, signal_other) = _get_bin_sigs(a, b)
	width = max(signal_self.bv.width, signal_other.bv.width)
	signed = signal_self.bv.signed and signal_other.bv.signed
	actor = actor_class(BV(width, signed))
	combinator = Combinator(actor.operands.layout(), ["a"], ["b"])
	add_connection(a.dfg, combinator, actor)
	add_connection(a.dfg, a.actor, combinator, a.endp, combinator.sinks()[0])
	add_connection(a.dfg, b.actor, combinator, b.endp, combinator.sinks()[1])
	return make_composable(a.dfg, actor)

class ComposableSource():
	def __init__(self, dfg, actor, endp):
		self.dfg = dfg
		self.actor = actor
		self.endp = endp
	
	def __add__(self, other):
		return _simple_binary(self, other, Add)
	def __radd__(self, other):
		return _simple_binary(other, self, Add)
	def __sub__(self, other):
		return _simple_binary(self, other, Sub)
	def __rsub__(self, other):
		return _simple_binary(other, self, Sub)
	def __mul__(self, other):
		return _simple_binary(self, other, Mul)
	def __rmul__(self, other):
		return _simple_binary(other, self, Mul)
	def __and__(self, other):
		return _simple_binary(self, other, And)
	def __rand__(self, other):
		return _simple_binary(other, self, And)
	def __xor__(self, other):
		return _simple_binary(self, other, Xor)
	def __rxor__(self, other):
		return _simple_binary(other, self, Xor)
	def __or__(self, other):
		return _simple_binary(self, other, Or)
	def __ror__(self, other):
		return _simple_binary(other, self, Or)

	def __lt__(self, other):
		return _simple_binary(self, other, LT)
	def __le__(self, other):
		return _simple_binary(self, other, LE)
	def __eq__(self, other):
		return _simple_binary(self, other, EQ)
	def __ne__(self, other):
		return _simple_binary(self, other, NE)
	def __gt__(self, other):
		return _simple_binary(other, self, LT)
	def __ge__(self, other):
		return _simple_binary(other, self, LE)

def make_composable(dfg, actor):
	sources = actor.sources()
	l = [ComposableSource(dfg, actor, source) for source in sources]
	if len(l) > 1:
		return tuple(l)
	elif len(l) > 0:
		return l[0]
	else:
		return None
