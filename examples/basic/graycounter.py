from random import Random

from migen.fhdl.module import Module
from migen.genlib.cdc import GrayCounter
from migen.sim.generic import Simulator

class TB(Module):
	def __init__(self, width=3):
		self.width = width
		self.submodules.gc = GrayCounter(self.width)
		self.prng = Random(7345)

	def do_simulation(self, s):
		print("{0:0{1}b} CE={2}".format(s.rd(self.gc.q),
			self.width, s.rd(self.gc.ce)))
		s.wr(self.gc.ce, self.prng.getrandbits(1))

sim = Simulator(TB())
sim.run(35)
