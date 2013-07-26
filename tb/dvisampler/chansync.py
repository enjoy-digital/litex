from migen.fhdl.std import *
from migen.sim.generic import *

from milkymist.dvisampler.chansync import ChanSync

class TB(Module):
	def __init__(self, test_seq_it):
		self.test_seq_it = test_seq_it

		self.submodules.chansync = RenameClockDomains(ChanSync(), {"pix": "sys"})
		self.comb += self.chansync.valid_i.eq(1)

	def do_simulation(self, s):
		try:
			de0, de1, de2 = next(self.test_seq_it)
		except StopIteration:
			s.interrupt = True
			return

		s.wr(self.chansync.data_in0.de, de0)
		s.wr(self.chansync.data_in1.de, de1)
		s.wr(self.chansync.data_in2.de, de2)
		s.wr(self.chansync.data_in0.d, s.cycle_counter)
		s.wr(self.chansync.data_in1.d, s.cycle_counter)
		s.wr(self.chansync.data_in2.d, s.cycle_counter)

		out0 = s.rd(self.chansync.data_out0.d)
		out1 = s.rd(self.chansync.data_out1.d)
		out2 = s.rd(self.chansync.data_out2.d)

		print("{0:5} {1:5} {2:5}".format(out0, out1, out2))

def main():
	test_seq = [
		(1, 1, 1),
		(1, 1, 0),
		(0, 0, 0),
		(0, 0, 0),
		(0, 0, 1),
		(1, 1, 1),
		(1, 1, 1),
	]
	tb = TB(iter(test_seq*2))
	Simulator(tb).run()

main()
