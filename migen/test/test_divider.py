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
                    with self.subTest(dividend=dividend, divisor=divisor):
                        yield self.tb.dut.dividend_i.eq(dividend)
                        yield self.tb.dut.divisor_i.eq(divisor)
                        yield self.tb.dut.start_i.eq(1)
                        yield
                        yield self.tb.dut.start_i.eq(0)
                        yield
                        while not (yield self.tb.dut.ready_o):
                            yield
                        self.assertEqual((yield self.tb.dut.quotient_o), dividend//divisor)
                        self.assertEqual((yield self.tb.dut.remainder_o), dividend%divisor)
        self.run_with(gen())
