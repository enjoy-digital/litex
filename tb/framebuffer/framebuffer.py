from migen.fhdl.structure import *
from migen.bus import asmibus
from migen.sim.generic import Simulator

from milkymist.framebuffer import *

def main():
	hub = asmibus.Hub(16, 128)
	port = hub.get_port()
	hub.finalize()
	
	dut = Framebuffer(1, port, True)
	
	fragment = hub.get_fragment() + dut.get_fragment()
	sim = Simulator(fragment)
	
	sim.run(1)
	def csr_w(addr, d):
		sim.wr(dut.bank.description[addr].field.storage, d)
		
	hres = 4
	vres = 4
	
	csr_w(1, hres) # hres
	csr_w(2, hres+3) # hsync_start
	csr_w(3, hres+5) # hsync_stop
	csr_w(4, hres+10) # hscan
	csr_w(5, vres) # vres
	csr_w(6, vres+3) # vsync_start
	csr_w(7, vres+5) # vsync_stop
	csr_w(8, vres+10) # vscan
	csr_w(10, hres*vres*4) # length
	csr_w(0, 1) # enable
	
	sim.run(1000)

main()
