from migen.flow.actor import *
from migen.flow.ala import *
from migen.flow.plumbing import *
from migen.flow.network import *

def _create(a, b, actor_class):
	assert id(a.dfg) == id(b.dfg)
	dfg = a.dfg
	
	bva = a.actor_node.get_dict()["bv_r"]
	bvb = b.actor_node.get_dict()["bv_r"]
	bv_op = BV(max(bva.width, bvb.width), bva.signed and bvb.signed)
	bv_r = actor_class.get_result_bv(bv_op)
	
	new_actor = ActorNode(actor_class, {"bv_op": bv_op, "bv_r": bv_r})
	dfg.add_connection(a.actor_node, new_actor, "result", "operands", sink_subr=["a"])
	dfg.add_connection(b.actor_node, new_actor, "result", "operands", sink_subr=["b"])
	
	return ComposableSource(dfg, new_actor)

class ComposableSource:
	def __init__(self, dfg, actor_node):
		self.dfg = dfg
		if not isinstance(actor_node, ActorNode):
			actor_node = ActorNode(actor_node)
		self.actor_node = actor_node
	
	def __add__(self, other):
		return _create(self, other, Add)
	def __radd__(self, other):
		return _create(other, self, Add)
	def __sub__(self, other):
		return _create(self, other, Sub)
	def __rsub__(self, other):
		return _create(other, self, Sub)
	def __mul__(self, other):
		return _create(self, other, Mul)
	def __rmul__(self, other):
		return _create(other, self, Mul)
	def __and__(self, other):
		return _create(self, other, And)
	def __rand__(self, other):
		return _create(other, self, And)
	def __xor__(self, other):
		return _create(self, other, Xor)
	def __rxor__(self, other):
		return _create(other, self, Xor)
	def __or__(self, other):
		return _create(self, other, Or)
	def __ror__(self, other):
		return _create(other, self, Or)

	def __lt__(self, other):
		return _create(self, other, LT)
	def __le__(self, other):
		return _create(self, other, LE)
	def __eq__(self, other):
		return _create(self, other, EQ)
	def __ne__(self, other):
		return _create(self, other, NE)
	def __gt__(self, other):
		return _create(other, self, LT)
	def __ge__(self, other):
		return _create(other, self, LE)
