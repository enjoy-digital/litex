from migen.fhdl.structure import *
from migen.bus.asmibus import *
from migen.sim.generic import Simulator, TopLevel

from milkymist.asmicon import *

from common import sdram_phy, sdram_geom, sdram_timing, DFILogger

def my_generator_r():
	for x in range(50):
		t = TRead(x)
		yield t
	print("reads done")

def my_generator_w():
	for x in range(50):
		t = TWrite(x, x)
		yield t
	print("writes done")

def main():
	dut = ASMIcon(sdram_phy, sdram_geom, sdram_timing)
	initiator1 = Initiator(my_generator_r(), dut.hub.get_port())
	initiator2 = Initiator(my_generator_w(), dut.hub.get_port())
	dut.finalize()
	
	logger = DFILogger(dut.dfi)
	
	def end_simulation(s):
		s.interrupt = initiator1.done and initiator2.done
	
	fragment = dut.get_fragment() + initiator1.get_fragment() + initiator2.get_fragment() + \
		logger.get_fragment() + \
		Fragment(sim=[end_simulation])
	sim = Simulator(fragment, TopLevel("my.vcd"))
	sim.run(700)

main()
