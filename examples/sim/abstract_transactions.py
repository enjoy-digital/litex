# Copyright (C) 2012 Vermeer Manufacturing Co.
# License: GPLv3 with additional permissions (see README).

from random import Random

from migen.fhdl.structure import *
from migen.fhdl import autofragment
from migen.bus.transactions import *
from migen.bus import wishbone, asmibus
from migen.sim.generic import Simulator

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
class MyModel:
	def read(self, address):
		return address + 4

class MyModelWB(MyModel, wishbone.TargetModel):
	def __init__(self):
		self.prng = Random(763627)

	def can_ack(self, bus):
		# Simulate variable latency.
		return self.prng.randrange(0, 2)

class MyModelASMI(MyModel, asmibus.TargetModel):
	pass

def test_wishbone():
	print("*** Wishbone test")
	
	# The "wishbone.Initiator" library component runs our generator
	# and manipulates the bus signals accordingly.
	master = wishbone.Initiator(my_generator())
	# The "wishbone.Target" library component examines the bus signals
	# and calls into our model object.
	slave = wishbone.Target(MyModelWB())
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
	sim = Simulator(fragment)
	sim.run()

def test_asmi():
	print("*** ASMI test")
	
	# Create a hub with one port for our initiator.
	hub = asmibus.Hub(32, 32)
	port = hub.get_port()
	hub.finalize()
	# Create the initiator, target and tap (similar to the Wishbone case).
	master = asmibus.Initiator(my_generator(), port)
	slave = asmibus.Target(MyModelASMI(), hub)
	tap = asmibus.Tap(hub)
	# Run the simulation (same as the Wishbone case).
	def end_simulation(s):
		s.interrupt = master.done
	fragment = autofragment.from_local() + Fragment(sim=[end_simulation])
	sim = Simulator(fragment)
	sim.run()
	
test_wishbone()
test_asmi()

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
