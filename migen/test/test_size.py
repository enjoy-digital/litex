import unittest

from migen.fhdl.std import *

def _same_slices(a, b):
	return a.value is b.value and a.start == b.start and a.stop == b.stop

class SignalSizeCase(unittest.TestCase):
	def setUp(self):
		self.i = 0xaa
		self.j = -127
		self.s = Signal((13, True))

	def test_flen(self):
		self.assertEqual(flen(self.s), 13)
		self.assertEqual(flen(self.i), 8)
		self.assertEqual(flen(self.j), 8)

	def test_flen_type(self):
		self.assertRaises(TypeError, flen, [])

	def test_fiter(self):
		for i, si in enumerate(fiter(self.s)):
			self.assertTrue(_same_slices(si, self.s[i]))
		self.assertEqual(list(fiter(self.i)),
				[(self.i >> i) & 1 for i in range(8)])
		self.assertEqual(list(fiter(self.j)),
				[(self.j >> i) & 1 for i in range(8)])

	def test_fiter_type(self):
		self.assertRaises(TypeError, fiter, [])

	def test_fslice(self):
		sl = slice(1, None, 2)
		fslice(self.s, sl)
		self.assertEqual(fslice(self.i, sl), 15)
		self.assertEqual(fslice(self.j, sl), 8)
		self.assertEqual(fslice(-1, 9), 1)
		self.assertEqual(fslice(-1, slice(0, 4)), 0b1)
		self.assertEqual(fslice(-7, slice(0, None, 1)), 0b1001)

	def test_fslice_type(self):
		self.assertRaises(TypeError, fslice, [], 3)

	def test_freversed(self):
		freversed(self.s)
		freversed(self.i)
		freversed(self.j)

	def test_freveseed_type(self):
		self.assertRaises(TypeError, freversed, [])
