import unittest

from migen import *


def _same_slices(a, b):
    return a.value is b.value and a.start == b.start and a.stop == b.stop


class SignalSizeCase(unittest.TestCase):
    def setUp(self):
        self.i = C(0xaa)
        self.j = C(-127)
        self.s = Signal((13, True))

    def test_flen(self):
        self.assertEqual(flen(self.s), 13)
        self.assertEqual(flen(self.i), 8)
        self.assertEqual(flen(self.j), 8)

    def test_flen_type(self):
        self.assertRaises(TypeError, flen, [])
