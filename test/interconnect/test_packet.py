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
            dut.first_errors  = 0
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
                    for field in ["field_8b", "field_16b", "field_32b", "field_64b", "field_128b"]:
                        if (yield getattr(dut.source, field)) != packet.header[field]:
                            dut.header_errors += 1
                    #print("{:x} vs {:x}".format((yield dut.source.data), data))
                    if ((yield dut.source.data) != data):
                        dut.data_errors += 1
                    if ((yield dut.source.first) != (n == 0)):
                        dut.first_errors += 1
                    if ((yield dut.source.last) != (n == (len(packet.datas) - 1))):
                        dut.last_errors += 1
                    yield dut.source.ready.eq(1)
                    yield
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
        self.assertEqual(dut.first_errors,  0)
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

    def test_packet_fifo_param_rollover(self):
        layout = EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 8), ("kind", 2)],
        )
        packets = [
            {"tag": 0x10 + i, "kind": i % 4, "datas": [0x80 + i]}
            for i in range(12)
        ]
        self.packet_fifo_test(layout, packets, payload_depth=4, param_depth=0, buffered=False)

    def test_packet_fifo_alternating_sizes_buffered(self):
        layout = EndpointDescription(
            payload_layout=[("data", 8)],
            param_layout=[("tag", 8), ("kind", 2)],
        )
        packets = []
        for packet_index in range(10):
            packets.append({
                "tag": 0x40 + packet_index,
                "kind": packet_index % 4,
                "datas": [(0x20 * (packet_index + 1) + beat) & 0xff for beat in range(1 + (packet_index % 4))],
            })
        self.packet_fifo_test(layout, packets, payload_depth=5, param_depth=1, buffered=True)

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
                "error": 0, "data": 0xab, "first": 1, "last": 1,
            },
            {
                "field_8b": 0x9a, "field_16b": 0xbcde, "field_32b": 0xfedcba98,
                "field_64b": 0x0fedcba987654321, "field_128b": 0xffeeddccbbaa99887766554433221100,
                "error": 1, "data": 0xcd, "first": 1, "last": 1,
            },
        ])

    def test_packetizer_holds_error_on_buffered_last_beat(self):
        class DUT(Module):
            def __init__(self):
                self.submodules.packetizer = Packetizer(
                    packet_description_with_error(32),
                    raw_description_with_error(32),
                    packet_header,
                )
                self.sink = self.packetizer.sink
                self.source = self.packetizer.source

        dut = DUT()
        observed = []

        def generator():
            yield dut.sink.field_8b.eq(0x12)
            yield dut.sink.field_16b.eq(0x3456)
            yield dut.sink.field_32b.eq(0x789abcde)
            yield dut.sink.field_64b.eq(0x0123456789abcdef)
            yield dut.sink.field_128b.eq(0x112233445566778899aabbccddeeff00)
            yield
            for index, data in enumerate([0x11111111, 0x22222222]):
                yield dut.sink.valid.eq(1)
                yield dut.sink.first.eq(index == 0)
                yield dut.sink.last.eq(index == 1)
                yield dut.sink.error.eq(1)
                yield dut.sink.data.eq(data)
                yield
                while (yield dut.sink.ready) == 0:
                    yield
            yield dut.sink.valid.eq(0)
            yield dut.sink.first.eq(0)
            yield dut.sink.last.eq(0)
            yield dut.sink.error.eq(0)
            for _ in range(16):
                yield

        def checker():
            yield dut.source.ready.eq(1)
            for _ in range(40):
                if (yield dut.source.valid):
                    observed.append({
                        "last":  (yield dut.source.last),
                        "error": (yield dut.source.error),
                    })
                yield

        run_simulation(dut, [generator(), checker()])
        self.assertGreater(len(observed), 0)
        self.assertTrue(any(beat["last"] for beat in observed))
        self.assertTrue(all(beat["error"] == 1 for beat in observed))

    def test_packetizer_depacketizer_multiword_payload_with_error(self):
        packets = [
            {
                "field_8b": 0x12, "field_16b": 0x3456, "field_32b": 0x789abcde,
                "field_64b": 0x0123456789abcdef, "field_128b": 0x112233445566778899aabbccddeeff00,
                "error": 1, "datas": [0x11111111, 0x22222222],
            },
            {
                "field_8b": 0x9a, "field_16b": 0xbcde, "field_32b": 0xfedcba98,
                "field_64b": 0x0fedcba987654321, "field_128b": 0xffeeddccbbaa99887766554433221100,
                "error": 0, "datas": [0x33333333, 0x44444444, 0x55555555],
            },
        ]

        class DUT(Module):
            def __init__(self):
                packetizer = Packetizer(packet_description_with_error(32), raw_description_with_error(32), packet_header)
                depacketizer = Depacketizer(raw_description_with_error(32), packet_description_with_error(32), packet_header)
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
                yield
                for index, data in enumerate(packet["datas"]):
                    yield dut.sink.valid.eq(1)
                    yield dut.sink.first.eq(index == 0)
                    yield dut.sink.last.eq(index == (len(packet["datas"]) - 1))
                    yield dut.sink.error.eq(packet["error"])
                    yield dut.sink.data.eq(data)
                    yield
                    while (yield dut.sink.ready) == 0:
                        yield
                yield dut.sink.valid.eq(0)
                yield dut.sink.first.eq(0)
                yield dut.sink.last.eq(0)
                yield dut.sink.error.eq(~packet["error"] & 0x1)
                yield

        def checker():
            prng = random.Random(7)
            for packet in packets:
                for index, data in enumerate(packet["datas"]):
                    yield dut.source.ready.eq(0)
                    yield
                    while (yield dut.source.valid) == 0:
                        yield
                    while prng.randrange(100) < 40:
                        yield
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
                    yield dut.source.ready.eq(1)
                    yield

        run_simulation(dut, [generator(), checker()])
        expected = []
        for packet in packets:
            for index, data in enumerate(packet["datas"]):
                expected.append({
                    "field_8b": packet["field_8b"],
                    "field_16b": packet["field_16b"],
                    "field_32b": packet["field_32b"],
                    "field_64b": packet["field_64b"],
                    "field_128b": packet["field_128b"],
                    "error": packet["error"],
                    "data": data,
                    "first": index == 0,
                    "last": index == (len(packet["datas"]) - 1),
                })
        self.assertEqual(received, expected)

    def test_packetizer_sets_first_on_header(self):
        class DUT(Module):
            def __init__(self):
                self.submodules.packetizer = Packetizer(packet_description(32), raw_description(32), packet_header)
                self.sink = self.packetizer.sink
                self.source = self.packetizer.source

        dut = DUT()
        observed = []

        def generator():
            yield dut.source.ready.eq(1)
            yield dut.sink.field_8b.eq(0x12)
            yield dut.sink.field_16b.eq(0x3456)
            yield dut.sink.field_32b.eq(0x789abcde)
            yield dut.sink.field_64b.eq(0x0123456789abcdef)
            yield dut.sink.field_128b.eq(0x112233445566778899aabbccddeeff00)
            for index, data in enumerate([0x11, 0x22]):
                yield dut.sink.valid.eq(1)
                yield dut.sink.first.eq(index == 0)
                yield dut.sink.last.eq(index == 1)
                yield dut.sink.data.eq(data)
                yield
                while (yield dut.sink.ready) == 0:
                    if (yield dut.source.valid):
                        observed.append(((yield dut.source.first), (yield dut.source.last)))
                    yield
            yield dut.sink.valid.eq(0)
            for _ in range(12):
                if (yield dut.source.valid):
                    observed.append(((yield dut.source.first), (yield dut.source.last)))
                yield

        run_simulation(dut, generator())
        self.assertGreater(len(observed), 0)
        self.assertEqual(observed[0][0], 1)
        self.assertTrue(all(first == 0 for first, _ in observed[1:]))

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

    def test_dispatcher_holds_sel_before_first_handshake(self):
        layout = EndpointDescription(payload_layout=[("data", 8)], param_layout=[("tag", 4)])

        class DUT(Module):
            def __init__(self):
                self.sink = Endpoint(layout)
                self.source0 = Endpoint(layout)
                self.source1 = Endpoint(layout)
                self.submodules.dispatcher = Dispatcher(self.sink, [self.source0, self.source1])

        dut = DUT()
        observations = {}

        def stimulus():
            yield dut.source0.ready.eq(0)
            yield dut.source1.ready.eq(0)
            yield dut.dispatcher.sel.eq(0)
            yield dut.sink.valid.eq(1)
            yield dut.sink.first.eq(1)
            yield dut.sink.last.eq(1)
            yield dut.sink.data.eq(0x55)
            yield dut.sink.tag.eq(9)
            yield
            yield dut.dispatcher.sel.eq(1)
            yield
            observations["sink_ready"] = (yield dut.sink.ready)
            observations["source0_valid"] = (yield dut.source0.valid)
            observations["source1_valid"] = (yield dut.source1.valid)

        run_simulation(dut, stimulus())
        self.assertEqual(observations, {
            "sink_ready": 0,
            "source0_valid": 1,
            "source1_valid": 0,
        })

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

