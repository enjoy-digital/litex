import random, copy

from migen.fhdl.std import *
from migen.genlib.record import *
from migen.sim.generic import run_simulation

from lib.sata.common import *
from lib.sata.link import SATALink
from lib.sata.transport import SATATransport
from lib.sata.command import SATACommand
from lib.sata.bist import SATABIST

from lib.sata.test.hdd import *
from lib.sata.test.common import *

class TB(Module):
	def __init__(self):
		self.submodules.hdd = HDD(
				link_debug=False, link_random_level=0,
				transport_debug=False, transport_loopback=False,
				hdd_debug=True)
		self.submodules.link = SATALink(self.hdd.phy)
		self.submodules.transport = SATATransport(self.link)
		self.submodules.command = SATACommand(self.transport)
		self.submodules.bist = SATABIST(sector_size=512, max_count=1)

		self.comb += [
			self.bist.source.connect(self.command.sink),
			self.command.source.connect(self.bist.sink)
		]

	def gen_simulation(self, selfp):
		hdd = self.hdd
		hdd.malloc(0, 64)
		while True:
			selfp.bist.start = 1
			yield
			selfp.bist.start = 0
			yield
			while selfp.bist.done == 0:
				yield
			print("ctrl_errors: {} / data_errors {}".format(selfp.bist.ctrl_errors, selfp.bist.data_errors))
			selfp.bist.sector += 1

if __name__ == "__main__":
	run_simulation(TB(), ncycles=4096, vcd_name="my.vcd", keep_files=True)
