from migen.fhdl.std import *
from migen.fhdl import verilog
from migen.bus import csr
from migen.sim.generic import run_simulation
from migen.bus.transactions import *

from miscope.std import *
from miscope.trigger import *

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

def csr_prog_mila(bus, regs):
	regs.trigger_port0_mask.write(0xFFFFFFFF)
	regs.trigger_port0_trig.write(0xDEADBEEF)
	regs.trigger_port1_mask.write(0xFFFFFFFF)
	regs.trigger_port1_trig.write(0xCAFEFADE)
	regs.trigger_port2_mask.write(0xFFFFFFFF)
	regs.trigger_port2_trig.write(0xDEADBEEF)
	regs.trigger_port3_mask.write(0xFFFFFFFF)
	regs.trigger_port3_trig.write(0xCAFEFADE)

	sum_tt = gen_truth_table("i1 & i2 & i3 & i4")
	sum_trans = []
	for i in range(len(sum_tt)):
		regs.trigger_sum_prog_adr.write(i)
		regs.trigger_sum_prog_dat.write(sum_tt[i])
		regs.trigger_sum_prog_we.write(1)

	return bus.t


csr_done = False

def csr_transactions(bus, regs):
	for t in csr_prog_mila(bus, regs):
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
	def __init__(self, addrmap=None):
		self.csr_base = 0

		# Trigger
		term0 = Term(32)
		term1 = Term(32)
		term2 = Term(32)
		term3 = Term(32)
		self.submodules.trigger = Trigger(32, [term0, term1, term2, term3])

		# Csr
		self.submodules.csrbankarray = csrgen.BankArray(self, 
			lambda name, memory: self.csr_map[name if memory is None else name + "_" + memory.name_override])

		# Csr Master
		csr_header = get_csr_csv(self.csr_base, self.csrbankarray)
		write_to_file("csr.csv", csr_header)

		bus = Csr2Trans()
		regs = build_map(addrmap, bus.read_csr, bus.write_csr)
		self.submodules.master = csr.Initiator(csr_transactions(bus, regs))

		self.submodules.csrcon = csr.Interconnect(self.master.bus,	self.csrbankarray.get_buses())

		self.terms = [term0, term1, term2, term3]

	def do_simulation(self, selfp):
		for term in selfp.terms:
			term.sink.stb = 1
		if csr_done:
			selfp.terms[0].sink.dat = 0xDEADBEEF
			selfp.terms[1].sink.dat = 0xCAFEFADE
			selfp.terms[2].sink.dat = 0xDEADBEEF
			selfp.terms[3].sink.dat = 0xCAFEFADE

def main():
	tb = TB(addrmap="csr.csv")
	run_simulation(tb, ncycles=2000, vcd_name="tb_trigger_csr.vcd")
	print("Sim Done")
	input()

main()
