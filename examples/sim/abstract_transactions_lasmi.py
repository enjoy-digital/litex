from migen.fhdl.std import *
from migen.bus.transactions import *
from migen.bus import lasmibus
from migen.sim.generic import Simulator

def my_generator(n):
	for x in range(4):
		t = TWrite(4*n+x, 0x100+x)
		yield t
		print("Wrote in {0} cycle(s)".format(t.latency))
		
	for x in range(4):
		t = TRead(4*n+x)
		yield t
		print("Read {0:x} in {1:x} cycle(s)".format(t.data, t.latency))

class MyModel(lasmibus.TargetModel):
	def read(self, bank, address):
		#print("read from bank {0} address {1}".format(bank, address))
		return 0x1000*bank + 0x200+address
	
	def write(self, bank, address, data, we):
		print("write to bank {0} address {1:x} data {2:x}".format(bank, address, data))

class TB(Module):
	def __init__(self):
		self.submodules.controller = lasmibus.Target(MyModel(), aw=4, dw=32, nbanks=4, read_latency=4, write_latency=1)
		self.submodules.xbar = lasmibus.Crossbar([self.controller.bus], 4, 2)
		self.initiators = [lasmibus.Initiator(my_generator(n), bus) for n, bus in enumerate(self.xbar.masters)]
		self.submodules += self.initiators

	def do_simulation(self, s):
		s.interrupt = all(m.done for m in self.initiators)

def main():
	tb = TB()
	sim = Simulator(tb)
	sim.run()
	
main()
