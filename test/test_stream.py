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
