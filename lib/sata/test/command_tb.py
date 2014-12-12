import random

from migen.fhdl.std import *
from migen.genlib.record import *
from migen.sim.generic import run_simulation

from lib.sata.std import *
from lib.sata.link import SATALink
from lib.sata.transport import SATATransport
from lib.sata.command import SATACommand

from lib.sata.test.bfm import *
from lib.sata.test.common import *

class TB(Module):
	def __init__(self):
		self.submodules.bfm = BFM(phy_debug=False,
				link_random_level=0, transport_debug=True, transport_loopback=False)
		self.submodules.link = SATALink(self.bfm.phy)
		self.submodules.transport = SATATransport(self.link)
		self.submodules.command = SATACommand(self.transport)

	def gen_simulation(self, selfp):
		for i in range(100):
			yield
		for i in range(32):
			selfp.command.sink.stb = 1
			selfp.command.sink.sop = (i==0)
			selfp.command.sink.eop = (i==31)
			selfp.command.sink.write = 1
			selfp.command.sink.address = 0x1234
			selfp.command.sink.length = 32
			selfp.command.sink.data = i
			yield
			while selfp.command.sink.ack == 0:
				yield
		selfp.command.sink.ack = 0

if __name__ == "__main__":
	run_simulation(TB(), ncycles=512, vcd_name="my.vcd", keep_files=True)
