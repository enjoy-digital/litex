from migen.fhdl.std import *
from migen.bus import wishbone, wishbone2lasmi, lasmibus
from migen.bus.transactions import *
from migen.sim.generic import Simulator, TopLevel

from misoclib.lasmicon import *

from common import sdram_phy, sdram_geom, sdram_timing, DFILogger

l2_size = 8192 # in bytes

def my_generator():
	for x in range(20):
		t = TWrite(x, x)
		yield t
		print(str(t) + " delay=" + str(t.latency))
	for x in range(20):
		t = TRead(x)
		yield t
		print(str(t) + " delay=" + str(t.latency))
	for x in range(20):
		t = TRead(x+l2_size//4)
		yield t
		print(str(t) + " delay=" + str(t.latency))

class TB(Module):
	def __init__(self):
		self.submodules.ctler = LASMIcon(sdram_phy, sdram_geom, sdram_timing)
		self.submodules.xbar = lasmibus.Crossbar([self.ctler.lasmic], self.ctler.nrowbits)
		self.xbar.get_master() # FIXME: remove dummy master
		self.submodules.logger = DFILogger(self.ctler.dfi)
		self.submodules.bridge = wishbone2lasmi.WB2LASMI(l2_size//4, self.xbar.get_master())
		self.submodules.initiator = wishbone.Initiator(my_generator())
		self.submodules.conn = wishbone.InterconnectPointToPoint(self.initiator.bus, self.bridge.wishbone)

	def do_simulation(self, s):
		s.interrupt = self.initiator.done

def main():
	sim = Simulator(TB(), TopLevel("my.vcd"))
	sim.run()

main()
