#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Unit tests for stream.PipeValid / stream.PipeReady / stream.Buffer — small timing-path
cuts that had no dedicated coverage."""

import unittest
import random

from migen import *

from litex.soc.interconnect import stream


LAYOUT = [("data", 8)]


def _producer(endpoint, values):
    for v in values:
        yield endpoint.valid.eq(1)
        yield endpoint.data.eq(v)
        yield
        while not (yield endpoint.ready):
            yield
    yield endpoint.valid.eq(0)


def _consumer(endpoint, n, captured, ready_prob=100, seed=0):
    prng = random.Random(seed)
    while len(captured) < n:
        while prng.randint(0, 99) >= ready_prob:
            yield endpoint.ready.eq(0)
            yield
        yield endpoint.ready.eq(1)
        yield
        if (yield endpoint.valid) and (yield endpoint.ready):
            captured.append((yield endpoint.data))


class TestPipeValid(unittest.TestCase):
    def test_values_pass_in_order(self):
        dut = stream.PipeValid(LAYOUT)
        values   = list(range(1, 33))
        captured = []

        def gen():
            yield from _producer(dut.sink, values)

        def consume():
            yield from _consumer(dut.source, len(values), captured)

        run_simulation(dut, [gen(), consume()])
        self.assertEqual(captured, values)

    def test_with_backpressure(self):
        dut = stream.PipeValid(LAYOUT)
        values   = list(range(1, 65))
        captured = []

        def gen():
            yield from _producer(dut.sink, values)

        def consume():
            yield from _consumer(dut.source, len(values), captured, ready_prob=60, seed=1)

        run_simulation(dut, [gen(), consume()])
        self.assertEqual(captured, values)


class TestPipeReady(unittest.TestCase):
    def test_values_pass_in_order(self):
        dut = stream.PipeReady(LAYOUT)
        values   = list(range(1, 33))
        captured = []

        def gen():
            yield from _producer(dut.sink, values)

        def consume():
            yield from _consumer(dut.source, len(values), captured)

        run_simulation(dut, [gen(), consume()])
        self.assertEqual(captured, values)


class TestBuffer(unittest.TestCase):
    def test_default_pipes_valid(self):
        # Default Buffer (pipe_valid=True, pipe_ready=False): end-to-end transparent.
        dut = stream.Buffer(LAYOUT)
        values   = list(range(1, 17))
        captured = []

        def gen():
            yield from _producer(dut.sink, values)

        def consume():
            yield from _consumer(dut.source, len(values), captured, ready_prob=70, seed=2)

        run_simulation(dut, [gen(), consume()])
        self.assertEqual(captured, values)

    def test_both_pipes(self):
        dut = stream.Buffer(LAYOUT, pipe_valid=True, pipe_ready=True)
        values   = list(range(1, 33))
        captured = []

        def gen():
            yield from _producer(dut.sink, values)

        def consume():
            yield from _consumer(dut.source, len(values), captured, ready_prob=70, seed=3)

        run_simulation(dut, [gen(), consume()])
        self.assertEqual(captured, values)


if __name__ == "__main__":
    unittest.main()
