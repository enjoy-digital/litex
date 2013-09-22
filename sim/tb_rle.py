from migen.fhdl.std import *
from migen.fhdl import verilog
from migen.sim.generic import Simulator, TopLevel
from migen.sim.icarus import Runner

from miscope.storage import RunLengthEncoder


rle_test_seq = iter(
	[	0x00AA,
		0x00AB,
		0x00AC,
		0x00AC,
		0x00AC,
		0x00AC,
		0x00AD,
		0x00AE,
		0x00AE,
		0x00AE,
		0x00AE,
		0x00AE,
		0x00AE,
		0x00AE,
		0x00AE
	]*10
)

class TB(Module):
	def __init__(self):
		
		# Rle
		self.submodules.rle = RunLengthEncoder(16, 32)

	def do_simulation(self, s):
		s.wr(self.rle._r_enable.storage, 1)
		s.wr(self.rle.sink.stb, 1)
		try:
			s.wr(self.rle.sink.dat, next(rle_test_seq))
		except:
			pass

def main():
	tb = TB()
	sim = Simulator(tb, TopLevel("tb_rle.vcd"))
	sim.run(2000)
	print("Sim Done")
	input()

main()
