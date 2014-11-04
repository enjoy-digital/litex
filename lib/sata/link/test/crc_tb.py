import subprocess

from migen.fhdl.std import *

from lib.sata.std import *
from lib.sata.link.crc import *
from lib.sata.link.test.common import check

class TB(Module):
	def __init__(self, length):
		self.submodules.crc = SATACRC()
		self.length = length

	def gen_simulation(self, selfp):
	# init CRC
		selfp.crc.d = 0x12345678
		selfp.crc.ce = 1
		selfp.crc.reset = 1
		yield
		selfp.crc.reset = 0

	# get C code results
		p = subprocess.Popen(["./crc"], stdout=subprocess.PIPE)
		out, err = p.communicate()
		ref = [int(e, 16) for e in out.decode("utf-8").split("\n")[:-1]]


	# log results
		res = []
		for i in range(self.length):
			res.append(selfp.crc.value)
			yield

	# check results
		s, l, e = check(ref, res)
		print("shift "+ str(s) + " / length " + str(l) + " / errors " + str(e))

if __name__ == "__main__":
	from migen.sim.generic import run_simulation
	length = 8192
	run_simulation(TB(length), ncycles=length+100, vcd_name="my.vcd", keep_files=True)
