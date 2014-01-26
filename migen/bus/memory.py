from migen.fhdl.std import *
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

	def do_simulation(self, selfp):
		try:
			transaction = next(self.generator)
		except StopIteration:
			transaction = None
			raise StopSimulation
		if isinstance(transaction, TRead):
			transaction.data = selfp.mem[transaction.address]
		elif isinstance(transaction, TWrite):
			d = selfp.mem[transaction.address]
			d_mask = _byte_mask(d, transaction.data, transaction.sel)
			selfp.mem[transaction.address] = d_mask
