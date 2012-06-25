from migen.fhdl.structure import *
from migen.fhdl.structure import _Operator
from migen.flow.actor import *
from migen.flow.network import *
from migen.corelogic.record import *
from migen.corelogic import divider

class _SimpleBinary(CombinatorialActor):
	def __init__(self, bv_op, bv_r=None):
		self.bv_op = bv_op
		if bv_r is None:
			bv_r = self.__class__.get_result_bv(bv_op)
		self.bv_r = bv_r
		super().__init__(
			("operands", Sink, [("a", bv_op), ("b", bv_op)]),
			("result", Source, [("r", bv_r)]))

	def get_process_fragment(self):
		return Fragment([
			self.token("result").r.eq(_Operator(self.op, 
				[self.token("operands").a, self.token("operands").b]))
		])

class Add(_SimpleBinary):
	op = "+"
	def get_result_bv(bv):
		return BV(bv.width+1, bv.signed)

class Sub(_SimpleBinary):
	op = "-"
	def get_result_bv(bv):
		return BV(bv.width+1, bv.signed)

class Mul(_SimpleBinary):
	op = "*"
	def get_result_bv(bv):
		return BV(2*bv.width, bv.signed)

class And(_SimpleBinary):
	op = "&"
	def get_result_bv(bv):
		return bv

class Xor(_SimpleBinary):
	op = "^"
	def get_result_bv(bv):
		return bv

class Or(_SimpleBinary):
	op = "|"
	def get_result_bv(bv):
		return bv

class LT(_SimpleBinary):
	op = "<"
	def get_result_bv(bv):
		return BV(1)

class LE(_SimpleBinary):
	op = "<="
	def get_result_bv(bv):
		return BV(1)

class EQ(_SimpleBinary):
	op = "=="
	def get_result_bv(bv):
		return BV(1)

class NE(_SimpleBinary):
	op = "!="
	def get_result_bv(bv):
		return BV(1)

class DivMod(SequentialActor):
	def __init__(self, width):
		self.div = divider.Divider(width)
		super().__init__(width,
			("operands", Sink, [("dividend", self.div.dividend_i), ("divisor", self.div.divisor_i)]),
			("result", Source, [("quotient", self.div.quotient_o), ("remainder", self.div.remainder_o)]))

	def get_process_fragment(self):
		return self.div.get_fragment() + Fragment([self.div.start_i.eq(self.trigger)])

def _create(a, b, actor_class):
	assert id(a.dfg) == id(b.dfg)
	dfg = a.dfg
	
	bva = a.get_dict()["bv_r"]
	bvb = b.get_dict()["bv_r"]
	bv_op = BV(max(bva.width, bvb.width), bva.signed and bvb.signed)
	bv_r = actor_class.get_result_bv(bv_op)
	
	new_actor = ComposableNode(dfg, actor_class, {"bv_op": bv_op, "bv_r": bv_r})
	dfg.add_connection(a, new_actor, "result", "operands", sink_subr=["a"])
	dfg.add_connection(b, new_actor, "result", "operands", sink_subr=["b"])
	
	return new_actor

class ComposableNode(ActorNode):
	def __init__(self, dfg, actor_class, parameters=dict()):
		self.dfg = dfg
		super().__init__(actor_class, parameters)
	
	def __hash__(self):
		return id(self)
	
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
