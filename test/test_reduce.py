#
# This file is part of LiteX.
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import random

from migen import *

from litex.gen import *

class TestReduce(unittest.TestCase):
    def reduce_test(self, operator, value, reduced):
        class DUT(Module):
            def __init__(self):
                self.errors = 0
                self.reduced = Reduce(operator, value)

            def checker(self):
                yield
                if (yield self.reduced) != reduced:
                    self.errors += 1

        dut = DUT()
        run_simulation(dut, [dut.checker()])
        self.assertEqual(dut.errors, 0)

    def test_reduced_and(self):
        self.reduce_test(operator="AND", value=Constant(0b00, 2), reduced=0b0)
        self.reduce_test(operator="AND", value=Constant(0b01, 2), reduced=0b0)
        self.reduce_test(operator="AND", value=Constant(0b10, 2), reduced=0b0)
        self.reduce_test(operator="AND", value=Constant(0b11, 2), reduced=0b1)

    def test_reduced_or(self):
        self.reduce_test(operator="OR", value=Constant(0b00, 2), reduced=0b0)
        self.reduce_test(operator="OR", value=Constant(0b01, 2), reduced=0b1)
        self.reduce_test(operator="OR", value=Constant(0b10, 2), reduced=0b1)
        self.reduce_test(operator="OR", value=Constant(0b11, 2), reduced=0b1)

    def test_reduced_nor(self):
        self.reduce_test(operator="NOR", value=Constant(0b00, 2), reduced=0b1)
        self.reduce_test(operator="NOR", value=Constant(0b01, 2), reduced=0b0)
        self.reduce_test(operator="NOR", value=Constant(0b10, 2), reduced=0b0)
        self.reduce_test(operator="NOR", value=Constant(0b11, 2), reduced=0b0)

    def test_reduced_nor(self):
        self.reduce_test(operator="XOR", value=Constant(0b00, 2), reduced=0b0)
        self.reduce_test(operator="XOR", value=Constant(0b01, 2), reduced=0b1)
        self.reduce_test(operator="XOR", value=Constant(0b10, 2), reduced=0b1)
        self.reduce_test(operator="XOR", value=Constant(0b11, 2), reduced=0b0)

    def test_reduced_add(self):
        self.reduce_test(operator="ADD", value=Constant(0b000, 3), reduced=0)
        self.reduce_test(operator="ADD", value=Constant(0b001, 3), reduced=1)
        self.reduce_test(operator="ADD", value=Constant(0b010, 3), reduced=1)
        self.reduce_test(operator="ADD", value=Constant(0b100, 3), reduced=1)
        self.reduce_test(operator="ADD", value=Constant(0b011, 3), reduced=2)
        self.reduce_test(operator="ADD", value=Constant(0b110, 3), reduced=2)
        self.reduce_test(operator="ADD", value=Constant(0b111, 3), reduced=3)
