# Copyright (C) 2012 Vermeer Manufacturing Co.
# License: GPLv3 with additional permissions (see README).

from migen.fhdl.std import *
from migen.sim.generic import Simulator

# Our simple counter, which increments at every cycle
# and prints its current value in simulation.
class Counter(Module):
	def __init__(self):
		self.count = Signal(4)

		# At each cycle, increase the value of the count signal.
		# We do it with convertible/synthesizable FHDL code.
		self.sync += self.count.eq(self.count + 1)
	
	# This function will be called at every cycle.
	def do_simulation(self, s):
		# Simply read the count signal and print it.
		# The output is:
		# Count: 0 
		# Count: 1
		# Count: 2
		# ...
		print("Count: " + str(s.rd(self.count)))

def main():
	dut = Counter()
	# We do not specify a top-level nor runner object, and use the defaults.
	sim = Simulator(dut)
	# Since we do not use sim.interrupt, limit the simulation
	# to some number of cycles.
	sim.run(20)

main()