# Last Byte-Enable Tests ---------------------------------------------------------------------------

# Byte-level helpers: packets are lists of bytes, driven/collected honoring last_be (one-hot on the
# last valid byte of the last word) when the endpoint carries it.

def bytes_to_words(data, bytes_per_word, fill=0):
    words = []
    for i in range(0, len(data), bytes_per_word):
        chunk = list(data[i:i + bytes_per_word])
        chunk += [fill]*(bytes_per_word - len(chunk))
        words.append(int.from_bytes(bytes(chunk), "little"))
    return words

def last_be_for(length, bytes_per_word):
    return 1 << ((length - 1) % bytes_per_word)

def byte_header(length):
    """Header of `length` 1-byte fields b00..bNN (byte i <-> field b{i:02d}), no byte swapping."""
    fields = {f"b{i:02d}": HeaderField(i, 0, 8) for i in range(length)}
    return Header(fields, length, swap_field_bytes=False)

def stream_insert(sink, packets, prng, valid_rand=50, with_garbage=True, timeout=4000):
    """Drive packets on sink: params dict + "data" bytes (+ optional "error"/"last_be" override)."""
    bytes_per_word = len(sink.data)//8
    has_last_be    = hasattr(sink, "last_be")
    cycles         = 0
    for packet in packets:
        for name, value in packet.get("params", {}).items():
            yield getattr(sink, name).eq(value)
        words = bytes_to_words(packet["data"], bytes_per_word, fill=prng.randrange(256))
        for i, word in enumerate(words):
            last = (i == len(words) - 1)
            # Bubble with changing (don't care) data before the word.
            while prng.randrange(100) < valid_rand:
                if with_garbage:
                    yield sink.data.eq(prng.randrange(2**len(sink.data)))
                    yield sink.last.eq(prng.randrange(2))
                yield sink.valid.eq(0)
                yield
            yield sink.valid.eq(1)
            yield sink.first.eq(i == 0)
            yield sink.last.eq(last)
            yield sink.data.eq(word)
            if hasattr(sink, "error"):
                yield sink.error.eq(packet.get("error", 0) if last else 0)
            if has_last_be:
                last_be = packet.get("last_be", last_be_for(len(packet["data"]), bytes_per_word))
                yield sink.last_be.eq(last_be if last else 0)
            yield
            while not (yield sink.ready):
                yield
                cycles += 1
                assert cycles < timeout, "timeout: sink not ready"
        yield sink.valid.eq(0)
        yield sink.first.eq(0)
        yield sink.last.eq(0)
    yield

