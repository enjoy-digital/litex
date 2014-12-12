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
		selfp.transport.sink.stb = 1
		selfp.transport.sink.sop = 1
		selfp.transport.sink.eop = 1
		selfp.transport.sink.type = fis_types["REG_H2D"]
		selfp.transport.sink.lba = 0x0123456789
		yield
		while selfp.transport.sink.ack == 0:
			yield
		selfp.transport.sink.stb = 1
		selfp.transport.sink.sop = 1
		selfp.transport.sink.eop = 1
		selfp.transport.sink.type = fis_types["DMA_SETUP"]
		selfp.transport.sink.dma_buffer_id = 0x0123456789ABCDEF
		yield
		while selfp.transport.sink.ack == 0:
			yield

		for i in range(32):
			selfp.transport.sink.stb = 1
			selfp.transport.sink.sop = (i==0)
			selfp.transport.sink.eop = (i==31)
			selfp.transport.sink.type = fis_types["DATA"]
			selfp.transport.sink.data = i
			if selfp.transport.sink.ack == 1:
				yield
			else:
				while selfp.transport.sink.ack == 0:
					yield
		selfp.transport.sink.stb = 0

if __name__ == "__main__":
	run_simulation(TB(), ncycles=512, vcd_name="my.vcd", keep_files=True)
