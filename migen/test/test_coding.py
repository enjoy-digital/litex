import unittest

from migen.fhdl.std import *
from migen.genlib.coding import *

from migen.test.support import SimCase, SimBench

class EncCase(SimCase, unittest.TestCase):
	class TestBench(SimBench):
		def __init__(self):
			self.submodules.dut = Encoder(8)

	def test_sizes(self):
		self.assertEqual(flen(self.tb.dut.i), 8)
		self.assertEqual(flen(self.tb.dut.o), 3)
		self.assertEqual(flen(self.tb.dut.n), 1)

	def test_run_sequence(self):
		seq = list(range(1<<8))
		cur = None
		def cb(tb, s):
			if seq:
				s.wr(tb.dut.i, seq.pop(0))
			i = s.rd(tb.dut.i)
			if s.rd(tb.dut.n):
				self.assertNotIn(i, [1<<i for i in range(8)])
			else:
				o = s.rd(tb.dut.o)
				self.assertEqual(i, 1<<o)
		self.run_with(cb, 256)

class PrioEncCase(SimCase, unittest.TestCase):
	class TestBench(SimBench):
		def __init__(self):
			self.submodules.dut = PriorityEncoder(8)

	def test_sizes(self):
		self.assertEqual(flen(self.tb.dut.i), 8)
		self.assertEqual(flen(self.tb.dut.o), 3)
		self.assertEqual(flen(self.tb.dut.n), 1)

	def test_run_sequence(self):
		seq = list(range(1<<8))
		cur = None
		def cb(tb, s):
			if seq:
				s.wr(tb.dut.i, seq.pop(0))
			i = s.rd(tb.dut.i)
			if s.rd(tb.dut.n):
				self.assertEqual(i, 0)
			else:
				o = s.rd(tb.dut.o)
				if o > 0:
					self.assertEqual(i & 1<<(o - 1), 0)
				self.assertGreaterEqual(i, 1<<o)
		self.run_with(cb, 256)

class DecCase(SimCase, unittest.TestCase):
	class TestBench(SimBench):
		def __init__(self):
			self.submodules.dut = Decoder(8)

	def test_sizes(self):
		self.assertEqual(flen(self.tb.dut.i), 3)
		self.assertEqual(flen(self.tb.dut.o), 8)
		self.assertEqual(flen(self.tb.dut.n), 1)

	def test_run_sequence(self):
		seq = list(range(8*2))
		cur = None
		def cb(tb, s):
			if seq:
				i = seq.pop()
				s.wr(tb.dut.i, i//2)
				s.wr(tb.dut.n, i%2)
			i = s.rd(tb.dut.i)
			o = s.rd(tb.dut.o)
			if s.rd(tb.dut.n):
				self.assertEqual(o, 0)
			else:
				self.assertEqual(o, 1<<i)
		self.run_with(cb, 256)
