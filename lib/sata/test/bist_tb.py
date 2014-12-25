from lib.sata.common import *
from lib.sata import SATACON
from lib.sata.bist import SATABISTUnit

from lib.sata.test.hdd import *
from lib.sata.test.common import *

class TB(Module):
	def __init__(self):
		self.hdd = HDD(
				link_debug=False, link_random_level=0,
				transport_debug=False, transport_loopback=False,
				hdd_debug=True)
		self.con = SATACON(self.hdd.phy)
		self.bist = SATABISTUnit(self.con)

	def gen_simulation(self, selfp):
		hdd = self.hdd
		hdd.malloc(0, 64)
		selfp.bist.sector = 0
		selfp.bist.count = 4
		while True:
			selfp.bist.start = 1
			yield
			selfp.bist.start = 0
			yield
			while selfp.bist.done == 0:
				yield
			print("ctrl_errors: {} / data_errors {}".format(selfp.bist.ctrl_errors, selfp.bist.data_errors))
			selfp.bist.sector += 1
			selfp.bist.count = max((selfp.bist.count + 1)%8, 1)

if __name__ == "__main__":
	run_simulation(TB(), ncycles=8192*2, vcd_name="my.vcd", keep_files=True)
