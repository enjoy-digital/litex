# Copyright (C) 2012 Vermeer Manufacturing Co.
# License: GPLv3 with additional permissions (see README).

from migen.fhdl.structure import *
from migen.sim.generic import Simulator
from migen.sim.icarus import Runner

class Mem:
	def __init__(self):
		# Initialize the beginning of the memory with integers
		# from 0 to 19.
		self.mem = Memory(16, 2**12, init=list(range(20)))
	
	def do_simulation(self, s):
		# Read the memory. Use the cycle counter as address.
		value = s.rd(self.mem, s.cycle_counter)
		# Print the result. Output is:
		# 0
		# 1
		# 2
		# ...
		print(value)
		# Demonstrate how to interrupt the simulator.
		if value == 10:
			s.interrupt = True
	
	def get_fragment(self):
		return Fragment(memories=[self.mem], sim=[self.do_simulation])

def main():
	dut = Mem()
	sim = Simulator(dut.get_fragment(), Runner())
	# No need for a cycle limit here, we use sim.interrupt instead.
	sim.run()

main()
