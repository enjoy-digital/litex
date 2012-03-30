from random import Random

from migen.fhdl.structure import *
from migen.sim.generic import Simulator, TopLevel
from migen.sim.icarus import Runner

from milkymist.asmicon.refresher import *

from common import CommandLogger

class Granter:
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
	
	def get_fragment(self):
		return Fragment(sim=[self.do_simulation])

def main():
	dut = Refresher(13, 2, tRP=3, tREFI=100, tRFC=5)
	logger = CommandLogger(dut.cmd)
	granter = Granter(dut.req, dut.ack)
	fragment = dut.get_fragment() + logger.get_fragment() + granter.get_fragment()
	sim = Simulator(fragment, Runner())
	sim.run(400)

main()
