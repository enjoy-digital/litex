from subprocess import check_output

from migen.fhdl.std import *

from lib.sata.std import *
from lib.sata.link.scrambler import *

def check(ref, res):
	shift = 0
	while((ref[0] != res[0]) and (len(res)>1)):
		res.pop(0)
		shift += 1
	length = min(len(ref), len(res))
	errors = 0
	for i in range(length):
		if ref.pop(0) != res.pop(0):
			errors += 1
	return shift, length, errors

class TB(Module):
	def __init__(self):
		self.submodules.scrambler = SATAScrambler()

	def gen_simulation(self, selfp):
		
	# init CRC
		selfp.scrambler.ce = 1
		selfp.scrambler.reset = 1
		yield
		selfp.scrambler.reset = 0

	# get C code results
		ref = []
		f = open("scrambler_ref", "r")
		for l in f:
			ref.append(int(l, 16))
		f.close()

	# log results
		yield
		res = []
		for i in range(256):
			res.append(selfp.scrambler.value)
			yield
		for e in res:
			print("%08x" %e)

	# check results
		s, l, e = check(ref, res)
		print("shift "+ str(s) + " / length " + str(l) + " / errors " + str(e))

if __name__ == "__main__":
	from migen.sim.generic import run_simulation
	run_simulation(TB(), ncycles=1000, vcd_name="my.vcd", keep_files=True)
