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
		self.bfm.command.allocate_dma(0x00000000, 64*1024*1024)
		self.bfm.command.enable_dma()
		selfp.command.source.ack = 1
		for i in range(100):
			yield
		for i in range(32):
			selfp.command.sink.stb = 1
			selfp.command.sink.sop = (i==0)
			selfp.command.sink.eop = (i==31)
			selfp.command.sink.write = 1
			selfp.command.sink.address = 1024
			selfp.command.sink.length = 32
			selfp.command.sink.data = i
			yield
			while selfp.command.sink.ack == 0:
				yield
		selfp.command.sink.stb = 0
		for i in range(32):
			yield
		selfp.command.sink.stb = 1
		selfp.command.sink.sop = 1
		selfp.command.sink.eop = 1
		selfp.command.sink.write = 0
		selfp.command.sink.read = 1
		selfp.command.sink.address = 1024
		selfp.command.sink.length = 32
		yield
		while selfp.command.sink.ack == 0:
			yield
		selfp.command.sink.stb = 0
		while True:
			if selfp.command.source.stb:
				print("%08x" %selfp.command.source.data)
			yield
		#dma_dump = self.bfm.command.dma_read(1024, 32*4)
		#for d in dma_dump:
		#	print("%08x" %d)

if __name__ == "__main__":
	run_simulation(TB(), ncycles=512, vcd_name="my.vcd", keep_files=True)
