from migen.fhdl.structure import *
from migen.fhdl import verilog
from migen.bus import csr
from migen.sim.generic import Simulator, PureSimulable, TopLevel
from migen.sim.icarus import Runner
from migen.bus.transactions import *

from miscope.recorder import *

arm_done = False
dat = 0

rec_done = False

dat_rdy = False

rec_size = 128

def csr_transactions():

	# Reset
	yield TWrite(REC_RST_BASE, 1)
	yield TWrite(REC_RST_BASE, 0)

	# RLE
	yield TWrite(REC_RLE_BASE, 1)
	
	# Size
	yield TWrite(REC_SIZE_BASE + 0, 0)
	yield TWrite(REC_SIZE_BASE + 1, rec_size)
	
	# Offset
	yield TWrite(REC_OFFSET_BASE + 0, 0)
	yield TWrite(REC_OFFSET_BASE + 1, 0)
	
	# Arm
	yield TWrite(REC_ARM_BASE, 1)
	yield TWrite(REC_ARM_BASE, 0)
	
	for t in range(10):
		yield None
		
	global arm_done
	arm_done = True
	
	global rec_done
	while not rec_done:
		yield None

	global dat_rdy
	for t in range(rec_size):
		yield TWrite(REC_READ_BASE, 1)
		dat_rdy = False
		yield TWrite(REC_READ_BASE, 0)
		yield TRead(REC_READ_DATA_BASE + 0)
		yield TRead(REC_READ_DATA_BASE + 1)
		yield TRead(REC_READ_DATA_BASE + 2)
		yield TRead(REC_READ_DATA_BASE + 3)
		dat_rdy = True

	dat_rdy = False

	for t in range(100):
		yield None

def main():
	# Csr Master
	csr_master0 = csr.Initiator(csr_transactions())

	# Recorder
	recorder0 = Recorder(32, 1024)
	
	# Csr Interconnect
	csrcon0 = csr.Interconnect(csr_master0.bus,
			[
				recorder0.bank.bus
			])

	# Recorder Data
	def recorder_data(s):
		global arm_done
		if arm_done:
			s.wr(recorder0.hit, 1)
			arm_done = False

		global dat
		s.wr(recorder0.dat, dat//5)
		dat += 1
			
		global rec_done
		if s.rd(recorder0.sequencer.enable) == 0:
			rec_done = True
		
		if dat_rdy:
			print("%08X" %s.rd(recorder0._pull_dat.field.w))

	# Simulation
	def end_simulation(s):
		s.interrupt = csr_master0.done

	fragment = csr_master0.get_fragment()
	fragment += recorder0.get_fragment()
	fragment += csrcon0.get_fragment()
	fragment += Fragment(sim=[end_simulation])
	fragment += Fragment(sim=[recorder_data])
	sim = Simulator(fragment, TopLevel("tb_RecorderCsr.vcd"))
	sim.run(10000)

main()
print("Sim Done")
input()