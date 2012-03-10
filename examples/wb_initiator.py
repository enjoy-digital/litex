from random import Random

from migen.fhdl.structure import *
from migen.fhdl import autofragment
from migen.bus.transactions import *
from migen.bus import wishbone
from migen.sim.generic import Simulator
from migen.sim.icarus import Runner

# Our bus master.
# Python generators let us program bus transactions in an elegant sequential style.
def my_generator():
	prng = Random(92837)

	# Write to the first addresses.
	for x in range(10):
		t = TWrite(x, 2*x)
		yield t
		print("Wrote in " + str(t.latency) + " cycle(s)")
		# Insert some dead cycles to simulate bus inactivity.
		for delay in range(prng.randrange(0, 3)):
			yield None

	# Read from the first addresses.
	for x in range(10):
		t = TRead(x)
		yield t
		print("Read " + str(t.data) + " in " + str(t.latency) + " cycle(s)")
		for delay in range(prng.randrange(0, 3)):
			yield None

# Our bus slave.
# All transactions complete with a random delay.
# Reads return address + 4. Writes are simply acknowledged.
class MyPeripheral:
	def __init__(self):
		self.bus = wishbone.Interface()
		self.ack_en = Signal()
		self.prng = Random(763627)

	def do_simulation(self, s):
		# Only authorize acks on certain cycles to simulate variable latency.
		s.wr(self.ack_en, self.prng.randrange(0, 2))

	def get_fragment(self):
		comb = [
			self.bus.ack.eq(self.bus.cyc & self.bus.stb & self.ack_en),
			self.bus.dat_r.eq(self.bus.adr + 4)
		]
		return Fragment(comb, sim=[self.do_simulation])

def main():
	# The "wishbone.Initiator" library component runs our generator
	# and manipulates the bus signals accordingly.
	master = wishbone.Initiator(my_generator())
	# Our slave.
	slave = MyPeripheral()
	# The "wishbone.Tap" library component examines the bus at the slave port
	# and displays the transactions on the console (<TRead...>/<TWrite...>).
	tap = wishbone.Tap(slave.bus)
	# Connect the master to the slave.
	intercon = wishbone.InterconnectPointToPoint(master.bus, slave.bus)
	# A small extra simulation function to terminate the process when
	# the initiator is done (i.e. our generator is exhausted).
	def end_simulation(s):
		s.interrupt = master.done
	fragment = autofragment.from_local() + Fragment(sim=[end_simulation])
	sim = Simulator(fragment, Runner())
	sim.run()

main()

# Output:
# <TWrite adr:0x0 dat:0x0>
# Wrote in 0 cycle(s)
# <TWrite adr:0x1 dat:0x2>
# Wrote in 0 cycle(s)
# <TWrite adr:0x2 dat:0x4>
# Wrote in 0 cycle(s)
# <TWrite adr:0x3 dat:0x6>
# Wrote in 1 cycle(s)
# <TWrite adr:0x4 dat:0x8>
# Wrote in 1 cycle(s)
# <TWrite adr:0x5 dat:0xa>
# Wrote in 2 cycle(s)
# ...
# <TRead adr:0x0 dat:0x4>
# Read 4 in 2 cycle(s)
# <TRead adr:0x1 dat:0x5>
# Read 5 in 2 cycle(s)
# <TRead adr:0x2 dat:0x6>
# Read 6 in 1 cycle(s)
# <TRead adr:0x3 dat:0x7>
# Read 7 in 1 cycle(s)
# ...
