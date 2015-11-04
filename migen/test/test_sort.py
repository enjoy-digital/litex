import unittest
from random import randrange

from migen import *
from migen.genlib.sort import *

from migen.test.support import SimCase


class BitonicCase(SimCase, unittest.TestCase):
    class TestBench(Module):
        def __init__(self):
            self.submodules.dut = BitonicSort(8, 4, ascending=True)

    def test_sizes(self):
        self.assertEqual(len(self.tb.dut.i), 8)
        self.assertEqual(len(self.tb.dut.o), 8)
        for i in range(8):
            self.assertEqual(len(self.tb.dut.i[i]), 4)
            self.assertEqual(len(self.tb.dut.o[i]), 4)

    def test_sort(self):
        def gen():
            for repeat in range(20):
                for i in self.tb.dut.i:
                    yield i.eq(randrange(1<<len(i)))
                yield
                self.assertEqual(sorted((yield self.tb.dut.i)),
                                 (yield self.tb.dut.o))
        self.run_with(gen())
