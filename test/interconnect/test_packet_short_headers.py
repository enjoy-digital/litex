#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.packet import Header, HeaderField, Packetizer
from test.interconnect.test_byte_enable import beats, description, qualified_bytes, simulate


class TestPacketShortHeaders(unittest.TestCase):
    def test_headers_and_empty_payloads(self):
        for width in [8, 32, 64, 128, 256, 512]:
            lanes = width//8
            lengths = sorted({1, max(1, lanes - 1), lanes, lanes + 1, 2*lanes, 3*lanes + 1, 12, 16})
            for header_length in lengths:
                for qualifier in ["be", "keep"]:
                    with self.subTest(width=width, header_length=header_length, qualifier=qualifier):
                        header_data = bytes(i % 256 for i in range(header_length))
                        header = Header({"value" : HeaderField(0, 0, header_length*8)}, header_length, swap_field_bytes=False)
                        dut = Packetizer(description(width, qualifier, header.get_layout()), description(width, qualifier), header)
                        dut.comb += dut.sink.value.eq(int.from_bytes(header_data, "little"))
                        packets = [bytes((i + n) % 256 for i in range(n)) for n in [0, 1, lanes, lanes + 1, 2*lanes - 1, 0]]
                        inputs = [beat for packet in packets for beat in (beats(packet, lanes) if packet else [(0, 0, 1, 1)])]
                        result = simulate(self, dut, inputs, qualifier)
                        expected = [beat for packet in packets for beat in beats(header_data + packet, lanes)]
                        self.assertEqual([(m, f, l) for _, m, f, l in result], [(m, f, l) for _, m, f, l in expected])
                        self.assertEqual(qualified_bytes(result, lanes), qualified_bytes(expected, lanes))

    def test_short_header_errors(self):
        for width in [32, 64, 128]:
            lanes = width//8
            for header_length in [1, lanes - 1]:
                with self.subTest(width=width, header_length=header_length):
                    header = Header({}, header_length)
                    layout = [("data", width), ("be", lanes), ("error", lanes)]
                    dut = Packetizer(stream.EndpointDescription(layout), stream.EndpointDescription(layout), header)
                    packet = bytes(range(2*lanes + 1))
                    inputs = beats(packet, lanes)
                    output_errors = []
                    result = simulate(self, dut, inputs, errors=[1, 1 << (lanes - 1), 1], output_errors=output_errors)
                    actual = [int(bool(error & (1 << i))) for (_, mask, _, _), error in zip(result, output_errors)
                        for i in range(lanes) if mask & (1 << i)]
                    errors = [int(i in [0, 2*lanes - 1, 2*lanes]) for i in range(len(packet))]
                    self.assertEqual(actual, [0]*header_length + errors)

    def test_short_header_verilog(self):
        from litex.gen.fhdl import verilog
        for width in [32, 64, 128, 256, 512]:
            for header_length in [1, 12, 16]:
                with self.subTest(width=width, header_length=header_length):
                    header = Header({}, header_length)
                    dut = Packetizer(description(width), description(width), header)
                    dut.clock_domains.cd_sys = ClockDomain("sys")
                    verilog.convert(dut, ios=set(dut.sink.flatten() + dut.source.flatten()))

    def test_first_discards_beats_outside_packets(self):
        for width in [32, 64, 128]:
            lanes = width//8
            for length in [1, lanes, lanes + 1, 2*lanes]:
                with self.subTest(width=width, length=length):
                    header = Header({}, length)
                    dut = Packetizer(description(width), description(width), header, with_first=True)
                    packet = bytes(range(2*lanes + 1))
                    junk = [(0xdead, (1 << lanes) - 1, 0, 1)]
                    inputs = junk + beats(packet, lanes) + junk + [(0, 0, 1, 1)] + junk + beats(packet, lanes)
                    result = simulate(self, dut, inputs)
                    expected = [beat for payload in [packet, b"", packet] for beat in beats(bytes(length) + payload, lanes)]
                    self.assertEqual([(m, f, l) for _, m, f, l in result], [(m, f, l) for _, m, f, l in expected])
                    self.assertEqual(qualified_bytes(result, lanes), qualified_bytes(expected, lanes))

    def test_reset_discards_header_and_saved_payload(self):
        for width in [32, 64, 128]:
            lanes = width//8
            for length in [lanes - 1, lanes, lanes + 1]:
                for stop_after in range(4):
                    with self.subTest(width=width, length=length, stop_after=stop_after):
                        header = Header({"value" : HeaderField(0, 0, 8*length)}, length, swap_field_bytes=False)
                        dut = ResetInserter()(Packetizer(description(width, params=header.get_layout()),
                            description(width), header, with_first=True))
                        received = []
                        header_data = bytes(range(length))
                        payload = b"\xa5"

                        def stimulus():
                            # Abandon a packet in the header or while payload is buffered.
                            yield dut.sink.value.eq((1 << (8*length)) - 1)
                            yield dut.sink.data.eq((1 << width) - 1)
                            yield dut.sink.be.eq((1 << lanes) - 1)
                            yield dut.sink.first.eq(1)
                            yield dut.sink.valid.eq(1)
                            yield dut.source.ready.eq(1)
                            yield
                            accepted = 0
                            for _ in range(30):
                                if accepted == stop_after:
                                    break
                                if (yield dut.source.valid):
                                    accepted += 1
                                yield
                            else:
                                self.fail("Packet did not reach reset point")
                            yield dut.source.ready.eq(0)
                            yield
                            yield dut.reset.eq(1)
                            yield dut.sink.valid.eq(0)
                            yield
                            yield
                            yield dut.reset.eq(0)
                            yield dut.sink.value.eq(int.from_bytes(header_data, "little"))
                            yield dut.sink.data.eq(payload[0])
                            yield dut.sink.be.eq(1)
                            yield dut.sink.last.eq(1)
                            yield dut.sink.valid.eq(1)
                            yield dut.source.ready.eq(1)
                            yield
                            for _ in range(30):
                                if (yield dut.source.valid):
                                    received.append(((yield dut.source.data), (yield dut.source.be),
                                        (yield dut.source.first), (yield dut.source.last)))
                                if (yield dut.sink.ready):
                                    yield dut.sink.valid.eq(0)
                                yield

                        run_simulation(dut, stimulus())
                        expected = beats(header_data + payload, lanes)
                        self.assertEqual([(m, f, l) for _, m, f, l in received],
                            [(m, f, l) for _, m, f, l in expected])
                        self.assertEqual(qualified_bytes(received, lanes), header_data + payload)
