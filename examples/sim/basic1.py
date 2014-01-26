from migen.fhdl.std import *
from migen.sim.generic import run_simulation

# Our simple counter, which increments at every cycle
# and prints its current value in simulation.
class Counter(Module):
	def __init__(self):
		self.count = Signal(4)

		# At each cycle, increase the value of the count signal.
		# We do it with convertible/synthesizable FHDL code.
		self.sync += self.count.eq(self.count + 1)
	
	# This function will be called at every cycle.
	def do_simulation(self, selfp):
		# Simply read the count signal and print it.
		# The output is:
		# Count: 0 
		# Count: 1
		# Count: 2
		# ...
		print("Count: " + str(selfp.count))

if __name__ == "__main__":
	dut = Counter()
	# Since we do not use StopSimulation, limit the simulation
	# to some number of cycles.
	run_simulation(dut, ncycles=20)
