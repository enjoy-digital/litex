import unittest

from migen import *
from migen.genlib.coding import *

from migen.test.support import SimCase


class EncCase(SimCase, unittest.TestCase):
    class TestBench(Module):
        def __init__(self):
            self.submodules.dut = Encoder(8)

    def test_sizes(self):
        self.assertEqual(len(self.tb.dut.i), 8)
        self.assertEqual(len(self.tb.dut.o), 3)
        self.assertEqual(len(self.tb.dut.n), 1)

    def test_run_sequence(self):
        seq = list(range(1<<8))
        def gen():
            for _ in range(256):
                if seq:
                    yield self.tb.dut.i.eq(seq.pop(0))
                if (yield self.tb.dut.n):
                    self.assertNotIn((yield self.tb.dut.i), [1<<i for i in range(8)])
                else:
                    self.assertEqual((yield self.tb.dut.i), 1<<(yield self.tb.dut.o))
                yield
        self.run_with(gen())


class PrioEncCase(SimCase, unittest.TestCase):
    class TestBench(Module):
        def __init__(self):
            self.submodules.dut = PriorityEncoder(8)

    def test_sizes(self):
        self.assertEqual(len(self.tb.dut.i), 8)
        self.assertEqual(len(self.tb.dut.o), 3)
        self.assertEqual(len(self.tb.dut.n), 1)

    def test_run_sequence(self):
        seq = list(range(1<<8))
        def gen():
            for _ in range(256):
                if seq:
                    yield self.tb.dut.i.eq(seq.pop(0))
                i = yield self.tb.dut.i
                if (yield self.tb.dut.n):
                    self.assertEqual(i, 0)
                else:
                    o = yield self.tb.dut.o
                    if o > 0:
                        self.assertEqual(i & 1<<(o - 1), 0)
                    self.assertGreaterEqual(i, 1<<o)
                yield
        self.run_with(gen())


class DecCase(SimCase, unittest.TestCase):
    class TestBench(Module):
        def __init__(self):
            self.submodules.dut = Decoder(8)

    def test_sizes(self):
        self.assertEqual(len(self.tb.dut.i), 3)
        self.assertEqual(len(self.tb.dut.o), 8)
        self.assertEqual(len(self.tb.dut.n), 1)

    def test_run_sequence(self):
        seq = list(range(8*2))
        def gen():
            for _ in range(256):
                if seq:
                    i = seq.pop()
                    yield self.tb.dut.i.eq(i//2)
                    yield self.tb.dut.n.eq(i%2)
                i = yield self.tb.dut.i
                o = yield self.tb.dut.o
                if (yield self.tb.dut.n):
                    self.assertEqual(o, 0)
                else:
                    self.assertEqual(o, 1<<i)
        self.run_with(gen())


class SmallPrioEncCase(SimCase, unittest.TestCase):
    class TestBench(Module):
        def __init__(self):
            self.submodules.dut = PriorityEncoder(1)

    def test_sizes(self):
        self.assertEqual(len(self.tb.dut.i), 1)
        self.assertEqual(len(self.tb.dut.o), 1)
        self.assertEqual(len(self.tb.dut.n), 1)

    def test_run_sequence(self):
        seq = list(range(1))
        def gen():
            for _ in range(5):
                if seq:
                    yield self.tb.dut.i.eq(seq.pop(0))
                i = yield self.tb.dut.i
                if (yield self.tb.dut.n):
                    self.assertEqual(i, 0)
                else:
                    o = yield self.tb.dut.o
                    if o > 0:
                        self.assertEqual(i & 1<<(o - 1), 0)
                    self.assertGreaterEqual(i, 1<<o)
                yield
        self.run_with(gen())
