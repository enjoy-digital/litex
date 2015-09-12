import unittest

from migen import *
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
        def cb(tb, tbp):
            if seq:
                tbp.dut.i = seq.pop(0)
            if tbp.dut.n:
                self.assertNotIn(tbp.dut.i, [1<<i for i in range(8)])
            else:
                self.assertEqual(tbp.dut.i, 1<<tbp.dut.o)
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
        def cb(tb, tbp):
            if seq:
                tbp.dut.i = seq.pop(0)
            i = tbp.dut.i
            if tbp.dut.n:
                self.assertEqual(i, 0)
            else:
                o = tbp.dut.o
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
        def cb(tb, tbp):
            if seq:
                i = seq.pop()
                tbp.dut.i = i//2
                tbp.dut.n = i%2
            i = tbp.dut.i
            o = tbp.dut.o
            if tbp.dut.n:
                self.assertEqual(o, 0)
            else:
                self.assertEqual(o, 1<<i)
        self.run_with(cb, 256)


class SmallPrioEncCase(SimCase, unittest.TestCase):
    class TestBench(SimBench):
        def __init__(self):
            self.submodules.dut = PriorityEncoder(1)

    def test_sizes(self):
        self.assertEqual(flen(self.tb.dut.i), 1)
        self.assertEqual(flen(self.tb.dut.o), 1)
        self.assertEqual(flen(self.tb.dut.n), 1)

    def test_run_sequence(self):
        seq = list(range(1))
        def cb(tb, tbp):
            if seq:
                tbp.dut.i = seq.pop(0)
            i = tbp.dut.i
            if tbp.dut.n:
                self.assertEqual(i, 0)
            else:
                o = tbp.dut.o
                if o > 0:
                    self.assertEqual(i & 1<<(o - 1), 0)
                self.assertGreaterEqual(i, 1<<o)
        self.run_with(cb, 5)
