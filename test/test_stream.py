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
    def test_endpoint_description_duplicate_field(self):
        description = EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("data", 4)],
        )
        with self.assertRaises(ValueError):
            description.get_full_layout()

    def test_endpoint_description_reserved_field(self):
        description = EndpointDescription(payload_layout=[("valid", 8)])
        with self.assertRaises(ValueError):
            description.get_full_layout()

    def test_get_endpoints(self):
        class DUT(Module):
            def __init__(self):
                self.sink = Endpoint([("data", 8)])
                self.source = Endpoint([("data", 8)])
                self.value = Signal(8)

        dut = DUT()
        endpoints = get_endpoints(dut)
        self.assertEqual(set(endpoints.keys()), {"sink", "source"})

    def test_get_single_ep(self):
        class SingleEP(Module):
            def __init__(self):
                self.source = Endpoint([("data", 8)])

        name, endpoint = get_single_ep(SingleEP(), Endpoint)
        self.assertEqual(name, "source")
        self.assertIsInstance(endpoint, Endpoint)

    def test_get_single_ep_raises_on_multiple(self):
        class MultiEP(Module):
            def __init__(self):
                self.sink = Endpoint([("data", 8)])
                self.source = Endpoint([("data", 8)])

        with self.assertRaises(ValueError):
            get_single_ep(MultiEP(), Endpoint)

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
                yield dut.sink.first.eq((data % 7) == 0)
                yield dut.sink.last.eq((data % 7) == 6)
                yield dut.sink.data.eq(data)
                if hasattr(dut.sink, "tag"):
                    yield dut.sink.tag.eq(data % 16)
                yield
                while (yield dut.sink.ready) == 0:
                    yield
                yield dut.sink.valid.eq(0)
                yield dut.sink.first.eq(0)
                yield dut.sink.last.eq(0)
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
                if ((yield dut.source.first) != ((data % 7) == 0)):
                    dut.errors += 1
                if ((yield dut.source.last) != ((data % 7) == 6)):
                    dut.errors += 1
                if hasattr(dut.source, "tag") and ((yield dut.source.tag) != (data % 16)):
                    dut.errors += 1
            yield
        run_simulation(dut, [generator(dut), checker(dut)])
        self.assertEqual(dut.errors, 0)

    def test_pipe_valid(self):
        dut = PipeValid(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ))
        self.pipe_test(dut)

    def test_pipe_ready(self):
        dut = PipeReady(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ))
        self.pipe_test(dut)

    def test_buffer_valid(self):
        dut = Buffer(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), pipe_valid=True, pipe_ready=False)
        self.pipe_test(dut)

    def test_buffer_ready(self):
        dut = Buffer(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), pipe_valid=False, pipe_ready=True)
        self.pipe_test(dut)

    def test_buffer_valid_ready(self):
        dut = Buffer(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), pipe_valid=True, pipe_ready=True)
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

    def test_multiplexer_invalid_sel_blocks_inputs(self):
        dut = Multiplexer(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), n=3)
        observations = {}

        def stimulus():
            yield dut.source.ready.eq(1)
            yield dut.sel.eq(0)
            yield dut.sink0.valid.eq(1)
            yield dut.sink0.first.eq(1)
            yield dut.sink0.last.eq(1)
            yield dut.sink0.data.eq(0x11)
            yield dut.sink0.tag.eq(1)
            yield
            yield dut.sel.eq(3)
            yield
            observations["source_valid"] = (yield dut.source.valid)
            observations["sink0_ready"] = (yield dut.sink0.ready)
            observations["sink1_ready"] = (yield dut.sink1.ready)
            observations["sink2_ready"] = (yield dut.sink2.ready)

        run_simulation(dut, stimulus())
        self.assertEqual(observations, {
            "source_valid": 0,
            "sink0_ready": 0,
            "sink1_ready": 0,
            "sink2_ready": 0,
        })

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

    def test_demultiplexer_invalid_sel_blocks_input(self):
        dut = Demultiplexer(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), n=3)
        observations = {}

        def stimulus():
            yield dut.source0.ready.eq(1)
            yield dut.source1.ready.eq(1)
            yield dut.source2.ready.eq(1)
            yield dut.sel.eq(0)
            yield dut.sink.valid.eq(1)
            yield dut.sink.first.eq(1)
            yield dut.sink.last.eq(1)
            yield dut.sink.data.eq(0x22)
            yield dut.sink.tag.eq(2)
            yield
            yield dut.sel.eq(3)
            yield
            observations["sink_ready"] = (yield dut.sink.ready)
            observations["source0_valid"] = (yield dut.source0.valid)
            observations["source1_valid"] = (yield dut.source1.valid)
            observations["source2_valid"] = (yield dut.source2.valid)

        run_simulation(dut, stimulus())
        self.assertEqual(observations, {
            "sink_ready": 0,
            "source0_valid": 0,
            "source1_valid": 0,
            "source2_valid": 0,
        })

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

    def test_pack(self):
        dut = Pack(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), n=2)
        received = []

        def generator():
            for index, data in enumerate([0x11, 0x22, 0x33]):
                yield dut.sink.valid.eq(1)
                yield dut.sink.first.eq(index == 0)
                yield dut.sink.last.eq(index == 2)
                yield dut.sink.data.eq(data)
                yield dut.sink.tag.eq(9)
                yield
                while (yield dut.sink.ready) == 0:
                    yield
            yield dut.sink.valid.eq(0)
            yield dut.sink.last.eq(0)

        def checker():
            yield dut.source.ready.eq(1)
            for _ in range(6):
                if (yield dut.source.valid):
                    received.append((
                        (yield dut.source.chunk0.data),
                        (yield dut.source.chunk1.data),
                        (yield dut.source.tag),
                        (yield dut.source.first),
                        (yield dut.source.last),
                    ))
                yield

        run_simulation(dut, [generator(), checker()])
        self.assertEqual(received, [
            (0x11, 0x22, 9, 1, 0),
            (0x33, 0x22, 9, 0, 1),
        ])

    def test_pack_reverse(self):
        dut = Pack(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), n=2, reverse=True)
        received = []

        def generator():
            for index, data in enumerate([0x11, 0x22]):
                yield dut.sink.valid.eq(1)
                yield dut.sink.first.eq(index == 0)
                yield dut.sink.last.eq(index == 1)
                yield dut.sink.data.eq(data)
                yield dut.sink.tag.eq(3)
                yield
                while (yield dut.sink.ready) == 0:
                    yield
            yield dut.sink.valid.eq(0)
            yield dut.sink.last.eq(0)

        def checker():
            yield dut.source.ready.eq(1)
            for _ in range(4):
                if (yield dut.source.valid):
                    received.append((
                        (yield dut.source.chunk0.data),
                        (yield dut.source.chunk1.data),
                        (yield dut.source.tag),
                        (yield dut.source.first),
                        (yield dut.source.last),
                    ))
                yield

        run_simulation(dut, [generator(), checker()])
        self.assertEqual(received, [
            (0x22, 0x11, 3, 1, 1),
        ])

    def test_unpack(self):
        dut = Unpack(2, EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ))
        received = []

        def generator():
            yield dut.sink.valid.eq(1)
            yield dut.sink.first.eq(1)
            yield dut.sink.last.eq(1)
            yield dut.sink.chunk0.data.eq(0x44)
            yield dut.sink.chunk1.data.eq(0x55)
            yield dut.sink.tag.eq(10)
            yield
            while (yield dut.sink.ready) == 0:
                yield
            yield dut.sink.valid.eq(0)

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
            (0x44, 10, 1, 0),
            (0x55, 10, 0, 1),
        ])

    def test_unpack_reverse(self):
        dut = Unpack(2, EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), reverse=True)
        received = []

        def generator():
            yield dut.sink.valid.eq(1)
            yield dut.sink.first.eq(1)
            yield dut.sink.last.eq(1)
            yield dut.sink.chunk0.data.eq(0x44)
            yield dut.sink.chunk1.data.eq(0x55)
            yield dut.sink.tag.eq(7)
            yield
            while (yield dut.sink.ready) == 0:
                yield
            yield dut.sink.valid.eq(0)

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
            (0x55, 7, 1, 0),
            (0x44, 7, 0, 1),
        ])

    def test_converter_up_valid_token_count(self):
        dut = Converter(8, 32, report_valid_token_count=True)
        received = []

        def generator():
            for index, data in enumerate([0x10, 0x11, 0x12]):
                yield dut.sink.valid.eq(1)
                yield dut.sink.first.eq(index == 0)
                yield dut.sink.last.eq(index == 2)
                yield dut.sink.data.eq(data)
                yield
                while (yield dut.sink.ready) == 0:
                    yield
            yield dut.sink.valid.eq(0)
            yield dut.sink.last.eq(0)

        def checker():
            yield dut.source.ready.eq(1)
            for _ in range(6):
                if (yield dut.source.valid):
                    received.append((
                        (yield dut.source.data),
                        (yield dut.source.valid_token_count),
                        (yield dut.source.first),
                        (yield dut.source.last),
                    ))
                yield

        run_simulation(dut, [generator(), checker()])
        self.assertEqual(received, [
            (0x00121110, 3, 1, 1),
        ])

    def test_converter_down(self):
        dut = Converter(32, 8)
        received = []

        def generator():
            yield dut.sink.valid.eq(1)
            yield dut.sink.first.eq(1)
            yield dut.sink.last.eq(1)
            yield dut.sink.data.eq(0x44332211)
            yield
            while (yield dut.sink.ready) == 0:
                yield
            yield dut.sink.valid.eq(0)

        def checker():
            yield dut.source.ready.eq(1)
            for _ in range(6):
                if (yield dut.source.valid):
                    received.append((
                        (yield dut.source.data),
                        (yield dut.source.first),
                        (yield dut.source.last),
                    ))
                yield

        run_simulation(dut, [generator(), checker()])
        self.assertEqual(received, [
            (0x11, 1, 0),
            (0x22, 0, 0),
            (0x33, 0, 0),
            (0x44, 0, 1),
        ])

    def test_converter_up_reverse(self):
        dut = Converter(8, 16, reverse=True, report_valid_token_count=True)
        received = []

        def generator():
            for index, data in enumerate([0x11, 0x22]):
                yield dut.sink.valid.eq(1)
                yield dut.sink.first.eq(index == 0)
                yield dut.sink.last.eq(index == 1)
                yield dut.sink.data.eq(data)
                yield
                while (yield dut.sink.ready) == 0:
                    yield
            yield dut.sink.valid.eq(0)
            yield dut.sink.last.eq(0)

        def checker():
            yield dut.source.ready.eq(1)
            for _ in range(4):
                if (yield dut.source.valid):
                    received.append((
                        (yield dut.source.data),
                        (yield dut.source.valid_token_count),
                        (yield dut.source.first),
                        (yield dut.source.last),
                    ))
                yield

        run_simulation(dut, [generator(), checker()])
        self.assertEqual(received, [
            (0x1122, 2, 1, 1),
        ])

    def test_converter_down_reverse(self):
        dut = Converter(16, 8, reverse=True)
        received = []

        def generator():
            yield dut.sink.valid.eq(1)
            yield dut.sink.first.eq(1)
            yield dut.sink.last.eq(1)
            yield dut.sink.data.eq(0x1122)
            yield
            while (yield dut.sink.ready) == 0:
                yield
            yield dut.sink.valid.eq(0)

        def checker():
            yield dut.source.ready.eq(1)
            for _ in range(4):
                if (yield dut.source.valid):
                    received.append((
                        (yield dut.source.data),
                        (yield dut.source.first),
                        (yield dut.source.last),
                    ))
                yield

        run_simulation(dut, [generator(), checker()])
        self.assertEqual(received, [
            (0x11, 1, 0),
            (0x22, 0, 1),
        ])

    def test_cast_reverse_from(self):
        dut = Cast([("a", 4), ("b", 4)], [("c", 4), ("d", 4)], reverse_from=True)
        observations = {}

        def stimulus():
            yield dut.sink.valid.eq(1)
            yield dut.sink.first.eq(1)
            yield dut.sink.last.eq(1)
            yield dut.sink.a.eq(0x1)
            yield dut.sink.b.eq(0x2)
            yield dut.source.ready.eq(1)
            yield
            observations["valid"] = (yield dut.source.valid)
            observations["first"] = (yield dut.source.first)
            observations["last"] = (yield dut.source.last)
            observations["c"] = (yield dut.source.c)
            observations["d"] = (yield dut.source.d)

        run_simulation(dut, stimulus())
        self.assertEqual(observations, {
            "valid": 1,
            "first": 1,
            "last": 1,
            "c": 0x2,
            "d": 0x1,
        })

    def test_stride_converter_up(self):
        dut = StrideConverter(
            EndpointDescription(payload_layout=[("a", 8), ("b", 8)], param_layout=[("tag", 4)]),
            EndpointDescription(payload_layout=[("a", 16), ("b", 16)], param_layout=[("tag", 4)]),
        )
        received = []

        def generator():
            for index, values in enumerate([(0x11, 0x22), (0x33, 0x44)]):
                yield dut.sink.valid.eq(1)
                yield dut.sink.first.eq(index == 0)
                yield dut.sink.last.eq(index == 1)
                yield dut.sink.a.eq(values[0])
                yield dut.sink.b.eq(values[1])
                yield dut.sink.tag.eq(0xC)
                yield
                while (yield dut.sink.ready) == 0:
                    yield
            yield dut.sink.valid.eq(0)
            yield dut.sink.last.eq(0)

        def checker():
            yield dut.source.ready.eq(1)
            for _ in range(5):
                if (yield dut.source.valid):
                    received.append((
                        (yield dut.source.a),
                        (yield dut.source.b),
                        (yield dut.source.tag),
                        (yield dut.source.first),
                        (yield dut.source.last),
                    ))
                yield

        run_simulation(dut, [generator(), checker()])
        self.assertEqual(received, [
            (0x3311, 0x4422, 0xC, 1, 1),
        ])

    def test_stride_converter_down(self):
        dut = StrideConverter(
            EndpointDescription(payload_layout=[("a", 16), ("b", 16)], param_layout=[("tag", 4)]),
            EndpointDescription(payload_layout=[("a", 8), ("b", 8)], param_layout=[("tag", 4)]),
        )
        received = []

        def generator():
            yield dut.sink.valid.eq(1)
            yield dut.sink.first.eq(1)
            yield dut.sink.last.eq(1)
            yield dut.sink.a.eq(0x3311)
            yield dut.sink.b.eq(0x4422)
            yield dut.sink.tag.eq(0xD)
            yield
            while (yield dut.sink.ready) == 0:
                yield
            yield dut.sink.valid.eq(0)

        def checker():
            yield dut.source.ready.eq(1)
            for _ in range(6):
                if (yield dut.source.valid):
                    received.append((
                        (yield dut.source.a),
                        (yield dut.source.b),
                        (yield dut.source.tag),
                        (yield dut.source.first),
                        (yield dut.source.last),
                    ))
                yield

        run_simulation(dut, [generator(), checker()])
        self.assertEqual(received, [
            (0x11, 0x22, 0xD, 1, 0),
            (0x33, 0x44, 0xD, 0, 1),
        ])

    def test_syncfifo_level(self):
        levels = {"depth0": [], "depth1": [], "depth4": []}

        class DUT(Module):
            def __init__(self):
                self.depth0 = SyncFIFO([("data", 8)], depth=0)
                self.depth1 = SyncFIFO([("data", 8)], depth=1)
                self.depth4 = SyncFIFO([("data", 8)], depth=4)
                self.submodules += self.depth0, self.depth1, self.depth4

        dut = DUT()

        def sample():
            levels["depth0"].append((yield dut.depth0.level))
            levels["depth1"].append((yield dut.depth1.level))
            levels["depth4"].append((yield dut.depth4.level))

        def stimulus():
            yield dut.depth0.source.ready.eq(0)
            yield dut.depth1.source.ready.eq(0)
            yield dut.depth4.source.ready.eq(0)
            yield from sample()

            yield dut.depth0.sink.valid.eq(1)
            yield dut.depth0.sink.data.eq(0x10)
            yield dut.depth1.sink.valid.eq(1)
            yield dut.depth1.sink.data.eq(0x11)
            yield dut.depth4.sink.valid.eq(1)
            yield dut.depth4.sink.data.eq(0x12)
            yield
            yield from sample()

            yield dut.depth0.sink.valid.eq(0)
            yield dut.depth1.sink.valid.eq(0)
            yield dut.depth4.sink.valid.eq(0)
            yield
            yield from sample()

            yield dut.depth1.source.ready.eq(1)
            yield dut.depth4.source.ready.eq(1)
            yield
            yield from sample()

            yield
            yield from sample()

        run_simulation(dut, stimulus())
        self.assertEqual(levels["depth0"], [0, 0, 0, 0, 0])
        self.assertEqual(levels["depth1"], [0, 0, 1, 1, 0])
        self.assertEqual(levels["depth4"], [0, 0, 1, 1, 0])

    def test_clock_domain_crossing_same_domain(self):
        packets = [
            {"tag": 0x1, "datas": [0x10, 0x11]},
            {"tag": 0x2, "datas": [0x20]},
            {"tag": 0x3, "datas": [0x30, 0x31, 0x32]},
        ]
        dut = ClockDomainCrossing(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), cd_from="sys", cd_to="sys", buffered=False)
        self.packetized_flow_test(dut, packets)

    def test_clock_domain_crossing_same_domain_buffered(self):
        packets = [
            {"tag": 0x4, "datas": [0x40]},
            {"tag": 0x5, "datas": [0x50, 0x51]},
            {"tag": 0x6, "datas": [0x60, 0x61, 0x62]},
        ]
        dut = ClockDomainCrossing(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), cd_from="sys", cd_to="sys", buffered=True)
        self.packetized_flow_test(dut, packets)

    def test_clock_domain_crossing_async(self):
        dut = ClockDomainCrossing(EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 4)],
        ), cd_from="write", cd_to="read", depth=8, buffered=True)
        packets = [
            {"tag": 0x1, "datas": [0x10, 0x11]},
            {"tag": 0x2, "datas": [0x20]},
            {"tag": 0x3, "datas": [0x30, 0x31, 0x32]},
        ]
        dut.errors = 0

        def generator():
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
                for _ in range(2):
                    yield

        def checker():
            for packet in packets:
                for index, data in enumerate(packet["datas"]):
                    yield dut.source.ready.eq(1)
                    yield
                    while (yield dut.source.valid) == 0:
                        yield
                    if (yield dut.source.data) != data:
                        dut.errors += 1
                    if (yield dut.source.tag) != packet["tag"]:
                        dut.errors += 1
                    if (yield dut.source.first) != (index == 0):
                        dut.errors += 1
                    if (yield dut.source.last) != (index == (len(packet["datas"]) - 1)):
                        dut.errors += 1
                yield dut.source.ready.eq(0)

        clocks = {
            "write": 10,
            "read": 7,
        }
        generators = {
            "write": [generator()],
            "read":  [checker()],
        }
        run_simulation(dut, generators, clocks)
        self.assertEqual(dut.errors, 0)

    def test_clock_domain_crossing_async_common_reset(self):
        class DUT(Module):
            def __init__(self):
                self.clock_domains.cd_write = ClockDomain("write")
                self.clock_domains.cd_read  = ClockDomain("read")
                self.submodules.cdc = ClockDomainCrossing(EndpointDescription(
                    payload_layout=[("data", 8)],
                    param_layout=[("tag", 4)],
                ), cd_from="write", cd_to="read", depth=8, buffered=True, with_common_rst=True)
                self.sink = self.cdc.sink
                self.source = self.cdc.source

        dut = DUT()
        packets = [
            {"tag": 0x7, "datas": [0x70, 0x71]},
            {"tag": 0x8, "datas": [0x80]},
        ]
        dut.errors = 0

        def generator():
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
                yield

        def checker():
            for packet in packets:
                for index, data in enumerate(packet["datas"]):
                    yield dut.source.ready.eq(1)
                    yield
                    while (yield dut.source.valid) == 0:
                        yield
                    if (yield dut.source.data) != data:
                        dut.errors += 1
                    if (yield dut.source.tag) != packet["tag"]:
                        dut.errors += 1
                    if (yield dut.source.first) != (index == 0):
                        dut.errors += 1
                    if (yield dut.source.last) != (index == (len(packet["datas"]) - 1)):
                        dut.errors += 1
                yield dut.source.ready.eq(0)

        clocks = {
            "write": 10,
            "read":  7,
            f"from{dut.cdc.duid}": 10,
            f"to{dut.cdc.duid}":   7,
        }
        generators = {
            "write": [generator()],
            "read":  [checker()],
        }
        run_simulation(dut, generators, clocks)
        self.assertEqual(dut.errors, 0)

    def test_shifter(self):
        dut = Shifter(8)
        received = []

        def generator():
            yield dut.shift.eq(4)
            for index, data in enumerate([0x12, 0x34, 0x56]):
                yield dut.sink.valid.eq(1)
                yield dut.sink.first.eq(index == 0)
                yield dut.sink.last.eq(index == 2)
                yield dut.sink.data.eq(data)
                yield
                while (yield dut.sink.ready) == 0:
                    yield
            yield dut.sink.valid.eq(0)
            yield dut.sink.first.eq(0)
            yield dut.sink.last.eq(0)

        def checker():
            yield dut.source.ready.eq(1)
            for _ in range(8):
                if (yield dut.source.valid):
                    received.append((
                        (yield dut.source.data),
                        (yield dut.source.first),
                        (yield dut.source.last),
                    ))
                yield

        run_simulation(dut, [generator(), checker()])
        self.assertEqual(received, [
            (0x41, 1, 0),
            (0x63, 0, 0),
            (0x65, 0, 1),
        ])

    def test_monitor(self):
        endpoint = Endpoint([("data", 8)])

        class DUT(Module):
            def __init__(self):
                self.endpoint = endpoint
                self.submodules.monitor = Monitor(
                    endpoint,
                    with_tokens=True,
                    with_overflows=True,
                    with_underflows=True,
                    with_packets=True,
                )

        dut = DUT()
        observations = {}

        def stimulus():
            yield dut.endpoint.valid.eq(1)
            yield dut.endpoint.ready.eq(1)
            yield dut.endpoint.first.eq(1)
            yield dut.endpoint.last.eq(0)
            yield

            yield dut.endpoint.first.eq(0)
            yield dut.endpoint.last.eq(1)
            yield

            yield dut.endpoint.valid.eq(1)
            yield dut.endpoint.ready.eq(0)
            yield dut.endpoint.last.eq(0)
            yield

            yield dut.endpoint.valid.eq(0)
            yield dut.endpoint.ready.eq(1)
            yield

            yield dut.monitor.latch.eq(1)
            yield
            yield dut.monitor.latch.eq(0)
            for _ in range(4):
                yield
            observations["tokens"] = (yield dut.monitor._tokens.status)
            observations["overflows"] = (yield dut.monitor._overflows.status)
            observations["underflows"] = (yield dut.monitor._underflows.status)
            observations["packets"] = (yield dut.monitor._packets.status)

            yield dut.endpoint.ready.eq(0)
            yield
            yield dut.monitor.reset.eq(1)
            yield
            yield dut.monitor.reset.eq(0)
            yield
            yield dut.monitor.latch.eq(1)
            yield
            yield dut.monitor.latch.eq(0)
            for _ in range(4):
                yield
            observations["tokens_after_reset"] = (yield dut.monitor._tokens.status)
            observations["overflows_after_reset"] = (yield dut.monitor._overflows.status)
            observations["underflows_after_reset"] = (yield dut.monitor._underflows.status)
            observations["packets_after_reset"] = (yield dut.monitor._packets.status)

        run_simulation(dut, stimulus())
        self.assertEqual(observations, {
            "tokens": 2,
            "overflows": 1,
            "underflows": 1,
            "packets": 1,
            "tokens_after_reset": 0,
            "overflows_after_reset": 0,
            "underflows_after_reset": 0,
            "packets_after_reset": 0,
        })
