from migen.fhdl.structure import *
from migen.bus.asmibus import *
from migen.sim.generic import Simulator, TopLevel

from milkymist.asmicon.bankmachine import *

from common import sdram_geom, sdram_timing, CommandLogger

def my_generator():
	for x in range(10):
		t = TWrite(x)
		yield t
	for x in range(10):
		t = TWrite(x + 2200)
		yield t

class Completer:
	def __init__(self, hub, cmd):
		self.hub = hub
		self.cmd = cmd
		
	def get_fragment(self):
		sync = [
			self.hub.call.eq(self.cmd.stb & self.cmd.ack & (self.cmd.is_read | self.cmd.is_write)),
			self.hub.tag_call.eq(self.cmd.tag)
		]
		return Fragment(sync=sync)

def main():
	hub = Hub(12, 128, 2)
	initiator = Initiator(hub.get_port(), my_generator())
	hub.finalize()
	
	dut = BankMachine(sdram_geom, sdram_timing, 2, 0, hub.get_slots())
	logger = CommandLogger(dut.cmd, True)
	completer = Completer(hub, dut.cmd)
	
	def end_simulation(s):
		s.interrupt = initiator.done
	
	fragment = hub.get_fragment() + initiator.get_fragment() + \
		dut.get_fragment() + logger.get_fragment() + completer.get_fragment() + \
		Fragment(sim=[end_simulation])
	sim = Simulator(fragment, TopLevel("my.vcd"))
	sim.run()

main()
