from migen.fhdl.structure import *
from migen.sim.generic import Simulator, TopLevel
from migen.sim.icarus import Runner

class Mem:
	def __init__(self):
		self.a = Signal(BV(12))
		self.d = Signal(BV(16))
		p = MemoryPort(self.a, self.d)
		self.mem = Memory(16, 2**12, p, init=list(range(20)))
	
	def do_simulation(self, s):
		if s.cycle_counter >= 0:
			value = s.rd(self.mem, s.cycle_counter)
			print(value)
			if value == 10:
				s.interrupt = True
	
	def get_fragment(self):
		return Fragment(memories=[self.mem], sim=[self.do_simulation])

def main():
	dut = Mem()
	sim = Simulator(dut.get_fragment(), Runner())
	sim.run()

main()
