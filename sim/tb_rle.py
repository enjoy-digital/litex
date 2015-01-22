from migen.fhdl.std import *
from migen.sim.generic import run_simulation

from miscope import storage

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
		self.submodules.rle = storage.RunLengthEncoder(16, 32)

	def do_simulation(self, selfp):
		selfp.rle._r_enable.storage = 1
		selfp.rle.sink.stb = 1
		try:
			selfp.rle.sink.dat = next(rle_test_seq)
		except:
			pass

def main():
	tb = TB()
	run_simulation(tb, ncycles=8000, vcd_name="tb_rle.vcd")
	print("Sim Done")
	input()

main()
