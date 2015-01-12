from migen.fhdl.std import *
from migen.fhdl import verilog
from migen.bus import csr
from migen.sim.generic import run_simulation
from migen.bus.transactions import *

from miscope.std import *
from miscope.storage import *

from mibuild.tools import write_to_file
from miscope.tools.regs import *
from miscope.tools.truthtable import *

from cpuif import *

class Csr2Trans():
	def __init__(self):
		self.t = []

	def write_csr(self, adr, value):
		self.t.append(TWrite(adr//4, value))

	def read_csr(self, adr):
		self.t.append(TRead(adr//4))
		return 0


triggered = False
dat = 0

rec_done = False

dat_rdy = False

rec_length = 128

def csr_configure(bus, regs):
	# Length
	regs.recorder_length.write(rec_length)

	# Offset
	regs.recorder_offset.write(0)

	# Trigger
	regs.recorder_trigger.write(1)

	return bus.t

def csr_read_data(bus, regs):
	for i in range(rec_length+100):
		regs.recorder_read_dat.read()
		regs.recorder_read_en.write(1)
	return bus.t

def csr_transactions(bus, regs):
	for t in csr_configure(bus, regs):
		yield t

	for t in range(100):
		yield None

	global triggered
	triggered = True

	for t in range(512):
		yield None

	for t in csr_read_data(bus, regs):
		yield t

	for t in range(100):
		yield None


class TB(Module):
	csr_base = 0
	csr_map = {
		"recorder": 1,
	}
	def __init__(self, addrmap=None):
		self.csr_base = 0

		# Recorder
		self.recorder = Recorder(32, 1024)

		# Csr
		self.csrbankarray = csrgen.BankArray(self,
			lambda name, memory: self.csr_map[name if memory is None else name + "_" + memory.name_override])

		# Csr Master
		csr_header = get_csr_csv(self.csr_base, self.csrbankarray)
		write_to_file("csr.csv", csr_header)

		bus = Csr2Trans()
		regs = build_map(addrmap, bus.read_csr, bus.write_csr)
		self.master = csr.Initiator(csr_transactions(bus, regs))

		self.csrcon = csr.Interconnect(self.master.bus,	self.csrbankarray.get_buses())

	# Recorder Data
	def recorder_data(self, selfp):
		selfp.recorder.dat_sink.stb = 1
		if not hasattr(self, "cnt"):
			self.cnt = 0
		self.cnt += 1

		selfp.recorder.dat_sink.dat =  self.cnt

		global triggered
		if triggered:
			selfp.recorder.trig_sink.stb = 1
			selfp.recorder.trig_sink.hit = 1
			triggered = False
		else:
			selfp.recorder.trig_sink.stb = 0
			selfp.recorder.trig_sink.hit = 0

	# Simulation
	def end_simulation(self, selfp):
		if self.master.done:
			raise StopSimulation

	def do_simulation(self, selfp):
		self.recorder_data(selfp)
		self.end_simulation(selfp)


def main():
	tb = TB(addrmap="csr.csv")
	run_simulation(tb, ncycles=2000, vcd_name="tb_recorder_csr.vcd")
	print("Sim Done")
	input()

main()