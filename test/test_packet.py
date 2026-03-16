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

def packet_description_with_error(dw):
    param_layout = packet_header.get_layout() + [("error", 1)]
    return EndpointDescription([("data", dw)], param_layout)

def raw_description_with_error(dw):
    return EndpointDescription([("data", dw)], [("error", 1)])

class Packet:
    def __init__(self, header, datas):
        self.header = header
        self.datas  = datas


class TestPacket(unittest.TestCase):
    def test_header_get_field_width_mismatch(self):
        header = Header(
            fields={"field_8b": HeaderField(0, 0, 16)},
            length=2,
            swap_field_bytes=False,
        )
        obj = Record([("field_8b", 8)])
        with self.assertRaises(ValueError):
            header.get_field(obj, "field_8b", 16)

    def test_header_encode_decode_no_swap(self):
        header = Header(
            fields={
                "field_8b":  HeaderField(0, 0, 8),
                "field_16b": HeaderField(1, 0, 16),
            },
            length=3,
            swap_field_bytes=False,
        )

        class EncodedHeader(Module):
            def __init__(self):
                self.obj = Record(header.get_layout())
                self.signal = Signal(header.length*8)
                self.comb += header.encode(self.obj, self.signal)

        class DecodedHeader(Module):
            def __init__(self):
                self.obj = Record(header.get_layout())
                self.signal = Signal(header.length*8)
                self.comb += header.decode(self.signal, self.obj)

        encoder = EncodedHeader()
        decoder = DecodedHeader()
        observations = {}

        def encode_stimulus():
            yield encoder.obj.field_8b.eq(0x12)
            yield encoder.obj.field_16b.eq(0x3456)
            yield
            observations["encoded"] = (yield encoder.signal)

        def decode_stimulus():
            yield decoder.signal.eq(0x345612)
            yield
            observations["decoded_8b"] = (yield decoder.obj.field_8b)
            observations["decoded_16b"] = (yield decoder.obj.field_16b)

        run_simulation(encoder, encode_stimulus())
        run_simulation(decoder, decode_stimulus())
        self.assertEqual(observations["encoded"], 0x345612)
        self.assertEqual(observations["decoded_8b"], 0x12)
        self.assertEqual(observations["decoded_16b"], 0x3456)

    def test_header_encode_decode_split_fields_with_swap(self):
        header = Header(
            fields={
                "field_lsb": HeaderField(0, 0, 16),
                "field_msb": HeaderField(2, 0, 16),
            },
            length=4,
            swap_field_bytes=True,
        )

        class EncodedHeader(Module):
            def __init__(self):
                self.obj = Record([("field", 32)])
                self.signal = Signal(header.length*8)
                self.comb += header.encode(self.obj, self.signal)

        class DecodedHeader(Module):
            def __init__(self):
                self.obj = Record([("field", 32)])
                self.signal = Signal(header.length*8)
                self.comb += header.decode(self.signal, self.obj)

        encoder = EncodedHeader()
        decoder = DecodedHeader()
        observations = {}

        def encode_stimulus():
            yield encoder.obj.field.eq(0x11223344)
            yield
            observations["encoded"] = (yield encoder.signal)

        def decode_stimulus():
            yield decoder.signal.eq(0x22114433)
            yield
            observations["decoded"] = (yield decoder.obj.field)

        run_simulation(encoder, encode_stimulus())
        run_simulation(decoder, decode_stimulus())
        self.assertEqual(observations["encoded"], 0x22114433)
        self.assertEqual(observations["decoded"], 0x11223344)

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
        generator_prng = random.Random(42)
        checker_prng   = random.Random(42)

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
                    while generator_prng.randrange(100) < valid_rand:
                        yield

        def checker(dut, ready_rand=60):
            dut.errors = 0
            for packet in packets:
                for index, data in enumerate(packet["datas"]):
                    yield dut.source.ready.eq(0)
                    yield
                    while (yield dut.source.valid) == 0:
                        yield
                    while checker_prng.randrange(100) < ready_rand:
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

    def test_packet_fifo_stress(self):
        prng = random.Random(123)
        layout = EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 8), ("kind", 2)],
        )
        packets = []
        for packet_index in range(24):
            packets.append({
                "tag": packet_index,
                "kind": packet_index % 4,
                "datas": [prng.randrange(256) for _ in range(1 + (packet_index % 5))],
            })
        self.packet_fifo_test(layout, packets, payload_depth=9, param_depth=1, buffered=True)

    def test_packetizer_depacketizer_single_byte_payload_with_error(self):
        packets = [
            {
                "field_8b": 0x12, "field_16b": 0x3456, "field_32b": 0x789abcde,
                "field_64b": 0x0123456789abcdef, "field_128b": 0x112233445566778899aabbccddeeff00,
                "error": 0, "data": 0xab,
            },
            {
                "field_8b": 0x9a, "field_16b": 0xbcde, "field_32b": 0xfedcba98,
                "field_64b": 0x0fedcba987654321, "field_128b": 0xffeeddccbbaa99887766554433221100,
                "error": 1, "data": 0xcd,
            },
        ]

        class DUT(Module):
            def __init__(self):
                packetizer = Packetizer(packet_description_with_error(8), raw_description_with_error(8), packet_header)
                depacketizer = Depacketizer(raw_description_with_error(8), packet_description_with_error(8), packet_header)
                self.submodules += packetizer, depacketizer
                self.comb += packetizer.source.connect(depacketizer.sink)
                self.sink = packetizer.sink
                self.source = depacketizer.source

        dut = DUT()
        received = []

        def generator():
            for packet in packets:
                yield dut.sink.field_8b.eq(packet["field_8b"])
                yield dut.sink.field_16b.eq(packet["field_16b"])
                yield dut.sink.field_32b.eq(packet["field_32b"])
                yield dut.sink.field_64b.eq(packet["field_64b"])
                yield dut.sink.field_128b.eq(packet["field_128b"])
                yield dut.sink.error.eq(packet["error"])
                yield dut.sink.valid.eq(1)
                yield dut.sink.first.eq(1)
                yield dut.sink.last.eq(1)
                yield dut.sink.data.eq(packet["data"])
                yield
                while (yield dut.sink.ready) == 0:
                    yield
                yield dut.sink.valid.eq(0)
                yield dut.sink.first.eq(0)
                yield dut.sink.last.eq(0)
                yield

        def checker():
            yield dut.source.ready.eq(1)
            for _ in range(96):
                if (yield dut.source.valid):
                    received.append({
                        "field_8b":  (yield dut.source.field_8b),
                        "field_16b": (yield dut.source.field_16b),
                        "field_32b": (yield dut.source.field_32b),
                        "field_64b": (yield dut.source.field_64b),
                        "field_128b": (yield dut.source.field_128b),
                        "error":     (yield dut.source.error),
                        "data":      (yield dut.source.data),
                        "first":     (yield dut.source.first),
                        "last":      (yield dut.source.last),
                    })
                    if len(received) == len(packets):
                        break
                yield

        run_simulation(dut, [generator(), checker()])
        self.assertEqual(received, [
            {
                "field_8b": 0x12, "field_16b": 0x3456, "field_32b": 0x789abcde,
                "field_64b": 0x0123456789abcdef, "field_128b": 0x112233445566778899aabbccddeeff00,
                "error": 0, "data": 0xab, "first": 0, "last": 1,
            },
            {
                "field_8b": 0x9a, "field_16b": 0xbcde, "field_32b": 0xfedcba98,
                "field_64b": 0x0fedcba987654321, "field_128b": 0xffeeddccbbaa99887766554433221100,
                "error": 1, "data": 0xcd, "first": 0, "last": 1,
            },
        ])

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

    def test_arbiter_multi_packet_alternation(self):
        layout = EndpointDescription(payload_layout=[("data", 8)], param_layout=[("tag", 4)])

        class DUT(Module):
            def __init__(self):
                self.sink0 = Endpoint(layout)
                self.sink1 = Endpoint(layout)
                self.source = Endpoint(layout)
                self.submodules.arbiter = Arbiter([self.sink0, self.sink1], self.source)

        dut = DUT()
        received_tags = []

        def packet_sender(sink, tag, base):
            for packet_index in range(2):
                for beat in range(2):
                    yield sink.tag.eq(tag)
                    yield sink.valid.eq(1)
                    yield sink.first.eq(beat == 0)
                    yield sink.last.eq(beat == 1)
                    yield sink.data.eq(base + packet_index*0x10 + beat)
                    yield
                    while (yield sink.ready) == 0:
                        yield
                yield sink.valid.eq(0)
                yield sink.first.eq(0)
                yield sink.last.eq(0)
                yield

        def checker():
            yield dut.source.ready.eq(1)
            for _ in range(16):
                if (yield dut.source.valid) and (yield dut.source.last):
                    received_tags.append((yield dut.source.tag))
                yield

        run_simulation(dut, [
            packet_sender(dut.sink0, tag=0, base=0x40),
            packet_sender(dut.sink1, tag=1, base=0x80),
            checker(),
        ])
        self.assertEqual(received_tags, [0, 1, 0, 1])

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

    def test_dispatcher_invalid_sel_drops_packet(self):
        layout = EndpointDescription(payload_layout=[("data", 8)], param_layout=[("tag", 4)])

        class DUT(Module):
            def __init__(self):
                self.sink = Endpoint(layout)
                self.source0 = Endpoint(layout)
                self.source1 = Endpoint(layout)
                self.source2 = Endpoint(layout)
                self.submodules.dispatcher = Dispatcher(self.sink, [self.source0, self.source1, self.source2])

        dut = DUT()
        observations = {}

        def stimulus():
            yield dut.dispatcher.sel.eq(3)
            yield dut.sink.valid.eq(1)
            yield dut.sink.first.eq(1)
            yield dut.sink.last.eq(1)
            yield dut.sink.data.eq(0x55)
            yield dut.sink.tag.eq(5)
            yield dut.source0.ready.eq(1)
            yield dut.source1.ready.eq(1)
            yield dut.source2.ready.eq(1)
            yield
            observations["sink_ready"] = (yield dut.sink.ready)
            observations["source0_valid"] = (yield dut.source0.valid)
            observations["source1_valid"] = (yield dut.source1.valid)
            observations["source2_valid"] = (yield dut.source2.valid)

        run_simulation(dut, stimulus())
        self.assertEqual(observations, {
            "sink_ready": 1,
            "source0_valid": 0,
            "source1_valid": 0,
            "source2_valid": 0,
        })
