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
    def packetized_flow_test(self, dut, packets):
        prng = random.Random(42)

        def generator(dut, valid_rand=75):
            for packet in packets:
                for index, data in enumerate(packet["datas"]):
                    yield dut.sink.valid.eq(1)
                    yield dut.sink.first.eq(index == 0)
                    yield dut.sink.last.eq(index == (len(packet["datas"]) - 1))
                    yield dut.sink.data.eq(data)
                    yield dut.sink.tag.eq(packet["tag"])
                    yield
                    while (yield dut.sink.ready) == 0:
                        yield
                    yield dut.sink.valid.eq(0)
                    yield dut.sink.first.eq(0)
                    yield dut.sink.last.eq(0)
                    while prng.randrange(100) < valid_rand:
                        yield

        def checker(dut, ready_rand=75):
            dut.errors = 0
            for packet in packets:
                for index, data in enumerate(packet["datas"]):
                    yield dut.source.ready.eq(0)
                    yield
                    while (yield dut.source.valid) == 0:
                        yield
                    while prng.randrange(100) < ready_rand:
                        yield
                    yield dut.source.ready.eq(1)
                    yield
                    if (yield dut.source.data) != data:
                        dut.errors += 1
                    if (yield dut.source.tag) != packet["tag"]:
                        dut.errors += 1
                    if (yield dut.source.first) != (index == 0):
                        dut.errors += 1
                    if (yield dut.source.last) != (index == (len(packet["datas"]) - 1)):
                        dut.errors += 1
            yield

        run_simulation(dut, [generator(dut), checker(dut)])
        self.assertEqual(dut.errors, 0)

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

    def test_buffer_valid(self):
        dut = Buffer([("data", 8)], pipe_valid=True, pipe_ready=False)
        self.pipe_test(dut)

    def test_buffer_ready(self):
        dut = Buffer([("data", 8)], pipe_valid=False, pipe_ready=True)
        self.pipe_test(dut)

    def test_buffer_valid_ready(self):
        dut = Buffer([("data", 8)], pipe_valid=True, pipe_ready=True)
        self.pipe_test(dut)

    def test_syncfifo_depth0(self):
        packets = [
            {"tag": 0x1, "datas": [0x10, 0x11]},
            {"tag": 0x2, "datas": [0x20]},
            {"tag": 0x3, "datas": [0x30, 0x31, 0x32]},
        ]
        dut = SyncFIFO(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), depth=0)
        self.packetized_flow_test(dut, packets)

    def test_syncfifo_depth1(self):
        packets = [
            {"tag": 0x4, "datas": [0x40]},
            {"tag": 0x5, "datas": [0x50, 0x51]},
            {"tag": 0x6, "datas": [0x60, 0x61, 0x62]},
        ]
        dut = SyncFIFO(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), depth=1)
        self.packetized_flow_test(dut, packets)

    def test_syncfifo_depth4_buffered(self):
        packets = [
            {"tag": 0x7, "datas": [0x70, 0x71, 0x72]},
            {"tag": 0x8, "datas": [0x80]},
            {"tag": 0x9, "datas": [0x90, 0x91]},
        ]
        dut = SyncFIFO(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), depth=4, buffered=True)
        self.packetized_flow_test(dut, packets)

    def test_multiplexer(self):
        dut = Multiplexer(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), n=2)
        received = []

        def generator():
            yield dut.sel.eq(0)
            yield dut.sink0.valid.eq(1)
            yield dut.sink0.first.eq(1)
            yield dut.sink0.last.eq(1)
            yield dut.sink0.data.eq(0x11)
            yield dut.sink0.tag.eq(1)
            yield
            while (yield dut.sink0.ready) == 0:
                yield
            yield dut.sink0.valid.eq(0)
            yield

            yield dut.sel.eq(1)
            yield dut.sink1.valid.eq(1)
            yield dut.sink1.first.eq(1)
            yield dut.sink1.last.eq(1)
            yield dut.sink1.data.eq(0x22)
            yield dut.sink1.tag.eq(2)
            yield
            while (yield dut.sink1.ready) == 0:
                yield
            yield dut.sink1.valid.eq(0)

        def checker():
            yield dut.source.ready.eq(1)
            for _ in range(4):
                if (yield dut.source.valid):
                    received.append((
                        (yield dut.source.data),
                        (yield dut.source.tag),
                        (yield dut.source.first),
                        (yield dut.source.last),
                    ))
                yield

        run_simulation(dut, [generator(), checker()])
        self.assertEqual(received, [
            (0x11, 1, 1, 1),
            (0x22, 2, 1, 1),
        ])

    def test_demultiplexer(self):
        dut = Demultiplexer(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), n=2)
        received0 = []
        received1 = []

        def generator():
            yield dut.sel.eq(0)
            yield dut.sink.valid.eq(1)
            yield dut.sink.first.eq(1)
            yield dut.sink.last.eq(1)
            yield dut.sink.data.eq(0x31)
            yield dut.sink.tag.eq(3)
            yield
            while (yield dut.sink.ready) == 0:
                yield
            yield dut.sink.valid.eq(0)
            yield

            yield dut.sel.eq(1)
            yield dut.sink.valid.eq(1)
            yield dut.sink.first.eq(1)
            yield dut.sink.last.eq(1)
            yield dut.sink.data.eq(0x42)
            yield dut.sink.tag.eq(4)
            yield
            while (yield dut.sink.ready) == 0:
                yield
            yield dut.sink.valid.eq(0)

        def collector(source, received):
            yield source.ready.eq(1)
            for _ in range(4):
                if (yield source.valid):
                    received.append((
                        (yield source.data),
                        (yield source.tag),
                        (yield source.first),
                        (yield source.last),
                    ))
                yield

        run_simulation(dut, [generator(), collector(dut.source0, received0), collector(dut.source1, received1)])
        self.assertEqual(received0, [(0x31, 3, 1, 1)])
        self.assertEqual(received1, [(0x42, 4, 1, 1)])

    def gate_disable_test(self, sink_ready_when_disabled, expected_ready):
        dut = Gate([("data", 8)], sink_ready_when_disabled=sink_ready_when_disabled)
        observations = {}

        def stimulus():
            yield dut.enable.eq(0)
            yield dut.sink.valid.eq(1)
            yield dut.sink.first.eq(1)
            yield dut.sink.last.eq(1)
            yield dut.sink.data.eq(0x55)
            yield dut.source.ready.eq(1)
            yield
            observations["disabled_ready"] = (yield dut.sink.ready)
            observations["disabled_valid"] = (yield dut.source.valid)

            yield dut.enable.eq(1)
            yield
            observations["enabled_ready"] = (yield dut.sink.ready)
            observations["enabled_valid"] = (yield dut.source.valid)
            observations["enabled_data"] = (yield dut.source.data)

        run_simulation(dut, stimulus())
        self.assertEqual(observations["disabled_ready"], expected_ready)
        self.assertEqual(observations["disabled_valid"], 0)
        self.assertEqual(observations["enabled_ready"], 1)
        self.assertEqual(observations["enabled_valid"], 1)
        self.assertEqual(observations["enabled_data"], 0x55)

    def test_gate_disable_backpressure(self):
        self.gate_disable_test(sink_ready_when_disabled=False, expected_ready=0)

    def test_gate_disable_absorb(self):
        self.gate_disable_test(sink_ready_when_disabled=True, expected_ready=1)

    def test_delay(self):
        dut = Delay(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), n=3)
        accepted_cycle = None
        output_cycles = []
        received = []

        def generator():
            nonlocal accepted_cycle
            cycle = 0
            yield dut.sink.valid.eq(1)
            yield dut.sink.first.eq(1)
            yield dut.sink.last.eq(0)
            yield dut.sink.data.eq(0x60)
            yield dut.sink.tag.eq(6)
            while True:
                if (yield dut.sink.ready):
                    accepted_cycle = cycle
                    break
                cycle += 1
                yield
            yield
            cycle += 1
            yield dut.sink.first.eq(0)
            yield dut.sink.last.eq(1)
            yield dut.sink.data.eq(0x61)
            while (yield dut.sink.ready) == 0:
                cycle += 1
                yield
            yield
            yield dut.sink.valid.eq(0)
            yield dut.sink.last.eq(0)

        def checker():
            yield dut.source.ready.eq(1)
            for cycle in range(12):
                if (yield dut.source.valid):
                    output_cycles.append(cycle)
                    received.append((
                        (yield dut.source.data),
                        (yield dut.source.tag),
                        (yield dut.source.first),
                        (yield dut.source.last),
                    ))
                yield

        run_simulation(dut, [generator(), checker()])
        self.assertEqual(received, [
            (0x60, 6, 1, 0),
            (0x61, 6, 0, 1),
        ])
        self.assertIsNotNone(accepted_cycle)
        self.assertEqual(output_cycles[0] - accepted_cycle, 4)
