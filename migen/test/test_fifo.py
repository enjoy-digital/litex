import unittest

from migen.fhdl.std import *
from migen.genlib.fifo import SyncFIFO, AsyncFIFO

from .support import SimCase, SimBench

class SyncFIFOCase(SimCase):
	class TestBench(SimBench):
		def __init__(self):
			self.submodules.dut = SyncFIFO([("a", 32), ("b", 32)], 2)

			self.sync += [
				If(self.dut.we & self.dut.writable,
					self.dut.din.a.eq(self.dut.din.a + 1),
					self.dut.din.b.eq(self.dut.din.b + 2)
				)
			]

	def test_sizes(self):
		self.assertEqual(flen(self.tb.dut.din_bits), 64)
		self.assertEqual(flen(self.tb.dut.dout_bits), 64)

	def test_run_sequence(self):
		seq = list(range(20))
		def cb(tb, s):
			# fire re and we at "random"
			s.wr(tb.dut.we, s.cycle_counter % 2 == 0)
			s.wr(tb.dut.re, s.cycle_counter % 3 == 0)
			# the output if valid must be correct
			if s.rd(tb.dut.readable) and s.rd(tb.dut.re):
				i = seq.pop(0)
				self.assertEqual(s.rd(tb.dut.dout.a), i)
				self.assertEqual(s.rd(tb.dut.dout.b), i*2)
		self.run_with(cb, 20)
