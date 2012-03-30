from migen.fhdl.structure import *
from migen.sim.generic import Proxy

class CommandLogger:
	def __init__(self, cmd):
		self.cmd = cmd
	
	def do_simulation(self, s):
		elts = ["@" + str(s.cycle_counter)]
		
		cmdp = Proxy(s, self.cmd)
		if not cmdp.ras_n and cmdp.cas_n and cmdp.we_n:
			elts.append("ACTIVATE")
			elts.append("BANK " + str(cmdp.ba))
			elts.append("ROW " + str(cmdp.a))
		elif cmdp.ras_n and not cmdp.cas_n and cmdp.we_n:
			elts.append("READ\t")
			elts.append("BANK " + str(cmdp.ba))
			elts.append("COL " + str(cmdp.a))
		elif cmdp.ras_n and not cmdp.cas_n and not cmdp.we_n:
			elts.append("WRITE\t")
			elts.append("BANK " + str(cmdp.ba))
			elts.append("COL " + str(cmdp.a))
		elif cmdp.ras_n and cmdp.cas_n and not cmdp.we_n:
			elts.append("BST")
		elif not cmdp.ras_n and not cmdp.cas_n and cmdp.we_n:
			elts.append("AUTO REFRESH")
		elif not cmdp.ras_n and cmdp.cas_n and not cmdp.we_n:
			elts.append("PRECHARGE")
			if cmdp.a & 2**10:
				elts.append("ALL")
			else:
				elts.append("BANK " + str(cmdp.ba))
		elif not cmdp.ras_n and not cmdp.cas_n and not cmdp.we_n:
			elts.append("LMR")
		
		if len(elts) > 1:
			print("\t".join(elts))
	
	def get_fragment(self):
		return Fragment(sim=[self.do_simulation])
