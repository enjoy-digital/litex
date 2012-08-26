from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import csr
from migen.sim.generic import Simulator, PureSimulable, TopLevel
from migen.sim.icarus import Runner
from migen.bus.transactions import *

import sys
sys.path.append("../")
import migScope

from migScope.tools.truthtable import *

def term_prog(off, dat):
	for i in range(4):
		yield TWrite(off+3-i, (dat>>(8*i))&0xFF)


def sum_prog(off, addr, dat):
	we = 2
	yield TWrite(off+3, addr%0xFF)
	yield TWrite(off+2, (addr>>8)%0xFF)
	yield TWrite(off+1, we+dat)
	yield TWrite(off+0, 0)
	for i in range(4):
		yield TWrite(off+i,0)


csr_done = False

def csr_transactions():

	term_trans = []
	term_trans += [term_prog(0x04  ,0xDEADBEEF)]
	term_trans += [term_prog(0x08  ,0xCAFEFADE)]
	term_trans += [term_prog(0x0C  ,0xDEADBEEF)]
	term_trans += [term_prog(0x10  ,0xCAFEFADE)]
	for t in term_trans:
		for r in t:
			yield r

	sum_trans = []
	sum_trans += [sum_prog(0x00,i,1) for i in range(8)]
	sum_trans += [sum_prog(0x00,i,0) for i in range(8)]
	for t in sum_trans:
		for r in t:
			yield r
			
	sum_tt = gen_truth_table("i1 & i2 & i3 & i4")
	sum_trans = []
	for i in range(len(sum_tt)):
		sum_trans.append(sum_prog(0x00,i,sum_tt[i]))
	print(sum_tt)
	for t in sum_trans:
		for r in t:
			yield r
	
	global csr_done
	csr_done = True
	
	for t in range(100):
		yield None


def main():
	# Csr Master
	csr_master0 = csr.Initiator(csr_transactions())

	# Trigger
	term0 = migScope.Term(32)
	term1 = migScope.Term(32)
	term2 = migScope.Term(32)
	term3 = migScope.Term(32)
	trigger0 = migScope.Trigger(0, 32, 64, [term0, term1, term2, term3])
	
	# Csr Interconnect
	csrcon0 = csr.Interconnect(csr_master0.bus, 
			[
				trigger0.bank.interface
			])

	# Term Test
	def term_stimuli(s):
		if csr_done:
			s.wr(term0.i,0xDEADBEEF)
			s.wr(term1.i,0xCAFEFADE)
			s.wr(term2.i,0xDEADBEEF)
			s.wr(term3.i,0xCAFEFADE)

	
	# Simulation
	def end_simulation(s):
		s.interrupt = csr_master0.done

	fragment = autofragment.from_local()
	fragment += Fragment(sim=[end_simulation])
	fragment += Fragment(sim=[term_stimuli])
	sim = Simulator(fragment, Runner(),TopLevel("tb_TriggerCsr.vcd"))
	sim.run(2000)

main()
input()





