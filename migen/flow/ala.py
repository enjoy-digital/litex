from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.corelogic.record import *
from migen.corelogic import divider

class Adder(Actor):
	def __init__(self, width):
		self.operands = Record([('a', BV(width)), ('b', BV(width))])
		self.result = Record([('sum', BV(width+1))])
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.COMBINATORIAL),
			self.operands, self.result)

	def get_process_fragment(self):
		return Fragment([self.result.sum.eq(self.operands.a + self.operands.b)])

class Divider(Actor):
	def __init__(self, width):
		self.div = divider.Inst(width)
		self.operands = Record([('dividend', self.div.dividend_i), ('divisor', self.div.divisor_i)])
		self.result = Record([('quotient', self.div.quotient_o), ('remainder', self.div.remainder_o)])
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.SEQUENTIAL, width),
			self.operands, self.result)

	def get_process_fragment(self):
		return self.div.get_fragment() + Fragment([self.div.start_i.eq(self.trigger)])
