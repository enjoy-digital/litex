#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Unit tests for stream.Multiplexer / stream.Demultiplexer / stream.Gate.

These primitives had no dedicated coverage — test_stream.py focuses on the FIFO/pipeline/packet
families. This file fills that gap with focused routing tests.
"""

import unittest

from migen import *

from litex.gen import *

from litex.soc.interconnect import stream


LAYOUT = [("data", 8)]


class TestStreamMultiplexer(unittest.TestCase):
    def test_sel_routes_chosen_sink(self):
        dut = stream.Multiplexer(LAYOUT, n=3)
        captured = []

        def gen():
            yield dut.source.ready.eq(1)
            # Push byte on each of the 3 sinks with matching sel; only the selected one should
            # appear on source.
            for chosen in range(3):
                yield dut.sel.eq(chosen)
                for i in range(3):
                    yield getattr(dut, f"sink{i}").valid.eq(1)
                    yield getattr(dut, f"sink{i}").data.eq(0xA0 + i)
                yield
                yield
                if (yield dut.source.valid):
                    captured.append((chosen, (yield dut.source.data)))
                for i in range(3):
                    yield getattr(dut, f"sink{i}").valid.eq(0)
                yield
        run_simulation(dut, gen())
        # Must have captured exactly the data byte matching the chosen sink each time.
        self.assertEqual(captured, [(0, 0xA0), (1, 0xA1), (2, 0xA2)])

    def test_out_of_range_sel_blocks_all(self):
        dut = stream.Multiplexer(LAYOUT, n=2)

        def gen():
            yield dut.source.ready.eq(1)
            # Drive sink0 valid, but sel out of 0..n-1 range (n=2, so sel=3 is invalid).
            yield dut.sink0.valid.eq(1)
            yield dut.sink0.data.eq(0x42)
            yield dut.sel.eq(3)
            yield
            yield
            self.assertEqual((yield dut.source.valid), 0)
        run_simulation(dut, gen())


class TestStreamDemultiplexer(unittest.TestCase):
    def test_sel_routes_to_chosen_source(self):
        dut = stream.Demultiplexer(LAYOUT, n=3)

        def gen():
            for i in range(3):
                yield getattr(dut, f"source{i}").ready.eq(1)
            results = []
            for chosen in range(3):
                yield dut.sel.eq(chosen)
                yield dut.sink.valid.eq(1)
                yield dut.sink.data.eq(0xB0 + chosen)
                yield
                yield
                # Only the chosen source sees valid.
                for i in range(3):
                    v = (yield getattr(dut, f"source{i}").valid)
                    d = (yield getattr(dut, f"source{i}").data)
                    if v:
                        results.append((chosen, i, d))
                yield dut.sink.valid.eq(0)
                yield
            self.assertEqual(results, [(0, 0, 0xB0), (1, 1, 0xB1), (2, 2, 0xB2)])
        run_simulation(dut, gen())


class TestStreamGate(unittest.TestCase):
    def test_gate_passes_when_enabled(self):
        dut = stream.Gate(LAYOUT)
        captured = []

        def gen():
            yield dut.source.ready.eq(1)
            yield dut.enable.eq(1)
            for byte in [0x11, 0x22, 0x33]:
                yield dut.sink.valid.eq(1)
                yield dut.sink.data.eq(byte)
                yield
                while not (yield dut.sink.ready):
                    yield
                captured.append((yield dut.source.data))
                yield dut.sink.valid.eq(0)
                yield
        run_simulation(dut, gen())
        self.assertEqual(captured, [0x11, 0x22, 0x33])

    def test_gate_drops_when_disabled(self):
        dut = stream.Gate(LAYOUT)

        def gen():
            yield dut.source.ready.eq(1)
            yield dut.enable.eq(0)
            yield dut.sink.valid.eq(1)
            yield dut.sink.data.eq(0xAA)
            for _ in range(16):
                yield
                self.assertEqual((yield dut.source.valid), 0)
        run_simulation(dut, gen())


if __name__ == "__main__":
    unittest.main()
