import random

from migen.fhdl.std import *
from migen.genlib.record import *
from migen.sim.generic import run_simulation

from lib.sata.std import *
from lib.sata.link import SATALinkLayer
from lib.sata.transport import SATATransportLayer

from lib.sata.test.bfm import *
from lib.sata.test.common import *

class TB(Module):
	def __init__(self):
		self.submodules.bfm = BFM(phy_debug=False,
				link_random_level=50, transport_debug=True, transport_loopback=True)
		self.submodules.link = SATALinkLayer(self.bfm.phy)
		self.submodules.transport = SATATransportLayer(self.link)

		self.comb += [
			self.transport.tx.cmd.stb.eq(1),
			self.transport.tx.cmd.type.eq(fis_types["REG_H2D"]),
			self.transport.tx.cmd.lba.eq(0x12345678)
		]

if __name__ == "__main__":
	run_simulation(TB(), ncycles=256, vcd_name="my.vcd", keep_files=True)
