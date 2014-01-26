from migen.fhdl.std import *
from migen.sim.generic import run_simulation

class Mem(Module):
	def __init__(self):
		# Initialize the beginning of the memory with integers
		# from 0 to 19.
		self.specials.mem = Memory(16, 2**12, init=list(range(20)))
	
	def do_simulation(self, selfp):
		# Read the memory. Use the cycle counter as address.
		value = selfp.mem[selfp.simulator.cycle_counter]
		# Print the result. Output is:
		# 0
		# 1
		# 2
		# ...
		print(value)
		# Raising StopSimulation disables the current (and here, only one)
		# simulation function. Simulator stops when all functions are disabled.
		if value == 10:
			raise StopSimulation

if __name__ == "__main__":
	run_simulation(Mem())
