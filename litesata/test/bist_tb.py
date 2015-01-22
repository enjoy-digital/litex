from litesata.common import *
from litesata import LiteSATA
from litesata.frontend.bist import LiteSATABISTGenerator, LiteSATABISTChecker

from litesata.test.hdd import *
from litesata.test.common import *

class TB(Module):
	def __init__(self):
		self.submodules.hdd = HDD(
				link_debug=False, link_random_level=0,
				transport_debug=False, transport_loopback=False,
				hdd_debug=True)
		self.submodules.controller = LiteSATA(self.hdd.phy)
		self.submodules.generator = LiteSATABISTGenerator(self.controller.crossbar.get_port())
		self.submodules.checker = LiteSATABISTChecker(self.controller.crossbar.get_port())

	def gen_simulation(self, selfp):
		hdd = self.hdd
		hdd.malloc(0, 64)
		selfp.generator.sector = 0
		selfp.generator.count = 17
		selfp.checker.sector = 0
		selfp.checker.count = 17
		while True:
			selfp.generator.start = 1
			yield
			selfp.generator.start = 0
			yield
			while selfp.generator.done == 0:
				yield
			selfp.checker.start = 1
			yield
			selfp.checker.start = 0
			yield
			while selfp.checker.done == 0:
				yield
			print("errors {}".format(selfp.checker.errors))
			selfp.generator.sector += 1
			selfp.generator.count = max((selfp.generator.count + 1)%8, 1)
			selfp.checker.sector += 1
			selfp.checker.count = max((selfp.checker.count + 1)%8, 1)

if __name__ == "__main__":
	run_simulation(TB(), ncycles=8192*2, vcd_name="my.vcd", keep_files=True)
