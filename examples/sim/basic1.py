# Copyright (C) 2012 Vermeer Manufacturing Co.
# License: GPLv3 with additional permissions (see README).

from migen.fhdl.structure import *
from migen.sim.generic import Simulator
from migen.sim.icarus import Runner

# Our simple counter, which increments at every cycle
# and prints its current value in simulation.
class Counter:
	def __init__(self):
		self.count = Signal(4)
	
	# This function will be called at every cycle.
	def do_simulation(self, s):
		# Simply read the count signal and print it.
		# The output is:
		# Count: 0 
		# Count: 1
		# Count: 2
		# ...
		print("Count: " + str(s.rd(self.count)))
	
	def get_fragment(self):
		# At each cycle, increase the value of the count signal.
		# We do it with convertible/synthesizable FHDL code.
		sync = [self.count.eq(self.count + 1)]
		# List our simulation function in the fragment.
		sim = [self.do_simulation]
		return Fragment(sync=sync, sim=sim)

def main():
	dut = Counter()
	# Use the Icarus Verilog runner.
	# We do not specify a top-level object, and use the default.
	sim = Simulator(dut.get_fragment(), Runner())
	# Since we do not use sim.interrupt, limit the simulation
	# to some number of cycles.
	sim.run(20)

main()
