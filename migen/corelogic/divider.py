from migen.fhdl.structure import *

class Divider:
	def __init__(self, w):
		self.w = w
		
		self.start_i = Signal()
		self.dividend_i = Signal(BV(w))
		self.divisor_i = Signal(BV(w))
		self.ready_o = Signal()
		self.quotient_o = Signal(BV(w))
		self.remainder_o = Signal(BV(w))
	
	def get_fragment(self):
		w = self.w
		
		qr = Signal(BV(2*w))
		counter = Signal(BV(bits_for(w)))
		divisor_r = Signal(BV(w))
		diff = Signal(BV(w+1))
		
		comb = [
			self.quotient_o.eq(qr[:w]),
			self.remainder_o.eq(qr[w:]),
			self.ready_o.eq(counter == Constant(0, counter.bv)),
			diff.eq(self.remainder_o - divisor_r)
		]
		sync = [
			If(self.start_i,
				counter.eq(w),
				qr.eq(self.dividend_i),
				divisor_r.eq(self.divisor_i)
			).Elif(~self.ready_o,
					If(diff[w],
						qr.eq(Cat(0, qr[:2*w-1]))
					).Else(
						qr.eq(Cat(1, qr[:w-1], diff[:w]))
					),
					counter.eq(counter - Constant(1, counter.bv))
			)
		]
		return Fragment(comb, sync)
