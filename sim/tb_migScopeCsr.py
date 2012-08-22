from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import csr
from migen.sim.generic import Simulator, PureSimulable, TopLevel
from migen.sim.icarus import Runner
from migen.bus.transactions import *

from random import Random

import sys
sys.path.append("../")
import migScope


def csr_transactions():
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



def main():
	# Csr Master
	csr_master0 = csr.Initiator(csr_transactions())

	term0 = migScope.Term(32)

	trigger0 = migScope.Trigger(0,32,64,[term0])
	csrcon0 = csr.Interconnect(csr_master0.bus, 
			[
				trigger0.bank.interface
			])
	def end_simulation(s):
			s.interrupt = csr_master0.done

	fragment = autofragment.from_local() + Fragment(sim=[end_simulation])
	sim = Simulator(fragment, Runner(),TopLevel("myvcd"))
	sim.run(20)

main()





