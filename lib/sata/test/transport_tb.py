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
				link_random_level=0, transport_debug=True, transport_loopback=True)
		self.submodules.link = SATALinkLayer(self.bfm.phy)
		self.submodules.transport = SATATransportLayer(self.link)

	def gen_simulation(self, selfp):
		for i in range(100):
			yield
		selfp.transport.tx.cmd.stb = 1
		selfp.transport.tx.cmd.type = fis_types["REG_H2D"]
		selfp.transport.tx.cmd.lba = 0x0123456789
		yield
		while selfp.transport.tx.cmd.ack == 0:
			yield
		selfp.transport.tx.cmd.stb = 1
		selfp.transport.tx.cmd.type = fis_types["DMA_SETUP"]
		selfp.transport.tx.cmd.dma_buffer_id = 0x0123456789ABCDEF
		yield
		while selfp.transport.tx.cmd.ack == 0:
			yield
		selfp.transport.tx.cmd.stb = 1
		selfp.transport.tx.cmd.type = fis_types["DATA"]
		yield
		for i in range(32):
			selfp.transport.tx.data.stb = 1
			#selfp.transport.tx.data.sop = (i==0)
			selfp.transport.tx.data.eop = (i==31)
			selfp.transport.tx.data.d = i
			if selfp.transport.tx.data.ack == 1:
				yield
			else:
				while selfp.transport.tx.data.ack == 0:
					yield
		selfp.transport.tx.cmd.stb = 0

if __name__ == "__main__":
	run_simulation(TB(), ncycles=512, vcd_name="my.vcd", keep_files=True)
