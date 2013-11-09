from random import Random

from migen.fhdl.std import *
from migen.sim.generic import Simulator, TopLevel

from misoclib.lasmicon.refresher import *

from common import CommandLogger

class Granter(Module):
	def __init__(self, req, ack):
		self.req = req
		self.ack = ack
		self.state = 0
		self.prng = Random(92837)
	
	def do_simulation(self, s):
		elts = ["@" + str(s.cycle_counter)]
		
		if self.state == 0:
			if s.rd(self.req):
				elts.append("Refresher requested access")
				self.state = 1
		elif self.state == 1:
			if self.prng.randrange(0, 5) == 0:
				elts.append("Granted access to refresher")
				s.wr(self.ack, 1)
				self.state = 2
		elif self.state == 2:
			if not s.rd(self.req):
				elts.append("Refresher released access")
				s.wr(self.ack, 0)
				self.state = 0
			
		if len(elts) > 1:
			print("\t".join(elts))

class TB(Module):
	def __init__(self):
		self.submodules.dut = Refresher(13, 2, tRP=3, tREFI=100, tRFC=5)
		self.submodules.logger = CommandLogger(self.dut.cmd)
		self.submodules.granter = Granter(self.dut.req, self.dut.ack)

def main():
	Simulator(TB()).run(400)

main()
