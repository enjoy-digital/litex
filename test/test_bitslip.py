import unittest
import random

from migen import *
from migen.genlib.misc import BitSlip


class BitSlipModel:
    def __init__(self, data_width, latency):
        self.data_width = data_width
        self.latency = latency

    def simulate(self, bitslip, sequence):
        # prepare sequence for simulation
        s = [0]*self.latency
        for d in sequence:
            s.append(d)
        # simulate bitslip
        r = []
        for i in range(len(s)-1):
            v = (s[i+1] << self.data_width) | s[i]
            v = v >> bitslip
            v &= 2**self.data_width-1
            r.append(v)
        return r


def main_generator(dut):
    dut.o_sequence = []
    yield dut.value.eq(dut.bitslip)
    for i, data in enumerate(dut.i_sequence):
        yield dut.i.eq(data)
        dut.o_sequence.append((yield dut.o))
        yield


class TestBitSlip(unittest.TestCase):
    def bitslip_test(self, data_width, length=128):
        prng = random.Random(42)
        sequence = [prng.randrange(2**data_width) for i in range(length)]

        for i in range(data_width):
            dut = BitSlip(data_width)
            dut.bitslip = i
            dut.i_sequence = sequence
            run_simulation(dut, main_generator(dut))

            model = BitSlipModel(data_width, 4)
            m_sequence = model.simulate(i, sequence)

            self.assertEqual(dut.o_sequence, m_sequence[:len(dut.o_sequence)])

    def test_bitslip_4b(self):
        self.bitslip_test(4)

    def test_bitslip_8b(self):
        self.bitslip_test(8)

    def test_bitslip_16b(self):
        self.bitslip_test(16)

    def test_bitslip_32b(self):
        self.bitslip_test(32)

    def test_bitslip_64b(self):
        self.bitslip_test(64)

    def test_bitslip_128b(self):
        self.bitslip_test(128)
