import unittest
from random import randrange

from migen.fhdl.std import *
from migen.genlib.sort import *

from migen.test.support import SimCase, SimBench

class BitonicCase(SimCase, unittest.TestCase):
	class TestBench(SimBench):
		def __init__(self):
			self.submodules.dut = BitonicSort(8, 4, ascending=True)

	def test_sizes(self):
		self.assertEqual(len(self.tb.dut.i), 8)
		self.assertEqual(len(self.tb.dut.o), 8)
		for i in range(8):
			self.assertEqual(flen(self.tb.dut.i[i]), 4)
			self.assertEqual(flen(self.tb.dut.o[i]), 4)

	def test_sort(self):
		def cb(tb, s):
			for i in tb.dut.i:
				s.wr(i, randrange(1<<flen(i)))
			i = [s.rd(i) for i in tb.dut.i]
			o = [s.rd(o) for o in tb.dut.o]
			self.assertEqual(sorted(i), o)
		self.run_with(cb, 20)
