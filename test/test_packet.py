#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import random

from migen import *

from litex.soc.interconnect.stream import *
from litex.soc.interconnect.packet import *

packet_header_length = 31
packet_header_fields = {
    "field_8b"  : HeaderField(0,  0,   8),
    "field_16b" : HeaderField(1,  0,  16),
    "field_32b" : HeaderField(3,  0,  32),
    "field_64b" : HeaderField(7,  0,  64),
    "field_128b": HeaderField(15, 0, 128),
}
packet_header = Header(
    fields           = packet_header_fields,
    length           = packet_header_length,
    swap_field_bytes = True)

def packet_description(dw):
    param_layout = packet_header.get_layout()
    payload_layout = [("data", dw)]
    return EndpointDescription(payload_layout, param_layout)

def raw_description(dw):
    payload_layout = [("data", dw)]
    return EndpointDescription(payload_layout)

class Packet:
    def __init__(self, header, datas):
        self.header = header
        self.datas  = datas


class TestPacket(unittest.TestCase):
    def test_status_transitions(self):
        endpoint = Endpoint([("data", 8)])

        class DUT(Module):
            def __init__(self):
                self.endpoint = endpoint
                self.submodules.status = Status(endpoint)

        dut = DUT()
        observations = []

        def stimulus(dut):
            observations.append(((yield dut.status.first), (yield dut.status.last), (yield dut.status.ongoing)))

            yield dut.endpoint.valid.eq(1)
            yield dut.endpoint.first.eq(1)
            yield dut.endpoint.last.eq(0)
            yield dut.endpoint.ready.eq(1)
            yield
            observations.append(((yield dut.status.first), (yield dut.status.last), (yield dut.status.ongoing)))

            yield dut.endpoint.first.eq(0)
            yield dut.endpoint.last.eq(1)
            yield
            observations.append(((yield dut.status.first), (yield dut.status.last), (yield dut.status.ongoing)))

            yield dut.endpoint.valid.eq(0)
            yield dut.endpoint.last.eq(0)
            yield
            observations.append(((yield dut.status.first), (yield dut.status.last), (yield dut.status.ongoing)))

        run_simulation(dut, stimulus(dut))
        self.assertEqual(observations, [
            (1, 0, 0),
            (1, 0, 1),
            (0, 1, 0),
            (1, 0, 0),
        ])

    def loopback_test(self, dw):
        prng = random.Random(42)
        # Prepare packets
        npackets = 8
        packets  = []
        for n in range(npackets):
            header               = {}
            header["field_8b"]   = prng.randrange(2**8)
            header["field_16b"]  = prng.randrange(2**16)
            header["field_32b"]  = prng.randrange(2**32)
            header["field_64b"]  = prng.randrange(2**64)
            header["field_128b"] = prng.randrange(2**128)
            datas = [prng.randrange(2**dw) for _ in range(prng.randrange(2**7))]
            packets.append(Packet(header, datas))

        def generator(dut, valid_rand=50):
            # Send packets
            for packet in packets:
                yield dut.sink.field_8b.eq(packet.header["field_8b"])
                yield dut.sink.field_16b.eq(packet.header["field_16b"])
                yield dut.sink.field_32b.eq(packet.header["field_32b"])
                yield dut.sink.field_64b.eq(packet.header["field_64b"])
                yield dut.sink.field_128b.eq(packet.header["field_128b"])
                yield
                for n, data in enumerate(packet.datas):
                    yield dut.sink.valid.eq(1)
                    yield dut.sink.last.eq(n == (len(packet.datas) - 1))
                    yield dut.sink.data.eq(data)
                    yield
                    while (yield dut.sink.ready) == 0:
                        yield
                    yield dut.sink.valid.eq(0)
                    yield dut.sink.last.eq(0)
                    while prng.randrange(100) < valid_rand:
                        yield

        def checker(dut, ready_rand=50):
            dut.header_errors = 0
            dut.data_errors   = 0
            dut.last_errors   = 0
            # Receive and check packets
            for packet in packets:
                for n, data in enumerate(packet.datas):
                    yield dut.source.ready.eq(0)
                    yield
                    while (yield dut.source.valid) == 0:
                        yield
                    while prng.randrange(100) < ready_rand:
                        yield
                    yield dut.source.ready.eq(1)
                    yield
                    for field in ["field_8b", "field_16b", "field_32b", "field_64b", "field_128b"]:
                        if (yield getattr(dut.source, field)) != packet.header[field]:
                            dut.header_errors += 1
                    #print("{:x} vs {:x}".format((yield dut.source.data), data))
                    if ((yield dut.source.data) != data):
                        dut.data_errors += 1
                    if ((yield dut.source.last) != (n == (len(packet.datas) - 1))):
                        dut.last_errors += 1
            yield

        class DUT(Module):
            def __init__(self):
                packetizer   = Packetizer(packet_description(dw), raw_description(dw), packet_header)
                depacketizer = Depacketizer(raw_description(dw), packet_description(dw), packet_header)
                self.submodules += packetizer, depacketizer
                self.comb += packetizer.source.connect(depacketizer.sink)
                self.sink, self.source = packetizer.sink, depacketizer.source

        dut = DUT()
        run_simulation(dut, [generator(dut), checker(dut)])
        self.assertEqual(dut.header_errors, 0)
        self.assertEqual(dut.data_errors,   0)
        self.assertEqual(dut.last_errors,   0)

    def test_8bit_loopback(self):
        self.loopback_test(dw=8)

    def test_32bit_loopback(self):
        self.loopback_test(dw=32)

    def test_64bit_loopback(self):
        self.loopback_test(dw=64)

    def test_128bit_loopback(self):
        self.loopback_test(dw=128)

    def packet_fifo_test(self, layout, packets, payload_depth, param_depth=None, buffered=False):
        prng = random.Random(42)

        def generator(dut, valid_rand=60):
            for packet in packets:
                for index, data in enumerate(packet["datas"]):
                    yield dut.sink.valid.eq(1)
                    yield dut.sink.first.eq(index == 0)
                    yield dut.sink.last.eq(index == (len(packet["datas"]) - 1))
                    yield dut.sink.data.eq(data)
                    if "tag" in packet:
                        yield dut.sink.tag.eq(packet["tag"])
                    if "kind" in packet:
                        yield dut.sink.kind.eq(packet["kind"])
                    yield
                    while (yield dut.sink.ready) == 0:
                        yield
                    yield dut.sink.valid.eq(0)
                    yield dut.sink.first.eq(0)
                    yield dut.sink.last.eq(0)
                    while prng.randrange(100) < valid_rand:
                        yield

        def checker(dut, ready_rand=60):
            dut.errors = 0
            for packet in packets:
                for index, data in enumerate(packet["datas"]):
                    yield dut.source.ready.eq(0)
                    yield
                    while (yield dut.source.valid) == 0:
                        yield
                    while prng.randrange(100) < ready_rand:
                        yield
                    if (yield dut.source.data) != data:
                        dut.errors += 1
                    if (yield dut.source.first) != (index == 0):
                        dut.errors += 1
                    if (yield dut.source.last) != (index == (len(packet["datas"]) - 1)):
                        dut.errors += 1
                    if "tag" in packet and (yield dut.source.tag) != packet["tag"]:
                        dut.errors += 1
                    if "kind" in packet and (yield dut.source.kind) != packet["kind"]:
                        dut.errors += 1
                    yield dut.source.ready.eq(1)
                    yield
            yield

        dut = PacketFIFO(layout, payload_depth=payload_depth, param_depth=param_depth, buffered=buffered)
        run_simulation(dut, [generator(dut), checker(dut)])
        self.assertEqual(dut.errors, 0)

    def test_packet_fifo_with_params(self):
        layout = EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 8), ("kind", 2)],
        )
        packets = [
            {"tag": 0x11, "kind": 0, "datas": [0x10]},
            {"tag": 0x22, "kind": 1, "datas": [0x20, 0x21, 0x22]},
            {"tag": 0x33, "kind": 2, "datas": [0x30, 0x31]},
            {"tag": 0x44, "kind": 3, "datas": [0x40, 0x41, 0x42, 0x43]},
        ]
        self.packet_fifo_test(layout, packets, payload_depth=8, param_depth=2, buffered=True)

    def test_packet_fifo_without_params(self):
        layout = EndpointDescription(payload_layout=[("data", 8)])
        packets = [
            {"datas": [0x01]},
            {"datas": [0x10, 0x11]},
            {"datas": [0x20, 0x21, 0x22]},
        ]
        self.packet_fifo_test(layout, packets, payload_depth=6, buffered=False)

    def test_arbiter_packet_lock(self):
        layout = EndpointDescription(payload_layout=[("data", 8)], param_layout=[("tag", 4)])

        class DUT(Module):
            def __init__(self):
                self.sink0 = Endpoint(layout)
                self.sink1 = Endpoint(layout)
                self.source = Endpoint(layout)
                self.submodules.arbiter = Arbiter([self.sink0, self.sink1], self.source)

        dut = DUT()
        received = []

        def sink0_gen():
            yield dut.sink0.tag.eq(0)
            yield dut.sink0.valid.eq(1)
            yield dut.sink0.first.eq(1)
            yield dut.sink0.data.eq(0x10)
            yield
            while (yield dut.sink0.ready) == 0:
                yield
            yield dut.sink0.first.eq(0)
            yield dut.sink0.last.eq(1)
            yield dut.sink0.data.eq(0x11)
            yield
            while (yield dut.sink0.ready) == 0:
                yield
            yield dut.sink0.valid.eq(0)
            yield dut.sink0.last.eq(0)

        def sink1_gen():
            yield
            yield dut.sink1.tag.eq(1)
            yield dut.sink1.valid.eq(1)
            yield dut.sink1.first.eq(1)
            yield dut.sink1.data.eq(0x20)
            yield
            while (yield dut.sink1.ready) == 0:
                yield
            yield dut.sink1.first.eq(0)
            yield dut.sink1.last.eq(1)
            yield dut.sink1.data.eq(0x21)
            yield
            while (yield dut.sink1.ready) == 0:
                yield
            yield dut.sink1.valid.eq(0)
            yield dut.sink1.last.eq(0)

        def source_check():
            for _ in range(4):
                while (yield dut.source.valid) == 0:
                    yield dut.source.ready.eq(1)
                    yield
                received.append({
                    "data":  (yield dut.source.data),
                    "tag":   (yield dut.source.tag),
                    "first": (yield dut.source.first),
                    "last":  (yield dut.source.last),
                })
                yield dut.source.ready.eq(1)
                yield
            yield dut.source.ready.eq(0)

        run_simulation(dut, [sink0_gen(), sink1_gen(), source_check()])
        self.assertEqual(received, [
            {"data": 0x10, "tag": 0, "first": 1, "last": 0},
            {"data": 0x11, "tag": 0, "first": 0, "last": 1},
            {"data": 0x20, "tag": 1, "first": 1, "last": 0},
            {"data": 0x21, "tag": 1, "first": 0, "last": 1},
        ])

    def dispatcher_hold_sel_test(self, one_hot):
        layout = EndpointDescription(payload_layout=[("data", 8)], param_layout=[("tag", 4)])

        class DUT(Module):
            def __init__(self):
                self.sink = Endpoint(layout)
                self.source0 = Endpoint(layout)
                self.source1 = Endpoint(layout)
                self.submodules.dispatcher = Dispatcher(self.sink, [self.source0, self.source1], one_hot=one_hot)

        dut = DUT()
        received0 = []
        received1 = []

        def generator():
            yield dut.dispatcher.sel.eq(1 if one_hot else 0)
            yield dut.sink.tag.eq(0xA)
            yield dut.sink.valid.eq(1)
            yield dut.sink.first.eq(1)
            yield dut.sink.data.eq(0x30)
            yield
            while (yield dut.sink.ready) == 0:
                yield

            yield dut.dispatcher.sel.eq(2 if one_hot else 1)
            yield dut.sink.first.eq(0)
            yield dut.sink.data.eq(0x31)
            yield
            while (yield dut.sink.ready) == 0:
                yield

            yield dut.sink.last.eq(1)
            yield dut.sink.data.eq(0x32)
            yield
            while (yield dut.sink.ready) == 0:
                yield

            yield dut.sink.valid.eq(0)
            yield dut.sink.last.eq(0)
            yield

            yield dut.sink.tag.eq(0xB)
            yield dut.sink.valid.eq(1)
            yield dut.sink.first.eq(1)
            yield dut.sink.last.eq(1)
            yield dut.sink.data.eq(0x40)
            yield
            while (yield dut.sink.ready) == 0:
                yield
            yield dut.sink.valid.eq(0)
            yield dut.sink.first.eq(0)
            yield dut.sink.last.eq(0)

        def source_collector(source, received):
            yield source.ready.eq(1)
            for _ in range(8):
                if (yield source.valid):
                    received.append({
                        "data":  (yield source.data),
                        "tag":   (yield source.tag),
                        "first": (yield source.first),
                        "last":  (yield source.last),
                    })
                yield

        run_simulation(dut, [generator(), source_collector(dut.source0, received0), source_collector(dut.source1, received1)])
        self.assertEqual(received0, [
            {"data": 0x30, "tag": 0xA, "first": 1, "last": 0},
            {"data": 0x31, "tag": 0xA, "first": 0, "last": 0},
            {"data": 0x32, "tag": 0xA, "first": 0, "last": 1},
        ])
        self.assertEqual(received1, [
            {"data": 0x40, "tag": 0xB, "first": 1, "last": 1},
        ])

    def test_dispatcher_hold_sel(self):
        self.dispatcher_hold_sel_test(one_hot=False)

    def test_dispatcher_hold_sel_one_hot(self):
        self.dispatcher_hold_sel_test(one_hot=True)