def stream_collect(source, beats, nbeats, prng, ready_rand=50, params=[], timeout=4000):
    """Collect nbeats accepted beats from source as dicts (data/first/last/last_be/error/params)."""
    cycles = 0
    while len(beats) < nbeats:
        yield source.ready.eq(int(prng.randrange(100) >= ready_rand))
        yield
        cycles += 1
        assert cycles < timeout, f"timeout after {len(beats)} beats"
        if (yield source.valid) and (yield source.ready):
            beat = {
                "data":  (yield source.data),
                "first": (yield source.first),
                "last":  (yield source.last),
            }
            if hasattr(source, "last_be"):
                beat["last_be"] = (yield source.last_be)
            if hasattr(source, "error"):
                beat["error"] = (yield source.error)
            for name in params:
                beat[name] = (yield getattr(source, name))
            beats.append(beat)
    yield source.ready.eq(0)
    yield

def split_packets(beats):
    packets, current = [], []
    for beat in beats:
        current.append(beat)
        if beat["last"]:
            packets.append(current)
            current = []
    assert current == [], "incomplete packet"
    return packets

def packet_bytes(beats, bytes_per_word, with_last_be=True):
    """Bytes of a collected packet, truncated at last_be of the last beat (0: full word)."""
    data = b""
    for beat in beats:
        word = beat["data"].to_bytes(bytes_per_word, "little")
        if beat["last"] and with_last_be and beat.get("last_be", 0):
            word = word[:beat["last_be"].bit_length()]
        data += word
    return data


