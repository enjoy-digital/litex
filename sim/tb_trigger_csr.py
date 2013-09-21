from migen.fhdl.std import *
from migen.fhdl import verilog
from migen.bus import csr
from migen.sim.generic import Simulator, TopLevel
from migen.sim.icarus import Runner
from migen.bus.transactions import *

from miscope.triggering import *
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
	
def csr_prog_mila():
	bus = Csr2Trans()
	trigger_port0_mask_write(bus, 0xFFFFFFFF)
	trigger_port0_trig_write(bus, 0xDEADBEEF)
	trigger_port1_mask_write(bus, 0xFFFFFFFF)
	trigger_port1_trig_write(bus, 0xDEADBEEF)
	trigger_port1_mask_write(bus, 0xFFFFFFFF)
	trigger_port1_mask_write(bus, 0xFFFFFFFF)
	trigger_port1_trig_write(bus, 0xDEADBEEF)

	sum_tt = gen_truth_table("i1 & i2 & i3 & i4")
	sum_trans = []
	for i in range(len(sum_tt)):
		trigger_sum_prog_adr_write(bus, i)
		trigger_sum_prog_dat_write(bus, sum_tt[i])
		trigger_sum_prog_we_write(bus, 1)

	return bus.t


csr_done = False

def csr_transactions():
	for t in csr_prog_mila():
		yield t
	global csr_done
	csr_done = True
	for t in range(100):
		yield None

class TB(Module):
	csr_base = 0
	csr_map = {
		"trigger": 1,
	}
	def __init__(self, first_run=False):
		

		# Csr Master
		if not first_run:
			self.submodules.master = csr.Initiator(csr_transactions())
	
		# Trigger
		term0 = Term(32)
		term1 = Term(32)
		term2 = Term(32)
		term3 = Term(32)
		self.submodules.trigger = Trigger(32, [term0, term1, term2, term3])
	
		# Csr
		self.submodules.csrbankarray = csrgen.BankArray(self, 
			lambda name, memory: self.csr_map[name if memory is None else name + "_" + memory.name_override])
		if not first_run:
			self.submodules.csrcon = csr.Interconnect(self.master.bus,	self.csrbankarray.get_buses())
	
		self.terms = [term0, term1, term2, term3]

	def do_simulation(self, s):
		for term in self.terms:
			s.wr(term.sink.stb, 1)
		if csr_done:
			s.wr(self.terms[0].sink.payload.d, 0xDEADBEEF)
			s.wr(self.terms[1].sink.payload.d ,0xCAFEFADE)
			s.wr(self.terms[2].sink.payload.d, 0xDEADBEEF)
			s.wr(self.terms[3].sink.payload.d, 0xCAFEFADE)
		s.interrupt = self.master.done

def main():
	tb = TB(first_run=True)
	csr_py_header = cif.get_py_csr_header(tb.csr_base, tb.csrbankarray)
	write_to_file("csr_header.py", csr_py_header)

	tb = TB()
	sim = Simulator(tb, TopLevel("tb_trigger_csr.vcd"))
	sim.run(2000)
	print("Sim Done")
	input()

main()
