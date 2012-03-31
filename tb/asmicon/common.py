from fractions import Fraction
from math import ceil

from migen.fhdl.structure import *
from migen.sim.generic import Proxy

from milkymist import asmicon

MHz = 1000000
clk_freq = (83 + Fraction(1, 3))*MHz

clk_period_ns = 1000000000/clk_freq
def ns(t, margin=True):
	if margin:
		t += clk_period_ns/2
	return ceil(t/clk_period_ns)

sdram_geom = asmicon.GeomSettings(
	bank_a=2,
	row_a=13,
	col_a=10
)
sdram_timing = asmicon.TimingSettings(
	tRP=ns(15),
	tRCD=ns(15),
	tWR=ns(15),
	tREFI=ns(7800, False),
	tRFC=ns(70),
	
	CL=3,
	rd_delay=4,

	slot_time=16,
	read_time=32,
	write_time=16
)

class CommandLogger:
	def __init__(self, cmd, rw=False):
		self.cmd = cmd
		self.rw = rw
	
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
		if self.rw:
			comb = [self.cmd.ack.eq(1)]
		else:
			comb = []
		return Fragment(comb, sim=[self.do_simulation])

class SlotsLogger:
	def __init__(self, slicer, slots):
		self.slicer = slicer
		self.slots = slots
		
	def do_simulation(self, sim):
		state_strs = ["EMPTY", "PEND", "PRCESS"]
		rw_strs = ["RD", "WR"]
		print("\t" + "\t".join([str(x) for x in range(len(self.slots))]))
		print("State:\t" + "\t".join([state_strs[sim.rd(s.state)] for s in self.slots]))
		print("RW:\t" + "\t".join([rw_strs[sim.rd(s.we)] for s in self.slots]))
		print("Row:\t" + "\t".join([str(self.slicer.row(sim.rd(s.adr))) for s in self.slots]))
		print("Bank:\t" + "\t".join([str(self.slicer.bank(sim.rd(s.adr))) for s in self.slots]))
		print("Col:\t" + "\t".join([str(self.slicer.col(sim.rd(s.adr))) for s in self.slots]))
		times = []
		for s in self.slots:
			if s.time:
				times.append(str(sim.rd(s._counter)) + "/" + str(s.time))
			else:
				times.append("N/A")
		print("Time:\t" + "\t".join(times))

	def get_fragment(self):
		return Fragment(sim=[self.do_simulation])
