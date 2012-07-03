from migen.fhdl.structure import *
from migen.bus import asmibus
from migen.sim.generic import Simulator, TopLevel
from migen.sim.icarus import Runner

from milkymist.framebuffer import *

def main():
	hub = asmibus.Hub(16, 128)
	port = hub.get_port()
	hub.finalize()
	
	dut = Framebuffer(1, port, True)
	
	fragment = hub.get_fragment() + dut.get_fragment()
	sim = Simulator(fragment, Runner(), TopLevel("my.vcd"))
	
	sim.run(1)
	def csr_w(addr, d):
		sim.wr(dut.bank.description[addr].field.storage, d)
	csr_w(1, 2) # hres
	csr_w(2, 3) # hsync_start
	csr_w(3, 4) # hsync_stop
	csr_w(4, 5) # hscan
	csr_w(5, 2) # vres
	csr_w(6, 3) # vsync_start
	csr_w(7, 4) # vsync_stop
	csr_w(8, 5) # vscan
	csr_w(10, 2*2*4) # length
	csr_w(0, 1) # enable
	
	sim.run(200)

main()
