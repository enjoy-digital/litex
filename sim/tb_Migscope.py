from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import csr
from migen.sim.generic import Simulator, PureSimulable, TopLevel
from migen.sim.icarus import Runner
from migen.bus.transactions import *

import sys
sys.path.append("../")

from migScope import trigger, recorder
from migScope.tools.truthtable import *
from migScope.tools.vcd import *

TRIGGER_ADDR  = 0x0000
RECORDER_ADDR = 0x0200

rec_done = False
dat_rdy  = False

dat_vcd = []

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

def csr_transactions(trigger0, recorder0):

	# Trigger Prog
	##############################

	# Term Prog
	term_trans = []
	term_trans += [term_prog(trigger0.ports[0].reg_base, 0x00000000)]
	term_trans += [term_prog(trigger0.ports[1].reg_base, 0x00000004)]
	term_trans += [term_prog(trigger0.ports[2].reg_base, 0x00000008)]
	term_trans += [term_prog(trigger0.ports[3].reg_base, 0x0000000C)]
	for t in term_trans:
		for r in t:
			yield r
	
	# Sum Prog
	sum_tt = gen_truth_table("term0 | term1 | term2 | term3")
	sum_trans = []
	for i in range(len(sum_tt)):
		sum_trans.append(sum_prog(trigger0.sum.reg_base, i, sum_tt[i]))
	for t in sum_trans:
		for r in t:
			yield r
	
	# Recorder Prog
	##############################
	#Reset
	yield TWrite(recorder0.address + 0,  1)
	yield TWrite(recorder0.address + 0,  0)
	
	#Size
	yield TWrite(recorder0.address + 3,  0)
	yield TWrite(recorder0.address + 4, 64)
	
	#Offset
	yield TWrite(recorder0.address + 5,   0)
	yield TWrite(recorder0.address + 6,  16)

	#Arm
	yield TWrite(recorder0.address + 1,  1)

	# Wait Record to be done
	##############################
	global rec_done
	while not rec_done:
		yield None

	# Read recorded data
	##############################
	global dat_rdy	
	for t in range(64):
		yield TWrite(recorder0.address + 7, 1)
		dat_rdy = False
		yield TWrite(recorder0.address + 7, 0)
		yield TRead(recorder0.address + 8)
		yield TRead(recorder0.address + 9)
		yield TRead(recorder0.address + 10)
		yield TRead(recorder0.address + 11)
		dat_rdy = True

	dat_rdy = False

	for t in range(512):
		yield None


trig_sig_val = 0


def main():

	# Trigger
	term0 = trigger.Term(32)
	term1 = trigger.Term(32)
	term2 = trigger.Term(32)
	term3 = trigger.Term(32)
	trigger0 = trigger.Trigger(TRIGGER_ADDR, 32, 64, [term0, term1, term2, term3])
	
	# Recorder
	recorder0 = recorder.Recorder(RECORDER_ADDR, 32, 1024)
	
	# Csr Master
	csr_master0 = csr.Initiator(csr_transactions(trigger0, recorder0))

	# Csr Interconnect
	csrcon0 = csr.Interconnect(csr_master0.bus, 
			[
				trigger0.bank.interface,
				recorder0.bank.interface
			])

	trig_sig = Signal(32)
	comb = []
	comb +=[
		trigger0.in_trig.eq(trig_sig)
	]
	
	comb += [
		recorder0.trig_dat.eq(trig_sig),
		recorder0.trig_hit.eq(trigger0.hit)
	]
	# Term Test
	def term_stimuli(s):
		global trig_sig_val
		s.wr(trig_sig,trig_sig_val)
		trig_sig_val += 1
		trig_sig_val = trig_sig_val % 256

	# Recorder Data
	def recorder_data(s):
		global rec_done
		if s.rd(recorder0.sequencer.rec_done) == 1:
			rec_done = True
		
		global dat_rdy
		if dat_rdy:
			print("%08X" %s.rd(recorder0._get_dat.field.w))
			global dat_vcd
			dat_vcd.append(s.rd(recorder0._get_dat.field.w))

	
	# Simulation
	def end_simulation(s):
		s.interrupt = csr_master0.done
		myvcd = Vcd()
		myvcd.add(Var("wire", 32, "trig_dat", dat_vcd))
		f = open("tb_Miscope_Out.vcd", "w")
		f.write(str(myvcd))
		f.close()
	
	
	fragment = autofragment.from_local()
	fragment += Fragment(comb=comb)
	fragment += Fragment(sim=[term_stimuli])
	fragment += Fragment(sim=[recorder_data])
	fragment += Fragment(sim=[end_simulation])

	sim = Simulator(fragment, Runner(),TopLevel("tb_MigScope.vcd"))
	sim.run(2000)

main()
input()