class TestPacketLastBE(unittest.TestCase):
    """Packetizer/Depacketizer with last_be: byte-exact packets for any header/payload length."""

    def _run(self, dut, generators):
        run_simulation(dut, generators)

    def _sweep(self, data_width):
        bytes_per_word = data_width//8
        # Header lengths covering every leftover and 1..2 header words, payload lengths covering
        # every last_be position over 1..3 words.
        for header_length in range(bytes_per_word, 3*bytes_per_word):
            for payload_length in range(1, 3*bytes_per_word + 1):
                yield header_length, payload_length

    # Packetizer ----------------------------------------------------------------------------------

    def _packetizer_case(self, data_width, header_length, payload_lengths,
        seed         = 0,
        with_last_be = True,
        errors       = None,
    ):
        bytes_per_word = data_width//8
        header         = byte_header(header_length)
        payload_layout = [("data", data_width), ("error", 1)]
        if with_last_be:
            payload_layout += [("last_be", bytes_per_word)]
        dut = Packetizer(
            sink_description   = EndpointDescription(payload_layout, header.get_layout()),
            source_description = EndpointDescription(payload_layout),
            header             = header,
        )
        prng = random.Random(seed)
        packets  = []
        expected = []
        for n, payload_length in enumerate(payload_lengths):
            header_bytes  = bytes(prng.randrange(256) for _ in range(header_length))
            payload_bytes = bytes(prng.randrange(256) for _ in range(payload_length))
            packets.append({
                "params": {f"b{i:02d}": header_bytes[i] for i in range(header_length)},
                "data":   payload_bytes,
                "error":  errors[n] if errors else 0,
            })
            expected.append(header_bytes + payload_bytes)
        nbeats = 0
        for e in expected:
            if with_last_be:
                nbeats += (len(e) + bytes_per_word - 1)//bytes_per_word
            else:
                # Whole payload words plus an extra word for the wrapped tail when unaligned.
                header_words  = header_length//bytes_per_word
                payload_words = (len(e) - header_length + bytes_per_word - 1)//bytes_per_word
                nbeats += header_words + payload_words + int(header_length % bytes_per_word != 0)
        beats = []
        self._run(dut, [
            stream_insert(dut.sink, packets, random.Random(seed + 1)),
            stream_collect(dut.source, beats, nbeats, random.Random(seed + 2)),
        ])
        received = split_packets(beats)
        self.assertEqual(len(received), len(expected))
        for n, (got, exp) in enumerate(zip(received, expected)):
            msg = f"dw={data_width} header={header_length} payload={payload_lengths[n]} packet={n}"
            self.assertEqual(packet_bytes(got, bytes_per_word, with_last_be)[:len(exp)], exp, msg)
            self.assertEqual([b["first"] for b in got], [1] + [0]*(len(got) - 1), msg)
            if with_last_be:
                self.assertEqual(len(packet_bytes(got, bytes_per_word)), len(exp), msg)
                self.assertEqual([b["last_be"] for b in got[:-1]], [0]*(len(got) - 1), msg)
                self.assertEqual(got[-1]["last_be"], last_be_for(len(exp), bytes_per_word), msg)
            if errors:
                self.assertEqual(got[-1]["error"], errors[n], msg)
        return received

    def test_packetizer_lengths(self):
        for data_width in [16, 32, 64]:
            for header_length, payload_length in self._sweep(data_width):
                lengths = [payload_length, payload_length + 1]
                with self.subTest(dw=data_width, header=header_length, payload=payload_length):
                    self._packetizer_case(data_width, header_length, lengths)

    def test_packetizer_random_stream(self):
        prng = random.Random(7)
        for data_width in [32, 64]:
            bytes_per_word = data_width//8
            for header_length in [bytes_per_word + 1, 2*bytes_per_word - 1, 2*bytes_per_word + 3]:
                lengths = [prng.randrange(1, 6*bytes_per_word) for _ in range(16)]
                with self.subTest(data_width=data_width, header_length=header_length):
                    self._packetizer_case(data_width, header_length, lengths, seed=header_length)

    def test_packetizer_without_last_be(self):
        # Without last_be the header/payload bytes are preserved (whole words, unaligned tail in an
        # extra word).
        for data_width in [32, 64]:
            bytes_per_word = data_width//8
            for header_length in [bytes_per_word, bytes_per_word + 2, 2*bytes_per_word + 1]:
                lengths = [bytes_per_word*n for n in [1, 2, 3, 1]]
                with self.subTest(data_width=data_width, header_length=header_length):
                    self._packetizer_case(data_width, header_length, lengths, with_last_be=False)

    def test_packetizer_error_on_last_beat(self):
        for data_width, header_length in [(32, 5), (64, 14), (64, 8)]:
            with self.subTest(data_width=data_width, header_length=header_length):
                self._packetizer_case(data_width, header_length, [1, 7, 12, 3],
                    errors = [1, 0, 1, 1],
                )

    # Depacketizer --------------------------------------------------------------------------------

    def _depacketizer_case(self, data_width, header_length, payload_lengths,
        seed         = 0,
        with_last_be = True,
        errors       = None,
        valid_rand   = 50,
        ready_rand   = 50,
    ):
        bytes_per_word = data_width//8
        header         = byte_header(header_length)
        payload_layout = [("data", data_width), ("error", 1)]
        if with_last_be:
            payload_layout += [("last_be", bytes_per_word)]
        dut = Depacketizer(
            sink_description   = EndpointDescription(payload_layout),
            source_description = EndpointDescription(payload_layout, header.get_layout()),
            header             = header,
        )
        prng = random.Random(seed)
        packets  = []
        expected = []
        for n, payload_length in enumerate(payload_lengths):
            header_bytes  = bytes(prng.randrange(256) for _ in range(header_length))
            payload_bytes = bytes(prng.randrange(256) for _ in range(payload_length))
            packets.append({
                "data":  header_bytes + payload_bytes,
                "error": errors[n] if errors else 0,
            })
            expected.append((header_bytes, payload_bytes))
        header_leftover = header_length % bytes_per_word
        nbeats = 0
        for _, payload in expected:
            if with_last_be:
                nbeats += (len(payload) + bytes_per_word - 1)//bytes_per_word
            else:
                # Tail of the last sink word dropped, except for a single payload word.
                sink_words = (header_leftover + len(payload) + bytes_per_word - 1)//bytes_per_word
                nbeats += max(sink_words - (1 if header_leftover else 0), 1)
        beats = []
        names = list(header.fields.keys())
        self._run(dut, [
            stream_insert(dut.sink, packets, random.Random(seed + 1), valid_rand=valid_rand),
            stream_collect(dut.source, beats, nbeats, random.Random(seed + 2),
                ready_rand = ready_rand,
                params     = names,
            ),
        ])
        received = split_packets(beats)
        self.assertEqual(len(received), len(expected))
        for n, (got, (header_bytes, payload)) in enumerate(zip(received, expected)):
            msg = f"dw={data_width} header={header_length} payload={len(payload)} packet={n}"
            self.assertEqual([b["first"] for b in got], [1] + [0]*(len(got) - 1), msg)
            for beat in got:
                decoded = bytes(beat[f"b{i:02d}"] for i in range(header_length))
                self.assertEqual(decoded, header_bytes, msg)
            if with_last_be:
                self.assertEqual(packet_bytes(got, bytes_per_word), payload, msg)
                self.assertEqual([b["last_be"] for b in got[:-1]], [0]*(len(got) - 1), msg)
                self.assertEqual(got[-1]["last_be"], last_be_for(len(payload), bytes_per_word), msg)
            else:
                data = packet_bytes(got, bytes_per_word, with_last_be=False)
                self.assertEqual(data[:min(len(data), len(payload))], payload[:len(data)], msg)
            if errors:
                self.assertEqual(got[-1]["error"], errors[n], msg)
        return received

    def test_depacketizer_lengths(self):
        for data_width in [16, 32, 64]:
            for header_length, payload_length in self._sweep(data_width):
                lengths = [payload_length, payload_length + 1]
                with self.subTest(dw=data_width, header=header_length, payload=payload_length):
                    self._depacketizer_case(data_width, header_length, lengths)

    def test_depacketizer_random_stream(self):
        prng = random.Random(11)
        for data_width in [32, 64]:
            bytes_per_word = data_width//8
            for header_length in [bytes_per_word + 1, 2*bytes_per_word - 1, 2*bytes_per_word + 3]:
                lengths = [prng.randrange(1, 6*bytes_per_word) for _ in range(16)]
                with self.subTest(data_width=data_width, header_length=header_length):
                    self._depacketizer_case(data_width, header_length, lengths, seed=header_length)

    def test_depacketizer_back_to_back(self):
        # No bubbles and always ready: the next packet's header is valid on the sink during the
        # extra (flush) source word and must not be consumed.
        for data_width in [32, 64]:
            bytes_per_word = data_width//8
            for header_length in [bytes_per_word + 1, bytes_per_word + 3, 2*bytes_per_word + 1]:
                lengths = [1, 2, bytes_per_word - 1, bytes_per_word, bytes_per_word + 1]
                lengths += [2*bytes_per_word, 1]
                with self.subTest(data_width=data_width, header_length=header_length):
                    self._depacketizer_case(data_width, header_length, lengths,
                        valid_rand = 0,
                        ready_rand = 0,
                    )

    def test_depacketizer_without_last_be(self):
        for data_width in [32, 64]:
            bytes_per_word = data_width//8
            for header_length in [bytes_per_word, bytes_per_word + 2, 2*bytes_per_word + 1]:
                lengths = [bytes_per_word*n for n in [1, 2, 3, 1]]
                with self.subTest(data_width=data_width, header_length=header_length):
                    self._depacketizer_case(data_width, header_length, lengths, with_last_be=False)

    def test_depacketizer_error_on_last_beat(self):
        for data_width, header_length in [(32, 5), (64, 14), (64, 8)]:
            with self.subTest(data_width=data_width, header_length=header_length):
                self._depacketizer_case(data_width, header_length, [1, 7, 12, 3],
                    errors = [1, 0, 1, 1],
                )

    # Legacy last_be / 8-bit ----------------------------------------------------------------------

    def test_last_be_zero_is_full_word(self):
        # A last_be of 0 on the last word (legacy producers) is a full word: for a packet ending on
        # a word boundary the result is the same as with the explicit last_be, and the output
        # last_be is one-hot.
        for data_width, header_length in [(32, 4), (32, 6), (64, 8), (64, 14)]:
            bytes_per_word = data_width//8
            header         = byte_header(header_length)
            payload_layout = [("data", data_width), ("last_be", bytes_per_word)]
            header_bytes   = bytes(range(0x80, 0x80 + header_length))
            params         = {f"b{i:02d}": header_bytes[i] for i in range(header_length)}
            raw_desc       = EndpointDescription(payload_layout)
            packet_desc    = EndpointDescription(payload_layout, header.get_layout())
            # Sink packet ending on a word boundary: payload for the Packetizer, header + payload
            # for the Depacketizer.
            pad = (-header_length) % bytes_per_word
            for cls, sink_desc, source_desc, payload_length in [
                (Packetizer,   packet_desc, raw_desc,    2*bytes_per_word),
                (Depacketizer, raw_desc,    packet_desc, 2*bytes_per_word + pad),
            ]:
                payload = bytes((i + 1) & 0xff for i in range(payload_length))
                data, expected = {
                    Packetizer   : (payload,                header_bytes + payload),
                    Depacketizer : (header_bytes + payload, payload),
                }[cls]
                packet = {"params": params if cls is Packetizer else {}, "data": data}
                packet["last_be"] = 0
                nbeats = (len(expected) + bytes_per_word - 1)//bytes_per_word
                with self.subTest(cls=cls.__name__, dw=data_width, header=header_length):
                    dut   = cls(sink_desc, source_desc, header)
                    beats = []
                    self._run(dut, [
                        stream_insert(dut.sink, [packet], random.Random(1)),
                        stream_collect(dut.source, beats, nbeats, random.Random(2)),
                    ])
                    self.assertEqual(packet_bytes(beats, bytes_per_word), expected)
                    expected_last_be = last_be_for(len(expected), bytes_per_word)
                    self.assertEqual(beats[-1]["last_be"], expected_last_be)

    def test_8bit_last_be(self):
        header         = byte_header(3)
        payload_layout = [("data", 8), ("last_be", 1)]
        payload        = bytes([1, 2, 3, 4, 5])
        header_bytes   = bytes([0xa, 0xb, 0xc])
        params         = {f"b{i:02d}": header_bytes[i] for i in range(3)}
        raw_desc       = EndpointDescription(payload_layout)
        packet_desc    = EndpointDescription(payload_layout, header.get_layout())
        for cls, sink_desc, source_desc, data, expected in [
            (Packetizer,   packet_desc, raw_desc,    payload,               header_bytes + payload),
            (Depacketizer, raw_desc,    packet_desc, header_bytes + payload, payload),
        ]:
            for last_be in [0, 1]:
                packet = {"params": params if cls is Packetizer else {}, "data": data}
                packet["last_be"] = last_be
                with self.subTest(cls=cls.__name__, last_be=last_be):
                    dut   = cls(sink_desc, source_desc, header)
                    beats = []
                    self._run(dut, [
                        stream_insert(dut.sink, [packet], random.Random(1)),
                        stream_collect(dut.source, beats, len(expected), random.Random(2)),
                    ])
                    self.assertEqual(bytes(b["data"] for b in beats), expected)
                    # last_be follows last on 8-bit data paths.
                    self.assertEqual([b["last_be"] for b in beats], [b["last"] for b in beats])

    # Truncated packets ---------------------------------------------------------------------------

    def test_depacketizer_drops_truncated_packets(self):
        # Packets ending within the header (or, unaligned, without payload in the tail of the word
        # holding the header leftover) are dropped and the following packet is intact.
        cases = [(32, 4), (32, 8), (32, 5), (32, 6), (64, 14), (64, 8), (64, 20)]
        for data_width, header_length in cases:
            bytes_per_word  = data_width//8
            header_leftover = header_length % bytes_per_word
            header          = byte_header(header_length)
            payload_layout  = [("data", data_width), ("last_be", bytes_per_word)]
            truncated = list(range(1, header_length + 1))
            if header_leftover == 0:
                # Aligned: only whole (or the last, partial) header words can end a packet.
                truncated = [l for l in truncated if l % bytes_per_word == 0 or l == header_length]
            for length in truncated:
                with self.subTest(data_width=data_width, header=header_length, truncated=length):
                    packet_desc = EndpointDescription(payload_layout, header.get_layout())
                    dut = Depacketizer(
                        sink_description   = EndpointDescription(payload_layout),
                        source_description = packet_desc,
                        header             = header,
                    )
                    header_bytes = bytes(range(0x40, 0x40 + header_length))
                    payload      = bytes(range(1, bytes_per_word + 3))
                    packets = [
                        {"data": bytes((0xf0 + i) & 0xff for i in range(length))}, # Truncated.
                        {"data": header_bytes + payload},                          # Valid.
                    ]
                    beats = []
                    self._run(dut, [
                        stream_insert(dut.sink, packets, random.Random(3), valid_rand=0),
                        stream_collect(dut.source, beats, 2, random.Random(4),
                            params = list(header.fields.keys()),
                        ),
                    ])
                    self.assertEqual(packet_bytes(beats, bytes_per_word), payload)
                    decoded = bytes(beats[0][f"b{i:02d}"] for i in range(header_length))
                    self.assertEqual(decoded, header_bytes)

    # Loopback with random headers ----------------------------------------------------------------

    def test_loopback_random_headers(self):
        # Packetizer -> Depacketizer with random header layouts (1..16-byte fields, optional byte
        # swapping, up to several words) and byte-granular payloads: packets come back byte-exact.
        for data_width in [8, 32, 64, 128]:
            for seed in range(42, 48):
                with self.subTest(data_width=data_width, seed=seed):
                    self._loopback_random_headers(data_width, seed)

    def _loopback_random_headers(self, data_width, seed, npackets=16):
        bytes_per_word = data_width//8
        prng           = random.Random(seed)

        # Random header: 1..16-byte fields, at least one word long.
        fields, header_length, i = {}, 0, 0
        nfields = prng.randrange(1, 12)
        while header_length < bytes_per_word or i < nfields:
            field_length = 2**prng.randrange(5)
            fields[f"field{i:02d}"] = HeaderField(header_length, 0, 8*field_length)
            header_length += field_length
            i += 1
        header = Header(fields, header_length, swap_field_bytes=bool(prng.getrandbits(1)))

        payload_layout = [("data", data_width), ("last_be", bytes_per_word)]
        raw_desc       = EndpointDescription(payload_layout)
        packet_desc    = EndpointDescription(payload_layout, header.get_layout())

        class DUT(Module):
            def __init__(self):
                self.submodules.packetizer   = Packetizer(packet_desc, raw_desc, header)
                self.submodules.depacketizer = Depacketizer(raw_desc, packet_desc, header)
                self.comb += self.packetizer.source.connect(self.depacketizer.sink)
                self.sink, self.source = self.packetizer.sink, self.depacketizer.source

        packets = []
        for _ in range(npackets):
            length = prng.randrange(1, 4*bytes_per_word + 2)
            packets.append({
                "params": {name: prng.randrange(2**field.width) for name, field in fields.items()},
                "data":   bytes(prng.randrange(256) for _ in range(length)),
            })
        nbeats = sum((len(p["data"]) + bytes_per_word - 1)//bytes_per_word for p in packets)

        dut   = DUT()
        beats = []
        self._run(dut, [
            stream_insert(dut.sink, packets, random.Random(seed + 1)),
            stream_collect(dut.source, beats, nbeats, random.Random(seed + 2),
                params = list(fields.keys()),
            ),
        ])
        received = split_packets(beats)
        self.assertEqual(len(received), npackets)
        for sent, got in zip(packets, received):
            self.assertEqual(packet_bytes(got, bytes_per_word), sent["data"])
            self.assertEqual(got[-1]["last_be"], last_be_for(len(sent["data"]), bytes_per_word))
            for beat in got:
                for name, value in sent["params"].items():
                    self.assertEqual(beat[name], value, name)
