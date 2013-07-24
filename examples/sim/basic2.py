# Copyright (C) 2012 Vermeer Manufacturing Co.
# License: GPLv3 with additional permissions (see README).

from migen.fhdl.std import *
from migen.sim.generic import Simulator, TopLevel

# A slightly improved counter.
# Has a clock enable (CE) signal, counts on more bits
# and resets with a negative number.
class Counter(Module):
	def __init__(self):
		self.ce = Signal()
		# Demonstrate negative numbers and signals larger than 32 bits.
		self.count = Signal((37, True), reset=-5)

		self.sync += If(self.ce, self.count.eq(self.count + 1))
	
	def do_simulation(self, s):
		# Only assert CE every second cycle.
		# => each counter value is held for two cycles.
		if s.cycle_counter % 2:
			s.wr(self.ce, 0) # This is how you write to a signal.
		else:
			s.wr(self.ce, 1)
		print("Cycle: " + str(s.cycle_counter) + " Count: " + \
			str(s.rd(self.count)))
	# Set the "initialize" property on our simulation function.
	# The simulator will call it during the reset cycle,
	# with s.cycle_counter == -1.
	do_simulation.initialize = True
	
	# Output is:
	# Cycle: -1 Count: 0
	# Cycle: 0 Count: -5
	# Cycle: 1 Count: -5
	# Cycle: 2 Count: -4
	# Cycle: 3 Count: -4
	# Cycle: 4 Count: -3
	# ...

def main():
	dut = Counter()
	# Instantiating the generic top-level ourselves lets us
	# specify a VCD output file.
	sim = Simulator(dut, TopLevel("my.vcd"))
	sim.run(20)

main()
