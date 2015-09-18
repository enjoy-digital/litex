import unittest

from migen import *
from migen.genlib.divider import Divider
from migen.test.support import SimCase


class DivisionCase(SimCase, unittest.TestCase):
    class TestBench(Module):
        def __init__(self):
            self.submodules.dut = Divider(4)

    def test_division(self):
        def gen():
            for dividend in range(16):
                for divisor in range(1, 16):
                    yield self.tb.dut.dividend_i, dividend
                    yield self.tb.dut.divisor_i, divisor
                    yield self.tb.dut.start_i, 1
                    yield
                    yield self.tb.dut.start_i, 0
                    while not (yield self.tb.dut.ready_o):
                        yield
                    self.assertEqual((yield self.tb.dut.quotient_o), dividend//divisor)
                    self.assertEqual((yield self.tb.dut.remainder_o), dividend%divisor)
        self.run_with(gen())
