#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import random

from migen import *

from litex.soc.interconnect.stream import *
#from litex.soc.interconnect.packet import *

def raw_description(dw):
    payload_layout = [
        ("data", dw),
        ("last_be", dw//8),
        ("error", dw//8)
    ]
    return EndpointDescription(payload_layout)


class Packet:
    def __init__(self, datas, last_be=0):
        self.datas  = datas
        self.last_be = last_be


class LastBE(Module):
    def __init__(self, description):
        self.sink   = sink = Endpoint(description)
        self.source = source = Endpoint(description)

        # # #
        if hasattr(self.sink, "last_be"):
            self.submodules.fsm = fsm = FSM(reset_state="COPY")
            fsm.act("COPY",
                sink.connect(source, omit=["last"]),
                If(sink.last_be,
                    source.last.eq(1),
                    If(sink.valid & sink.ready & ~sink.last,
                        NextState("WAIT-LAST")
                    )
                )
            )
            fsm.act("WAIT-LAST",
                sink.ready.eq(1),
                If(sink.valid & sink.last,
                    NextState("COPY")
                )
            )
        else:
            self.comb += self.sink.connect(self.source)


class TestStrideConverter(unittest.TestCase):

    def bytes_to_packet(self, data_bytes, dw):
        bytes_per_word = dw // 8
        data_list = data_bytes.copy()
        number_of_last_valid_bytes = len(data_list) % bytes_per_word
        if number_of_last_valid_bytes:
            data_list += [0] * (bytes_per_word - number_of_last_valid_bytes)
            last_be = 2**(number_of_last_valid_bytes - 1) # little endian
        else:
            last_be = 2**(dw // 8 - 1)
        datas = [0 for _ in range(len(data_list) // bytes_per_word)]
        for i, item in enumerate(data_list):
            word_index = i // bytes_per_word
            byte_index = i%bytes_per_word
            if byte_index:
                datas[word_index] += int(item << (8 * byte_index))
            else:
                datas[word_index] = item
        return Packet(datas, last_be)

    def get_last_be_mask(self, val):
        assert val > 0
        byte_mask = (val << 1) - 1
        mask=0
        while byte_mask & 0x1:
            mask = (mask << 8) | 0xFF
            byte_mask = byte_mask >> 1
        assert byte_mask == 0
        return mask
    
    def hexlist(self, values):
        return [hex(item) for item in values]

    def stride_convert_test(self, dw, dw_out):
        prng = random.Random(42)
        # Prepare packets
        npackets = 8
        packets  = []
        packets_ref = []
        for n in range(npackets):
            data_bytes = [prng.randrange(2**8) for _ in range(prng.randrange(2**7))]
            packets.append(self.bytes_to_packet(data_bytes, dw))
            packets_ref.append(self.bytes_to_packet(data_bytes, dw_out))

        def generator(dut, valid_rand=50):
            # Send packets
            for packet in packets:
                yield
                for n, data in enumerate(packet.datas):
                    yield dut.sink.valid.eq(1)
                    if n == (len(packet.datas) - 1):
                        yield dut.sink.last.eq(1)
                        yield dut.sink.last_be.eq(packet.last_be)
                        yield dut.sink.error.eq(0xF)
                    else:
                        yield dut.sink.last.eq(0)
                        yield dut.sink.last_be.eq(0)
                        yield dut.sink.error.eq(0x0)
                    yield dut.sink.data.eq(data)
                    yield
                    while (yield dut.sink.ready) == 0:
                        yield
                    yield dut.sink.valid.eq(0)
                    yield dut.sink.last.eq(0)
                    while prng.randrange(100) < valid_rand:
                        yield

        def checker(dut, ready_rand=50):
            dut.data_errors    = 0
            dut.last_errors    = 0
            dut.last_be_errors = 0
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
                    if (yield dut.source.last) and dw_out > 8:
                        last_be_mask = self.get_last_be_mask((yield dut.source.last_be))
                    else:
                        last_be_mask = 2**dw_out - 1

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
                        print((yield dut.source.last_be), packet.last_be)
                        yield dut.checker_flag.eq(1); yield; return
                yield dut.source.ready.eq(0)
                yield
                packet_counter += 1
            yield

        class DUT(Module):
            def __init__(self):
                self.checker_flag = Signal()
                converter = StrideConverter(raw_description(dw), raw_description(dw_out), reverse=False)
                lastbe = LastBE(raw_description(dw_out))
                self.submodules += [converter, lastbe]
                self.comb += converter.source.connect(lastbe.sink)
                self.sink, self.source = converter.sink, lastbe.source

        dut = DUT()
        run_simulation(dut, [generator(dut), checker(dut)], vcd_name="wave_test_stride_converter.vcd")
        self.assertEqual(dut.data_errors,    0)
        self.assertEqual(dut.last_errors,    0)
        self.assertEqual(dut.last_be_errors, 0)

    def test_8bit_to_32bit(self):
        self.stride_convert_test(dw=8, dw_out=32)

    def test_32bit_to_16_bit(self):
        self.stride_convert_test(dw=32, dw_out=16)

    def test_24bit_to_8_bit(self):
        self.stride_convert_test(dw=24, dw_out=8)

    def test_8bit_to_24_bit(self):
        self.stride_convert_test(dw=8, dw_out=24)
