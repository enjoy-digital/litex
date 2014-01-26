from migen.fhdl.std import *
from migen.sim.generic import run_simulation

# A slightly more elaborate counter.
# Has a clock enable (CE) signal, counts on more bits
# and resets with a negative number.
class Counter(Module):
	def __init__(self):
		self.ce = Signal()
		# Demonstrate negative numbers and signals larger than 32 bits.
		self.count = Signal((37, True), reset=-5)

		self.sync += If(self.ce, self.count.eq(self.count + 1))
	
	def do_simulation(self, selfp):
		# Only assert CE every second cycle.
		# => each counter value is held for two cycles.
		if selfp.simulator.cycle_counter % 2:
			selfp.ce = 0 # This is how you write to a signal.
		else:
			selfp.ce = 1
		print("Cycle: " + str(selfp.simulator.cycle_counter) + " Count: " + \
			str(selfp.count))
	
# Output is:
# Cycle: 0 Count: -5
# Cycle: 1 Count: -5
# Cycle: 2 Count: -4
# Cycle: 3 Count: -4
# Cycle: 4 Count: -3
# ...

if __name__ == "__main__":
	dut = Counter()
	# Demonstrate VCD output
	run_simulation(dut, vcd_name="my.vcd", ncycles=20)
