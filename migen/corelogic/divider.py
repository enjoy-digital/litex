from functools import partial

from migen.fhdl.structure import *

class Inst:
	def __init__(self, w):
		self.w = w
		
		d = partial(declare_signal, self)
		
		d("start_i")
		d("dividend_i", BV(w))
		d("divisor_i", BV(w))
		d("ready_o")
		d("quotient_o", BV(w))
		d("remainder_o", BV(w))
		
		d("_qr", BV(2*w))
		d("_counter", BV(bits_for(w)))
		d("_divisor_r", BV(w))
		d("_diff", BV(w+1))
	
	def get_fragment(self):
		comb = [
			self.quotient_o.eq(self._qr[:self.w]),
			self.remainder_o.eq(self._qr[self.w:]),
			self.ready_o.eq(self._counter == Constant(0, self._counter.bv)),
			self._diff.eq(self.remainder_o - self._divisor_r)
		]
		sync = [
			If(self.start_i,
				self._counter.eq(self.w),
				self._qr.eq(self.dividend_i),
				self._divisor_r.eq(self.divisor_i)
			).Elif(~self.ready_o,
					If(self._diff[self.w],
						self._qr.eq(Cat(0, self._qr[:2*self.w-1]))
					).Else(
						self._qr.eq(Cat(1, self._qr[:self.w-1], self._diff[:self.w]))
					),
					self._counter.eq(self._counter - Constant(1, self._counter.bv))
			)
		]
		return Fragment(comb, sync)
