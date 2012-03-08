from random import Random

from migen.fhdl.structure import *
from migen.fhdl import autofragment
from migen.bus.transactions import *
from migen.bus import wishbone
from migen.sim.generic import Simulator
from migen.sim.icarus import Runner

def my_generator():
	prng = Random(92837)
	for x in range(10):
		t = TWrite(x, 2*x)
		yield t
		print("Wrote in " + str(t.latency) + " cycle(s)")
		for delay in range(prng.randrange(0, 3)):
			yield None
	for x in range(10):
		t = TRead(x)
		yield t
		print("Read " + str(t.data) + " in " + str(t.latency) + " cycle(s)")
		for delay in range(prng.randrange(0, 3)):
			yield None

class MyPeripheral:
	def __init__(self):
		self.bus = wishbone.Interface()
		self.ack_en = Signal()
		self.prng = Random(763627)

	def do_simulation(self, s):
		# Only authorize acks on certain cycles to simulate variable latency
		s.wr(self.ack_en, self.prng.randrange(0, 2))

	def get_fragment(self):
		comb = [
			self.bus.ack.eq(self.bus.cyc & self.bus.stb & self.ack_en),
			self.bus.dat_r.eq(self.bus.adr + 4)
		]
		return Fragment(comb, sim=[self.do_simulation])

def main():
	master = wishbone.Initiator(my_generator())
	slave = MyPeripheral()
	tap = wishbone.Tap(slave.bus)
	intercon = wishbone.InterconnectPointToPoint(master.bus, slave.bus)
	def end_simulation(s):
		s.interrupt = master.done
	fragment = autofragment.from_local() + Fragment(sim=[end_simulation])
	sim = Simulator(fragment, Runner())
	sim.run()

main()
