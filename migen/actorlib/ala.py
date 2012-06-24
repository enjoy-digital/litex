from migen.fhdl.structure import *
from migen.fhdl.structure import _Operator
from migen.flow.actor import *
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
