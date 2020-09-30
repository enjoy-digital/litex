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
    def __init__(self):
        self.submodules.gearbox0 = Gearbox(20, 32)
        self.submodules.gearbox1 = Gearbox(32, 20)
        self.comb += self.gearbox0.source.connect(self.gearbox1.sink)


class TestGearbox(unittest.TestCase):
    def test_gearbox(self):
        prng = random.Random(42)
        dut = GearboxDUT()
        datas = [prng.randrange(2**20) for i in range(128)]
        generators = [
            data_generator(dut, dut.gearbox0, datas),
            data_checker(dut, dut.gearbox1, datas)
        ]
        run_simulation(dut, generators)
        self.assertEqual(dut.errors, 0)
