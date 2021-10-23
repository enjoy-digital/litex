#
# This file is part of LiteX.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import random

from migen import *

from litex.soc.interconnect.stream import *


class TestStream(unittest.TestCase):
    def pipe_test(self, dut):
        prng = random.Random(42)
        def generator(dut, valid_rand=90):
            for data in range(128):
                yield dut.sink.valid.eq(1)
                yield dut.sink.data.eq(data)
                yield
                while (yield dut.sink.ready) == 0:
                    yield
                yield dut.sink.valid.eq(0)
                while prng.randrange(100) < valid_rand:
                    yield

        def checker(dut, ready_rand=90):
            dut.errors = 0
            for data in range(128):
                yield dut.source.ready.eq(0)
                yield
                while (yield dut.source.valid) == 0:
                    yield
                while prng.randrange(100) < ready_rand:
                    yield
                yield dut.source.ready.eq(1)
                yield
                if ((yield dut.source.data) != data):
                    dut.errors += 1
            yield
        run_simulation(dut, [generator(dut), checker(dut)])
        self.assertEqual(dut.errors, 0)

    def test_pipe_valid(self):
        dut = PipeValid([("data", 8)])
        self.pipe_test(dut)

    def test_pipe_ready(self):
        dut = PipeReady([("data", 8)])
        self.pipe_test(dut)
