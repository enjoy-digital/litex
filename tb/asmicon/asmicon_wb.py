from migen.fhdl.structure import *
from migen.bus import wishbone, wishbone2asmi, asmibus
from migen.sim.generic import Simulator, TopLevel

from milkymist.asmicon import *

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

def main():
	controller = ASMIcon(sdram_phy, sdram_geom, sdram_timing)
	bridge = wishbone2asmi.WB2ASMI(l2_size//4, controller.hub.get_port())
	controller.finalize()
	initiator = wishbone.Initiator(my_generator())
	conn = wishbone.InterconnectPointToPoint(initiator.bus, bridge.wishbone)
	
	logger = DFILogger(controller.dfi)
	
	def end_simulation(s):
		s.interrupt = initiator.done
	
	fragment = controller.get_fragment() + \
		bridge.get_fragment() + \
		initiator.get_fragment() + \
		conn.get_fragment() + \
		logger.get_fragment() + \
		Fragment(sim=[end_simulation])
	sim = Simulator(fragment, TopLevel("my.vcd"))
	sim.run()

main()
