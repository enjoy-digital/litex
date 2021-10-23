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
