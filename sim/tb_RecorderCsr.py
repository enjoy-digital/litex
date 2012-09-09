from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import csr
from migen.sim.generic import Simulator, PureSimulable, TopLevel
from migen.sim.icarus import Runner
from migen.bus.transactions import *

import sys
sys.path.append("../")

from migScope import recorder


arm_done = False
trig_dat = 0

rec_done = False

dat_rdy = False

def csr_transactions():

	#Reset
	yield TWrite(0, 1)
	yield TWrite(0, 0)
	
	#Size
	yield TWrite(3, 0)
	yield TWrite(4, 32)
	
	#Offset
	yield TWrite(5, 0)
	yield TWrite(6, 0)
	
	#Arm
	yield TWrite(1, 1)
	
	for t in range(10):
		yield None
		
	global arm_done
	arm_done = True
	
	global rec_done
	while not rec_done:
		yield None

	global dat_rdy
	for t in range(32):
		yield TWrite(7, 1)
		dat_rdy = False
		yield TWrite(7, 0)
		yield TRead(8)
		yield TRead(9)
		yield TRead(10)
		yield TRead(11)
		dat_rdy = True

	dat_rdy = False

	for t in range(100):
		yield None

def main():
	# Csr Master
	csr_master0 = csr.Initiator(csr_transactions())

	# Recorder
	recorder0 = recorder.Recorder(0, 32, 1024)
	
	# Csr Interconnect
	csrcon0 = csr.Interconnect(csr_master0.bus,
			[
				recorder0.bank.interface
			])

	# Recorder Data
	def recorder_data(s):
		global arm_done
		if arm_done:
			s.wr(recorder0.trig_hit, 1)
			arm_done = False

		global trig_dat
		s.wr(recorder0.trig_dat,trig_dat)
		trig_dat += 1
			
		global rec_done
		if s.rd(recorder0.sequencer.rec_done) == 1:
			rec_done = True
		
		if dat_rdy:
			print("%08X" %s.rd(recorder0._get_dat.field.w))
		

	# Simulation
	def end_simulation(s):
		s.interrupt = csr_master0.done

	fragment = autofragment.from_local()
	fragment += Fragment(sim=[end_simulation])
	fragment += Fragment(sim=[recorder_data])
	sim = Simulator(fragment, Runner(), TopLevel("tb_RecorderCsr.vcd"))
	sim.run(10000)

main()
input()