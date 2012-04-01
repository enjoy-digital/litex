from migen.fhdl.structure import *
from migen.bus.asmibus import *
from migen.sim.generic import Simulator, TopLevel
from migen.sim.icarus import Runner

from milkymist.asmicon import *

from common import sdram_phy, sdram_geom, sdram_timing, DFILogger

def my_generator():
	for x in range(100):
		t = TRead(x)
		yield t

def main():
	dut = ASMIcon(sdram_phy, sdram_geom, sdram_timing)
	initiator = Initiator(dut.hub.get_port(), my_generator())
	dut.finalize()
	
	logger = DFILogger(dut.dfi)
	
	def end_simulation(s):
		s.interrupt = initiator.done
	
	fragment = dut.get_fragment() + initiator.get_fragment() + \
		logger.get_fragment() + \
		Fragment(sim=[end_simulation])
	sim = Simulator(fragment, Runner(keep_files=True), TopLevel("my.vcd"))
	sim.run()

main()
