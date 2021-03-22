#
# This file is part of LiteX.
#
# Copyright (c) 2017-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import random

from migen import *

from litex.soc.interconnect.stream import Gearbox


def data_generator(dut, gearbox, datas):
    prng = random.Random(42)
    for i, data in enumerate(datas):
        while prng.randrange(4):
            yield
        yield gearbox.sink.valid.eq(1)
        yield gearbox.sink.data.eq(data)
        yield
        while (yield gearbox.sink.ready) == 0:
            yield
        yield gearbox.sink.valid.eq(0)


def data_checker(dut, gearbox, datas):
        prng = random.Random(42)
        dut.errors = 0
        for i, reference in enumerate(datas):
            yield gearbox.source.ready.eq(1)
            yield
            while (yield gearbox.source.valid) == 0:
                yield
            data =  (yield gearbox.source.data)
            if data != reference:
                dut.errors += 1
            yield gearbox.source.ready.eq(0)
            while prng.randrange(4):
                yield


class GearboxDUT(Module):
    def __init__(self, dw0=20, dw1=32):
        self.submodules.gearbox0 = Gearbox(dw0, dw1)
        self.submodules.gearbox1 = Gearbox(dw1, dw0)
        self.comb += self.gearbox0.source.connect(self.gearbox1.sink)


class TestGearbox(unittest.TestCase):
    def gearbox_test(self, dw0, dw1):
        prng = random.Random(42)
        dut = GearboxDUT(dw0, dw1)
        datas = [prng.randrange(2**dw0) for i in range(128)]
        generators = [
            data_generator(dut, dut.gearbox0, datas),
            data_checker(dut, dut.gearbox1, datas)
        ]
        run_simulation(dut, generators)
        self.assertEqual(dut.errors, 0)

    def test_gearbox_20_32(self):
        self.gearbox_test(20, 32)

    def test_gearbox_10_2(self):
        self.gearbox_test(10, 2)

    def test_gearbox_10_4(self):
        self.gearbox_test(10, 4)
