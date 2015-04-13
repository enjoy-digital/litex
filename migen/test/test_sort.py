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
        def cb(tb, tbp):
            for i in tb.dut.i:
                tbp.simulator.wr(i, randrange(1<<flen(i)))
            self.assertEqual(sorted(list(tbp.dut.i)), list(tbp.dut.o))
        self.run_with(cb, 20)
