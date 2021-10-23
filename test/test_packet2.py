#
# This file is part of LiteX.
#
# Copyright (c) 2021 Leon Schuermann <leon@is.currently.online>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import random

from migen import *

from litex.soc.interconnect.stream import *
from litex.soc.interconnect.packet import *

from .test_stream2 import StreamPacket, stream_inserter, stream_collector, compare_packets

def mask_last_be(dw, data, last_be):
    masked_data = 0

    for byte in range(dw // 8):
        if 2**byte > last_be:
            break
        masked_data |= data & (0xFF << (byte * 8))

    return masked_data

class TestPacket(unittest.TestCase):
    def loopback_test(self, dw, seed=42, with_last_be=False, debug_print=False):
        # Independent random number generator to ensure we're the
        # stream_inserter and stream_collectors still have
        # reproducible behavior independent of the headers
        prng = random.Random(seed + 5)

        # Generate a random number of differently sized header fields
        nheader_fields = prng.randrange(16)
        i = 0
        packet_header_length = 0
        packet_header_fields = {}
        while packet_header_length < dw // 8 or i < nheader_fields:
            # Header field size can be 1, 2, 4, 8, 16 bytes
            field_length = 2**prng.randrange(5)
            packet_header_fields["field{}_{}b".format(i, field_length * 8)] = \
                HeaderField(packet_header_length, 0, field_length * 8)
            packet_header_length += field_length
            i += 1

        packet_header = Header(
            fields           = packet_header_fields,
            length           = packet_header_length,
            swap_field_bytes = bool(prng.getrandbits(1)))

        def packet_description(dw):
            param_layout = packet_header.get_layout()
            payload_layout = [("data", dw)]

            if with_last_be:
                payload_layout += [("last_be", dw // 8)]

            return EndpointDescription(payload_layout, param_layout)

        def raw_description(dw):
            payload_layout = [("data", dw)]

            if with_last_be:
                payload_layout += [("last_be", dw // 8)]

            return EndpointDescription(payload_layout)

        # Prepare packets
        npackets = 32
        packets  = []
        for n in range(npackets):
            header               = {}
            for name, headerfield in packet_header_fields.items():
                header[name] = prng.randrange(2**headerfield.width)
            datas = [prng.randrange(2**8) for _ in range(prng.randrange(dw - 1) + 1)]
            packets.append(StreamPacket(datas, header))

        class DUT(Module):
            def __init__(self):
                self.submodules.packetizer = Packetizer(
                    packet_description(dw),
                    raw_description(dw),
                    packet_header,
                )
                self.submodules.depacketizer = Depacketizer(
                    raw_description(dw),
                    packet_description(dw),
                    packet_header,
                )
                self.comb += self.packetizer.source.connect(self.depacketizer.sink)
                self.sink, self.source = self.packetizer.sink, self.depacketizer.source

        dut = DUT()
        recvd_packets = []
        run_simulation(
            dut,
            [
                stream_inserter(
                    dut.sink,
                    src=packets,
                    seed=seed,
                    debug_print=debug_print,
                    valid_rand=50,
                ),
                stream_collector(
                    dut.source,
                    dest=recvd_packets,
                    expect_npackets=npackets,
                    seed=seed,
                    debug_print=debug_print,
                    ready_rand=50,
                ),
            ],
        )

        # When we don't have a last_be signal, the Packetizer will simply throw
        # away the partial bus word. The Depacketizer will then fill up these
        # values with garbage again. Thus we also have to remove the proper
        # amount of bytes from the sent packets so the comparson will work.
        if not with_last_be and dw != 8:
            # Modulo operation which returns the divisor instead of zero.
            def upmod(a, b):
                return b if a % b == 0 else a % b

            for (packet, recvd_packet) in zip(packets, recvd_packets):
                # How many bytes of the header have to be interleaved with the
                # first data word on the bus.
                header_leftover = packet_header_length % (dw // 8)

                # If the last word of our data would fit together with the
                # header_leftover bytes in a single bus word, all data (plus
                # some trailing garbage) will arrive. Otherwise, some data bytes
                # will be missing.
                if header_leftover != 0 and \
                   header_leftover + upmod(len(packet.data), dw // 8) <= (dw // 8):
                    # The entire data will arrive, plus some trailing
                    # garbage. Remove that.
                    garbage_bytes = -len(packet.data) % (dw // 8)
                    recvd_packet.data = recvd_packet.data[:-garbage_bytes]
                else:
                    # header_leftover bytes in received data have been replaced
                    # with garbage. Remove these bytes from the received and
                    # sent data.
                    recvd_packet.data = recvd_packet.data[:-header_leftover]
                    packet.data = packet.data[:len(recvd_packet.data)]

        self.assertTrue(compare_packets(packets, recvd_packets))

#    def test_8bit_loopback(self):
#        for seed in range(42, 48):
#            with self.subTest(seed=seed):
#                self.loopback_test(dw=8, seed=seed)
#
#    def test_8bit_loopback_last_be(self):
#        for seed in range(42, 48):
#            with self.subTest(seed=seed):
#                self.loopback_test(dw=8, seed=seed, with_last_be=True)
#
#    def test_32bit_loopback(self):
#        for seed in range(42, 48):
#            with self.subTest(seed=seed):
#                self.loopback_test(dw=32, seed=seed)
#
#    def test_32bit_loopback_last_be(self):
#        for seed in range(42, 48):
#            with self.subTest(seed=seed):
#                self.loopback_test(dw=32, seed=seed, with_last_be=True)
#
#    def test_64bit_loopback(self):
#        for seed in range(42, 48):
#            with self.subTest(seed=seed):
#                self.loopback_test(dw=64, seed=seed)
#
#    def test_64bit_loopback_last_be(self):
#        for seed in range(42, 48):
#            with self.subTest(seed=seed):
#                self.loopback_test(dw=64, seed=seed, with_last_be=True)
#
#    def test_128bit_loopback(self):
#        for seed in range(42, 48):
#            with self.subTest(seed=seed):
#                self.loopback_test(dw=128, seed=seed)
#
#    def test_128bit_loopback_last_be(self):
#        for seed in range(42, 48):
#            with self.subTest(seed=seed):
#                self.loopback_test(dw=128, seed=seed, with_last_be=True)
