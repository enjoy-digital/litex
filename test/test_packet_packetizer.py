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

packet_header_length = 15
packet_header_fields = {
    "field_8b"  : HeaderField(0,  0,   8),
    "field_16b" : HeaderField(1,  0,  16),
    "field_32b" : HeaderField(3,  0,  32),
    "field_64b" : HeaderField(7,  0,  64),
}
packet_header = Header(
    fields           = packet_header_fields,
    length           = packet_header_length,
    swap_field_bytes = True)

def packet_description(dw):
    param_layout = packet_header.get_layout()
    payload_layout = [
        ("data", dw),
        ("last_be", dw//8),
        ("error", dw//8)
    ]
    return EndpointDescription(payload_layout, param_layout)

def raw_description(dw):
    payload_layout = [
        ("data", dw),
        ("last_be", dw//8),
        ("error", dw//8)
    ]
    return EndpointDescription(payload_layout)

class Packet:
    def __init__(self, header, datas, last_be=0):
        self.header = header
        self.datas  = datas
        self.last_be = last_be


class TestPacketizerLastBE(unittest.TestCase):
    def bytes_to_packet(self, header, data_bytes, dw):
        bytes_per_word = dw // 8
        number_of_last_valid_bytes = len(data_bytes) % bytes_per_word
        if number_of_last_valid_bytes:
            data_bytes += [0] * (bytes_per_word - number_of_last_valid_bytes)
            last_be = 2**(number_of_last_valid_bytes - 1) # little endian
        else:
            last_be = 2**(dw // 8 - 1)
        datas = [0 for _ in range(len(data_bytes) // bytes_per_word)]
        for i, item in enumerate(data_bytes):
            word_index = i // bytes_per_word
            byte_index = i%bytes_per_word
            if byte_index:
                datas[word_index] += int(item << (8 * byte_index))
            else:
                datas[word_index] = item
        return Packet(header, datas, last_be)

    def get_last_be_mask(self, val):
        assert val > 0
        byte_mask = (val << 1) - 1
        mask=0
        while byte_mask & 0x1:
            mask = (mask << 8) | 0xFF
            byte_mask = byte_mask >> 1
        assert byte_mask == 0
        return mask

    def packetizer_test(self, dw):
        prng = random.Random(42)
        # Prepare packets
        npackets = 8
        packets  = []
        packets_ref = []
        for n in range(npackets):
            header               = {}
            header["field_8b"]   = 0x11
            header["field_16b"]  = 0x2222
            header["field_32b"]  = 0x33333333
            header["field_64b"]  = 0x4444444444444444

            data_bytes =  [header["field_8b"]]
            data_bytes += list(header["field_16b"].to_bytes(2, byteorder="big"))
            data_bytes += list(header["field_32b"].to_bytes(4, byteorder="big"))
            data_bytes += list(header["field_64b"].to_bytes(8, byteorder="big"))
            payload_bytes = [prng.randrange(2**8) for _ in range(prng.randrange(2**7))]
            data_bytes += payload_bytes

            packets.append(self.bytes_to_packet(header, payload_bytes, dw))
            packets_ref.append(self.bytes_to_packet(header, data_bytes, dw))

        def generator(dut, valid_rand=50):
            # Send packets
            for packet in packets:
                yield
                for field in ["field_8b", "field_16b", "field_32b", "field_64b"]:
                    yield getattr(dut.sink, field).eq(packet.header[field])
                for n, data in enumerate(packet.datas):
                    yield dut.sink.valid.eq(1)
                    if n == (len(packet.datas) - 1):
                        yield dut.sink.last.eq(1)
                        yield dut.sink.last_be.eq(packet.last_be)
                        yield dut.sink.error.eq(~packet.last_be)
                    else:
                        yield dut.sink.last.eq(0)
                        yield dut.sink.last_be.eq(0)
                        yield dut.sink.error.eq(2**(dw//8) - 1)
                    yield dut.sink.data.eq(data)
                    yield
                    while (yield dut.sink.ready) == 0:
                        yield
                    yield dut.sink.valid.eq(0)
                    yield dut.sink.last.eq(0)
                    while prng.randrange(100) < valid_rand:
                        yield

        def checker(dut, ready_rand=50):
            dut.header_errors  = 0
            dut.data_errors    = 0
            dut.last_errors    = 0
            dut.last_be_errors = 0
            dut.last_error_errors = 0
            # Receive and check packets
            packet_counter = 0
            for packet in packets_ref:
                yield dut.checker_flag.eq(0)
                for n, data in enumerate(packet.datas):
                    yield dut.source.ready.eq(0)
                    while prng.randrange(100) < ready_rand:
                        yield
                    yield dut.source.ready.eq(1)
                    yield
                    while not (yield dut.source.valid):
                        yield
                    if (yield dut.source.last) and dw > 8:
                        last_be_mask = self.get_last_be_mask((yield dut.source.last_be))
                    else:
                        last_be_mask = 2**dw - 1

                    if (last_be_mask & (yield dut.source.data) != data):
                        print(f"{packet_counter}, {n}: {hex((yield dut.source.data))} vs {hex(data)}")
                        print(last_be_mask)
                        dut.data_errors += 1
                        yield dut.checker_flag.eq(1); yield; return
                    if ((yield dut.source.last) != (n == (len(packet.datas) - 1))):
                        dut.last_errors += 1
                        yield dut.checker_flag.eq(1); yield; return
                    if (yield dut.source.last) and ((yield dut.source.last_be) != packet.last_be):
                        dut.last_be_errors += 1
                        yield dut.checker_flag.eq(1); yield; return
                    if (yield dut.source.last):
                        if (yield dut.source.last_be) & (yield dut.source.error):
                            dut.last_error_errors += 1
                            yield dut.checker_flag.eq(1); yield; return
                yield dut.source.ready.eq(0)
                yield
                packet_counter += 1
            yield

        class DUT(Module):
            def __init__(self):
                self.checker_flag = Signal()
                packetizer = Packetizer(packet_description(dw), raw_description(dw), packet_header)
                self.submodules += packetizer
                self.sink, self.source = packetizer.sink, packetizer.source

        dut = DUT()
        run_simulation(dut, [generator(dut), checker(dut)], vcd_name="wave_test_packetizer.vcd")
        self.assertEqual(dut.header_errors,  0)
        self.assertEqual(dut.data_errors,    0)
        self.assertEqual(dut.last_errors,    0)
        self.assertEqual(dut.last_be_errors, 0)
        self.assertEqual(dut.last_error_errors, 0)

    def test_8bit_loopback(self):
        self.packetizer_test(dw=8)

    def test_32bit_loopback(self):
        self.packetizer_test(dw=32)

    def test_64bit_loopback(self):
        self.packetizer_test(dw=64)


class TestPacketizerError(unittest.TestCase):
    def bytes_to_packet(self, header, data_bytes, dw):
        bytes_per_word = dw // 8
        number_of_last_valid_bytes = len(data_bytes) % bytes_per_word
        if number_of_last_valid_bytes:
            data_bytes += [0] * (bytes_per_word - number_of_last_valid_bytes)
            last_be = 2**(number_of_last_valid_bytes - 1) # little endian
        else:
            last_be = 2**(dw // 8 - 1)
        datas = [0 for _ in range(len(data_bytes) // bytes_per_word)]
        for i, item in enumerate(data_bytes):
            word_index = i // bytes_per_word
            byte_index = i%bytes_per_word
            if byte_index:
                datas[word_index] += int(item << (8 * byte_index))
            else:
                datas[word_index] = item
        return Packet(header, datas, last_be)

    def get_last_be_mask(self, val):
        assert val > 0
        byte_mask = (val << 1) - 1
        mask=0
        while byte_mask & 0x1:
            mask = (mask << 8) | 0xFF
            byte_mask = byte_mask >> 1
        assert byte_mask == 0
        return mask

    def packetizer_test_error(self, dw):
        prng = random.Random(23)
        # Prepare packets
        npackets = 8
        packets  = []
        packets_ref = []
        for n in range(npackets):
            header               = {}
            header["field_8b"]   = 0x11
            header["field_16b"]  = 0x2222
            header["field_32b"]  = 0x33333333
            header["field_64b"]  = 0x4444444444444444

            data_bytes =  [header["field_8b"]]
            data_bytes += list(header["field_16b"].to_bytes(2, byteorder="big"))
            data_bytes += list(header["field_32b"].to_bytes(4, byteorder="big"))
            data_bytes += list(header["field_64b"].to_bytes(8, byteorder="big"))
            payload_bytes = [prng.randrange(2**8) for _ in range(1, prng.randrange(2**7))]
            data_bytes += payload_bytes

            packets.append(self.bytes_to_packet(header, payload_bytes, dw))
            packets_ref.append(self.bytes_to_packet(header, data_bytes, dw))

        def generator(dut, valid_rand=50):
            # Send packets
            for packet in packets:
                yield
                for field in ["field_8b", "field_16b", "field_32b", "field_64b"]:
                    yield getattr(dut.sink, field).eq(packet.header[field])
                for n, data in enumerate(packet.datas):
                    yield dut.sink.valid.eq(1)
                    if n == (len(packet.datas) - 1):
                        yield dut.sink.last.eq(1)
                        yield dut.sink.last_be.eq(packet.last_be)
                        random_error_flag = prng.randrange(2**(dw//8))
                        yield dut.sink.error.eq(random_error_flag | packet.last_be)
                    else:
                        yield dut.sink.last.eq(0)
                        yield dut.sink.last_be.eq(0)
                        yield dut.sink.error.eq(2**(dw//8) - 1)
                    yield dut.sink.data.eq(data)
                    yield
                    while (yield dut.sink.ready) == 0:
                        yield
                    yield dut.sink.valid.eq(0)
                    yield dut.sink.last.eq(0)
                    while prng.randrange(100) < valid_rand:
                        yield

        def checker(dut, ready_rand=50):
            dut.last_error_errors = 0
            # Receive and check packets
            packet_counter = 0
            for packet in packets_ref:
                yield dut.checker_flag.eq(0)
                for n, data in enumerate(packet.datas):
                    yield dut.source.ready.eq(0)
                    while prng.randrange(100) < ready_rand:
                        yield
                    yield dut.source.ready.eq(1)
                    yield
                    while not (yield dut.source.valid):
                        yield

                    if (yield dut.source.last):
                        if (yield dut.source.last_be) & (yield dut.source.error):
                            dut.last_error_errors += 1
                        else:
                            yield dut.checker_flag.eq(1); yield; return
                yield dut.source.ready.eq(0)
                yield
                packet_counter += 1
            yield

        class DUT(Module):
            def __init__(self):
                self.checker_flag = Signal()
                packetizer = Packetizer(packet_description(dw), raw_description(dw), packet_header)
                self.submodules += packetizer
                self.sink, self.source = packetizer.sink, packetizer.source

        dut = DUT()
        run_simulation(dut, [generator(dut), checker(dut)], vcd_name="wave_test_packetizer_error.vcd")
        self.assertEqual(dut.last_error_errors, npackets)

    def test_8bit_loopback(self):
        self.packetizer_test_error(dw=8)

    def test_32bit_loopback(self):
        self.packetizer_test_error(dw=32)

    def test_64bit_loopback(self):
        self.packetizer_test_error(dw=64)
