from migen.fhdl.std import *
from migen.fhdl import verilog
from migen.bus import csr
from migen.sim.generic import Simulator, TopLevel
from migen.sim.icarus import Runner
from migen.bus.transactions import *

from miscope.recording import *
from miscope.std.truthtable import *

from miscope.std import cif

from mibuild.tools import write_to_file

try:
	from csr_header import *
	print("csr_header imported")
except:
	print("csr_header not found")

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

def csr_configure():
	bus = Csr2Trans()

	# Length
	recorder_length_write(bus, rec_length)

	# Offset
	recorder_offset_write(bus, 0)
	
	# Trigger
	recorder_trigger_write(bus, 1)

	return bus.t

def csr_read_data():
	bus = Csr2Trans()

	for i in range(rec_length+100):
		recorder_read_dat_read(bus)
		recorder_read_en_write(bus, 1)
	return bus.t

def csr_transactions():
	for t in csr_configure():
		yield t

	for t in range(100):
		yield None
	
	global triggered
	triggered = True

	for t in range(512):
		yield None

	for t in csr_read_data():
		yield t

	for t in range(100):
		yield None


class TB(Module):
	csr_base = 0
	csr_map = {
		"recorder": 1,
	}
	def __init__(self, first_run=False):
		self.csr_base = 0

		# Csr Master
		if not first_run:
			self.submodules.master = csr.Initiator(csr_transactions())
	
		# Recorder
		self.submodules.recorder = Recorder(32, 1024)
	
		# Csr
		self.submodules.csrbankarray = csrgen.BankArray(self, 
			lambda name, memory: self.csr_map[name if memory is None else name + "_" + memory.name_override])
		if not first_run:
			self.submodules.csrcon = csr.Interconnect(self.master.bus,	self.csrbankarray.get_buses())

	# Recorder Data
	def recorder_data(self, s):
		s.wr(self.recorder.sink.stb, 1)
		if not hasattr(self, "cnt"):
			self.cnt = 0
		self.cnt += 1	

		s.wr(self.recorder.sink.payload.d, self.cnt)

		global triggered
		if triggered:
			s.wr(self.recorder.sink.payload.hit, 1)
			triggered = False
		else:
			s.wr(self.recorder.sink.payload.hit, 0)

	# Simulation
	def end_simulation(self, s):
		s.interrupt = self.master.done


	def do_simulation(self, s):
		self.recorder_data(s)
		self.end_simulation(s)


def main():
	tb = TB(first_run=True)
	csr_py_header = cif.get_py_csr_header(tb.csr_base, tb.csrbankarray)
	write_to_file("csr_header.py", csr_py_header)

	tb = TB()
	sim = Simulator(tb, TopLevel("tb_recorder_csr.vcd"))
	sim.run(2000)
	print("Sim Done")
	input()

main()