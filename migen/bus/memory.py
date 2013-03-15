from migen.fhdl.module import Module
from migen.bus.transactions import *

def _byte_mask(orig, dat_w, sel):
	r = 0
	shift = 0
	while sel:
		if sel & 1:
			r |= (dat_w & 0xff) << shift
		else:
			r |= (orig & 0xff) << shift
		orig >>= 8
		dat_w >>= 8
		sel >>= 1
		shift += 8
	return r

class Initiator(Module):
	def __init__(self, generator, mem):
		self.generator = generator
		self.mem = mem
		self.done = False

	def do_simulation(self, s):
		if not self.done:
			try:
				transaction = next(self.generator)
			except StopIteration:
				self.done = True
				transaction = None
			if isinstance(transaction, TRead):
				transaction.data = s.rd(self.mem, transaction.address)
			elif isinstance(transaction, TWrite):
				d = s.rd(self.mem, transaction.address)
				d_mask = _byte_mask(d, transaction.data, transaction.sel)
				s.wr(s.mem, d_mask, transaction.address)
