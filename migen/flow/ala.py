from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.corelogic import divider

class Sum(Actor):
	def __init__(self, width):
		self.a = Signal(BV(width))
		self.b = Signal(BV(width))
		self.r = Signal(BV(width+1))
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.COMBINATORIAL),
			[Sink(self, [self.a, self.b])],
			[Source(self, self.r)])
	
	def get_process_fragment(self):
		return Fragment([self.r.eq(self.a + self.b)])

class Divider(Actor):
	def __init__(self, width):
		self.div = divider.Inst(width)
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.SEQUENTIAL, width),
			[Sink(self, [self.div.dividend_i]), Sink(self, [self.div.divisor_i])],
			[Source(self, [self.div.quotient_o]), Source(self, [self.div.remainder_o])])
	
	def get_process_fragment(self):
		return self.div.get_fragment() + Fragment([self.div.start_i.eq(self.trigger)])
