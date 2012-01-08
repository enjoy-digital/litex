from migen.fhdl.structure import *
from migen.fhdl.structure import _Operator
from migen.flow.actor import *
from migen.corelogic.record import *
from migen.corelogic import divider

class _SimpleBinary(Actor):
	def __init__(self, op, bv_op, bv_r):
		self.op = op
		self.operands = Record([('a', bv_op), ('b', bv_op)])
		self.result = Record([('r', bv_r)])
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.COMBINATORIAL),
			self.operands, self.result)

	def get_process_fragment(self):
		return Fragment([
			self.result.r.eq(_Operator(self.op, [self.operands.a, self.operands.b]))
		])

class Add(_SimpleBinary):
	def __init__(self, bv):
		_SimpleBinary.__init__(self, '+', bv, BV(bv.width+1, bv.signed))

class Sub(_SimpleBinary):
	def __init__(self, bv):
		_SimpleBinary.__init__(self, '-', bv, BV(bv.width+1, bv.signed))

class Mul(_SimpleBinary):
	def __init__(self, bv):
		_SimpleBinary.__init__(self, '*', bv, BV(2*bv.width, bv.signed))

class And(_SimpleBinary):
	def __init__(self, bv):
		_SimpleBinary.__init__(self, '*', bv, bv)

class Xor(_SimpleBinary):
	def __init__(self, bv):
		_SimpleBinary.__init__(self, '^', bv, bv)

class Or(_SimpleBinary):
	def __init__(self, bv):
		_SimpleBinary.__init__(self, '|', bv, bv)

class LT(_SimpleBinary):
	def __init__(self, bv):
		_SimpleBinary.__init__(self, '<', bv, BV(1))

class LE(_SimpleBinary):
	def __init__(self, bv):
		_SimpleBinary.__init__(self, '<=', bv, BV(1))

class EQ(_SimpleBinary):
	def __init__(self, bv):
		_SimpleBinary.__init__(self, '==', bv, BV(1))

class NE(_SimpleBinary):
	def __init__(self, bv):
		_SimpleBinary.__init__(self, '!=', bv, BV(1))

class DivMod(Actor):
	def __init__(self, width):
		self.div = divider.Inst(width)
		self.operands = Record([('dividend', self.div.dividend_i), ('divisor', self.div.divisor_i)])
		self.result = Record([('quotient', self.div.quotient_o), ('remainder', self.div.remainder_o)])
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.SEQUENTIAL, width),
			self.operands, self.result)

	def get_process_fragment(self):
		return self.div.get_fragment() + Fragment([self.div.start_i.eq(self.trigger)])
